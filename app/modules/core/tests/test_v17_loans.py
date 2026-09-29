import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from modules.core.models import BusinessSettings, Collector, Sale
from modules.core.services.installments import create_installments
from modules.core.tests.factories import make_customer, make_sale

pytestmark = pytest.mark.django_db


def _loan(**overrides):
    today = timezone.localdate()
    values = {
        "operation_type": Sale.OperationType.LOAN,
        "product": None,
        "product_description": "Préstamo para capital de trabajo",
        "loan_disbursement_method": "Efectivo",
        "loan_interest_rate": Decimal("20.00"),
        "delivery_date": today,
        "first_due_date": today,
        "cash_price": Decimal("100000.00"),
        "financed_amount": Decimal("120000.00"),
        "installment_count": 6,
    }
    values.update(overrides)
    return make_sale(**values)


def test_daily_loan_uses_enabled_collection_days():
    settings = BusinessSettings.get_solo()
    settings.collection_days = [0, 2, 4]
    settings.available_frequencies = [Sale.Frequency.DAILY]
    settings.save(update_fields=["collection_days", "available_frequencies", "updated_at"])
    monday = timezone.localdate()
    while monday.weekday() != 0:
        monday += timedelta(days=1)

    loan = _loan(
        delivery_date=monday,
        first_due_date=monday,
        frequency=Sale.Frequency.DAILY,
        installment_count=5,
        financed_amount=Decimal("125000.00"),
        loan_interest_rate=Decimal("25.00"),
    )
    installments = create_installments(loan)

    assert [item.due_date.weekday() for item in installments] == [0, 2, 4, 0, 2]
    assert [item.original_amount for item in installments] == [Decimal("25000.00")] * 5


def test_loan_can_be_corrected_without_turning_into_a_product_sale(client):
    loan = _loan()
    create_installments(loan)

    response = client.post(
        reverse("core:sale_edit", args=[loan.pk]),
        {
            "customer": loan.customer_id,
            "product": "",
            "product_description": "Préstamo corregido para herramientas",
            "delivery_date": loan.delivery_date.isoformat(),
            "cash_price": "100000",
            "loan_disbursement_method": "Transferencia",
            "loan_interest_rate": "30",
            "down_payment": "",
            "down_payment_method": "",
            "custom_installment_total": "",
            "financed_amount": "1",
            "frequency": Sale.Frequency.WEEKLY,
            "installment_count": "5",
            "first_due_date": loan.first_due_date.isoformat(),
            "edit_reason": "Se corrigieron interés y cantidad de cuotas.",
            "operation_key": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 302
    loan.refresh_from_db()
    assert loan.operation_type == Sale.OperationType.LOAN
    assert loan.product is None
    assert loan.loan_disbursement_method == "Transferencia"
    assert loan.loan_interest_rate == Decimal("30.00")
    assert loan.financed_amount == Decimal("130000.00")
    assert loan.installment_count == 5
    assert loan.revisions.count() == 1


def test_loan_is_clear_in_customer_collection_and_collector_planner(client):
    today = timezone.localdate()
    customer = make_customer(first_name="María", last_name="Préstamo QA")
    loan = _loan(customer=customer, first_due_date=today, delivery_date=today)
    create_installments(loan)
    collector = Collector.objects.create(name="Esteban QA")

    customer_page = client.get(reverse("core:customer_detail", args=[customer.pk]))
    operation_detail = client.get(reverse("core:sale_detail", args=[loan.pk]))
    collection_page = client.get(reverse("core:collection_list"), {"fecha": today.isoformat()})
    planner = client.get(
        reverse("core:collection_routes"),
        {"fecha": today.isoformat(), "cobrador": collector.pk},
    )

    customer_content = customer_page.content.decode()
    detail_content = operation_detail.content.decode()
    collection_content = collection_page.content.decode()
    assert "Préstamo para capital de trabajo" in customer_content
    assert "Préstamo" in customer_content
    assert 'class="is-loan-row"' in customer_content
    assert "sale-hero is-loan-hero" in detail_content
    assert "sale-summary-grid is-loan-summary" in detail_content
    assert "Préstamo para capital de trabajo" in collection_content
    assert "is-loan-operation" in collection_content
    planner_content = planner.content.decode()
    assert "Operaciones pendientes:" in planner_content
    assert "Préstamo para capital de trabajo" in planner_content


def test_loan_ui_has_distinct_controls_and_labels(client):
    customer = make_customer()
    response = client.get(reverse("core:sale_create"), {"cliente": customer.pk})
    content = response.content.decode()

    assert 'value="loan"' in content
    assert "Préstamo de dinero" in content
    assert "¿Cómo se entregó el dinero?" in content
    assert "Interés total" in content
    assert 'id="financed-amount-label"' in content
    assert 'id="custom-total-label"' in content
