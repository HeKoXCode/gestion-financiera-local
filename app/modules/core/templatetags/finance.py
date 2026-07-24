from decimal import ROUND_DOWN, Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def ars(value) -> str:
    try:
        amount = Decimal(value or 0).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return "$ 0,00"

    formatted = f"{amount:,.2f}"
    integer, decimals = formatted.split(".")
    integer = integer.replace(",", ".")
    return f"$ {integer},{decimals}"


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
