from datetime import date
from decimal import Decimal

import pytest

from modules.core.models import (
    BusinessSettings,
    Installment,
    Payment,
    PaymentAllocation,
    Sale,
)
from modules.core.services.balances import get_installment_balance, get_sale_balance
from modules.core.services.late_fees import generate_missing_late_fees
from modules.core.tests.factories import make_sale

pytestmark = pytest.mark.django_db


def make_single_installment_sale(
    *,
    due_date: date = date(2026, 8, 18),
    amount: Decimal = Decimal("20000.00"),
) -> tuple[Sale, Installment]:
    sale = make_sale(
        installment_count=1,
        financed_amount=amount,
        first_due_date=due_date,
    )
    installment = Installment.objects.create(
        sale=sale,
        number=1,
        due_date=due_date,
        original_amount=amount,
    )
    return sale, installment


def create_payment_with_allocations(
    installment: Installment,
    *,
    payment_date: date,
    late_fee_amount: Decimal = Decimal("0.00"),
    principal_amount: Decimal = Decimal("0.00"),
    status: str = Payment.Status.REGISTERED,
) -> Payment:
    total = late_fee_amount + principal_amount
    payment = Payment.objects.create(
        customer=installment.sale.customer,
        sale=installment.sale,
        payment_date=payment_date,
        amount=total,
        payment_method="Efectivo",
        status=status,
    )
    if late_fee_amount:
        PaymentAllocation.objects.create(
            payment=payment,
            installment=installment,
            component=PaymentAllocation.Component.LATE_FEE,
            amount=late_fee_amount,
        )
    if principal_amount:
        PaymentAllocation.objects.create(
            payment=payment,
            installment=installment,
            component=PaymentAllocation.Component.PRINCIPAL,
            amount=principal_amount,
        )
    return payment


def test_three_days_late_generate_expected_amount():
    _, installment = make_single_installment_sale()

    result = generate_missing_late_fees(as_of=date(2026, 8, 21))
    balance = get_installment_balance(installment, as_of=date(2026, 8, 21))

    assert result.created == 3
    assert installment.late_fees.count() == 3
    assert balance.principal_due == Decimal("20000.00")
    assert balance.late_fees_due == Decimal("15000.00")
    assert balance.total_due == Decimal("35000.00")
    assert balance.days_overdue == 3


def test_late_fee_generation_is_idempotent():
    _, installment = make_single_installment_sale()

    first = generate_missing_late_fees(as_of=date(2026, 8, 20))
    second = generate_missing_late_fees(as_of=date(2026, 8, 20))

    assert first.created == 2
    assert second.created == 0
    assert installment.late_fees.count() == 2


def test_due_date_has_no_late_fee():
    _, installment = make_single_installment_sale()

    result = generate_missing_late_fees(as_of=date(2026, 8, 18))

    assert result.created == 0
    assert installment.late_fees.count() == 0


def test_sunday_generates_late_fee_by_default():
    _, installment = make_single_installment_sale(due_date=date(2026, 8, 22))

    result = generate_missing_late_fees(as_of=date(2026, 8, 23))

    assert result.created == 1
    assert installment.late_fees.get().fee_date.weekday() == 6


def test_sunday_can_be_excluded_by_configuration():
    settings = BusinessSettings.get_solo()
    settings.charge_sundays = False
    settings.save()
    _, installment = make_single_installment_sale(due_date=date(2026, 8, 22))

    result = generate_missing_late_fees(as_of=date(2026, 8, 24), settings=settings)

    assert result.created == 1
    assert list(installment.late_fees.values_list("fee_date", flat=True)) == [
        date(2026, 8, 24)
    ]


def test_partial_payment_keeps_generating_full_daily_fee():
    _, installment = make_single_installment_sale()
    generate_missing_late_fees(as_of=date(2026, 8, 19))
    create_payment_with_allocations(
        installment,
        payment_date=date(2026, 8, 19),
        late_fee_amount=Decimal("5000.00"),
        principal_amount=Decimal("5000.00"),
    )

    result = generate_missing_late_fees(as_of=date(2026, 8, 21))
    balance = get_installment_balance(installment, as_of=date(2026, 8, 21))

    assert result.created == 2
    assert balance.principal_due == Decimal("15000.00")
    assert balance.late_fees_due == Decimal("10000.00")
    assert balance.total_due == Decimal("25000.00")


def test_configuration_can_stop_fees_after_partial_payment():
    settings = BusinessSettings.get_solo()
    settings.late_fee_after_partial_payment = False
    settings.save()
    _, installment = make_single_installment_sale()
    generate_missing_late_fees(as_of=date(2026, 8, 19), settings=settings)
    create_payment_with_allocations(
        installment,
        payment_date=date(2026, 8, 19),
        late_fee_amount=Decimal("5000.00"),
        principal_amount=Decimal("5000.00"),
    )

    result = generate_missing_late_fees(as_of=date(2026, 8, 21), settings=settings)

    assert result.created == 0
    assert installment.late_fees.count() == 1


def test_fully_paid_installment_stops_generating_fees():
    _, installment = make_single_installment_sale()
    generate_missing_late_fees(as_of=date(2026, 8, 19))
    create_payment_with_allocations(
        installment,
        payment_date=date(2026, 8, 19),
        late_fee_amount=Decimal("5000.00"),
        principal_amount=Decimal("20000.00"),
    )

    result = generate_missing_late_fees(as_of=date(2026, 8, 21))

    assert result.created == 0
    assert installment.late_fees.count() == 1
    assert get_installment_balance(installment).total_due == Decimal("0.00")


def test_voided_payment_does_not_reduce_balance():
    _, installment = make_single_installment_sale()
    payment = create_payment_with_allocations(
        installment,
        payment_date=date(2026, 8, 18),
        principal_amount=Decimal("20000.00"),
    )
    payment.status = Payment.Status.VOIDED
    payment.voided_at = payment.created_at
    payment.void_reason = "Pago cargado por error"
    payment.save()

    balance = get_installment_balance(installment, as_of=date(2026, 8, 18))

    assert balance.principal_paid == Decimal("0.00")
    assert balance.total_due == Decimal("20000.00")


def test_cancelled_sale_does_not_generate_new_fees():
    sale, installment = make_single_installment_sale()
    sale.status = Sale.Status.CANCELLED
    sale.cancelled_on = date(2026, 8, 19)
    sale.cancellation_reason = "Operación dejada sin efecto"
    sale.save()

    result = generate_missing_late_fees(as_of=date(2026, 8, 21))

    assert result.created == 0
    assert installment.late_fees.count() == 0


def test_sale_balance_aggregates_its_installments():
    sale = make_sale(installment_count=2, financed_amount=Decimal("30000.00"))
    Installment.objects.bulk_create(
        [
            Installment(
                sale=sale,
                number=1,
                due_date=date(2026, 8, 18),
                original_amount=Decimal("15000.00"),
            ),
            Installment(
                sale=sale,
                number=2,
                due_date=date(2026, 8, 25),
                original_amount=Decimal("15000.00"),
            ),
        ]
    )

    balance = get_sale_balance(sale, as_of=date(2026, 8, 18))

    assert balance.principal_original == Decimal("30000.00")
    assert balance.total_due == Decimal("30000.00")
