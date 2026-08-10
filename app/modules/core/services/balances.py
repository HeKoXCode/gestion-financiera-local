from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Prefetch, Q, Sum
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


@dataclass(frozen=True)
class InstallmentPaymentTiming:
    paid_on: date | None
    days_late: int


def _sum_amount(queryset) -> Decimal:
    value = queryset.aggregate(total=Sum("amount"))["total"]
    return as_money(value or ZERO)


def installment_balance_prefetches(prefix: str = "") -> tuple[Prefetch, Prefetch]:
    """Return the relations needed to calculate balances without N+1 queries."""
    relation_prefix = f"{prefix}__" if prefix else ""
    return (
        Prefetch(f"{relation_prefix}late_fees"),
        Prefetch(
            f"{relation_prefix}payment_allocations",
            queryset=PaymentAllocation.objects.select_related("payment"),
        ),
    )


def _cached_relation(instance, relation: str):
    return getattr(instance, "_prefetched_objects_cache", {}).get(relation)


def registered_payment_filter(as_of: date | None, prefix: str = "") -> Q:
    """Payments that were still valid at the requested business date."""
    field_prefix = f"{prefix}__" if prefix else ""
    registered = Q(**{f"{field_prefix}status": Payment.Status.REGISTERED})
    if as_of is None:
        return registered
    return registered | Q(
        **{
            f"{field_prefix}status": Payment.Status.VOIDED,
            f"{field_prefix}voided_at__date__gt": as_of,
        }
    )


def sale_effective_filter(as_of: date, prefix: str = "") -> Q:
    """Sales that had not yet been cancelled at the requested date."""
    field_prefix = f"{prefix}__" if prefix else ""
    return ~Q(**{f"{field_prefix}status": Sale.Status.CANCELLED}) | Q(
        **{f"{field_prefix}cancelled_on__gt": as_of}
    )


def _payment_was_registered(payment: Payment, as_of: date | None) -> bool:
    if payment.status == Payment.Status.REGISTERED:
        return True
    return bool(
        as_of is not None
        and payment.status == Payment.Status.VOIDED
        and payment.voided_at
        and timezone.localdate(payment.voided_at) > as_of
    )


def get_installment_payment_timing(
    installment: Installment,
    *,
    as_of: date | None = None,
) -> InstallmentPaymentTiming:
    """Return when a fully paid installment was settled and its calendar delay."""
    cached_allocations = _cached_relation(installment, "payment_allocations")
    if cached_allocations is None:
        allocations = list(
            installment.payment_allocations.select_related("payment").all()
        )
    else:
        allocations = list(cached_allocations)

    registered_allocations = [
        allocation
        for allocation in allocations
        if _payment_was_registered(allocation.payment, as_of)
        and (as_of is None or allocation.payment.payment_date <= as_of)
    ]
    principal_paid = as_money(
        sum(
            (
                allocation.amount
                for allocation in registered_allocations
                if allocation.component == PaymentAllocation.Component.PRINCIPAL
            ),
            ZERO,
        )
    )
    if principal_paid < as_money(installment.original_amount):
        return InstallmentPaymentTiming(paid_on=None, days_late=0)

    paid_on = max(
        (allocation.payment.payment_date for allocation in registered_allocations),
        default=None,
    )
    if paid_on is None:
        return InstallmentPaymentTiming(paid_on=None, days_late=0)
    return InstallmentPaymentTiming(
        paid_on=paid_on,
        days_late=max(0, (paid_on - installment.due_date).days),
    )


def get_installment_balance(
    installment: Installment,
    *,
    as_of: date | None = None,
) -> InstallmentBalance:
    cached_allocations = _cached_relation(installment, "payment_allocations")
    cached_late_fees = _cached_relation(installment, "late_fees")
    if cached_allocations is not None and cached_late_fees is not None:
        allocations = [
            allocation
            for allocation in cached_allocations
            if _payment_was_registered(allocation.payment, as_of)
            and (
                as_of is None
                or allocation.payment.payment_date <= as_of
            )
        ]
        late_fees = [
            late_fee
            for late_fee in cached_late_fees
            if as_of is None or late_fee.fee_date <= as_of
        ]
        principal_paid = as_money(
            sum(
                (
                    allocation.amount
                    for allocation in allocations
                    if allocation.component
                    == PaymentAllocation.Component.PRINCIPAL
                ),
                ZERO,
            )
        )
        late_fees_paid = as_money(
            sum(
                (
                    allocation.amount
                    for allocation in allocations
                    if allocation.component
                    == PaymentAllocation.Component.LATE_FEE
                ),
                ZERO,
            )
        )
        late_fees_generated = as_money(
            sum((late_fee.amount for late_fee in late_fees), ZERO)
        )
    else:
        allocation_queryset = PaymentAllocation.objects.filter(
            registered_payment_filter(as_of, "payment"),
            installment=installment,
        )
        late_fee_queryset = installment.late_fees.all()

        if as_of is not None:
            allocation_queryset = allocation_queryset.filter(
                payment__payment_date__lte=as_of
            )
            late_fee_queryset = late_fee_queryset.filter(fee_date__lte=as_of)

        principal_paid = _sum_amount(
            allocation_queryset.filter(
                component=PaymentAllocation.Component.PRINCIPAL
            )
        )
        late_fees_paid = _sum_amount(
            allocation_queryset.filter(
                component=PaymentAllocation.Component.LATE_FEE
            )
        )
        late_fees_generated = _sum_amount(late_fee_queryset)

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


def get_due_sale_balance(sale: Sale, *, as_of: date) -> SaleBalance:
    """Return only debt that is due on or before the selected date."""
    cached_installments = _cached_relation(sale, "installments")
    installments = (
        [
            installment
            for installment in cached_installments
            if installment.due_date <= as_of
        ]
        if cached_installments is not None
        else sale.installments.filter(due_date__lte=as_of)
    )
    balances = [
        get_installment_balance(installment, as_of=as_of) for installment in installments
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
