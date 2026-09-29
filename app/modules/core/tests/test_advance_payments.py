import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from modules.core.models import BusinessSettings, Payment, PaymentAllocation
from modules.core.services.balances import (
    get_due_sale_balance,
    get_installment_balance,
)
from modules.core.services.installments import create_installments
from modules.core.services.late_fees import generate_missing_late_fees
from modules.core.services.payments import register_payment, void_payment
from modules.core.tests.factories import make_sale

pytestmark = pytest.mark.django_db


def make_future_sale(*, today: date, installment_count: int = 3):
    sale = make_sale(
        delivery_date=today - timedelta(days=7),
        first_due_date=today + timedelta(days=7),
        financed_amount=Decimal("60000.00"),
        installment_count=installment_count,
        daily_late_fee=Decimal("5000.00"),
    )
    create_installments(sale)
    return sale


def advance(sale, amount="20000.00"):
    return register_payment(
        sale=sale,
        amount=Decimal(amount),
        payment_date=timezone.localdate(),
        payment_method="Efectivo",
        notes="",
        operation_key=uuid.uuid4(),
        advance=True,
    )


def test_full_advance_pays_next_installment_without_moving_schedule(monkeypatch):
    today = date(2026, 8, 25)
    monkeypatch.setattr(timezone, "localdate", lambda value=None: today)
    sale = make_future_sale(today=today)
    original_dates = list(sale.installments.values_list("due_date", flat=True))

    result = advance(sale)
    sale.refresh_from_db()
    installments = list(sale.installments.order_by("number"))

    assert result.payment.is_advance is True
    assert result.payment.movement_label == "Pago adelantado"
    assert result.payment.payment_date == today
    assert list(sale.installments.values_list("due_date", flat=True)) == original_dates
    assert get_installment_balance(installments[0], as_of=today).principal_due == Decimal("0.00")
    assert get_installment_balance(
        installments[1],
        as_of=today,
    ).principal_due == Decimal("20000.00")
    assert get_due_sale_balance(sale, as_of=today + timedelta(days=13)).total_due == Decimal("0.00")
    assert get_due_sale_balance(sale, as_of=today + timedelta(days=14)).total_due == Decimal(
        "20000.00"
    )


def test_partial_advance_keeps_original_due_date_and_no_grace(monkeypatch):
    today = date(2026, 8, 25)
    monkeypatch.setattr(timezone, "localdate", lambda value=None: today)
    sale = make_future_sale(today=today)
    first = sale.installments.get(number=1)

    advance(sale, "10000.00")

    assert get_installment_balance(first, as_of=first.due_date).total_due == Decimal("10000.00")
    generate_missing_late_fees(
        as_of=first.due_date + timedelta(days=1),
        settings=BusinessSettings.get_solo(),
        sale=sale,
    )
    assert get_installment_balance(
        first,
        as_of=first.due_date + timedelta(days=1),
    ).total_due == Decimal("15000.00")


def test_advance_can_cover_several_future_installments_in_order(monkeypatch):
    today = date(2026, 8, 25)
    monkeypatch.setattr(timezone, "localdate", lambda value=None: today)
    sale = make_future_sale(today=today)

    payment = advance(sale, "40000.00").payment
    allocations = list(
        payment.allocations.filter(
            component=PaymentAllocation.Component.PRINCIPAL,
        ).order_by("installment__number")
    )

    assert [allocation.installment.number for allocation in allocations] == [1, 2]
    assert [allocation.amount for allocation in allocations] == [
        Decimal("20000.00"),
        Decimal("20000.00"),
    ]


def test_normal_payment_never_consumes_future_installment(monkeypatch):
    today = date(2026, 8, 25)
    monkeypatch.setattr(timezone, "localdate", lambda value=None: today)
    sale = make_future_sale(today=today)
    settings = BusinessSettings.get_solo()
    assert settings.allow_advance_payments is True

    with pytest.raises(ValidationError, match="no tiene cuotas pendientes"):
        register_payment(
            sale=sale,
            amount=Decimal("20000.00"),
            payment_date=today,
            payment_method="Efectivo",
            operation_key=uuid.uuid4(),
            settings=settings,
        )

    assert Payment.objects.count() == 0


def test_advance_requires_sale_to_be_current(monkeypatch):
    today = date(2026, 8, 25)
    monkeypatch.setattr(timezone, "localdate", lambda value=None: today)
    sale = make_sale(
        delivery_date=today - timedelta(days=7),
        first_due_date=today,
        financed_amount=Decimal("40000.00"),
        installment_count=2,
    )
    create_installments(sale)

    with pytest.raises(ValidationError, match="Registrá primero el pago normal"):
        advance(sale)

    assert Payment.objects.count() == 0


def test_voiding_advance_restores_same_original_installment(monkeypatch):
    today = date(2026, 8, 25)
    monkeypatch.setattr(timezone, "localdate", lambda value=None: today)
    monkeypatch.setattr(
        timezone,
        "now",
        lambda: datetime(2026, 8, 25, 12, tzinfo=timezone.get_current_timezone()),
    )
    sale = make_future_sale(today=today)
    first = sale.installments.get(number=1)
    payment = advance(sale).payment

    void_payment(payment=payment, reason="Adelanto cargado por error")

    assert get_installment_balance(first, as_of=today).principal_due == Decimal("20000.00")
    assert first.due_date == today + timedelta(days=7)


def test_advance_flow_is_available_from_collection_and_sale(client, monkeypatch):
    today = date(2026, 8, 25)
    monkeypatch.setattr(timezone, "localdate", lambda value=None: today)
    sale = make_future_sale(today=today)

    collection = client.get(reverse("core:collection_list"))
    sale_page = client.get(reverse("core:sale_detail", args=[sale.pk]))
    selection = client.get(reverse("core:advance_payment_list"))
    form_page = client.get(reverse("core:advance_payment_create", args=[sale.pk]))

    assert "Registrar pago adelantado" in collection.content.decode()
    assert sale_page.content.decode().count("Adelantar esta cuota") == 1
    assert "Después de la anterior" in sale_page.content.decode()
    assert sale.customer.full_name in selection.content.decode()
    assert "No mueve las fechas" in form_page.content.decode()
    assert form_page.context["form"].initial["amount"] == Decimal("20000.00")


def test_advance_form_registers_today_and_returns_a_clear_history_label(client, monkeypatch):
    today = date(2026, 8, 25)
    monkeypatch.setattr(timezone, "localdate", lambda value=None: today)
    sale = make_future_sale(today=today)

    response = client.post(
        reverse("core:advance_payment_create", args=[sale.pk]),
        {
            "operation_key": str(uuid.uuid4()),
            "amount": "20000.00",
            "payment_date": today.isoformat(),
            "payment_method": "Efectivo",
            "notes": "Cuota de la semana siguiente",
            "origin": "venta",
        },
        follow=True,
    )
    payment = Payment.objects.get()

    assert response.status_code == 200
    assert "Las fechas de las cuotas no se modificaron" in response.content.decode()
    assert payment.payment_date == today
    assert payment.is_advance is True
    assert response.resolver_match.url_name == "sale_detail"
    sale_page = client.get(reverse("core:sale_detail", args=[sale.pk]))
    assert "Pago adelantado" in sale_page.content.decode()
