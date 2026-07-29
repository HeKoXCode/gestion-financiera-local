import csv
import uuid
from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from zipfile import ZipFile

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from modules.core.forms import BusinessSettingsForm, SaleForm
from modules.core.models import (
    BusinessSettings,
    CollectionAttempt,
    Customer,
    Payment,
    Product,
    Sale,
)
from modules.core.services.balances import get_installment_balance
from modules.core.services.collection import build_collection_rows
from modules.core.services.export_data import create_data_export
from modules.core.services.installments import create_installments
from modules.core.services.payments import register_payment
from modules.core.services.reports import build_reports
from modules.core.services.whatsapp import build_payment_reminder_url
from modules.core.tests.factories import make_sale

pytestmark = pytest.mark.django_db


def settings_payload(**overrides):
    payload = {
        "business_name": "Negocio QA",
        "daily_late_fee": "2500.00",
        "collection_days": ["0", "1", "2", "3", "4", "5"],
        "payment_methods_text": "Efectivo\nTransferencia\nOtro",
        "available_frequencies": [
            Sale.Frequency.WEEKLY,
            Sale.Frequency.BIWEEKLY,
            Sale.Frequency.MONTHLY,
        ],
        "max_installments": "60",
        "late_fee_after_partial_payment": "on",
        "whatsapp_message": "Hola {nombre}, debés {monto} el {vencimiento}.",
    }
    payload.update(overrides)
    return payload


def test_demo_seed_requires_explicit_reset_confirmation():
    with pytest.raises(CommandError, match="confirm-reset"):
        call_command("seed_demo_data", as_of=date(2026, 7, 29))


def test_demo_seed_covers_the_complete_business_workflow(client):
    call_command(
        "seed_demo_data",
        confirm_reset=True,
        as_of=date(2026, 7, 29),
        verbosity=0,
    )

    assert Customer.objects.count() == 48
    assert Customer.objects.filter(is_active=False).count() == 4
    assert Product.objects.count() == 14
    assert Product.objects.filter(is_active=False).count() == 1
    assert Sale.objects.count() == 48
    assert set(Sale.objects.values_list("frequency", flat=True)) == {
        Sale.Frequency.WEEKLY,
        Sale.Frequency.BIWEEKLY,
        Sale.Frequency.MONTHLY,
    }
    assert set(Sale.objects.values_list("status", flat=True)) == {
        Sale.Status.ACTIVE,
        Sale.Status.COMPLETED,
        Sale.Status.CANCELLED,
    }
    assert set(Payment.objects.values_list("payment_method", flat=True)) == {
        "Efectivo",
        "Transferencia",
        "Tarjeta",
        "Otro",
    }
    assert set(Payment.objects.values_list("kind", flat=True)) == {
        Payment.Kind.INITIAL,
        Payment.Kind.INSTALLMENT,
    }
    assert set(Payment.objects.values_list("status", flat=True)) == {
        Payment.Status.REGISTERED,
        Payment.Status.VOIDED,
    }
    assert set(CollectionAttempt.objects.values_list("result", flat=True)) == set(
        CollectionAttempt.Result.values
    )
    assert Sale.objects.filter(down_payment__gt=0).exists()
    assert Sale.objects.filter(down_payment=0).exists()

    created_dates = list(
        Customer.objects.order_by("created_at").values_list("created_at", flat=True)
    )
    assert created_dates[0].date() == date(2026, 4, 30)
    assert created_dates[-1].date() == date(2026, 7, 29)

    for sale in Sale.objects.prefetch_related("installments"):
        installment_total = sum(
            sale.installments.values_list("original_amount", flat=True),
            Decimal("0.00"),
        )
        assert installment_total == sale.financed_amount

    for payment in Payment.objects.filter(kind=Payment.Kind.INSTALLMENT):
        allocation_total = sum(
            payment.allocations.values_list("amount", flat=True),
            Decimal("0.00"),
        )
        assert allocation_total == payment.amount

    primary_routes = [
        reverse("core:home"),
        reverse("core:collection_list"),
        reverse("core:agenda"),
        reverse("core:reports"),
        reverse("core:customer_list"),
        reverse("core:product_list"),
        reverse("core:sale_list"),
        reverse("core:data_management"),
        reverse("core:configuration"),
    ]
    for route in primary_routes:
        response = client.get(route, {"fecha": "2026-07-29"})
        assert response.status_code == 200, route


@pytest.mark.parametrize(
    "route_name",
    [
        "core:home",
        "core:collection_list",
        "core:collection_print",
        "core:agenda",
        "core:reports",
    ],
)
@pytest.mark.parametrize("extreme_date", ["0001-01-01", "9999-12-31", "no-es-fecha"])
def test_extreme_navigation_dates_never_break_a_screen(
    client,
    route_name,
    extreme_date,
):
    response = client.get(reverse(route_name), {"fecha": extreme_date})

    assert response.status_code == 200


def test_configuration_rejects_unknown_or_malformed_whatsapp_variables():
    settings = BusinessSettings.get_solo()
    unknown = BusinessSettingsForm(
        data=settings_payload(
            whatsapp_message="Hola {nombre}, debés {importe}.",
        ),
        instance=settings,
    )
    malformed = BusinessSettingsForm(
        data=settings_payload(
            whatsapp_message="Hola {nombre",
        ),
        instance=settings,
    )

    assert unknown.is_valid() is False
    assert "Variable no permitida" in unknown.errors["whatsapp_message"][0]
    assert malformed.is_valid() is False
    assert "llave" in malformed.errors["whatsapp_message"][0]


def test_old_malformed_whatsapp_setting_falls_back_without_breaking_collection():
    settings = BusinessSettings.get_solo()
    BusinessSettings.objects.filter(pk=settings.pk).update(
        whatsapp_message="Hola {variable_que_no_existe}",
    )
    customer = Customer.objects.create(
        first_name="Nombre",
        last_name="QA",
        phone="11 5555 1234",
        address="Domicilio inventado",
    )
    settings.refresh_from_db()

    url = build_payment_reminder_url(
        customer=customer,
        amount=Decimal("12345.67"),
        due_date=date(2026, 7, 29),
        settings=settings,
    )

    assert url.startswith("https://wa.me/549")
    assert "variable_que_no_existe" not in url


def test_configuration_limits_payment_methods_to_database_capacity():
    settings = BusinessSettings.get_solo()
    too_long = BusinessSettingsForm(
        data=settings_payload(payment_methods_text="X" * 41),
        instance=settings,
    )
    too_many = BusinessSettingsForm(
        data=settings_payload(
            payment_methods_text="\n".join(f"Método {index}" for index in range(21))
        ),
        instance=settings,
    )

    assert too_long.is_valid() is False
    assert "40 caracteres" in too_long.errors["payment_methods_text"][0]
    assert too_many.is_valid() is False
    assert "20 medios" in too_many.errors["payment_methods_text"][0]


def test_sale_form_rejects_money_overflow_instead_of_raising_an_error():
    settings = BusinessSettings.get_solo()
    customer = Customer.objects.create(
        first_name="Importe",
        last_name="Extremo",
        address="Domicilio inventado",
    )
    product = Product.objects.create(name="Producto de importe extremo")
    form = SaleForm(
        data={
            "customer": customer.pk,
            "product": product.pk,
            "product_description": "Prueba",
            "delivery_date": "2026-07-01",
            "cash_price": "999999999999999999999999999999",
            "down_payment": "0",
            "financed_amount": "1",
            "frequency": Sale.Frequency.WEEKLY,
            "installment_count": "12",
            "first_due_date": "2026-07-08",
        },
        settings=settings,
    )

    assert form.is_valid() is False
    assert "cash_price" in form.errors


def test_export_protects_formulas_even_after_leading_spaces(tmp_path):
    Customer.objects.create(
        first_name="CSV",
        last_name="Seguro",
        address="Domicilio inventado",
        notes='   =HYPERLINK("malicioso")',
    )

    export_path = create_data_export(tmp_path)
    with ZipFile(export_path) as archive:
        rows = list(
            csv.DictReader(
                StringIO(archive.read("clientes.csv").decode("utf-8-sig")),
                delimiter=";",
            )
        )

    assert rows[0]["observaciones"].startswith("'   =")


def test_historical_views_respect_the_actual_cancellation_date():
    sale = make_sale(
        delivery_date=date(2026, 7, 1),
        first_due_date=date(2026, 7, 8),
        financed_amount=Decimal("20000.00"),
        installment_count=1,
        daily_late_fee=Decimal("0.00"),
    )
    create_installments(sale)
    sale.status = Sale.Status.CANCELLED
    sale.cancelled_on = date(2026, 7, 20)
    sale.cancellation_reason = "Cancelación posterior a la consulta histórica"
    sale.save()

    before_cancellation = build_collection_rows(as_of=date(2026, 7, 10))
    on_cancellation = build_collection_rows(as_of=date(2026, 7, 20))
    report_before = build_reports(as_of=date(2026, 7, 10))
    report_after = build_reports(as_of=date(2026, 7, 20))

    assert [row["sale"] for row in before_cancellation] == [sale]
    assert on_cancellation == []
    assert report_before["portfolio_pending"] == Decimal("20000.00")
    assert report_after["portfolio_pending"] == Decimal("0.00")


def test_cancelled_sale_detail_labels_its_balance_as_non_collectible(client):
    sale = make_sale(
        delivery_date=date(2026, 7, 1),
        first_due_date=date(2026, 7, 8),
        financed_amount=Decimal("20000.00"),
        installment_count=1,
        daily_late_fee=Decimal("0.00"),
    )
    create_installments(sale)
    sale.status = Sale.Status.CANCELLED
    sale.cancelled_on = date(2026, 7, 20)
    sale.cancellation_reason = "Cancelación para comprobar el detalle"
    sale.save()

    response = client.get(reverse("core:sale_detail", args=[sale.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Saldo fuera de cobranza" in content
    assert "no forma parte de la cobranza" in content
    assert "badge-cancelled" in content


def test_historical_balance_counts_a_payment_until_its_void_date():
    sale = make_sale(
        delivery_date=date(2026, 7, 1),
        first_due_date=date(2026, 7, 8),
        financed_amount=Decimal("20000.00"),
        installment_count=1,
        daily_late_fee=Decimal("0.00"),
    )
    installment = create_installments(sale)[0]
    payment = register_payment(
        sale=sale,
        amount=Decimal("20000.00"),
        payment_date=date(2026, 7, 10),
        payment_method="Efectivo",
        operation_key=uuid.uuid4(),
    ).payment
    Payment.objects.filter(pk=payment.pk).update(
        status=Payment.Status.VOIDED,
        voided_at=timezone.make_aware(datetime(2026, 7, 20, 12)),
        void_reason="Anulación posterior",
    )

    before_void = get_installment_balance(installment, as_of=date(2026, 7, 19))
    after_void = get_installment_balance(installment, as_of=date(2026, 7, 20))

    assert before_void.total_due == Decimal("0.00")
    assert after_void.total_due == Decimal("20000.00")


def test_demo_portfolio_pages_keep_bounded_query_counts(client):
    call_command(
        "seed_demo_data",
        confirm_reset=True,
        as_of=date(2026, 7, 29),
        verbosity=0,
    )
    limits = {
        "/?fecha=2026-07-29": 35,
        "/cobranza/?fecha=2026-07-29": 25,
        "/agenda/?fecha=2026-07-29": 55,
        "/reportes/?fecha=2026-07-29": 30,
    }

    for path, maximum in limits.items():
        with CaptureQueriesContext(connection) as queries:
            response = client.get(path)
        assert response.status_code == 200
        assert len(queries) <= maximum, f"{path}: {len(queries)} consultas"
