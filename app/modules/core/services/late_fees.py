from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from modules.core.models import (
    BusinessSettings,
    Installment,
    LateFee,
    Payment,
    PaymentAllocation,
    Sale,
)
from modules.core.services.balances import (
    installment_balance_prefetches,
    sale_effective_filter,
)
from modules.core.services.money import ZERO, as_money


@dataclass(frozen=True)
class LateFeeGenerationResult:
    created: int
    evaluated_installments: int
    as_of: date


@transaction.atomic
def generate_missing_late_fees(
    *,
    as_of: date | None = None,
    settings: BusinessSettings | None = None,
    sale: Sale | None = None,
) -> LateFeeGenerationResult:
    effective_date = as_of or timezone.localdate()
    settings = settings or BusinessSettings.get_solo()
    installments = (
        Installment.objects.select_related("sale")
        .prefetch_related(*installment_balance_prefetches())
        .filter(
            due_date__lt=effective_date,
        )
        .filter(sale_effective_filter(effective_date, "sale"))
        .order_by("due_date", "pk")
    )
    if sale is not None:
        installments = installments.filter(sale=sale)

    pending_fees: list[LateFee] = []
    evaluated = 0
    for installment in installments:
        evaluated += 1
        if installment.sale.daily_late_fee <= ZERO:
            continue

        allocations_by_date: dict[date, list[PaymentAllocation]] = defaultdict(list)
        for allocation in installment.payment_allocations.all():
            if allocation.payment.status == Payment.Status.REGISTERED:
                allocations_by_date[allocation.payment.payment_date].append(allocation)

        fees_by_date = {
            late_fee.fee_date: late_fee.amount
            for late_fee in installment.late_fees.all()
        }
        principal_paid = ZERO
        late_fees_paid = ZERO
        late_fees_generated = ZERO
        had_payment = False

        for payment_date, allocations in allocations_by_date.items():
            if payment_date > installment.due_date:
                continue
            had_payment = True
            for allocation in allocations:
                if allocation.component == PaymentAllocation.Component.PRINCIPAL:
                    principal_paid += allocation.amount
                else:
                    late_fees_paid += allocation.amount
        for fee_date, amount in fees_by_date.items():
            if fee_date <= installment.due_date:
                late_fees_generated += amount

        fee_day = installment.due_date + timedelta(days=1)
        while fee_day <= effective_date:
            previous_day = fee_day - timedelta(days=1)
            for allocation in allocations_by_date.get(previous_day, []):
                had_payment = True
                if allocation.component == PaymentAllocation.Component.PRINCIPAL:
                    principal_paid += allocation.amount
                else:
                    late_fees_paid += allocation.amount
            late_fees_generated += fees_by_date.get(previous_day, ZERO)

            if not settings.charge_sundays and fee_day.weekday() == 6:
                fee_day += timedelta(days=1)
                continue

            principal_due = max(
                ZERO,
                as_money(installment.original_amount - principal_paid),
            )
            late_fees_due = max(
                ZERO,
                as_money(late_fees_generated - late_fees_paid),
            )
            if principal_due + late_fees_due <= ZERO:
                break

            if not settings.late_fee_after_partial_payment and had_payment:
                break

            if fee_day not in fees_by_date:
                amount = as_money(installment.sale.daily_late_fee)
                fees_by_date[fee_day] = amount
                pending_fees.append(
                    LateFee(
                        installment=installment,
                        fee_date=fee_day,
                        amount=amount,
                    )
                )
            fee_day += timedelta(days=1)

    if pending_fees:
        LateFee.objects.bulk_create(
            pending_fees,
            batch_size=1000,
            ignore_conflicts=True,
        )

    return LateFeeGenerationResult(
        created=len(pending_fees),
        evaluated_installments=evaluated,
        as_of=effective_date,
    )
