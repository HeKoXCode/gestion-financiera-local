from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from modules.core.models import Installment, Payment, PaymentAllocation, Sale
from modules.core.services.money import ZERO, as_money


@dataclass(frozen=True)
class InstallmentBalance:
    principal_original: Decimal
    principal_paid: Decimal
    principal_due: Decimal
    late_fees_generated: Decimal
    late_fees_paid: Decimal
    late_fees_due: Decimal
    total_paid: Decimal
    total_due: Decimal
    days_overdue: int


@dataclass(frozen=True)
class SaleBalance:
    principal_original: Decimal
    principal_paid: Decimal
    principal_due: Decimal
    late_fees_generated: Decimal
    late_fees_paid: Decimal
    late_fees_due: Decimal
    total_paid: Decimal
    total_due: Decimal


def _sum_amount(queryset) -> Decimal:
    value = queryset.aggregate(total=Sum("amount"))["total"]
    return as_money(value or ZERO)


def get_installment_balance(
    installment: Installment,
    *,
    as_of: date | None = None,
) -> InstallmentBalance:
    allocations = PaymentAllocation.objects.filter(
        installment=installment,
        payment__status=Payment.Status.REGISTERED,
    )
    late_fees = installment.late_fees.all()

    if as_of is not None:
        allocations = allocations.filter(payment__payment_date__lte=as_of)
        late_fees = late_fees.filter(fee_date__lte=as_of)

    principal_paid = _sum_amount(
        allocations.filter(component=PaymentAllocation.Component.PRINCIPAL)
    )
    late_fees_paid = _sum_amount(
        allocations.filter(component=PaymentAllocation.Component.LATE_FEE)
    )
    late_fees_generated = _sum_amount(late_fees)

    principal_original = as_money(installment.original_amount)
    principal_due = max(ZERO, as_money(principal_original - principal_paid))
    late_fees_due = max(ZERO, as_money(late_fees_generated - late_fees_paid))
    total_due = as_money(principal_due + late_fees_due)
    effective_date = as_of or timezone.localdate()
    days_overdue = (
        max(0, (effective_date - installment.due_date).days) if total_due > ZERO else 0
    )

    return InstallmentBalance(
        principal_original=principal_original,
        principal_paid=principal_paid,
        principal_due=principal_due,
        late_fees_generated=late_fees_generated,
        late_fees_paid=late_fees_paid,
        late_fees_due=late_fees_due,
        total_paid=as_money(principal_paid + late_fees_paid),
        total_due=total_due,
        days_overdue=days_overdue,
    )


def get_sale_balance(sale: Sale, *, as_of: date | None = None) -> SaleBalance:
    balances = [
        get_installment_balance(installment, as_of=as_of)
        for installment in sale.installments.all()
    ]

    def total(attribute: str) -> Decimal:
        return as_money(sum((getattr(balance, attribute) for balance in balances), ZERO))

    return SaleBalance(
        principal_original=total("principal_original"),
        principal_paid=total("principal_paid"),
        principal_due=total("principal_due"),
        late_fees_generated=total("late_fees_generated"),
        late_fees_paid=total("late_fees_paid"),
        late_fees_due=total("late_fees_due"),
        total_paid=total("total_paid"),
        total_due=total("total_due"),
    )
