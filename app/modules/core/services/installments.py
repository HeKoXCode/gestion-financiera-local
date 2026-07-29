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


def calculate_installment_amounts(financed_amount: Decimal, count: int) -> list[Decimal]:
    if count < 1:
        raise ValidationError("La cantidad de cuotas debe ser mayor que cero.")

    total = as_money(financed_amount)
    if total <= 0:
        raise ValidationError("El monto financiado debe ser mayor que cero.")

    regular_amount = (total / count).quantize(CENT, rounding=ROUND_DOWN)
    if regular_amount <= 0:
        raise ValidationError("El monto es demasiado pequeño para la cantidad de cuotas.")

    amounts = [regular_amount] * (count - 1)
    amounts.append(as_money(total - sum(amounts, Decimal("0.00"))))
    return amounts


def calculate_installment_schedule(sale: Sale) -> list[PlannedInstallment]:
    if sale.frequency == Sale.Frequency.WEEKLY:
        interval_days = 7
    elif sale.frequency == Sale.Frequency.BIWEEKLY:
        interval_days = 14
    elif sale.frequency == Sale.Frequency.MONTHLY:
        interval_days = None
    else:
        raise ValidationError({"frequency": "La frecuencia de la venta no es válida."})

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
    return [
        PlannedInstallment(
            number=index,
            due_date=(
                add_months(sale.first_due_date, index - 1)
                if interval_days is None
                else sale.first_due_date
                + timedelta(days=(index - 1) * interval_days)
            ),
            amount=amount,
        )
        for index, amount in enumerate(amounts, start=1)
    ]


@transaction.atomic
def create_installments(sale: Sale) -> list[Installment]:
    if not sale.pk:
        raise ValidationError("La venta debe guardarse antes de generar sus cuotas.")
    if sale.installments.exists():
        raise ValidationError("La venta ya tiene cuotas generadas.")

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
