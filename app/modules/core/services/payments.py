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
    CollectionAssignment,
    Payment,
    PaymentAllocation,
    Sale,
)
from modules.core.services.balances import (
    get_due_sale_balance,
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
            "La operación todavía no tiene cuotas generadas."
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
    due_installments = [
        installment for installment in installments if installment.due_date <= today
    ]

    errors: dict[str, str] = {}
    if paid_installment_count > len(installments):
        errors["historical_paid_installments"] = (
            f"La operación tiene solamente {len(installments)} cuotas."
        )
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
    installments_to_pay.sort(
        key=lambda installment: (
            installment.due_date + timedelta(days=late_installments.get(installment.number, 0)),
            installment.number,
        )
    )
    if installments_to_pay and payment_method not in settings.payment_methods:
        errors["historical_payment_method"] = "El medio de pago no está habilitado."
    if errors:
        raise ValidationError(errors)

    payments = []
    for installment in installments_to_pay:
        late_days = late_installments.get(installment.number, 0)
        payment_date = installment.due_date + timedelta(days=late_days)

        generate_missing_late_fees(
            as_of=payment_date,
            settings=settings,
            sale=sale,
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


def _remove_obsolete_late_fees_after_payment(
    *,
    sale: Sale,
    payment_date: date,
    settings: BusinessSettings,
) -> None:
    """Recalculate the single daily stream after a backdated payment."""
    if payment_date >= timezone.localdate():
        return
    generate_missing_late_fees(
        as_of=timezone.localdate(),
        settings=settings,
        sale=sale,
        create_missing=False,
    )


def reallocate_existing_installment_payment(
    *,
    payment: Payment,
    sale: Sale,
    settings: BusinessSettings,
) -> None:
    """Replay one preserved payment against a corrected installment plan.

    The caller owns the surrounding transaction and must remove the payment's
    old allocations first. The Payment row itself is never recreated, so its
    date, amount, method, notes and audit identity remain unchanged.
    """
    if payment.kind != Payment.Kind.INSTALLMENT or payment.status != Payment.Status.REGISTERED:
        return

    if payment.payment_date < sale.delivery_date:
        raise ValidationError(
            {
                "exceptional_confirmation": (
                    f"El pago #{payment.pk} del {payment.payment_date:%d/%m/%Y} quedaría "
                    "antes de la nueva fecha de entrega. No se guardó ningún cambio."
                )
            }
        )

    generate_missing_late_fees(as_of=payment.payment_date, settings=settings, sale=sale)
    if (
        payment.is_advance
        and get_due_sale_balance(
            sale,
            as_of=payment.payment_date,
        ).total_due
        > ZERO
    ):
        raise ValidationError(
            {
                "exceptional_confirmation": (
                    f"El pago adelantado #{payment.pk} ya no sería un adelanto con "
                    "las nuevas fechas. No se guardó ningún cambio."
                )
            }
        )
    installment_balances = [
        (installment, get_installment_balance(installment, as_of=payment.payment_date))
        for installment in _eligible_installments(
            sale,
            payment.payment_date,
            allow_advance=payment.is_advance,
        )
        if not payment.is_advance or installment.due_date > payment.payment_date
    ]
    exigible_total = as_money(
        sum(
            (
                balance.principal_due if payment.is_advance else balance.total_due
                for _, balance in installment_balances
            ),
            ZERO,
        )
    )
    if exigible_total <= ZERO or payment.amount > exigible_total:
        raise ValidationError(
            {
                "exceptional_confirmation": (
                    f"El pago #{payment.pk} del {payment.payment_date:%d/%m/%Y} por "
                    f"{format_ars(payment.amount)} no entra en el plan corregido "
                    f"(disponible en esa fecha: {format_ars(exigible_total)}). "
                    "No se guardó ningún cambio."
                )
            }
        )

    remaining = as_money(payment.amount)
    allocations = []
    for installment, balance in installment_balances:
        if remaining <= ZERO:
            break
        late_fee_amount = ZERO if payment.is_advance else min(remaining, balance.late_fees_due)
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
        raise ValidationError(
            {
                "exceptional_confirmation": (
                    f"No se pudo redistribuir por completo el pago #{payment.pk}. "
                    "No se guardó ningún cambio."
                )
            }
        )
    PaymentAllocation.objects.bulk_create(allocations)


def refresh_sale_status(sale: Sale) -> None:
    """Public, narrow wrapper used after a safe historical replay."""
    _refresh_sale_status(sale)


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
    advance: bool = False,
    collection_assignment: CollectionAssignment | None = None,
) -> PaymentRegistration:
    existing = Payment.objects.filter(idempotency_key=operation_key).first()
    if existing:
        return PaymentRegistration(payment=existing, created=False)

    sale = Sale.objects.select_for_update().select_related("customer").get(pk=sale.pk)
    if collection_assignment is not None:
        collection_assignment = (
            CollectionAssignment.objects.select_for_update()
            .select_related("route", "route__collector")
            .get(pk=collection_assignment.pk)
        )
    settings = settings or BusinessSettings.get_solo()
    amount = as_money(amount)

    errors: dict[str, str] = {}
    if sale.status != Sale.Status.ACTIVE:
        errors["sale"] = "Solo se pueden registrar pagos en operaciones activas."
    if payment_date < sale.delivery_date:
        errors["payment_date"] = "La fecha de pago no puede ser anterior a la entrega."
    if payment_date > timezone.localdate():
        errors["payment_date"] = "No se puede registrar un pago con fecha futura."
    if advance and payment_date != timezone.localdate():
        errors["payment_date"] = "El pago adelantado debe registrarse con la fecha real de hoy."
    if advance and not settings.allow_advance_payments:
        errors["sale"] = "Los pagos adelantados están deshabilitados en Configuración."
    if amount <= ZERO:
        errors["amount"] = "El monto abonado debe ser mayor que cero."
    if payment_method not in settings.payment_methods:
        errors["payment_method"] = "El medio de pago no está habilitado."
    if collection_assignment is not None:
        if advance:
            errors["sale"] = "Los pagos adelantados no pertenecen a un recorrido diario."
        elif collection_assignment.customer_id != sale.customer_id:
            errors["sale"] = "El recorrido elegido no pertenece a este cliente."
        elif collection_assignment.assigned_date != payment_date:
            errors["payment_date"] = "El recorrido no pertenece a la fecha del pago."
    if (
        payment_date < timezone.localdate()
        and Payment.objects.filter(
            sale=sale,
            status=Payment.Status.REGISTERED,
            kind=Payment.Kind.INSTALLMENT,
            payment_date__gt=payment_date,
        ).exists()
    ):
        errors["payment_date"] = (
            "Ya existe un pago de cuotas posterior a esa fecha. Para proteger "
            "la contabilidad, anulá o revisá primero ese movimiento posterior."
        )
    if errors:
        raise ValidationError(errors)

    generate_missing_late_fees(as_of=payment_date, settings=settings, sale=sale)
    if advance and get_due_sale_balance(sale, as_of=payment_date).total_due > ZERO:
        raise ValidationError(
            {
                "amount": (
                    "Esta operación tiene una cuota vencida o que vence hoy. "
                    "Registrá primero el pago normal y después el adelanto."
                )
            }
        )
    installment_balances = [
        (installment, get_installment_balance(installment, as_of=payment_date))
        for installment in _eligible_installments(
            sale,
            payment_date,
            allow_advance=advance,
        )
        if not advance or installment.due_date > payment_date
    ]
    exigible_total = as_money(
        sum(
            (
                balance.principal_due if advance else balance.total_due
                for _, balance in installment_balances
            ),
            ZERO,
        )
    )
    if exigible_total <= ZERO:
        message = (
            "La operación no tiene cuotas futuras pendientes."
            if advance
            else "La operación no tiene cuotas pendientes en esa fecha."
        )
        raise ValidationError({"amount": message})
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
        is_advance=advance,
        notes=notes.strip(),
        collector=(
            collection_assignment.route.collector if collection_assignment is not None else None
        ),
        collection_assignment=collection_assignment,
    )
    payment.full_clean()
    payment.save()

    remaining = amount
    allocations = []
    for installment, balance in installment_balances:
        if remaining <= ZERO:
            break

        late_fee_amount = ZERO if advance else min(remaining, balance.late_fees_due)
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
    if not advance:
        _remove_obsolete_late_fees_after_payment(
            sale=sale,
            payment_date=payment_date,
            settings=settings,
        )
    _refresh_sale_status(sale)
    return PaymentRegistration(payment=payment, created=True)


@transaction.atomic
def void_payment(*, payment: Payment, reason: str) -> bool:
    payment = (
        Payment.objects.select_for_update().select_related("sale", "customer").get(pk=payment.pk)
    )
    if payment.status == Payment.Status.VOIDED:
        return False
    if payment.sale.status == Sale.Status.CANCELLED:
        raise ValidationError(
            {"reason": "Los pagos de una venta cancelada pertenecen al Archivo seguro."}
        )
    if payment.customer.deleted_at is not None:
        raise ValidationError(
            {"reason": "Los movimientos de un cliente borrado pertenecen al Archivo seguro."}
        )
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
