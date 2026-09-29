from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_DOWN, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from modules.core.models import BusinessSettings, Installment, Sale
from modules.core.services.money import CENT, as_money


@dataclass(frozen=True)
class PlannedInstallment:
    number: int
    due_date: date
    amount: Decimal


def add_months(anchor: date, months: int) -> date:
    """Move from the original due date, using month-end when needed."""
    month_index = anchor.month - 1 + months
    year = anchor.year + month_index // 12
    month = month_index % 12 + 1
    day = min(anchor.day, monthrange(year, month)[1])
    return date(year, month, day)


def next_enabled_collection_day(
    anchor: date,
    collection_days: list[int],
    *,
    include_anchor: bool = True,
) -> date:
    enabled_days = {int(day) for day in collection_days}
    if not enabled_days:
        raise ValidationError(
            "Configurá al menos un día habilitado para usar la frecuencia diaria."
        )
    candidate = anchor if include_anchor else anchor + timedelta(days=1)
    for _ in range(8):
        if candidate.weekday() in enabled_days:
            return candidate
        candidate += timedelta(days=1)
    raise ValidationError("No se pudo calcular el próximo día de cobranza.")


def calculate_due_dates(
    *,
    first_due_date: date,
    frequency: str,
    installment_count: int,
    collection_days: list[int] | None = None,
) -> list[date]:
    if installment_count < 1:
        raise ValidationError("La cantidad de cuotas debe ser mayor que cero.")
    if frequency == Sale.Frequency.DAILY:
        due_dates = []
        current = next_enabled_collection_day(
            first_due_date,
            collection_days or [],
        )
        for _ in range(installment_count):
            due_dates.append(current)
            current = next_enabled_collection_day(
                current,
                collection_days or [],
                include_anchor=False,
            )
        return due_dates
    if frequency == Sale.Frequency.WEEKLY:
        return [first_due_date + timedelta(days=offset * 7) for offset in range(installment_count)]
    if frequency == Sale.Frequency.BIWEEKLY:
        return [first_due_date + timedelta(days=offset * 14) for offset in range(installment_count)]
    if frequency == Sale.Frequency.MONTHLY:
        return [add_months(first_due_date, offset) for offset in range(installment_count)]
    raise ValidationError({"frequency": "La frecuencia de la operación no es válida."})


def calculate_installment_amounts(financed_amount: Decimal, count: int) -> list[Decimal]:
    if count < 1:
        raise ValidationError("La cantidad de cuotas debe ser mayor que cero.")

    total = as_money(financed_amount)
    if total <= 0:
        raise ValidationError("El total en cuotas debe ser mayor que cero.")

    regular_amount = (total / count).quantize(CENT, rounding=ROUND_DOWN)
    if regular_amount <= 0:
        raise ValidationError("El monto es demasiado pequeño para la cantidad de cuotas.")

    amounts = [regular_amount] * (count - 1)
    amounts.append(as_money(total - sum(amounts, Decimal("0.00"))))
    return amounts


def calculate_installment_schedule(sale: Sale) -> list[PlannedInstallment]:
    settings = BusinessSettings.get_solo()
    if sale.frequency not in settings.available_frequencies:
        raise ValidationError({"frequency": "La frecuencia no está habilitada."})
    if sale.installment_count > settings.max_installments:
        raise ValidationError(
            {
                "installment_count": (
                    f"La configuración permite hasta {settings.max_installments} cuotas."
                )
            }
        )

    amounts = calculate_installment_amounts(sale.financed_amount, sale.installment_count)
    due_dates = calculate_due_dates(
        first_due_date=sale.first_due_date,
        frequency=sale.frequency,
        installment_count=sale.installment_count,
        collection_days=settings.collection_days,
    )
    return [
        PlannedInstallment(
            number=index,
            due_date=due_date,
            amount=amount,
        )
        for index, (amount, due_date) in enumerate(
            zip(amounts, due_dates, strict=True),
            start=1,
        )
    ]


@transaction.atomic
def create_installments(sale: Sale) -> list[Installment]:
    if not sale.pk:
        raise ValidationError("La operación debe guardarse antes de generar sus cuotas.")
    if sale.installments.exists():
        raise ValidationError("La operación ya tiene cuotas generadas.")

    schedule = calculate_installment_schedule(sale)
    return Installment.objects.bulk_create(
        [
            Installment(
                sale=sale,
                number=item.number,
                due_date=item.due_date,
                original_amount=item.amount,
            )
            for item in schedule
        ]
    )
