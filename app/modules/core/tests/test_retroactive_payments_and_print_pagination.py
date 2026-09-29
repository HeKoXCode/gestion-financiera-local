import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from modules.core.models import BusinessSettings, LateFee, Payment
from modules.core.services.balances import get_installment_balance
from modules.core.services.installments import create_installments
from modules.core.services.late_fees import generate_missing_late_fees
from modules.core.services.payments import register_payment
from modules.core.tests.factories import make_customer, make_product, make_sale

pytestmark = pytest.mark.django_db


def make_retroactive_sale(*, today: date):
    sale = make_sale(
        delivery_date=today - timedelta(days=30),
        first_due_date=today - timedelta(days=2),
        financed_amount=Decimal("20000.00"),
        installment_count=1,
        daily_late_fee=Decimal("5000.00"),
    )
    create_installments(sale)
    return sale


def test_collection_previous_day_requires_confirmation_and_records_real_date(
    client,
    monkeypatch,
):
    today = date(2026, 8, 20)
    selected_date = today - timedelta(days=1)
    monkeypatch.setattr(timezone, "localdate", lambda *args, **kwargs: today)
    sale = make_retroactive_sale(today=today)
    installment = sale.installments.get()

    generate_missing_late_fees(as_of=today, sale=sale)
    assert list(installment.late_fees.values_list("fee_date", flat=True)) == [
        selected_date,
        today,
    ]

    collection = client.get(
        reverse("core:collection_list"),
        {"fecha": selected_date.isoformat()},
    )
    payment_url = reverse("core:payment_create", args=[sale.pk])
    assert f"{payment_url}?fecha={selected_date:%Y-%m-%d}" in collection.content.decode()

    warning = client.get(payment_url, {"fecha": selected_date.isoformat()})
    warning_content = warning.content.decode()
    assert warning.status_code == 200
    assert "Estás por registrar un pago de un día anterior" in warning_content
    assert "recargo diario se recalculará" in warning_content
    assert Payment.objects.count() == 0

    confirmed = client.post(
        payment_url,
        {
            "stage": "confirm",
            "selected_date": selected_date.isoformat(),
            "from_collection": "1",
        },
    )
    confirmed_content = confirmed.content.decode()
    assert confirmed.status_code == 200
    assert "Pago de una fecha anterior confirmado" in confirmed_content
    assert f'value="{selected_date:%Y-%m-%d}"' in confirmed_content
    assert f'name="payment_date" value="{selected_date:%Y-%m-%d}"' in confirmed_content

    saved = client.post(
        payment_url,
        {
            "stage": "payment",
            "selected_date": selected_date.isoformat(),
            "from_collection": "1",
            "operation_key": str(uuid.uuid4()),
            "amount": "25000.00",
            "payment_date": selected_date.isoformat(),
            "payment_method": "Efectivo",
            "notes": "Pago que faltaba registrar",
        },
    )

    payment = Payment.objects.get()
    assert saved.status_code == 302
    assert saved.url == f"/cobranza/?fecha={selected_date:%Y-%m-%d}"
    assert payment.payment_date == selected_date
    assert payment.amount == Decimal("25000.00")
    assert LateFee.objects.count() == 2
    assert list(fee.fee_date for fee in LateFee.objects.all() if fee.effective_amount > 0) == [
        selected_date
    ]
    sale.refresh_from_db()
    assert sale.status == sale.Status.COMPLETED


def test_retroactive_payment_cannot_be_inserted_before_a_later_payment(monkeypatch):
    today = date(2026, 8, 20)
    selected_date = today - timedelta(days=1)
    monkeypatch.setattr(timezone, "localdate", lambda *args, **kwargs: today)
    sale = make_retroactive_sale(today=today)
    register_payment(
        sale=sale,
        amount=Decimal("1000.00"),
        payment_date=today,
        payment_method="Efectivo",
        operation_key=uuid.uuid4(),
    )

    with pytest.raises(ValidationError, match="pago de cuotas posterior"):
        register_payment(
            sale=sale,
            amount=Decimal("1000.00"),
            payment_date=selected_date,
            payment_method="Efectivo",
            operation_key=uuid.uuid4(),
        )

    assert Payment.objects.count() == 1


@pytest.mark.parametrize("continue_after_partial", [False, True])
def test_retroactive_partial_payment_respects_daily_continuation_setting(
    monkeypatch,
    continue_after_partial,
):
    today = date(2026, 8, 20)
    selected_date = today - timedelta(days=1)
    monkeypatch.setattr(timezone, "localdate", lambda *args, **kwargs: today)
    settings = BusinessSettings.get_solo()
    settings.late_fee_after_partial_payment = continue_after_partial
    settings.save(update_fields=["late_fee_after_partial_payment", "updated_at"])
    sale = make_retroactive_sale(today=today)
    installment = sale.installments.get()
    generate_missing_late_fees(as_of=today, settings=settings, sale=sale)

    register_payment(
        sale=sale,
        amount=Decimal("5000.00"),
        payment_date=selected_date,
        payment_method="Efectivo",
        operation_key=uuid.uuid4(),
        settings=settings,
    )
    generate_missing_late_fees(as_of=today, settings=settings, sale=sale)

    assert list(installment.late_fees.values_list("fee_date", flat=True)) == [
        date(2026, 8, 19),
        date(2026, 8, 20),
    ]
    assert get_installment_balance(installment, as_of=today).total_due == (
        Decimal("25000.00") if continue_after_partial else Decimal("20000.00")
    )


def test_payment_form_rejects_a_date_different_from_collection_day(
    client,
    monkeypatch,
):
    today = date(2026, 8, 20)
    selected_date = today - timedelta(days=1)
    monkeypatch.setattr(timezone, "localdate", lambda *args, **kwargs: today)
    sale = make_retroactive_sale(today=today)

    response = client.post(
        reverse("core:payment_create", args=[sale.pk]),
        {
            "stage": "payment",
            "selected_date": selected_date.isoformat(),
            "from_collection": "1",
            "operation_key": str(uuid.uuid4()),
            "amount": "25000.00",
            "payment_date": (selected_date - timedelta(days=1)).isoformat(),
            "payment_method": "Efectivo",
            "notes": "Fecha alterada",
        },
    )

    assert response.status_code == 200
    assert "La fecha debe coincidir con el día elegido en Cobranza" in response.content.decode()
    assert Payment.objects.count() == 0


def test_daily_collection_print_splits_fifty_entries_into_ten_per_a4(client):
    today = timezone.localdate()
    product = make_product(name="Producto de planilla")
    for number in range(1, 51):
        customer = make_customer(
            first_name=f"Cliente {number:02d}",
            last_name="Prueba",
            address=f"Domicilio inventado {number}",
        )
        sale = make_sale(
            customer=customer,
            product=product,
            delivery_date=today - timedelta(days=30),
            first_due_date=today,
            financed_amount=Decimal("20000.00"),
            installment_count=1,
            daily_late_fee=Decimal("0.00"),
        )
        create_installments(sale)

    response = client.get(reverse("core:collection_print"))
    content = response.content.decode()
    pages = response.context["print_pages"]

    assert response.status_code == 200
    assert response.context["entries_per_page"] == 10
    assert response.context["print_page_count"] == 5
    assert [len(page["rows"]) for page in pages] == [10] * 5
    assert [row["print_number"] for page in pages for row in page["rows"]] == list(range(1, 51))
    assert content.count('class="print-sheet print-page"') == 5
    assert "5 de 5" in content
    assert "Hoja 5/5" in content
