from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.core.models import (
    BusinessSettings,
    Payment,
    PaymentAllocation,
    Sale,
)
from modules.core.services.balances import (
    get_installment_balance,
    get_sale_balance,
)
from modules.core.services.late_fees import generate_missing_late_fees
from modules.core.services.money import ZERO, as_money, format_ars


@dataclass(frozen=True)
class PaymentRegistration:
    payment: Payment
    created: bool


def _eligible_installments(sale: Sale, payment_date: date, *, allow_advance: bool):
    installments = sale.installments.order_by("due_date", "number", "pk")
    if not allow_advance:
        installments = installments.filter(due_date__lte=payment_date)
    return installments


def _refresh_sale_status(sale: Sale) -> None:
    balance = get_sale_balance(sale)
    expected_status = (
        Sale.Status.COMPLETED if balance.total_due <= ZERO else Sale.Status.ACTIVE
    )
    if sale.status != expected_status:
        sale.status = expected_status
        sale.cancelled_on = None
        sale.cancellation_reason = ""
        sale.save(
            update_fields=[
                "status",
                "cancelled_on",
                "cancellation_reason",
                "updated_at",
            ]
        )


@transaction.atomic
def register_payment(
    *,
    sale: Sale,
    amount: Decimal,
    payment_date: date,
    payment_method: str,
    notes: str = "",
    operation_key: uuid.UUID,
    settings: BusinessSettings | None = None,
) -> PaymentRegistration:
    existing = Payment.objects.filter(idempotency_key=operation_key).first()
    if existing:
        return PaymentRegistration(payment=existing, created=False)

    sale = Sale.objects.select_for_update().select_related("customer").get(pk=sale.pk)
    settings = settings or BusinessSettings.get_solo()
    amount = as_money(amount)

    errors: dict[str, str] = {}
    if sale.status != Sale.Status.ACTIVE:
        errors["sale"] = "Solo se pueden registrar pagos en ventas activas."
    if payment_date < sale.delivery_date:
        errors["payment_date"] = "La fecha de pago no puede ser anterior a la entrega."
    if payment_date > timezone.localdate():
        errors["payment_date"] = "No se puede registrar un pago con fecha futura."
    if amount <= ZERO:
        errors["amount"] = "El monto abonado debe ser mayor que cero."
    if payment_method not in settings.payment_methods:
        errors["payment_method"] = "El método de pago no está habilitado."
    if errors:
        raise ValidationError(errors)

    generate_missing_late_fees(as_of=payment_date, settings=settings, sale=sale)
    installment_balances = [
        (installment, get_installment_balance(installment, as_of=payment_date))
        for installment in _eligible_installments(
            sale,
            payment_date,
            allow_advance=settings.allow_advance_payments,
        )
    ]
    exigible_total = as_money(
        sum((balance.total_due for _, balance in installment_balances), ZERO)
    )
    if exigible_total <= ZERO:
        raise ValidationError({"amount": "La venta no tiene deuda exigible en esa fecha."})
    if amount > exigible_total:
        raise ValidationError(
            {
                "amount": (
                    f"El pago supera la deuda exigible de {format_ars(exigible_total)}."
                )
            }
        )

    payment = Payment(
        idempotency_key=operation_key,
        customer=sale.customer,
        sale=sale,
        payment_date=payment_date,
        amount=amount,
        payment_method=payment_method,
        notes=notes.strip(),
    )
    payment.full_clean()
    payment.save()

    remaining = amount
    allocations = []
    for installment, balance in installment_balances:
        if remaining <= ZERO:
            break

        late_fee_amount = min(remaining, balance.late_fees_due)
        if late_fee_amount > ZERO:
            allocations.append(
                PaymentAllocation(
                    payment=payment,
                    installment=installment,
                    component=PaymentAllocation.Component.LATE_FEE,
                    amount=late_fee_amount,
                )
            )
            remaining = as_money(remaining - late_fee_amount)

        principal_amount = min(remaining, balance.principal_due)
        if principal_amount > ZERO:
            allocations.append(
                PaymentAllocation(
                    payment=payment,
                    installment=installment,
                    component=PaymentAllocation.Component.PRINCIPAL,
                    amount=principal_amount,
                )
            )
            remaining = as_money(remaining - principal_amount)

    if remaining != ZERO:
        raise ValidationError("No se pudo distribuir la totalidad del pago.")

    PaymentAllocation.objects.bulk_create(allocations)
    _refresh_sale_status(sale)
    return PaymentRegistration(payment=payment, created=True)


@transaction.atomic
def void_payment(*, payment: Payment, reason: str) -> bool:
    payment = Payment.objects.select_for_update().select_related("sale").get(pk=payment.pk)
    if payment.status == Payment.Status.VOIDED:
        return False
    if not reason.strip():
        raise ValidationError({"reason": "Debés indicar el motivo de la anulación."})

    payment.status = Payment.Status.VOIDED
    payment.voided_at = timezone.now()
    payment.void_reason = reason.strip()
    payment.full_clean()
    payment.save(
        update_fields=[
            "status",
            "voided_at",
            "void_reason",
            "updated_at",
        ]
    )

    sale = payment.sale
    if sale.status == Sale.Status.COMPLETED:
        sale.status = Sale.Status.ACTIVE
        sale.save(update_fields=["status", "updated_at"])
    if sale.status == Sale.Status.ACTIVE:
        generate_missing_late_fees(
            as_of=timezone.localdate(),
            settings=BusinessSettings.get_solo(),
            sale=sale,
        )
    return True
