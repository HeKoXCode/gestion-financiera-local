import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from modules.core.models import CollectionAttempt, Payment, Sale
from modules.core.services.balances import get_sale_balance
from modules.core.services.installments import create_installments
from modules.core.tests.factories import make_sale

pytestmark = pytest.mark.django_db


def make_collectible_sale():
    today = timezone.localdate()
    sale = make_sale(
        delivery_date=today - timedelta(days=10),
        first_due_date=today,
        financed_amount=Decimal("20000.00"),
        installment_count=1,
        daily_late_fee=Decimal("0.00"),
    )
    create_installments(sale)
    return sale


def payment_form_data(**overrides):
    values = {
        "operation_key": str(uuid.uuid4()),
        "amount": "10000",
        "payment_date": timezone.localdate().isoformat(),
        "payment_method": "Efectivo",
        "notes": "Pago parcial",
    }
    values.update(overrides)
    return values


def test_collection_screen_shows_collectible_sale(client):
    sale = make_collectible_sale()

    response = client.get(reverse("core:collection_list"))
    content = response.content.decode()

    assert response.status_code == 200
    assert sale.customer.full_name in content
    assert "Registrar pago" in content
    assert "$ 20.000,00" in content


def test_opening_today_generates_missing_late_fees(client):
    today = timezone.localdate()
    sale = make_sale(
        delivery_date=today - timedelta(days=10),
        first_due_date=today - timedelta(days=1),
        financed_amount=Decimal("20000.00"),
        installment_count=1,
        daily_late_fee=Decimal("5000.00"),
    )
    create_installments(sale)

    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert sale.installments.get().late_fees.count() == 1
    assert "$ 25.000,00" in response.content.decode()


def test_phase_four_forms_render(client):
    sale = make_collectible_sale()
    client.post(
        reverse("core:payment_create", args=[sale.pk]),
        payment_form_data(amount="10000"),
    )
    payment = Payment.objects.get()
    urls = [
        reverse("core:payment_create", args=[sale.pk]),
        reverse("core:collection_attempt_create", args=[sale.pk]),
        reverse("core:payment_void", args=[payment.pk]),
    ]

    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, url


def test_partial_payment_can_be_registered_from_screen(client):
    sale = make_collectible_sale()

    response = client.post(
        reverse("core:payment_create", args=[sale.pk]),
        payment_form_data(),
    )

    assert response.status_code == 302
    assert Payment.objects.count() == 1
    assert get_sale_balance(sale).total_due == Decimal("10000.00")

    detail = client.get(reverse("core:sale_detail", args=[sale.pk]))
    assert "Pago parcial" in detail.content.decode()


def test_payment_screen_rejects_overpayment(client):
    sale = make_collectible_sale()

    response = client.post(
        reverse("core:payment_create", args=[sale.pk]),
        payment_form_data(amount="20001"),
    )

    assert response.status_code == 200
    assert "supera la deuda exigible" in response.content.decode()
    assert Payment.objects.count() == 0


def test_no_payment_quick_action_does_not_duplicate(client):
    sale = make_collectible_sale()
    url = reverse("core:collection_did_not_pay", args=[sale.pk])
    data = {"fecha": timezone.localdate().isoformat()}

    first = client.post(url, data)
    second = client.post(url, data)

    assert first.status_code == 302
    assert second.status_code == 302
    assert CollectionAttempt.objects.count() == 1
    assert get_sale_balance(sale).total_due == Decimal("20000.00")


def test_detailed_collection_attempt_is_saved(client):
    sale = make_collectible_sale()

    response = client.post(
        reverse("core:collection_attempt_create", args=[sale.pk]),
        {
            "attempt_date": timezone.localdate().isoformat(),
            "result": CollectionAttempt.Result.PROMISED,
            "notes": "Prometió pagar el viernes",
        },
    )

    assert response.status_code == 302
    attempt = CollectionAttempt.objects.get()
    assert attempt.result == CollectionAttempt.Result.PROMISED
    assert attempt.notes == "Prometió pagar el viernes"


def test_payment_can_be_voided_from_screen(client):
    sale = make_collectible_sale()
    client.post(
        reverse("core:payment_create", args=[sale.pk]),
        payment_form_data(amount="20000"),
    )
    payment = Payment.objects.get()
    sale.refresh_from_db()
    assert sale.status == Sale.Status.COMPLETED

    response = client.post(
        reverse("core:payment_void", args=[payment.pk]),
        {"reason": "Transferencia rechazada"},
    )
    payment.refresh_from_db()
    sale.refresh_from_db()

    assert response.status_code == 302
    assert payment.status == Payment.Status.VOIDED
    assert sale.status == Sale.Status.ACTIVE
    assert get_sale_balance(sale).total_due == Decimal("20000.00")


def test_completed_sale_disappears_from_collection(client):
    sale = make_collectible_sale()
    client.post(
        reverse("core:payment_create", args=[sale.pk]),
        payment_form_data(amount="20000"),
    )

    response = client.get(reverse("core:collection_list"))

    assert sale.customer.full_name not in response.content.decode()


def test_completed_sale_remains_visible_before_its_payment_date(client):
    today = timezone.localdate()
    sale = make_sale(
        delivery_date=today - timedelta(days=10),
        first_due_date=today - timedelta(days=1),
        financed_amount=Decimal("20000.00"),
        installment_count=1,
        daily_late_fee=Decimal("0.00"),
    )
    create_installments(sale)
    client.post(
        reverse("core:payment_create", args=[sale.pk]),
        payment_form_data(amount="20000"),
    )

    response = client.get(
        reverse("core:collection_list"),
        {"fecha": sale.first_due_date.isoformat()},
    )

    assert sale.customer.full_name in response.content.decode()
