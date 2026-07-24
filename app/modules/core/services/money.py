from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def as_money(value: Decimal | int | str) -> Decimal:
    """Return an exact two-decimal monetary value."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def format_ars(value) -> str:
    try:
        amount = Decimal(value or 0).quantize(CENT)
    except (InvalidOperation, TypeError, ValueError):
        return "$ 0,00"

    formatted = f"{amount:,.2f}"
    integer, decimals = formatted.split(".")
    return f"$ {integer.replace(',', '.')},{decimals}"
