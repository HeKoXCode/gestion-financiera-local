from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from modules.core.models import Sale
from modules.core.services.export_data import _export_tables
from modules.core.services.installments import create_installments
from modules.core.services.reports import build_reports
from modules.core.tests.factories import make_customer, make_sale

pytestmark = pytest.mark.django_db


def loan_post_data(customer, **overrides):
    today = timezone.localdate()
    values = {
        "operation_type": Sale.OperationType.LOAN,
        "customer": customer.pk,
        "product": "",
        "product_description": "",
        "delivery_date": today.isoformat(),
        "cash_price": "100000",
        "loan_disbursement_method": "Efectivo",
        "loan_interest_rate": "20",
        "down_payment": "",
        "down_payment_method": "",
        "custom_installment_total": "",
        "financed_amount": "1",
        "frequency": Sale.Frequency.WEEKLY,
        "installment_count": "10",
        "first_due_date": (today + timedelta(days=7)).isoformat(),
        "first_installment_delivery_status": "",
        "first_installment_payment_method": "",
        "historical_paid_installments": "0",
        "historical_payment_method": "Efectivo",
        "historical_late_installments": "{}",
    }
    values.update(overrides)
    return values


def test_loan_is_registered_without_fake_product_and_generates_installments(client):
    customer = make_customer()

    response = client.post(
        reverse("core:sale_create"),
        loan_post_data(customer),
    )

    assert response.status_code == 302
    loan = Sale.objects.get()
    assert loan.operation_type == Sale.OperationType.LOAN
    assert loan.product is None
    assert loan.product_description == "Préstamo de dinero"
    assert loan.cash_price == Decimal("100000.00")
    assert loan.down_payment == Decimal("0.00")
    assert loan.loan_disbursement_method == "Efectivo"
    assert loan.loan_interest_rate == Decimal("20.00")
    assert loan.financed_amount == Decimal("120000.00")
    assert loan.loan_interest_amount == Decimal("20000.00")
    assert list(loan.installments.values_list("original_amount", flat=True)) == [
        Decimal("12000.00")
    ] * 10
    assert not loan.payments.exists()


def test_loan_custom_repayment_total_derives_effective_interest(client):
    customer = make_customer()

    response = client.post(
        reverse("core:sale_create"),
        loan_post_data(
            customer,
            loan_disbursement_method="Transferencia",
            custom_installment_total="on",
            financed_amount="135000",
        ),
    )

    assert response.status_code == 302
    loan = Sale.objects.get()
    assert loan.loan_disbursement_method == "Transferencia"
    assert loan.financed_amount == Decimal("135000.00")
    assert loan.loan_interest_rate == Decimal("35.00")


def test_installment_amount_can_define_loan_total_and_interest(client):
    customer = make_customer()

    response = client.post(
        reverse("core:sale_create"),
        loan_post_data(
            customer,
            cash_price="200000",
            installment_count="12",
            installment_amount="20000",
        ),
    )

    assert response.status_code == 302
    loan = Sale.objects.get()
    assert loan.financed_amount == Decimal("240000.00")
    assert loan.loan_interest_rate == Decimal("20.00")
    assert loan.installments.count() == 12


def test_loan_rejects_missing_delivery_method_and_total_below_principal(client):
    customer = make_customer()

    response = client.post(
        reverse("core:sale_create"),
        loan_post_data(
            customer,
            loan_disbursement_method="",
            custom_installment_total="on",
            financed_amount="90000",
        ),
    )

    assert response.status_code == 200
    assert not Sale.objects.exists()
    assert "Elegí cómo se entregó el dinero" in response.content.decode()
    assert "no puede ser menor al dinero prestado" in response.content.decode()


def test_model_prevents_product_loan_and_product_sale_without_product():
    loan = make_sale(
        operation_type=Sale.OperationType.LOAN,
        product=None,
        loan_disbursement_method="Efectivo",
        cash_price=Decimal("100000.00"),
        financed_amount=Decimal("120000.00"),
        loan_interest_rate=Decimal("20.00"),
    )
    product_sale = make_sale()
    loan.product = product_sale.product
    with pytest.raises(ValidationError):
        loan.full_clean()

    product_sale.product = None
    with pytest.raises(ValidationError):
        product_sale.full_clean()


def test_loan_uses_existing_history_collection_and_customer_summary(client):
    today = timezone.localdate()
    loan = make_sale(
        operation_type=Sale.OperationType.LOAN,
        product=None,
        product_description="Préstamo para refacción",
        loan_disbursement_method="Transferencia",
        loan_interest_rate=Decimal("25.00"),
        delivery_date=today,
        first_due_date=today,
        cash_price=Decimal("80000.00"),
        financed_amount=Decimal("100000.00"),
        installment_count=5,
    )
    create_installments(loan)

    detail = client.get(reverse("core:sale_detail", args=[loan.pk]))
    collection = client.get(reverse("core:collection_list"), {"fecha": today.isoformat()})
    customer = client.get(reverse("core:customer_detail", args=[loan.customer_id]))

    assert detail.status_code == collection.status_code == customer.status_code == 200
    assert "Préstamo para refacción" in detail.content.decode()
    assert "Dinero prestado" in detail.content.decode()
    assert "Transferencia" in detail.content.decode()
    assert "Préstamo para refacción" in collection.content.decode()
    assert "Ventas y préstamos" in customer.content.decode()


def test_reports_keep_loans_out_of_product_ranking_and_export_loan_fields():
    today = timezone.localdate()
    product_sale = make_sale(
        delivery_date=today,
        first_due_date=today,
        cash_price=Decimal("40000.00"),
        financed_amount=Decimal("48000.00"),
        installment_count=4,
    )
    create_installments(product_sale)
    loan = make_sale(
        operation_type=Sale.OperationType.LOAN,
        product=None,
        loan_disbursement_method="Efectivo",
        loan_interest_rate=Decimal("20.00"),
        delivery_date=today,
        first_due_date=today,
        cash_price=Decimal("100000.00"),
        financed_amount=Decimal("120000.00"),
        installment_count=10,
    )
    create_installments(loan)

    report = build_reports(as_of=today)
    headers, rows = _export_tables()["ventas.csv"]

    assert len(report["products_most_sold"]) == 1
    assert report["products_most_sold"][0]["product"] == product_sale.product
    assert report["loans_count"] == 1
    assert report["loan_principal_total"] == Decimal("100000.00")
    assert report["loan_repayment_total"] == Decimal("120000.00")
    assert "tipo_operacion" in headers
    assert "medio_entrega_prestamo" in headers
    operation_type_index = headers.index("tipo_operacion")
    assert any(row[operation_type_index] == Sale.OperationType.LOAN for row in rows)
