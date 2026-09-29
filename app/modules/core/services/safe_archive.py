from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.core.models import (
    BusinessSettings,
    Customer,
    CustomerCollectorLink,
    CustomerRevision,
    Payment,
    PaymentAllocation,
    Sale,
    SaleRevision,
)
from modules.core.services.installments import create_installments
from modules.core.services.late_fees import generate_missing_late_fees
from modules.core.services.payments import (
    reallocate_existing_installment_payment,
    refresh_sale_status,
    register_initial_payment,
)

MAX_SALE_EDITS = 2
EDITABLE_SALE_FIELDS = (
    "customer",
    "product",
    "product_description",
    "delivery_date",
    "cash_price",
    "loan_disbursement_method",
    "loan_interest_rate",
    "down_payment",
    "financed_amount",
    "frequency",
    "installment_count",
    "first_due_date",
)
EDITABLE_CUSTOMER_FIELDS = (
    "first_name",
    "last_name",
    "dni",
    "phone",
    "address",
    "neighborhood",
    "address_reference",
    "notes",
)


def _serialized(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def build_customer_snapshot(customer: Customer) -> dict:
    return {
        "id": customer.pk,
        "first_name": customer.first_name,
        "last_name": customer.last_name,
        "full_name": customer.full_name,
        "dni": customer.dni or "",
        "phone": customer.phone,
        "address": customer.address,
        "neighborhood": customer.neighborhood,
        "address_reference": customer.address_reference,
        "notes": customer.notes,
        "is_active": customer.is_active,
        "deleted_at": _serialized(customer.deleted_at),
        "deletion_reason": customer.deletion_reason,
        "created_at": _serialized(customer.created_at),
        "created_at_display": timezone.localtime(customer.created_at).strftime("%d/%m/%Y %H:%M"),
        "updated_at": _serialized(customer.updated_at),
    }


def build_sale_snapshot(sale: Sale) -> dict:
    """Capture the complete pre-edit state using JSON-safe values."""
    customer = sale.customer
    product = sale.product
    installments = []
    for installment in sale.installments.all():
        installments.append(
            {
                "id": installment.pk,
                "number": installment.number,
                "due_date": _serialized(installment.due_date),
                "due_date_display": installment.due_date.strftime("%d/%m/%Y"),
                "original_amount": _serialized(installment.original_amount),
                "late_fees": [
                    {
                        "id": fee.pk,
                        "fee_date": _serialized(fee.fee_date),
                        "fee_date_display": fee.fee_date.strftime("%d/%m/%Y"),
                        "amount": _serialized(fee.amount),
                        "waived_amount": _serialized(fee.waived_amount),
                        "effective_amount": _serialized(fee.effective_amount),
                        "waived_reason": fee.waived_reason,
                        "waived_at": _serialized(fee.waived_at),
                    }
                    for fee in installment.late_fees.all()
                ],
            }
        )

    payments = []
    for payment in sale.payments.all():
        payments.append(
            {
                "id": payment.pk,
                "payment_date": _serialized(payment.payment_date),
                "payment_date_display": payment.payment_date.strftime("%d/%m/%Y"),
                "amount": _serialized(payment.amount),
                "payment_method": payment.payment_method,
                "kind": payment.kind,
                "kind_label": payment.movement_label,
                "is_advance": payment.is_advance,
                "status": payment.status,
                "status_label": payment.get_status_display(),
                "notes": payment.notes,
                "voided_at": _serialized(payment.voided_at),
                "void_reason": payment.void_reason,
                "allocations": [
                    {
                        "installment_id": allocation.installment_id,
                        "installment_number": allocation.installment.number,
                        "installment_due_date": _serialized(allocation.installment.due_date),
                        "component": allocation.component,
                        "component_label": allocation.get_component_display(),
                        "amount": _serialized(allocation.amount),
                    }
                    for allocation in payment.allocations.all()
                ],
            }
        )

    return {
        "sale": {
            "id": sale.pk,
            "customer_id": customer.pk,
            "customer_name": customer.full_name,
            "customer_dni": customer.dni or "",
            "customer_address": customer.address,
            "product_id": product.pk if product else None,
            "product_name": product.name if product else "",
            "product_description": sale.product_description,
            "operation_type": sale.operation_type,
            "operation_type_label": sale.get_operation_type_display(),
            "loan_disbursement_method": sale.loan_disbursement_method,
            "loan_interest_rate": _serialized(sale.loan_interest_rate),
            "delivery_date": _serialized(sale.delivery_date),
            "delivery_date_display": sale.delivery_date.strftime("%d/%m/%Y"),
            "cash_price": _serialized(sale.cash_price),
            "down_payment": _serialized(sale.down_payment),
            "financed_amount": _serialized(sale.financed_amount),
            "frequency": sale.frequency,
            "frequency_label": sale.get_frequency_display(),
            "installment_count": sale.installment_count,
            "daily_late_fee": _serialized(sale.daily_late_fee),
            "first_due_date": _serialized(sale.first_due_date),
            "first_due_date_display": sale.first_due_date.strftime("%d/%m/%Y"),
            "status": sale.status,
            "status_label": sale.get_status_display(),
            "cancelled_on": _serialized(sale.cancelled_on),
            "cancellation_reason": sale.cancellation_reason,
            "edit_count": sale.edit_count,
            "created_at": _serialized(sale.created_at),
            "updated_at": _serialized(sale.updated_at),
        },
        "installments": installments,
        "payments": payments,
        "collection_attempts": [
            {
                "id": attempt.pk,
                "attempt_date": _serialized(attempt.attempt_date),
                "attempt_date_display": attempt.attempt_date.strftime("%d/%m/%Y"),
                "result": attempt.result,
                "result_label": attempt.get_result_display(),
                "notes": attempt.notes,
            }
            for attempt in sale.collection_attempts.all()
        ],
        "late_fee_pause_periods": [
            {
                "id": period.pk,
                "paused_from": _serialized(period.paused_from),
                "resumed_at": _serialized(period.resumed_at),
                "reason": period.reason,
                "resume_reason": period.resume_reason,
                "created_at": _serialized(period.created_at),
                "updated_at": _serialized(period.updated_at),
            }
            for period in sale.late_fee_pause_periods.all()
        ],
    }


def customer_deletion_block_reason(customer: Customer) -> str:
    if customer.deleted_at is not None:
        return "Este cliente ya está guardado en el Archivo seguro."
    active_count = customer.sales.filter(status=Sale.Status.ACTIVE).count()
    if active_count:
        if active_count == 1:
            return (
                "El cliente tiene una operación activa. Cancelala o terminá de cobrarla "
                "antes de borrar al cliente."
            )
        return (
            f"El cliente tiene {active_count} operaciones activas. "
            "Cancelalas o terminá de cobrarlas "
            "antes de borrar al cliente."
        )
    return ""


@transaction.atomic
def move_customer_to_safe_archive(*, customer: Customer, reason: str) -> Customer:
    customer = Customer.objects.select_for_update().get(pk=customer.pk)
    blocked = customer_deletion_block_reason(customer)
    if blocked:
        raise ValidationError({"reason": blocked})
    if not reason.strip():
        raise ValidationError({"reason": "Indicá por qué se borra este cliente."})

    customer.is_active = False
    customer.deleted_at = timezone.now()
    customer.deletion_reason = reason.strip()
    customer.save(
        update_fields=[
            "is_active",
            "deleted_at",
            "deletion_reason",
            "updated_at",
        ]
    )
    closed_on = timezone.localdate()
    active_links = list(
        CustomerCollectorLink.objects.select_for_update().filter(
            customer=customer,
            ended_at__isnull=True,
        )
    )
    for link in active_links:
        link.ended_at = max(closed_on, link.started_at)
        link.reason = "Finalizado al enviar al cliente al Archivo seguro"
        link.save(update_fields=["ended_at", "reason", "updated_at"])
    return customer


@transaction.atomic
def edit_customer_with_revision(
    *,
    customer: Customer,
    changes: dict,
    reason: str,
    operation_key,
) -> tuple[Customer, CustomerRevision, bool]:
    existing = CustomerRevision.objects.filter(operation_key=operation_key).first()
    if existing:
        return existing.customer, existing, False

    customer = Customer.objects.select_for_update().get(pk=customer.pk)
    if customer.deleted_at is not None:
        raise ValidationError("Este cliente está en el Archivo seguro y no puede editarse.")
    if not reason.strip():
        raise ValidationError({"edit_reason": "Indicá qué dato estás corrigiendo."})

    normalized_changes = {}
    for field in EDITABLE_CUSTOMER_FIELDS:
        if field not in changes:
            continue
        value = changes[field]
        if isinstance(value, str):
            value = value.strip()
        if field == "dni":
            value = value or None
        normalized_changes[field] = value

    if not any(getattr(customer, field) != value for field, value in normalized_changes.items()):
        raise ValidationError("No cambiaste ningún dato del cliente.")

    revision_number = customer.revisions.count() + 1
    revision = CustomerRevision.objects.create(
        customer=customer,
        operation_key=operation_key,
        revision_number=revision_number,
        reason=reason.strip(),
        snapshot=build_customer_snapshot(customer),
    )
    for field, value in normalized_changes.items():
        setattr(customer, field, value)
    customer.full_clean()
    customer.save()
    return customer, revision, True


def sale_has_protected_activity(sale: Sale) -> bool:
    return (
        sale.payments.exclude(kind=Payment.Kind.INITIAL).exists()
        or sale.collection_attempts.exists()
    )


def sale_edit_block_reason(
    sale: Sale,
    settings: BusinessSettings | None = None,
) -> str:
    if sale.status != Sale.Status.ACTIVE:
        return "Solo se pueden editar operaciones activas."
    if sale.edit_count >= MAX_SALE_EDITS:
        return "Esta operación ya alcanzó el máximo de 2 ediciones."
    settings = settings or BusinessSettings.get_solo()
    if (
        sale.payments.exclude(kind=Payment.Kind.INITIAL).exists()
        and not settings.allow_exceptional_sale_edits
    ):
        return (
            "La operación ya tiene pagos de cuotas registrados. Para proteger el dinero "
            "cobrado, solo puede corregirse con la autorización excepcional de Configuración."
        )
    if sale.collection_attempts.exists() and not settings.allow_exceptional_sale_edits:
        return (
            "La operación ya tiene visitas o resultados de cobranza registrados. "
            "Solo puede corregirse con la autorización excepcional de Configuración."
        )
    return ""


@transaction.atomic
def edit_sale_with_revision(
    *,
    sale: Sale,
    changes: dict,
    reason: str,
    down_payment_method: str,
    operation_key,
    settings: BusinessSettings | None = None,
) -> tuple[Sale, SaleRevision, bool]:
    existing = SaleRevision.objects.filter(operation_key=operation_key).first()
    if existing:
        return existing.sale, existing, False

    sale = (
        Sale.objects.select_for_update()
        .select_related("customer", "product")
        .prefetch_related(
            "installments__late_fees",
            "payments__allocations",
            "collection_attempts",
            "late_fee_pause_periods",
        )
        .get(pk=sale.pk)
    )
    settings = BusinessSettings.objects.select_for_update().get(
        pk=(settings or BusinessSettings.get_solo()).pk
    )
    exceptional_mode = sale_has_protected_activity(sale)
    blocked = sale_edit_block_reason(sale, settings)
    if blocked:
        raise ValidationError(blocked)
    if not reason.strip():
        raise ValidationError({"edit_reason": "Indicá qué dato estás corrigiendo."})

    has_field_changes = any(
        field in changes and getattr(sale, field) != changes[field]
        for field in EDITABLE_SALE_FIELDS
    )
    current_initial = sale.payments.filter(kind=Payment.Kind.INITIAL).first()
    current_initial_method = current_initial.payment_method if current_initial else ""
    method_changed = (
        changes.get("down_payment", sale.down_payment) > 0
        and down_payment_method != current_initial_method
    )
    if not has_field_changes and not method_changed:
        raise ValidationError("No cambiaste ningún dato de la operación.")

    revision_number = sale.edit_count + 1
    revision = SaleRevision.objects.create(
        sale=sale,
        operation_key=operation_key,
        revision_number=revision_number,
        reason=reason.strip(),
        snapshot=build_sale_snapshot(sale),
    )

    installment_payments = list(
        Payment.objects.filter(sale=sale, kind=Payment.Kind.INSTALLMENT).order_by(
            "payment_date", "created_at", "pk"
        )
    )
    if exceptional_mode:
        proposed_delivery = changes.get("delivery_date", sale.delivery_date)
        earliest_attempt = sale.collection_attempts.order_by("attempt_date", "pk").first()
        if earliest_attempt and earliest_attempt.attempt_date < proposed_delivery:
            raise ValidationError(
                {
                    "exceptional_confirmation": (
                        f"La visita del {earliest_attempt.attempt_date:%d/%m/%Y} quedaría antes "
                        "de la nueva entrega. No se guardó ningún cambio."
                    )
                }
            )
        PaymentAllocation.objects.filter(payment__sale=sale).delete()

    Payment.objects.filter(sale=sale, kind=Payment.Kind.INITIAL).delete()
    sale.installments.all().delete()

    for field in EDITABLE_SALE_FIELDS:
        if field in changes:
            setattr(sale, field, changes[field])
    if sale.customer.deleted_at is not None:
        raise ValidationError({"customer": "El cliente está en el Archivo seguro."})

    sale.edit_count = revision_number
    sale.status = Sale.Status.ACTIVE
    sale.cancelled_on = None
    sale.cancellation_reason = ""
    sale.full_clean()
    sale.save()

    if exceptional_mode:
        Payment.objects.filter(sale=sale).update(customer=sale.customer)
        sale.collection_attempts.update(customer=sale.customer)

    create_installments(sale)
    register_initial_payment(
        sale=sale,
        payment_method=down_payment_method,
        settings=settings,
    )
    if exceptional_mode:
        for payment in installment_payments:
            payment.customer = sale.customer
            reallocate_existing_installment_payment(
                payment=payment,
                sale=sale,
                settings=settings,
            )
    generate_missing_late_fees(
        as_of=timezone.localdate(),
        settings=settings,
        sale=sale,
    )
    if exceptional_mode:
        refresh_sale_status(sale)
        settings.allow_exceptional_sale_edits = False
        settings.save(update_fields=["allow_exceptional_sale_edits", "updated_at"])
    return sale, revision, True
