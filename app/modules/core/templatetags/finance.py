from decimal import ROUND_DOWN, Decimal, InvalidOperation

from django import template

from modules.core.services.money import format_ars

register = template.Library()


@register.filter
def ars(value) -> str:
    return format_ars(value)


@register.filter
def installment_estimate(value, count) -> Decimal:
    try:
        total = Decimal(value)
        quantity = Decimal(count)
        if quantity <= 0:
            return Decimal("0.00")
        return (total / quantity).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    except (InvalidOperation, TypeError, ValueError, ZeroDivisionError):
        return Decimal("0.00")
