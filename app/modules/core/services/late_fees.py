from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.core.models import (
    BusinessSettings,
    LateFee,
    LateFeePausePeriod,
    Payment,
    PaymentAllocation,
    Sale,
)
from modules.core.services.balances import (
    installment_balance_prefetches,
    sale_effective_filter,
)
from modules.core.services.money import ZERO, as_money

SINGLE_DAILY_POLICY_REASON = (
    "Política v1.3: sólo corresponde un recargo por día para toda la venta; "
    "el cargo duplicado por otra cuota queda como registro histórico."
)


@dataclass(frozen=True)
class LateFeeGenerationResult:
    created: int
    evaluated_installments: int
    as_of: date


def late_fee_is_paused_for_charge_date(
    periods: list[LateFeePausePeriod],
    fee_date: date,
) -> bool:
    """A fee dated D is produced by the unpaid state of D-1.

    Pausing on a day prevents that day from producing tomorrow's fee. Resuming
    on a day enables that day again, so a new fee may appear the following day.
    """
    accrual_day = fee_date - timedelta(days=1)
    return any(
        period.paused_from <= accrual_day
        and (period.resumed_at is None or accrual_day < period.resumed_at)
        for period in periods
    )


@transaction.atomic
def pause_late_fee_generation(
    *,
    sale: Sale,
    reason: str,
    action_date: date | None = None,
) -> tuple[LateFeePausePeriod, bool]:
    effective_date = action_date or timezone.localdate()
    if effective_date > timezone.localdate():
        raise ValidationError("La pausa no puede comenzar en una fecha futura.")
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    if sale.status != Sale.Status.ACTIVE:
        raise ValidationError("Solo se puede pausar el recargo de una operación activa.")
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValidationError("Indicá por qué se pausa el recargo diario.")
    current = (
        LateFeePausePeriod.objects.select_for_update()
        .filter(sale=sale, resumed_at__isnull=True)
        .first()
    )
    if current:
        return current, False
    period = LateFeePausePeriod(
        sale=sale,
        paused_from=effective_date,
        reason=normalized_reason,
    )
    period.full_clean()
    period.save()
    return period, True


@transaction.atomic
def resume_late_fee_generation(
    *,
    sale: Sale,
    reason: str = "Reactivado desde Cobranza",
    action_date: date | None = None,
) -> tuple[LateFeePausePeriod, bool]:
    effective_date = action_date or timezone.localdate()
    if effective_date > timezone.localdate():
        raise ValidationError("La reanudación no puede registrarse en una fecha futura.")
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    current = (
        LateFeePausePeriod.objects.select_for_update()
        .filter(sale=sale, resumed_at__isnull=True)
        .first()
    )
    if current is None:
        latest = sale.late_fee_pause_periods.order_by("-paused_from", "-pk").first()
        if latest is not None:
            return latest, False
        raise ValidationError("Esta operación no tiene el recargo diario pausado.")
    if effective_date < current.paused_from:
        raise ValidationError("La reanudación no puede ser anterior a la pausa.")
    current.resumed_at = effective_date
    current.resume_reason = reason.strip() or "Reactivado desde Cobranza"
    current.full_clean()
    current.save(update_fields=["resumed_at", "resume_reason", "updated_at"])
    return current, True


def _payment_was_registered(payment: Payment, as_of: date) -> bool:
    if payment.status == Payment.Status.REGISTERED:
        return payment.payment_date <= as_of
    return bool(
        payment.status == Payment.Status.VOIDED
        and payment.voided_at
        and payment.payment_date <= as_of
        and timezone.localdate(payment.voided_at) > as_of
    )


def _reconcile_fee_day(
    *,
    fees: list[LateFee],
    target: object,
    fee_date: date,
    host_installment,
    create_missing: bool,
) -> tuple[int, object]:
    """Leave one effective daily charge without deleting duplicate audit rows."""
    target = as_money(target)
    fees.sort(key=lambda fee: (fee.installment.due_date, fee.installment.number, fee.pk))
    effective_total = as_money(sum((fee.effective_amount for fee in fees), ZERO))
    changed: list[LateFee] = []

    if effective_total > target:
        surplus = as_money(effective_total - target)
        for fee in reversed(fees):
            if surplus <= ZERO:
                break
            reduction = min(surplus, fee.effective_amount)
            if reduction <= ZERO:
                continue
            fee.waived_amount = as_money(fee.waived_amount + reduction)
            fee.waived_reason = SINGLE_DAILY_POLICY_REASON
            fee.waived_at = timezone.now()
            surplus = as_money(surplus - reduction)
            changed.append(fee)
    elif effective_total < target:
        missing = as_money(target - effective_total)
        for fee in fees:
            if missing <= ZERO:
                break
            restored = min(missing, fee.waived_amount)
            if restored <= ZERO:
                continue
            fee.waived_amount = as_money(fee.waived_amount - restored)
            if fee.waived_amount <= ZERO:
                fee.waived_amount = ZERO
                fee.waived_reason = ""
                fee.waived_at = None
            missing = as_money(missing - restored)
            changed.append(fee)

    if changed:
        changed_at = timezone.now()
        for fee in changed:
            fee.updated_at = changed_at
        LateFee.objects.bulk_update(
            changed,
            ["waived_amount", "waived_reason", "waived_at", "updated_at"],
            batch_size=500,
        )

    effective_total = as_money(sum((fee.effective_amount for fee in fees), ZERO))
    missing = as_money(target - effective_total)
    if missing <= ZERO:
        return 0, effective_total

    if fees:
        fee = fees[0]
        fee.amount = as_money(fee.amount + missing)
        fee.full_clean()
        fee.save(update_fields=["amount", "updated_at"])
        return 0, target

    if not create_missing:
        return 0, effective_total

    fee = LateFee.objects.create(
        installment=host_installment,
        fee_date=fee_date,
        amount=missing,
    )
    fees.append(fee)
    return 1, target


@transaction.atomic
def generate_missing_late_fees(
    *,
    as_of: date | None = None,
    settings: BusinessSettings | None = None,
    sale: Sale | None = None,
    create_missing: bool = True,
) -> LateFeeGenerationResult:
    """Generate one daily charge per overdue sale, never one per installment.

    All installments whose dates have arrived still add their unpaid principal.
    The late charge follows the sale as a single daily stream beginning with the
    oldest unpaid due date. A second or third overdue installment can therefore
    add principal and display its own delay, but cannot duplicate the charge for
    a calendar day that was already charged to the sale.
    """
    effective_date = as_of or timezone.localdate()
    settings = settings or BusinessSettings.get_solo()
    sales = (
        Sale.objects.select_related("customer")
        .prefetch_related(
            "installments",
            "late_fee_pause_periods",
            *installment_balance_prefetches("installments"),
        )
        .filter(delivery_date__lte=effective_date)
        .filter(sale_effective_filter(effective_date))
        .order_by("pk")
    )
    if sale is not None:
        sales = sales.filter(pk=sale.pk)

    created = 0
    evaluated = 0
    for current_sale in sales:
        pause_periods = list(current_sale.late_fee_pause_periods.all())
        installments = sorted(
            current_sale.installments.all(),
            key=lambda item: (item.due_date, item.number, item.pk),
        )
        evaluated += len(installments)
        if not installments or current_sale.daily_late_fee <= ZERO:
            continue

        allocations_by_date: dict[date, list[PaymentAllocation]] = defaultdict(list)
        fees_by_date: dict[date, list[LateFee]] = defaultdict(list)
        for installment in installments:
            for allocation in installment.payment_allocations.all():
                if _payment_was_registered(allocation.payment, effective_date):
                    allocations_by_date[allocation.payment.payment_date].append(allocation)
            for fee in installment.late_fees.all():
                if fee.fee_date <= effective_date:
                    fees_by_date[fee.fee_date].append(fee)

        first_due_date = installments[0].due_date
        principal_paid = defaultdict(lambda: ZERO)
        late_fees_paid = ZERO
        generated_total = ZERO
        had_payment_while_open = False

        for payment_date, allocations in allocations_by_date.items():
            if payment_date > first_due_date:
                continue
            had_payment_while_open = True
            for allocation in allocations:
                if allocation.component == PaymentAllocation.Component.PRINCIPAL:
                    principal_paid[allocation.installment_id] = as_money(
                        principal_paid[allocation.installment_id] + allocation.amount
                    )
                else:
                    late_fees_paid = as_money(late_fees_paid + allocation.amount)
        for fee_date, fees in fees_by_date.items():
            if fee_date <= first_due_date:
                generated_total = as_money(
                    generated_total + sum((fee.effective_amount for fee in fees), ZERO)
                )

        fee_day = first_due_date + timedelta(days=1)
        while fee_day <= effective_date:
            previous_day = fee_day - timedelta(days=1)
            previous_allocations = allocations_by_date.get(previous_day, [])
            if previous_allocations:
                had_payment_while_open = True
            for allocation in previous_allocations:
                if allocation.component == PaymentAllocation.Component.PRINCIPAL:
                    principal_paid[allocation.installment_id] = as_money(
                        principal_paid[allocation.installment_id] + allocation.amount
                    )
                else:
                    late_fees_paid = as_money(late_fees_paid + allocation.amount)
            generated_total = as_money(
                generated_total
                + sum(
                    (fee.effective_amount for fee in fees_by_date.get(previous_day, [])),
                    ZERO,
                )
            )

            overdue_principal = []
            for installment in installments:
                if installment.due_date >= fee_day:
                    continue
                principal_due = max(
                    ZERO,
                    as_money(installment.original_amount - principal_paid[installment.pk]),
                )
                if principal_due > ZERO:
                    overdue_principal.append(installment)

            late_fees_due = max(ZERO, as_money(generated_total - late_fees_paid))
            is_behind = bool(overdue_principal or late_fees_due > ZERO)
            if not is_behind:
                had_payment_while_open = False

            should_charge = (
                is_behind
                and not late_fee_is_paused_for_charge_date(pause_periods, fee_day)
                and (settings.charge_sundays or fee_day.weekday() != 6)
                and (settings.late_fee_after_partial_payment or not had_payment_while_open)
            )
            target = current_sale.daily_late_fee if should_charge else ZERO
            host_installment = overdue_principal[0] if overdue_principal else installments[0]
            new_count, _ = _reconcile_fee_day(
                fees=fees_by_date[fee_day],
                target=target,
                fee_date=fee_day,
                host_installment=host_installment,
                create_missing=create_missing,
            )
            created += new_count
            fee_day += timedelta(days=1)

    return LateFeeGenerationResult(
        created=created,
        evaluated_installments=evaluated,
        as_of=effective_date,
    )
