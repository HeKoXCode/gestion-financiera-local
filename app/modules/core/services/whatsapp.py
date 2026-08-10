from decimal import Decimal
from urllib.parse import quote

from modules.core.models import BusinessSettings, Customer
from modules.core.services.money import format_ars


def normalize_argentina_whatsapp_number(phone: str) -> str:
    digits = "".join(character for character in phone if character.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = digits[1:]

    if digits.startswith("549"):
        return digits
    if digits.startswith("54"):
        local_number = digits[2:]
        if local_number.startswith("15"):
            local_number = local_number[2:]
        return f"549{local_number}"
    if digits.startswith("15"):
        digits = digits[2:]
    return f"549{digits}" if digits else ""


def build_payment_reminder_url(
    *,
    customer: Customer,
    amount: Decimal,
    due_date,
    settings: BusinessSettings | None = None,
) -> str:
    number = normalize_argentina_whatsapp_number(customer.phone)
    if not number:
        return ""

    settings = settings or BusinessSettings.get_solo()
    values = {
        "nombre": customer.first_name,
        "monto": format_ars(amount),
        "vencimiento": due_date.strftime("%d/%m/%Y"),
    }
    try:
        message = settings.whatsapp_message.format(**values)
    except (AttributeError, IndexError, KeyError, ValueError):
        # A malformed value from an older database must never break cobranza.
        message = (
            "Hola {nombre}. Te recordamos que tenés una cuota pendiente "
            "de {monto} con vencimiento {vencimiento}."
        ).format(**values)
    return f"https://wa.me/{number}?text={quote(message)}"


def build_customer_statement_whatsapp_url(
    *,
    customer: Customer,
    as_of,
    settings: BusinessSettings | None = None,
) -> str:
    """Build a privacy-conscious message for manually attaching a customer statement."""
    number = normalize_argentina_whatsapp_number(customer.phone)
    if not number:
        return ""

    settings = settings or BusinessSettings.get_solo()
    message = (
        f"Hola {customer.first_name}, te comparto tu resumen de cuenta de "
        f"{settings.business_name}, actualizado al {as_of:%d/%m/%Y}. "
        "Adjunto el archivo PDF."
    )
    return f"https://wa.me/{number}?text={quote(message)}"
