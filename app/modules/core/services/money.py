from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def as_money(value: Decimal | int | str) -> Decimal:
    """Return an exact two-decimal monetary value."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)

