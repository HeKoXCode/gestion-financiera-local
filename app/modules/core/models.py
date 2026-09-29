from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
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
        Sale.Frequency.DAILY,
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
        verbose_name="recargo diario por atraso",
    )
    collection_days = models.JSONField(
        default=default_collection_days,
        verbose_name="días de cobranza",
    )
    payment_methods = models.JSONField(
        default=default_payment_methods,
        verbose_name="medios de pago",
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
        default=True,
        verbose_name="permitir pagos adelantados",
    )
    allow_exceptional_sale_edits = models.BooleanField(
        default=False,
        verbose_name="habilitar una corrección excepcional de venta",
        help_text=(
            "Permite corregir una venta con pagos o visitas. Se desactiva "
            "automáticamente después de usarla una vez."
        ),
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
            errors["payment_methods"] = "Debe existir al menos un medio de pago válido."
        elif len(self.payment_methods) > 20:
            errors["payment_methods"] = "Puede haber hasta 20 medios de pago."
        elif any(len(method.strip()) > 40 for method in self.payment_methods):
            errors["payment_methods"] = "Cada medio de pago puede tener hasta 40 caracteres."

        valid_frequencies = {choice for choice, _ in Sale.Frequency.choices}
        if not self.available_frequencies or not set(self.available_frequencies).issubset(
            valid_frequencies
        ):
            errors["available_frequencies"] = "Las frecuencias configuradas no son válidas."
        elif Sale.Frequency.DAILY in self.available_frequencies and not self.collection_days:
            errors["collection_days"] = (
                "La frecuencia diaria necesita al menos un día de cobranza habilitado."
            )

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
    deleted_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="enviado al archivo seguro",
    )
    deletion_reason = models.TextField(
        blank=True,
        verbose_name="motivo del borrado",
    )

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
            models.Index(fields=["deleted_at"], name="customer_deleted_idx"),
        ]

    def __str__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def save(self, *args, **kwargs) -> None:
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original and original.deleted_at is not None:
                protected_fields = (
                    "first_name",
                    "last_name",
                    "dni",
                    "phone",
                    "address",
                    "neighborhood",
                    "address_reference",
                    "notes",
                    "is_active",
                    "deleted_at",
                    "deletion_reason",
                )
                if any(
                    getattr(self, field) != getattr(original, field) for field in protected_fields
                ):
                    raise ValidationError("Un cliente del Archivo seguro no puede modificarse.")
        self.first_name = self.first_name.strip()
        self.last_name = self.last_name.strip()
        self.dni = (self.dni or "").strip() or None
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Los clientes no se eliminan físicamente; deben enviarse al Archivo seguro."
        )


class CustomerRevision(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="revisions",
        verbose_name="cliente actual",
    )
    operation_key = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name="clave de operación",
    )
    revision_number = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="número de edición",
    )
    reason = models.TextField(verbose_name="motivo de la edición")
    snapshot = models.JSONField(verbose_name="copia completa anterior")
    archived_at = models.DateTimeField(auto_now_add=True, verbose_name="archivada el")

    class Meta:
        ordering = ["-archived_at", "-pk"]
        verbose_name = "versión anterior de cliente"
        verbose_name_plural = "versiones anteriores de clientes"
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "revision_number"],
                name="customer_revision_unique_number",
            ),
        ]
        indexes = [
            models.Index(fields=["archived_at"], name="customer_revision_archived_idx"),
        ]

    def __str__(self) -> str:
        return f"Cliente #{self.customer_id} — versión anterior {self.revision_number}"

    def save(self, *args, **kwargs) -> None:
        if self.pk:
            raise ValidationError("Una versión del Archivo seguro no puede modificarse.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Una versión del Archivo seguro no puede eliminarse.")


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
    class OperationType(models.TextChoices):
        PRODUCT = "product", "Venta de producto"
        LOAN = "loan", "Préstamo de dinero"

    class Frequency(models.TextChoices):
        DAILY = "daily", "Diaria"
        WEEKLY = "weekly", "Semanal"
        BIWEEKLY = "biweekly", "Cada 2 semanas"
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
        blank=True,
        null=True,
        verbose_name="producto",
    )
    operation_type = models.CharField(
        max_length=16,
        choices=OperationType.choices,
        default=OperationType.PRODUCT,
        verbose_name="tipo de operación",
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
        verbose_name="precio del producto",
    )
    loan_disbursement_method = models.CharField(
        max_length=40,
        blank=True,
        verbose_name="medio de entrega del préstamo",
    )
    loan_interest_rate = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
        verbose_name="interés total del préstamo",
    )
    down_payment = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
        verbose_name="pago inicial",
    )
    financed_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(MIN_MONEY)],
        verbose_name="total en cuotas",
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
    edit_count = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="cantidad de ediciones",
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
                condition=Q(down_payment__gte=ZERO),
                name="sale_down_payment_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(installment_count__gte=1),
                name="sale_installment_count_positive",
            ),
            models.CheckConstraint(
                condition=Q(daily_late_fee__gte=ZERO),
                name="sale_late_fee_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(loan_interest_rate__gte=ZERO),
                name="sale_loan_interest_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(edit_count__gte=0) & Q(edit_count__lte=2),
                name="sale_edit_count_between_zero_and_two",
            ),
            models.CheckConstraint(
                condition=(
                    Q(operation_type="product", product__isnull=False)
                    | Q(operation_type="loan", product__isnull=True)
                ),
                name="sale_product_matches_operation_type",
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

    @property
    def is_loan(self) -> bool:
        return self.operation_type == self.OperationType.LOAN

    @property
    def operation_name(self) -> str:
        return "Préstamo" if self.is_loan else "Venta"

    @property
    def loan_interest_amount(self) -> Decimal:
        if not self.is_loan:
            return ZERO
        return max(ZERO, self.financed_amount - self.cash_price)

    @property
    def base_financed_amount(self) -> Decimal:
        """Price left after the initial payment, before financing adjustments."""
        if self.is_loan:
            return self.cash_price
        return max(ZERO, self.cash_price - self.down_payment)

    @property
    def operation_total(self) -> Decimal:
        return self.down_payment + self.financed_amount

    @property
    def financing_adjustment(self) -> Decimal:
        return self.operation_total - self.cash_price

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}

        if self.is_loan:
            if self.product_id is not None:
                errors["product"] = "Un préstamo no debe estar vinculado a un producto."
            if self.down_payment != ZERO:
                errors["down_payment"] = "Un préstamo no utiliza pago inicial."
            if not self.loan_disbursement_method.strip():
                errors["loan_disbursement_method"] = (
                    "El préstamo debe indicar cómo se entregó el dinero."
                )
            if (
                self.cash_price is not None
                and self.financed_amount is not None
                and self.financed_amount < self.cash_price
            ):
                errors["financed_amount"] = (
                    "El total a devolver no puede ser menor al dinero prestado."
                )
        else:
            if self.product_id is None:
                errors["product"] = "Una venta debe indicar el producto."
            if (
                self.cash_price is not None
                and self.down_payment is not None
                and self.down_payment >= self.cash_price
            ):
                errors["down_payment"] = (
                    "El pago inicial debe ser menor al precio del producto; "
                    "el resto se paga en cuotas."
                )

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

    def save(self, *args, **kwargs) -> None:
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).first()
            if original and original.status == self.Status.CANCELLED:
                protected_fields = (
                    "customer_id",
                    "product_id",
                    "operation_type",
                    "product_description",
                    "delivery_date",
                    "cash_price",
                    "loan_disbursement_method",
                    "loan_interest_rate",
                    "down_payment",
                    "financed_amount",
                    "frequency",
                    "installment_count",
                    "daily_late_fee",
                    "first_due_date",
                    "status",
                    "cancelled_on",
                    "cancellation_reason",
                    "edit_count",
                )
                if any(
                    getattr(self, field) != getattr(original, field) for field in protected_fields
                ):
                    raise ValidationError(
                        "Una venta cancelada del Archivo seguro no puede modificarse."
                    )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Las ventas no se eliminan físicamente; permanecen como registro seguro."
        )


class SaleRevision(models.Model):
    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="revisions",
        verbose_name="venta actual",
    )
    operation_key = models.UUIDField(
        blank=True,
        null=True,
        unique=True,
        editable=False,
        verbose_name="clave de operación",
    )
    revision_number = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="número de edición",
    )
    reason = models.TextField(verbose_name="motivo de la edición")
    snapshot = models.JSONField(verbose_name="copia completa anterior")
    archived_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="archivada el",
    )

    class Meta:
        ordering = ["-archived_at", "-pk"]
        verbose_name = "versión anterior de venta"
        verbose_name_plural = "versiones anteriores de ventas"
        constraints = [
            models.UniqueConstraint(
                fields=["sale", "revision_number"],
                name="sale_revision_unique_number",
            ),
            models.CheckConstraint(
                condition=Q(revision_number__gte=1) & Q(revision_number__lte=2),
                name="sale_revision_number_between_one_and_two",
            ),
        ]
        indexes = [
            models.Index(fields=["archived_at"], name="sale_revision_archived_idx"),
        ]

    def __str__(self) -> str:
        return f"Venta #{self.sale_id} — versión anterior {self.revision_number}"

    def save(self, *args, **kwargs) -> None:
        if self.pk:
            raise ValidationError("Una versión del Archivo seguro no puede modificarse.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Una versión del Archivo seguro no puede eliminarse.")


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
    waived_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
        verbose_name="importe dejado sin efecto",
    )
    waived_reason = models.TextField(
        blank=True,
        verbose_name="motivo del importe dejado sin efecto",
    )
    waived_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="dejado sin efecto el",
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
            models.CheckConstraint(
                condition=Q(waived_amount__gte=ZERO) & Q(waived_amount__lte=F("amount")),
                name="late_fee_waived_amount_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["fee_date"], name="late_fee_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.installment} — {self.fee_date:%d/%m/%Y}"

    @property
    def effective_amount(self) -> Decimal:
        return max(ZERO, self.amount - self.waived_amount)


class LateFeePausePeriod(TimestampedModel):
    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="late_fee_pause_periods",
        verbose_name="venta",
    )
    paused_from = models.DateField(verbose_name="pausado desde")
    resumed_at = models.DateField(
        blank=True,
        null=True,
        verbose_name="reanudado el",
    )
    reason = models.TextField(verbose_name="motivo de la pausa")
    resume_reason = models.TextField(
        blank=True,
        verbose_name="motivo de la reanudación",
    )

    class Meta:
        ordering = ["-paused_from", "-pk"]
        verbose_name = "pausa de recargo diario"
        verbose_name_plural = "pausas de recargo diario"
        constraints = [
            models.UniqueConstraint(
                fields=["sale"],
                condition=Q(resumed_at__isnull=True),
                name="late_fee_pause_one_open_sale",
            ),
            models.CheckConstraint(
                condition=Q(resumed_at__isnull=True) | Q(resumed_at__gte=F("paused_from")),
                name="late_fee_pause_valid_period",
            ),
        ]
        indexes = [
            models.Index(
                fields=["sale", "resumed_at"],
                name="late_fee_pause_sale_idx",
            ),
        ]

    def __str__(self) -> str:
        state = "activa" if self.resumed_at is None else f"hasta {self.resumed_at:%d/%m/%Y}"
        return f"{self.sale} — pausa {self.paused_from:%d/%m/%Y} ({state})"

    @property
    def is_active(self) -> bool:
        return self.resumed_at is None

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}
        self.reason = self.reason.strip()
        self.resume_reason = self.resume_reason.strip()
        if not self.reason:
            errors["reason"] = "Indicá por qué se pausa el recargo diario."
        if self.resumed_at and self.resumed_at < self.paused_from:
            errors["resumed_at"] = "La reanudación no puede ser anterior a la pausa."
        if errors:
            raise ValidationError(errors)


class Collector(TimestampedModel):
    name = models.CharField(max_length=120, unique=True, verbose_name="nombre")
    is_active = models.BooleanField(default=True, verbose_name="activo")
    archived_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="enviado al archivo seguro",
    )
    archive_reason = models.TextField(
        blank=True,
        verbose_name="motivo del archivado",
    )

    class Meta:
        ordering = ["name", "pk"]
        verbose_name = "cobrador"
        verbose_name_plural = "cobradores"
        indexes = [
            models.Index(fields=["archived_at"], name="collector_archived_idx"),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None

    def clean(self) -> None:
        super().clean()
        self.name = " ".join(self.name.split())
        if not self.name:
            raise ValidationError({"name": "Ingresá el nombre del cobrador."})
        duplicate = Collector.objects.filter(name__iexact=self.name)
        if self.pk:
            duplicate = duplicate.exclude(pk=self.pk)
        if duplicate.exists():
            raise ValidationError({"name": "Ya existe un cobrador con ese nombre."})

    def save(self, *args, **kwargs) -> None:
        self.name = " ".join(self.name.split())
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Los cobradores no se eliminan físicamente; deben enviarse al Archivo seguro."
        )


class CollectionRoute(TimestampedModel):
    collection_date = models.DateField(verbose_name="fecha del recorrido")
    collector = models.ForeignKey(
        Collector,
        on_delete=models.PROTECT,
        related_name="routes",
        verbose_name="cobrador",
    )

    class Meta:
        ordering = ["-collection_date", "collector__name", "pk"]
        verbose_name = "recorrido de cobranza"
        verbose_name_plural = "recorridos de cobranza"
        constraints = [
            models.UniqueConstraint(
                fields=["collection_date", "collector"],
                name="route_unique_date_collector",
            )
        ]
        indexes = [
            models.Index(fields=["collection_date"], name="collection_route_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.collector} — {self.collection_date:%d/%m/%Y}"


class CollectionAssignment(TimestampedModel):
    route = models.ForeignKey(
        CollectionRoute,
        on_delete=models.PROTECT,
        related_name="assignments",
        verbose_name="recorrido",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="collection_assignments",
        verbose_name="cliente",
    )
    assigned_date = models.DateField(verbose_name="fecha asignada")
    expected_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(ZERO)],
        verbose_name="importe esperado al asignar",
    )
    snapshot = models.JSONField(default=dict, verbose_name="detalle al asignar")

    class Meta:
        ordering = ["assigned_date", "customer__last_name", "customer__first_name", "pk"]
        verbose_name = "cliente asignado a cobranza"
        verbose_name_plural = "clientes asignados a cobranza"
        constraints = [
            models.UniqueConstraint(
                fields=["route", "customer"],
                name="assignment_unique_route_customer",
            ),
            models.UniqueConstraint(
                fields=["assigned_date", "customer"],
                name="assignment_unique_date_customer",
            ),
            models.CheckConstraint(
                condition=Q(expected_amount__gte=ZERO),
                name="assignment_expected_non_negative",
            ),
        ]
        indexes = [
            models.Index(
                fields=["assigned_date", "customer"],
                name="assignment_date_customer_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.customer} → {self.route}"

    def clean(self) -> None:
        super().clean()
        if self.route_id and self.assigned_date != self.route.collection_date:
            raise ValidationError(
                {"assigned_date": "La fecha asignada debe coincidir con el recorrido."}
            )


class CustomerCollectorLink(TimestampedModel):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="collector_links",
        verbose_name="cliente",
    )
    collector = models.ForeignKey(
        Collector,
        on_delete=models.PROTECT,
        related_name="customer_links",
        verbose_name="cobrador",
    )
    started_at = models.DateField(verbose_name="asignado desde")
    ended_at = models.DateField(
        blank=True,
        null=True,
        verbose_name="asignación finalizada el",
    )
    source_route = models.ForeignKey(
        CollectionRoute,
        on_delete=models.SET_NULL,
        related_name="habitual_links_created",
        blank=True,
        null=True,
        verbose_name="recorrido de origen",
    )
    reason = models.CharField(
        max_length=250,
        default="Asignación guardada desde Preparar planillas",
        verbose_name="motivo",
    )

    class Meta:
        ordering = ["-started_at", "-pk"]
        verbose_name = "cobrador habitual del cliente"
        verbose_name_plural = "historial de cobradores habituales"
        constraints = [
            models.UniqueConstraint(
                fields=["customer"],
                condition=Q(ended_at__isnull=True),
                name="customer_collector_one_active",
            ),
            models.CheckConstraint(
                condition=Q(ended_at__isnull=True) | Q(ended_at__gte=F("started_at")),
                name="customer_collector_valid_period",
            ),
        ]
        indexes = [
            models.Index(
                fields=["collector", "ended_at"],
                name="customer_collector_active_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.customer} → {self.collector}"

    @property
    def is_active(self) -> bool:
        return self.ended_at is None

    def clean(self) -> None:
        super().clean()
        if self.ended_at and self.ended_at < self.started_at:
            raise ValidationError(
                {"ended_at": "El fin no puede ser anterior al inicio de la asignación."}
            )


class Payment(TimestampedModel):
    class Kind(models.TextChoices):
        INSTALLMENT = "installment", "Pago de cuota"
        INITIAL = "initial", "Pago inicial"

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
    collector = models.ForeignKey(
        Collector,
        on_delete=models.PROTECT,
        related_name="payments_collected",
        blank=True,
        null=True,
        verbose_name="cobrador",
    )
    collection_assignment = models.ForeignKey(
        CollectionAssignment,
        on_delete=models.PROTECT,
        related_name="payments",
        blank=True,
        null=True,
        verbose_name="asignación de cobranza",
    )
    payment_date = models.DateField(default=timezone.localdate, verbose_name="fecha")
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(MIN_MONEY)],
        verbose_name="importe",
    )
    payment_method = models.CharField(max_length=40, verbose_name="medio de pago")
    kind = models.CharField(
        max_length=16,
        choices=Kind.choices,
        default=Kind.INSTALLMENT,
        verbose_name="tipo de movimiento",
    )
    is_advance = models.BooleanField(
        default=False,
        verbose_name="pago adelantado",
    )
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

    @property
    def movement_label(self) -> str:
        if self.kind == self.Kind.INSTALLMENT and self.is_advance:
            return "Pago adelantado"
        return self.get_kind_display()

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}

        if self.sale_id and self.customer_id and self.sale.customer_id != self.customer_id:
            errors["customer"] = "El cliente del pago no coincide con el de la venta."

        if bool(self.collector_id) != bool(self.collection_assignment_id):
            errors["collector"] = (
                "El cobrador y la asignación de cobranza deben registrarse juntos."
            )
        if self.collection_assignment_id:
            assignment = self.collection_assignment
            if assignment.customer_id != self.customer_id:
                errors["collection_assignment"] = "La asignación no pertenece al cliente del pago."
            elif assignment.assigned_date != self.payment_date:
                errors["collection_assignment"] = "La asignación no pertenece a la fecha del pago."
            elif assignment.route.collector_id != self.collector_id:
                errors["collector"] = "El cobrador no coincide con el recorrido asignado."
            elif self.kind != self.Kind.INSTALLMENT or self.is_advance:
                errors["collection_assignment"] = (
                    "Solo los pagos normales de cuotas pueden pertenecer a un recorrido."
                )

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
        ABSENT = "absent", "No estaba en el domicilio"
        PROMISED = "promised", "Prometió pagar"
        OTHER = "other", "Otro resultado"

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
    collector = models.ForeignKey(
        Collector,
        on_delete=models.PROTECT,
        related_name="collection_attempts",
        blank=True,
        null=True,
        verbose_name="cobrador",
    )
    collection_assignment = models.ForeignKey(
        CollectionAssignment,
        on_delete=models.PROTECT,
        related_name="attempts",
        blank=True,
        null=True,
        verbose_name="asignación de cobranza",
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
        errors: dict[str, str] = {}
        if self.sale_id and self.customer_id and self.sale.customer_id != self.customer_id:
            errors["customer"] = "El cliente del intento no coincide con el de la venta."
        if bool(self.collector_id) != bool(self.collection_assignment_id):
            errors["collector"] = (
                "El cobrador y la asignación de cobranza deben registrarse juntos."
            )
        if self.collection_assignment_id:
            assignment = self.collection_assignment
            if assignment.customer_id != self.customer_id:
                errors["collection_assignment"] = (
                    "La asignación no pertenece al cliente de la visita."
                )
            elif assignment.assigned_date != self.attempt_date:
                errors["collection_assignment"] = (
                    "La asignación no pertenece a la fecha de la visita."
                )
            elif assignment.route.collector_id != self.collector_id:
                errors["collector"] = "El cobrador no coincide con el recorrido asignado."
        if errors:
            raise ValidationError(errors)


class AuditEvent(models.Model):
    """Append-only trace of successful state-changing web operations."""

    request_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="gestion_audit_events",
        blank=True,
        null=True,
        verbose_name="usuario",
    )
    action = models.CharField(max_length=120, verbose_name="acción")
    path = models.CharField(max_length=500, verbose_name="ruta")
    method = models.CharField(max_length=10, verbose_name="método")
    status_code = models.PositiveSmallIntegerField(verbose_name="estado HTTP")
    remote_address = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name="dirección remota",
    )
    metadata = models.JSONField(default=dict, blank=True, verbose_name="metadatos")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="fecha")

    class Meta:
        ordering = ["-created_at", "-pk"]
        verbose_name = "evento de auditoría"
        verbose_name_plural = "eventos de auditoría"
        indexes = [
            models.Index(fields=["-created_at"], name="audit_created_idx"),
            models.Index(fields=["actor", "-created_at"], name="audit_actor_created_idx"),
            models.Index(fields=["action", "-created_at"], name="audit_action_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.created_at:%d/%m/%Y %H:%M} — {self.action}"

    def save(self, *args, **kwargs) -> None:
        if self.pk:
            raise ValidationError("Los eventos de auditoría no pueden modificarse.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Los eventos de auditoría no pueden eliminarse.")
