import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.core.models import Payment, PaymentAllocation, Sale
from modules.core.services.balances import get_installment_balance, get_sale_balance
from modules.core.services.installments import create_installments
from modules.core.services.payments import (
    register_initial_payment,
    register_payment,
    void_payment,
)
from modules.core.tests.factories import make_sale

pytestmark = pytest.mark.django_db


def make_due_sale(
    *,
    amount: Decimal = Decimal("20000.00"),
    installment_count: int = 1,
    first_due_offset: int = 0,
    daily_late_fee: Decimal = Decimal("0.00"),
    **sale_overrides,
):
    today = timezone.localdate()
    delivery_date = sale_overrides.pop(
        "delivery_date",
        today - timedelta(days=30),
    )
    sale = make_sale(
        delivery_date=delivery_date,
        first_due_date=today + timedelta(days=first_due_offset),
        financed_amount=amount,
        installment_count=installment_count,
        daily_late_fee=daily_late_fee,
        **sale_overrides,
    )
    create_installments(sale)
    return sale


def register(
    sale,
    amount,
    *,
    payment_date=None,
    operation_key=None,
    method="Efectivo",
):
    return register_payment(
        sale=sale,
        amount=Decimal(amount),
        payment_date=payment_date or timezone.localdate(),
        payment_method=method,
        notes="Pago de prueba",
        operation_key=operation_key or uuid.uuid4(),
    )


def test_payment_applies_late_fees_before_principal():
    sale = make_due_sale(first_due_offset=-3, daily_late_fee=Decimal("5000.00"))
    installment = sale.installments.get()

    result = register(sale, "20000.00")
    allocations = result.payment.allocations.order_by("component")
    balance = get_installment_balance(installment)

    assert result.created is True
    assert installment.late_fees.count() == 3
    assert allocations.get(component=PaymentAllocation.Component.LATE_FEE).amount == Decimal(
        "15000.00"
    )
    assert allocations.get(component=PaymentAllocation.Component.PRINCIPAL).amount == Decimal(
        "5000.00"
    )
    assert balance.principal_due == Decimal("15000.00")
    assert balance.late_fees_due == Decimal("0.00")


def test_payment_continues_with_next_oldest_installment():
    sale = make_due_sale(
        amount=Decimal("40000.00"),
        installment_count=2,
        first_due_offset=-14,
    )

    result = register(sale, "25000.00")
    first, second = sale.installments.all()

    assert get_installment_balance(first).total_due == Decimal("0.00")
    assert get_installment_balance(second).principal_due == Decimal("15000.00")
    assert result.payment.allocations.count() == 2


def test_payment_cannot_exceed_exigible_debt():
    sale = make_due_sale()

    with pytest.raises(ValidationError):
        register(sale, "20000.01")

    assert Payment.objects.count() == 0


def test_payment_cannot_be_advanced_by_default():
    sale = make_due_sale(first_due_offset=1)

    with pytest.raises(ValidationError):
        register(sale, "1000.00")

    assert Payment.objects.count() == 0


def test_operation_key_makes_payment_idempotent():
    sale = make_due_sale()
    operation_key = uuid.uuid4()

    first = register(sale, "20000.00", operation_key=operation_key)
    second = register(sale, "20000.00", operation_key=operation_key)

    assert first.created is True
    assert second.created is False
    assert first.payment.pk == second.payment.pk
    assert Payment.objects.count() == 1


def test_fully_paid_sale_becomes_completed():
    sale = make_due_sale()

    register(sale, "20000.00")
    sale.refresh_from_db()

    assert sale.status == Sale.Status.COMPLETED
    assert get_sale_balance(sale).total_due == Decimal("0.00")


def test_voiding_payment_restores_balance_and_active_status():
    sale = make_due_sale()
    payment = register(sale, "20000.00").payment

    changed = void_payment(payment=payment, reason="Importe cargado por error")
    payment.refresh_from_db()
    sale.refresh_from_db()

    assert changed is True
    assert payment.status == Payment.Status.VOIDED
    assert payment.void_reason == "Importe cargado por error"
    assert sale.status == Sale.Status.ACTIVE
    assert get_sale_balance(sale).total_due == Decimal("20000.00")
    assert void_payment(payment=payment, reason="Repetido") is False


def test_voiding_old_payment_recreates_missing_late_fee():
    sale = make_due_sale(first_due_offset=-1, daily_late_fee=Decimal("5000.00"))
    due_date = sale.first_due_date
    payment = register(sale, "20000.00", payment_date=due_date).payment

    void_payment(payment=payment, reason="Transferencia rechazada")
    installment = sale.installments.get()

    assert installment.late_fees.count() == 1
    assert get_installment_balance(installment).total_due == Decimal("25000.00")


def test_invalid_payment_method_is_rejected():
    sale = make_due_sale()

    with pytest.raises(ValidationError):
        register(sale, "1000.00", method="Cheque")


def test_initial_payment_cannot_be_voided_separately():
    sale = make_due_sale(
        amount=Decimal("40000.00"),
        cash_price=Decimal("60000.00"),
        down_payment=Decimal("20000.00"),
        delivery_date=timezone.localdate(),
    )
    payment = register_initial_payment(
        sale=sale,
        payment_method="Efectivo",
    )

    with pytest.raises(ValidationError, match="no se anula por separado"):
        void_payment(payment=payment, reason="Importe incorrecto")

    payment.refresh_from_db()
    assert payment.status == Payment.Status.REGISTERED
