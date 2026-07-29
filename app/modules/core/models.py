from __future__ import annotations

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

ZERO = Decimal("0.00")
MIN_MONEY = Decimal("0.01")


def default_collection_days() -> list[int]:
    """Monday=0 through Saturday=5, matching Python's weekday convention."""
    return [0, 1, 2, 3, 4, 5]


def default_payment_methods() -> list[str]:
    return ["Efectivo", "Transferencia", "Otro"]


def default_frequencies() -> list[str]:
    return [
        Sale.Frequency.WEEKLY,
        Sale.Frequency.BIWEEKLY,
        Sale.Frequency.MONTHLY,
    ]


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="creado")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="modificado")

    class Meta:
        abstract = True


class BusinessSettings(TimestampedModel):
    SINGLETON_PK = 1

    business_name = models.CharField(
        max_length=120,
        default="Gestión Financiera",
        verbose_name="nombre del negocio",
    )
    logo = models.FileField(upload_to="logos/", blank=True, verbose_name="logo")
    daily_late_fee = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("5000.00"),
        validators=[MinValueValidator(ZERO)],
        verbose_name="recargo diario",
    )
    collection_days = models.JSONField(
        default=default_collection_days,
        verbose_name="días de cobranza",
    )
    payment_methods = models.JSONField(
        default=default_payment_methods,
        verbose_name="métodos de pago",
    )
    available_frequencies = models.JSONField(
        default=default_frequencies,
        verbose_name="frecuencias disponibles",
    )
    max_installments = models.PositiveSmallIntegerField(
        default=60,
        validators=[MinValueValidator(1)],
        verbose_name="máximo de cuotas",
    )
    charge_sundays = models.BooleanField(
        default=True,
        verbose_name="generar recargo los domingos",
    )
    late_fee_after_partial_payment = models.BooleanField(
        default=True,
        verbose_name="continuar recargo después de un pago parcial",
    )
    allow_advance_payments = models.BooleanField(
        default=False,
        verbose_name="permitir pagos adelantados",
    )
    whatsapp_message = models.TextField(
        default=(
            "Hola {nombre}. Te recordamos que tenés una cuota pendiente "
            "de {monto} con vencimiento {vencimiento}."
        ),
        verbose_name="mensaje de WhatsApp",
    )

    class Meta:
        verbose_name = "configuración"
        verbose_name_plural = "configuración"
        constraints = [
            models.CheckConstraint(
                condition=Q(daily_late_fee__gte=ZERO),
                name="settings_late_fee_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(max_installments__gte=1),
                name="settings_max_installments_positive",
            ),
        ]

    def __str__(self) -> str:
        return self.business_name

    @classmethod
    def get_solo(cls) -> BusinessSettings:
        settings, _ = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        return settings

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}

        if not isinstance(self.collection_days, list) or any(
            not isinstance(day, int) or isinstance(day, bool) or day < 0 or day > 6
            for day in self.collection_days
        ):
            errors["collection_days"] = "Los días deben ser números enteros entre 0 y 6."
        elif len(set(self.collection_days)) != len(self.collection_days):
            errors["collection_days"] = "Los días de cobranza no pueden repetirse."

        if not self.payment_methods or any(
            not isinstance(method, str) or not method.strip() for method in self.payment_methods
        ):
            errors["payment_methods"] = "Debe existir al menos un método de pago válido."

        valid_frequencies = {choice for choice, _ in Sale.Frequency.choices}
        if (
            not self.available_frequencies
            or not set(self.available_frequencies).issubset(valid_frequencies)
        ):
            errors["available_frequencies"] = "Las frecuencias configuradas no son válidas."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs) -> None:
        self.pk = self.SINGLETON_PK
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("La configuración general no puede eliminarse.")


class Customer(TimestampedModel):
    first_name = models.CharField(max_length=80, verbose_name="nombre")
    last_name = models.CharField(max_length=80, verbose_name="apellido")
    dni = models.CharField(max_length=20, blank=True, null=True, verbose_name="DNI")
    phone = models.CharField(max_length=40, blank=True, verbose_name="teléfono")
    address = models.CharField(max_length=180, verbose_name="dirección")
    neighborhood = models.CharField(max_length=100, blank=True, verbose_name="barrio")
    address_reference = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="referencia del domicilio",
    )
    notes = models.TextField(blank=True, verbose_name="observaciones")
    is_active = models.BooleanField(default=True, verbose_name="activo")

    class Meta:
        ordering = ["last_name", "first_name", "pk"]
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        constraints = [
            models.UniqueConstraint(
                fields=["dni"],
                condition=Q(dni__isnull=False),
                name="customer_unique_non_null_dni",
            )
        ]
        indexes = [
            models.Index(fields=["last_name", "first_name"], name="customer_name_idx"),
            models.Index(fields=["is_active"], name="customer_active_idx"),
        ]

    def __str__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def save(self, *args, **kwargs) -> None:
        self.first_name = self.first_name.strip()
        self.last_name = self.last_name.strip()
        self.dni = (self.dni or "").strip() or None
        super().save(*args, **kwargs)


class Product(TimestampedModel):
    name = models.CharField(max_length=120, verbose_name="nombre")
    description = models.TextField(blank=True, verbose_name="descripción")
    is_active = models.BooleanField(default=True, verbose_name="activo")

    class Meta:
        ordering = ["name", "pk"]
        verbose_name = "producto"
        verbose_name_plural = "productos"
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                name="product_unique_name",
            )
        ]

    def __str__(self) -> str:
        return self.name


class Sale(TimestampedModel):
    class Frequency(models.TextChoices):
        WEEKLY = "weekly", "Semanal"
        BIWEEKLY = "biweekly", "Quincenal"
        MONTHLY = "monthly", "Mensual"

    class Status(models.TextChoices):
        ACTIVE = "active", "Activa"
        COMPLETED = "completed", "Finalizada"
        CANCELLED = "cancelled", "Cancelada"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="sales",
        verbose_name="cliente",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="sales",
        verbose_name="producto",
    )
    product_description = models.CharField(
        max_length=250,
        verbose_name="descripción congelada",
    )
    delivery_date = models.DateField(verbose_name="fecha de entrega")
    cash_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(MIN_MONEY)],
        verbose_name="precio contado",
    )
    financed_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(MIN_MONEY)],
        verbose_name="monto financiado",
    )
    frequency = models.CharField(
        max_length=16,
        choices=Frequency.choices,
        verbose_name="frecuencia",
    )
    installment_count = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="cantidad de cuotas",
    )
    daily_late_fee = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(ZERO)],
        verbose_name="recargo diario congelado",
    )
    first_due_date = models.DateField(verbose_name="primer vencimiento")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
        verbose_name="estado",
    )
    cancelled_on = models.DateField(
        blank=True,
        null=True,
        verbose_name="fecha de cancelación",
    )
    cancellation_reason = models.TextField(
        blank=True,
        verbose_name="motivo de cancelación",
    )

    class Meta:
        ordering = ["-delivery_date", "-pk"]
        verbose_name = "venta"
        verbose_name_plural = "ventas"
        constraints = [
            models.CheckConstraint(
                condition=Q(cash_price__gt=ZERO),
                name="sale_cash_price_positive",
            ),
            models.CheckConstraint(
                condition=Q(financed_amount__gt=ZERO),
                name="sale_financed_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(installment_count__gte=1),
                name="sale_installment_count_positive",
            ),
            models.CheckConstraint(
                condition=Q(daily_late_fee__gte=ZERO),
                name="sale_late_fee_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["status"], name="sale_status_idx"),
            models.Index(fields=["customer", "status"], name="sale_customer_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.customer} — {self.product_description}"

    @property
    def is_collectible(self) -> bool:
        return self.status == self.Status.ACTIVE

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}

        if self.first_due_date and self.delivery_date and self.first_due_date < self.delivery_date:
            errors["first_due_date"] = "El primer vencimiento no puede ser anterior a la entrega."

        is_cancelled = self.status == self.Status.CANCELLED
        if is_cancelled and not self.cancelled_on:
            errors["cancelled_on"] = "Una venta cancelada debe indicar la fecha."
        if is_cancelled and not self.cancellation_reason.strip():
            errors["cancellation_reason"] = "Una venta cancelada debe indicar el motivo."
        if not is_cancelled and (self.cancelled_on or self.cancellation_reason.strip()):
            errors["status"] = "Solo una venta cancelada puede tener datos de cancelación."

        if errors:
            raise ValidationError(errors)


class Installment(TimestampedModel):
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="installments",
        verbose_name="venta",
    )
    number = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="número",
    )
    due_date = models.DateField(verbose_name="vencimiento")
    original_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(MIN_MONEY)],
        verbose_name="importe original",
    )

    class Meta:
        ordering = ["due_date", "number", "pk"]
        verbose_name = "cuota"
        verbose_name_plural = "cuotas"
        constraints = [
            models.UniqueConstraint(
                fields=["sale", "number"],
                name="installment_unique_sale_number",
            ),
            models.CheckConstraint(
                condition=Q(number__gte=1),
                name="installment_number_positive",
            ),
            models.CheckConstraint(
                condition=Q(original_amount__gt=ZERO),
                name="installment_amount_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["due_date"], name="installment_due_idx"),
            models.Index(fields=["sale", "due_date"], name="installment_sale_due_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.sale} — cuota {self.number}"


class LateFee(TimestampedModel):
    installment = models.ForeignKey(
        Installment,
        on_delete=models.CASCADE,
        related_name="late_fees",
        verbose_name="cuota",
    )
    fee_date = models.DateField(verbose_name="fecha")
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(MIN_MONEY)],
        verbose_name="importe",
    )

    class Meta:
        ordering = ["fee_date", "pk"]
        verbose_name = "recargo"
        verbose_name_plural = "recargos"
        constraints = [
            models.UniqueConstraint(
                fields=["installment", "fee_date"],
                name="late_fee_unique_installment_date",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=ZERO),
                name="late_fee_amount_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["fee_date"], name="late_fee_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.installment} — {self.fee_date:%d/%m/%Y}"


class Payment(TimestampedModel):
    class Status(models.TextChoices):
        REGISTERED = "registered", "Registrado"
        VOIDED = "voided", "Anulado"

    idempotency_key = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name="clave de operación",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name="cliente",
    )
    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="payments",
        verbose_name="venta",
    )
    payment_date = models.DateField(default=timezone.localdate, verbose_name="fecha")
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(MIN_MONEY)],
        verbose_name="importe",
    )
    payment_method = models.CharField(max_length=40, verbose_name="método de pago")
    notes = models.TextField(blank=True, verbose_name="observaciones")
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.REGISTERED,
        verbose_name="estado",
    )
    voided_at = models.DateTimeField(blank=True, null=True, verbose_name="anulado el")
    void_reason = models.TextField(blank=True, verbose_name="motivo de anulación")

    class Meta:
        ordering = ["-payment_date", "-created_at", "-pk"]
        verbose_name = "pago"
        verbose_name_plural = "pagos"
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=ZERO),
                name="payment_amount_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["payment_date", "status"], name="payment_date_status_idx"),
            models.Index(fields=["customer", "payment_date"], name="payment_customer_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.customer} — ${self.amount} — {self.payment_date:%d/%m/%Y}"

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}

        if self.sale_id and self.customer_id and self.sale.customer_id != self.customer_id:
            errors["customer"] = "El cliente del pago no coincide con el de la venta."

        is_voided = self.status == self.Status.VOIDED
        if is_voided and not self.voided_at:
            errors["voided_at"] = "Un pago anulado debe registrar cuándo se anuló."
        if is_voided and not self.void_reason.strip():
            errors["void_reason"] = "Un pago anulado debe indicar el motivo."
        if not is_voided and (self.voided_at or self.void_reason.strip()):
            errors["status"] = "Solo un pago anulado puede contener datos de anulación."

        if errors:
            raise ValidationError(errors)


class PaymentAllocation(TimestampedModel):
    class Component(models.TextChoices):
        LATE_FEE = "late_fee", "Recargo"
        PRINCIPAL = "principal", "Capital"

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="allocations",
        verbose_name="pago",
    )
    installment = models.ForeignKey(
        Installment,
        on_delete=models.PROTECT,
        related_name="payment_allocations",
        verbose_name="cuota",
    )
    component = models.CharField(
        max_length=16,
        choices=Component.choices,
        verbose_name="componente",
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(MIN_MONEY)],
        verbose_name="importe aplicado",
    )

    class Meta:
        ordering = ["payment_id", "installment__due_date", "component", "pk"]
        verbose_name = "aplicación de pago"
        verbose_name_plural = "aplicaciones de pago"
        constraints = [
            models.UniqueConstraint(
                fields=["payment", "installment", "component"],
                name="allocation_unique_payment_installment_component",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=ZERO),
                name="allocation_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.payment} → {self.installment} ({self.get_component_display()})"

    def clean(self) -> None:
        super().clean()
        if (
            self.payment_id
            and self.installment_id
            and self.payment.sale_id != self.installment.sale_id
        ):
            raise ValidationError(
                {"installment": "La cuota aplicada no pertenece a la venta del pago."}
            )


class CollectionAttempt(TimestampedModel):
    class Result(models.TextChoices):
        DID_NOT_PAY = "did_not_pay", "No pagó"
        ABSENT = "absent", "Ausente"
        PROMISED = "promised", "Prometió pagar"
        OTHER = "other", "Otro"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="collection_attempts",
        verbose_name="cliente",
    )
    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="collection_attempts",
        verbose_name="venta",
    )
    attempt_date = models.DateField(default=timezone.localdate, verbose_name="fecha")
    result = models.CharField(max_length=20, choices=Result.choices, verbose_name="resultado")
    notes = models.TextField(blank=True, verbose_name="observaciones")

    class Meta:
        ordering = ["-attempt_date", "-created_at", "-pk"]
        verbose_name = "intento de cobranza"
        verbose_name_plural = "intentos de cobranza"
        constraints = [
            models.UniqueConstraint(
                fields=["sale", "attempt_date", "result"],
                name="attempt_unique_sale_date_result",
            )
        ]
        indexes = [
            models.Index(fields=["attempt_date"], name="attempt_date_idx"),
            models.Index(fields=["customer", "attempt_date"], name="attempt_customer_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.customer} — {self.get_result_display()} — {self.attempt_date:%d/%m/%Y}"

    def clean(self) -> None:
        super().clean()
        if self.sale_id and self.customer_id and self.sale.customer_id != self.customer_id:
            raise ValidationError(
                {"customer": "El cliente del intento no coincide con el de la venta."}
            )
