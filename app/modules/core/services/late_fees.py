from __future__ import annotations

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
from modules.core.services.balances import get_installment_balance
from modules.core.services.money import ZERO


@dataclass(frozen=True)
class LateFeeGenerationResult:
    created: int
    evaluated_installments: int
    as_of: date


def _had_payment_before(installment: Installment, day: date) -> bool:
    return PaymentAllocation.objects.filter(
        installment=installment,
        payment__status=Payment.Status.REGISTERED,
        payment__payment_date__lt=day,
    ).exists()


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
        .filter(
            sale__status=Sale.Status.ACTIVE,
            due_date__lt=effective_date,
        )
        .order_by("due_date", "pk")
    )
    if sale is not None:
        installments = installments.filter(sale=sale)

    created = 0
    evaluated = 0
    for installment in installments:
        evaluated += 1
        if installment.sale.daily_late_fee <= ZERO:
            continue

        fee_day = installment.due_date + timedelta(days=1)
        while fee_day <= effective_date:
            if not settings.charge_sundays and fee_day.weekday() == 6:
                fee_day += timedelta(days=1)
                continue

            previous_day = fee_day - timedelta(days=1)
            prior_balance = get_installment_balance(installment, as_of=previous_day)
            if prior_balance.total_due <= ZERO:
                break

            if (
                not settings.late_fee_after_partial_payment
                and _had_payment_before(installment, fee_day)
            ):
                break

            _, was_created = LateFee.objects.get_or_create(
                installment=installment,
                fee_date=fee_day,
                defaults={"amount": installment.sale.daily_late_fee},
            )
            created += int(was_created)
            fee_day += timedelta(days=1)

    return LateFeeGenerationResult(
        created=created,
        evaluated_installments=evaluated,
        as_of=effective_date,
    )
