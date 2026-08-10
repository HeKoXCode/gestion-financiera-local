from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.core.models import (
    BusinessSettings,
    LateFee,
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


@transaction.atomic
def register_initial_payment(
    *,
    sale: Sale,
    payment_method: str,
    settings: BusinessSettings | None = None,
) -> Payment | None:
    """Record the cash received when a financed sale is delivered."""
    sale = Sale.objects.select_for_update().select_related("customer").get(pk=sale.pk)
    if sale.down_payment <= ZERO:
        return None

    settings = settings or BusinessSettings.get_solo()
    errors: dict[str, str] = {}
    if sale.delivery_date > timezone.localdate():
        errors["delivery_date"] = "No se puede registrar un pago inicial con fecha futura."
    if payment_method not in settings.payment_methods:
        errors["down_payment_method"] = "El medio de pago no está habilitado."
    if Payment.objects.filter(sale=sale, kind=Payment.Kind.INITIAL).exists():
        errors["down_payment"] = "Esta venta ya tiene un pago inicial registrado."
    if errors:
        raise ValidationError(errors)

    payment = Payment(
        customer=sale.customer,
        sale=sale,
        payment_date=sale.delivery_date,
        amount=sale.down_payment,
        payment_method=payment_method,
        kind=Payment.Kind.INITIAL,
        notes="Registrada junto con la venta.",
    )
    payment.full_clean()
    payment.save()
    return payment


@transaction.atomic
def register_delivery_installment_payment(
    *,
    sale: Sale,
    payment_method: str,
    settings: BusinessSettings | None = None,
) -> Payment:
    """Register installment one as paid on the product delivery date."""
    sale = Sale.objects.select_for_update().select_related("customer").get(pk=sale.pk)
    settings = settings or BusinessSettings.get_solo()
    first_installment = sale.installments.order_by("number", "pk").first()

    errors: dict[str, str] = {}
    if first_installment is None:
        errors["first_installment_delivery_status"] = (
            "La venta todavía no tiene cuotas generadas."
        )
    elif first_installment.due_date != sale.delivery_date:
        errors["first_installment_delivery_status"] = (
            "La cuota 1 solo puede registrarse al entregar cuando ambas fechas coinciden."
        )
    if sale.delivery_date > timezone.localdate():
        errors["delivery_date"] = (
            "No se puede registrar la cuota 1 como pagada en una fecha futura."
        )
    if payment_method not in settings.payment_methods:
        errors["first_installment_payment_method"] = "El medio de pago no está habilitado."
    if errors:
        raise ValidationError(errors)

    registration = register_payment(
        sale=sale,
        amount=first_installment.original_amount,
        payment_date=sale.delivery_date,
        payment_method=payment_method,
        notes="Cuota 1 pagada al recibir el producto.",
        operation_key=uuid.uuid4(),
        settings=settings,
    )
    return registration.payment


@transaction.atomic
def register_historical_installment_payments(
    *,
    sale: Sale,
    paid_installment_count: int,
    payment_method: str,
    late_installments: dict[int, int] | None = None,
    settings: BusinessSettings | None = None,
) -> list[Payment]:
    """Import the oldest paid installments with their actual payment timing.

    This is intended only for importing an existing payment plan. Each paid
    installment remains a separate payment so weekly, biweekly and monthly
    histories keep their real cadence. ``late_installments`` maps an installment
    number to its calendar days of delay; installments omitted from that map are
    recorded on their due date.
    """
    if paid_installment_count <= 0:
        return []

    sale = Sale.objects.select_for_update().select_related("customer").get(pk=sale.pk)
    settings = settings or BusinessSettings.get_solo()
    late_installments = late_installments or {}
    installments = list(sale.installments.order_by("due_date", "number", "pk"))
    today = timezone.localdate()

    errors: dict[str, str] = {}
    if paid_installment_count > len(installments):
        errors["historical_paid_installments"] = (
            f"La venta tiene solamente {len(installments)} cuotas."
        )
    due_installments = [
        installment for installment in installments if installment.due_date <= today
    ]
    if paid_installment_count > len(due_installments):
        errors["historical_paid_installments"] = (
            f"Hasta hoy vencieron {len(due_installments)} cuotas; "
            "no se pueden marcar cuotas futuras como pagadas desde la carga histórica."
        )
    for installment_number, late_days in late_installments.items():
        if installment_number < 1 or installment_number > paid_installment_count:
            errors["historical_late_installments"] = (
                f"La cuota {installment_number} no está entre las cuotas pagadas."
            )
            break
        if late_days < 1:
            errors["historical_late_installments"] = (
                "La cantidad de días de atraso debe ser mayor que cero."
            )
            break
        installment = installments[installment_number - 1]
        if installment.due_date + timedelta(days=late_days) > today:
            errors["historical_late_installments"] = (
                f"El pago de la cuota {installment_number} quedaría en una fecha futura."
            )
            break

    installments_to_pay = [
        installment
        for installment in installments[:paid_installment_count]
        if get_installment_balance(installment, as_of=today).total_due > ZERO
    ]
    if installments_to_pay and payment_method not in settings.payment_methods:
        errors["historical_payment_method"] = "El medio de pago no está habilitado."
    if errors:
        raise ValidationError(errors)

    payments = []
    for installment in installments_to_pay:
        late_days = late_installments.get(installment.number, 0)
        payment_date = installment.due_date + timedelta(days=late_days)

        if late_days and sale.daily_late_fee > ZERO:
            fee_dates = []
            fee_date = installment.due_date + timedelta(days=1)
            while fee_date <= payment_date:
                if settings.charge_sundays or fee_date.weekday() != 6:
                    fee_dates.append(fee_date)
                fee_date += timedelta(days=1)
            LateFee.objects.bulk_create(
                [
                    LateFee(
                        installment=installment,
                        fee_date=fee_date,
                        amount=sale.daily_late_fee,
                    )
                    for fee_date in fee_dates
                ],
                ignore_conflicts=True,
            )

        balance = get_installment_balance(installment, as_of=payment_date)
        if balance.total_due <= ZERO:
            continue
        timing_note = (
            f"pagada con {late_days} día{'s' if late_days != 1 else ''} de atraso"
            if late_days
            else "pagada en fecha"
        )
        payment = Payment(
            idempotency_key=uuid.uuid4(),
            customer=sale.customer,
            sale=sale,
            payment_date=payment_date,
            amount=balance.total_due,
            payment_method=payment_method,
            kind=Payment.Kind.INSTALLMENT,
            notes=(
                "Carga histórica: "
                f"cuota {installment.number}/{sale.installment_count} {timing_note}."
            ),
        )
        payment.full_clean()
        payment.save()
        allocations = []
        if balance.late_fees_due > ZERO:
            allocations.append(
                PaymentAllocation(
                    payment=payment,
                    installment=installment,
                    component=PaymentAllocation.Component.LATE_FEE,
                    amount=balance.late_fees_due,
                )
            )
        if balance.principal_due > ZERO:
            allocations.append(
                PaymentAllocation(
                    payment=payment,
                    installment=installment,
                    component=PaymentAllocation.Component.PRINCIPAL,
                    amount=balance.principal_due,
                )
            )
        PaymentAllocation.objects.bulk_create(allocations)
        payments.append(payment)

    _refresh_sale_status(sale)
    return payments


def _eligible_installments(sale: Sale, payment_date: date, *, allow_advance: bool):
    installments = sale.installments.order_by("due_date", "number", "pk")
    if not allow_advance:
        installments = installments.filter(due_date__lte=payment_date)
    return installments


def _refresh_sale_status(sale: Sale) -> None:
    balance = get_sale_balance(sale)
    expected_status = Sale.Status.COMPLETED if balance.total_due <= ZERO else Sale.Status.ACTIVE
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
        errors["payment_method"] = "El medio de pago no está habilitado."
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
    exigible_total = as_money(sum((balance.total_due for _, balance in installment_balances), ZERO))
    if exigible_total <= ZERO:
        raise ValidationError({"amount": "La venta no tiene cuotas pendientes en esa fecha."})
    if amount > exigible_total:
        raise ValidationError(
            {"amount": (f"El pago supera el monto pendiente de {format_ars(exigible_total)}.")}
        )

    payment = Payment(
        idempotency_key=operation_key,
        customer=sale.customer,
        sale=sale,
        payment_date=payment_date,
        amount=amount,
        payment_method=payment_method,
        kind=Payment.Kind.INSTALLMENT,
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
    if payment.kind == Payment.Kind.INITIAL:
        raise ValidationError(
            {
                "reason": (
                    "El pago inicial forma parte de la venta y no se anula por separado. "
                    "Si fue cargada por error, cancelá la venta y registrala nuevamente."
                )
            }
        )
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
