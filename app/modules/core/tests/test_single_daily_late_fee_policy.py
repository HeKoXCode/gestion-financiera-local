import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from django.utils import timezone

from modules.core.models import BusinessSettings, LateFee
from modules.core.services.collection import build_collection_rows
from modules.core.services.customer_history import build_customer_history
from modules.core.services.installments import create_installments
from modules.core.services.late_fees import generate_missing_late_fees
from modules.core.services.payments import register_payment
from modules.core.tests.factories import make_sale

pytestmark = pytest.mark.django_db


def make_two_overdue_installments():
    today = timezone.localdate()
    settings = BusinessSettings.get_solo()
    settings.charge_sundays = True
    settings.late_fee_after_partial_payment = True
    settings.save(
        update_fields=[
            "charge_sundays",
            "late_fee_after_partial_payment",
            "updated_at",
        ]
    )
    sale = make_sale(
        delivery_date=today - timedelta(days=30),
        first_due_date=today - timedelta(days=10),
        financed_amount=Decimal("40000.00"),
        installment_count=2,
        daily_late_fee=Decimal("5000.00"),
    )
    create_installments(sale)
    return settings, sale, list(sale.installments.order_by("number"))


def test_two_overdue_installments_add_principal_but_share_one_daily_stream():
    today = timezone.localdate()
    settings, sale, installments = make_two_overdue_installments()

    generate_missing_late_fees(as_of=today, settings=settings, sale=sale)
    row = build_collection_rows(as_of=today)[0]

    assert row["oldest_installment"] == installments[0]
    assert row["due_installment_count"] == 2
    assert row["capital_due"] == Decimal("40000.00")
    assert row["late_fees_due"] == Decimal("50000.00")
    assert row["total_due"] == Decimal("90000.00")
    assert row["days_overdue"] == 10
    assert LateFee.objects.filter(installment__sale=sale).count() == 10

    effective_by_date = {}
    for fee in LateFee.objects.filter(installment__sale=sale):
        effective_by_date.setdefault(fee.fee_date, Decimal("0.00"))
        effective_by_date[fee.fee_date] += fee.effective_amount
    assert set(effective_by_date.values()) == {Decimal("5000.00")}


def test_history_keeps_each_installments_own_delay_for_information():
    today = timezone.localdate()
    settings, sale, _ = make_two_overdue_installments()
    generate_missing_late_fees(as_of=today, settings=settings, sale=sale)

    history = build_customer_history(customer=sale.customer, as_of=today)

    assert history["overdue_installments"] == 2
    assert [row["status"] for row in history["installment_rows"]] == [
        "overdue",
        "overdue",
    ]
    assert [row["status_label"] for row in history["installment_rows"]] == [
        "10 días de atraso",
        "3 días de atraso",
    ]


def test_full_payment_covers_shared_charge_and_both_due_installments():
    today = timezone.localdate()
    settings, sale, installments = make_two_overdue_installments()
    generate_missing_late_fees(as_of=today, settings=settings, sale=sale)

    payment = register_payment(
        sale=sale,
        amount=Decimal("90000.00"),
        payment_date=today,
        payment_method="Efectivo",
        operation_key=uuid.uuid4(),
        settings=settings,
    ).payment

    principal_installments = set(
        payment.allocations.filter(component="principal").values_list("installment_id", flat=True)
    )
    assert principal_installments == {installments[0].pk, installments[1].pk}
    assert sum(
        payment.allocations.filter(component="late_fee").values_list("amount", flat=True),
        Decimal("0.00"),
    ) == Decimal("50000.00")


def test_partial_payment_does_not_duplicate_a_day_and_next_day_adds_once():
    today = timezone.localdate()
    settings, sale, _ = make_two_overdue_installments()
    generate_missing_late_fees(as_of=today, settings=settings, sale=sale)

    register_payment(
        sale=sale,
        amount=Decimal("20000.00"),
        payment_date=today,
        payment_method="Efectivo",
        operation_key=uuid.uuid4(),
        settings=settings,
    )
    generate_missing_late_fees(
        as_of=today + timedelta(days=1),
        settings=settings,
        sale=sale,
    )
    row = build_collection_rows(as_of=today + timedelta(days=1))[0]

    assert row["capital_due"] == Decimal("40000.00")
    assert row["late_fees_due"] == Decimal("35000.00")
    assert row["total_due"] == Decimal("75000.00")
    assert LateFee.objects.filter(installment__sale=sale).count() == 11


def test_v12_overlapping_rows_are_preserved_but_only_one_per_date_is_effective():
    today = timezone.localdate()
    settings, sale, installments = make_two_overdue_installments()
    for day_offset in range(1, 11):
        fee_date = installments[0].due_date + timedelta(days=day_offset)
        LateFee.objects.create(
            installment=installments[0],
            fee_date=fee_date,
            amount=Decimal("5000.00"),
        )
        if fee_date > installments[1].due_date:
            LateFee.objects.create(
                installment=installments[1],
                fee_date=fee_date,
                amount=Decimal("5000.00"),
            )

    generate_missing_late_fees(as_of=today, settings=settings, sale=sale)
    rows = list(LateFee.objects.filter(installment__sale=sale))

    assert len(rows) == 13
    assert sum((row.effective_amount for row in rows), Decimal("0.00")) == Decimal("50000.00")
    assert sum((row.waived_amount for row in rows), Decimal("0.00")) == Decimal("15000.00")
    assert all(row.waived_reason for row in rows if row.waived_amount)
    assert build_collection_rows(as_of=today)[0]["total_due"] == Decimal("90000.00")


def test_configuration_explains_single_daily_charge_and_keeps_daily_options(client):
    content = client.get(reverse("core:configuration")).content.decode()

    assert "Recargo diario por atraso" in content
    assert "aunque existan varias cuotas vencidas" in content
    assert "Generar recargos los domingos" in content
    assert "Seguir sumando recargo después de un pago parcial" in content


@pytest.mark.django_db(transaction=True)
def test_real_migration_from_v12_waives_only_overlapping_daily_rows():
    old_target = [("core", "0009_businesssettings_allow_exceptional_sale_edits_and_more")]
    new_target = [("core", "0010_single_daily_late_fee_policy")]
    executor = MigrationExecutor(connection)
    executor.migrate(old_target)
    old_apps = executor.loader.project_state(old_target).apps

    try:
        Customer = old_apps.get_model("core", "Customer")
        Product = old_apps.get_model("core", "Product")
        Sale = old_apps.get_model("core", "Sale")
        OldInstallment = old_apps.get_model("core", "Installment")
        OldLateFee = old_apps.get_model("core", "LateFee")
        today = timezone.localdate()
        customer = Customer.objects.create(
            first_name="Cliente",
            last_name="Migración",
            phone="1111111111",
            address="Domicilio de prueba",
        )
        product = Product.objects.create(name="Producto de migración")
        sale = Sale.objects.create(
            customer=customer,
            product=product,
            product_description=product.name,
            delivery_date=today - timedelta(days=30),
            cash_price=Decimal("40000.00"),
            financed_amount=Decimal("40000.00"),
            frequency="weekly",
            installment_count=2,
            daily_late_fee=Decimal("5000.00"),
            first_due_date=today - timedelta(days=10),
            status="active",
        )
        first = OldInstallment.objects.create(
            sale=sale,
            number=1,
            due_date=today - timedelta(days=10),
            original_amount=Decimal("20000.00"),
        )
        second = OldInstallment.objects.create(
            sale=sale,
            number=2,
            due_date=today - timedelta(days=3),
            original_amount=Decimal("20000.00"),
        )
        for day_offset in range(1, 11):
            fee_date = first.due_date + timedelta(days=day_offset)
            OldLateFee.objects.create(
                installment=first,
                fee_date=fee_date,
                amount=Decimal("5000.00"),
            )
            if fee_date > second.due_date:
                OldLateFee.objects.create(
                    installment=second,
                    fee_date=fee_date,
                    amount=Decimal("5000.00"),
                )

        executor = MigrationExecutor(connection)
        executor.migrate(new_target)
        migrated_apps = executor.loader.project_state(new_target).apps
        MigratedLateFee = migrated_apps.get_model("core", "LateFee")
        migrated_rows = MigratedLateFee.objects.filter(installment__sale_id=sale.pk)

        assert migrated_rows.count() == 13
        assert sum(
            (row.amount - row.waived_amount for row in migrated_rows),
            Decimal("0.00"),
        ) == Decimal("50000.00")
        assert sum(
            (row.waived_amount for row in migrated_rows),
            Decimal("0.00"),
        ) == Decimal("15000.00")
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
