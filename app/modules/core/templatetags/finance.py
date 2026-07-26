from decimal import ROUND_DOWN, Decimal, InvalidOperation
from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

from modules.core.services.money import format_ars

register = template.Library()


@lru_cache(maxsize=32)
def _static_digest(asset_path: str) -> str:
    resolved_path = finders.find(asset_path)
    if not resolved_path:
        return ""

    try:
        return sha256(Path(resolved_path).read_bytes()).hexdigest()[:12]
    except OSError:
        return ""


@register.simple_tag
def versioned_static(asset_path: str) -> str:
    """Return a static URL that changes when the bundled file changes."""
    asset_url = static(asset_path)
    digest = _static_digest(asset_path)
    return f"{asset_url}?v={digest}" if digest else asset_url


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
