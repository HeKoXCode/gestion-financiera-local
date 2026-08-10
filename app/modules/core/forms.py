import json
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from string import Formatter

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.core.models import (
    ZERO,
    BusinessSettings,
    CollectionAttempt,
    Customer,
    Product,
    Sale,
)
from modules.core.services.installments import add_months


class StyledModelForm(forms.ModelForm):
    """Apply the local design system to Django-generated controls."""

    def _apply_styles(self) -> None:
        for field in self.fields.values():
            widget = field.widget
            if isinstance(
                widget,
                (forms.CheckboxInput, forms.RadioSelect, forms.CheckboxSelectMultiple),
            ):
                continue
            current = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{current} form-control".strip()


class CustomerForm(StyledModelForm):
    class Meta:
        model = Customer
        fields = [
            "first_name",
            "last_name",
            "dni",
            "phone",
            "address",
            "neighborhood",
            "address_reference",
            "notes",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "dni": forms.TextInput(attrs={"inputmode": "numeric", "placeholder": "Opcional"}),
            "phone": forms.TextInput(
                attrs={"autocomplete": "tel", "inputmode": "tel", "placeholder": "Ej. 11 2233 4455"}
            ),
            "address": forms.TextInput(
                attrs={"autocomplete": "street-address", "placeholder": "Calle y número"}
            ),
            "neighborhood": forms.TextInput(attrs={"placeholder": "Opcional"}),
            "address_reference": forms.TextInput(
                attrs={"placeholder": "Ej. portón negro, frente a la plaza"}
            ),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_styles()
        self.fields["first_name"].widget.attrs["autofocus"] = True

    def clean_dni(self):
        return (self.cleaned_data.get("dni") or "").strip() or None


class ProductForm(StyledModelForm):
    class Meta:
        model = Product
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ej. Smart TV 50 pulgadas"}),
            "description": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Características o detalles útiles para identificarlo",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_styles()
        self.fields["name"].widget.attrs["autofocus"] = True

    def clean_name(self):
        return self.cleaned_data["name"].strip()


class BusinessSettingsForm(StyledModelForm):
    WHATSAPP_FIELDS = {"nombre", "monto", "vencimiento"}
    DAY_CHOICES = [
        (0, "Lunes"),
        (1, "Martes"),
        (2, "Miércoles"),
        (3, "Jueves"),
        (4, "Viernes"),
        (5, "Sábado"),
        (6, "Domingo"),
    ]

    collection_days = forms.TypedMultipleChoiceField(
        label="Días habilitados para cobranza",
        choices=DAY_CHOICES,
        coerce=int,
        widget=forms.CheckboxSelectMultiple,
    )
    payment_methods_text = forms.CharField(
        label="Medios de pago",
        help_text="Escribí uno por línea. Por ejemplo: Efectivo, Transferencia y Otro.",
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    available_frequencies = forms.MultipleChoiceField(
        label="Frecuencias disponibles",
        choices=Sale.Frequency.choices,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = BusinessSettings
        fields = [
            "business_name",
            "logo",
            "daily_late_fee",
            "collection_days",
            "payment_methods_text",
            "available_frequencies",
            "max_installments",
            "charge_sundays",
            "late_fee_after_partial_payment",
            "allow_advance_payments",
            "whatsapp_message",
        ]
        widgets = {
            "daily_late_fee": forms.TextInput(
                attrs={"inputmode": "decimal", "data-money-input": ""}
            ),
            "max_installments": forms.NumberInput(attrs={"min": 1, "max": 999}),
            "whatsapp_message": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_styles()
        if self.instance and self.instance.pk:
            self.initial["collection_days"] = self.instance.collection_days
            self.initial["payment_methods_text"] = "\n".join(self.instance.payment_methods)
            self.initial["available_frequencies"] = self.instance.available_frequencies

    def clean_business_name(self):
        return self.cleaned_data["business_name"].strip()

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if not logo or not hasattr(logo, "size"):
            return logo
        if logo.size > 2 * 1024 * 1024:
            raise ValidationError("El logo no puede superar los 2 MB.")
        valid_extensions = {".png", ".jpg", ".jpeg", ".webp"}
        if Path(logo.name).suffix.lower() not in valid_extensions:
            raise ValidationError("Usá un logo PNG, JPG, JPEG o WEBP.")
        return logo

    def clean_payment_methods_text(self):
        raw_value = self.cleaned_data["payment_methods_text"]
        methods = []
        for line in raw_value.replace(",", "\n").splitlines():
            method = line.strip()
            if method and method.casefold() not in {existing.casefold() for existing in methods}:
                methods.append(method)
        if not methods:
            raise ValidationError("Indicá al menos un medio de pago.")
        if len(methods) > 20:
            raise ValidationError("Podés configurar hasta 20 medios de pago.")
        if any(len(method) > 40 for method in methods):
            raise ValidationError("Cada medio de pago puede tener hasta 40 caracteres.")
        return methods

    def clean_whatsapp_message(self):
        message = self.cleaned_data["whatsapp_message"].strip()
        try:
            fields = {
                field_name
                for _, field_name, _, _ in Formatter().parse(message)
                if field_name is not None
            }
        except ValueError as exc:
            raise ValidationError(
                "El mensaje tiene una llave abierta o cerrada incorrectamente."
            ) from exc
        invalid_fields = fields - self.WHATSAPP_FIELDS
        if invalid_fields:
            invalid = ", ".join(sorted(invalid_fields))
            raise ValidationError(
                f"Variable no permitida: {invalid}. "
                "Usá solamente {nombre}, {monto} y {vencimiento}."
            )
        return message

    def save(self, commit=True):
        settings = super().save(commit=False)
        settings.collection_days = self.cleaned_data["collection_days"]
        settings.payment_methods = self.cleaned_data["payment_methods_text"]
        settings.available_frequencies = self.cleaned_data["available_frequencies"]
        if commit:
            settings.save()
        return settings


class SaleForm(StyledModelForm):
    FIRST_INSTALLMENT_PAID = "paid"
    FIRST_INSTALLMENT_PENDING = "pending"

    operation_type = forms.ChoiceField(
        label="Tipo de operación",
        choices=Sale.OperationType.choices,
        initial=Sale.OperationType.PRODUCT,
        required=False,
        widget=forms.RadioSelect,
    )

    cash_price = forms.DecimalField(
        label="Precio del producto",
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
        localize=True,
        widget=forms.TextInput(
            attrs={
                "inputmode": "decimal",
                "placeholder": "Ej. 400000",
                "data-money-input": "",
            }
        ),
    )
    down_payment = forms.DecimalField(
        label="Pago inicial aparte",
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        localize=True,
        widget=forms.TextInput(
            attrs={
                "inputmode": "decimal",
                "placeholder": "Ej. 200000",
                "data-money-input": "",
            }
        ),
    )
    down_payment_method = forms.ChoiceField(
        label="Medio del pago inicial aparte",
        required=False,
    )
    loan_disbursement_method = forms.ChoiceField(
        label="Cómo se entregó el dinero",
        required=False,
    )
    loan_interest_rate = forms.DecimalField(
        label="Interés total",
        max_digits=7,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        localize=True,
        widget=forms.TextInput(
            attrs={
                "inputmode": "decimal",
                "placeholder": "Ej. 20",
            }
        ),
    )
    custom_installment_total = forms.BooleanField(
        label="Modificar el total que se pagará en cuotas",
        required=False,
    )
    financed_amount = forms.DecimalField(
        label="Total en cuotas",
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
        localize=True,
        widget=forms.TextInput(
            attrs={
                "inputmode": "decimal",
                "placeholder": "Ej. 480000",
                "data-money-input": "",
            }
        ),
    )
    installment_amount = forms.DecimalField(
        label="Monto de cada cuota",
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
        localize=True,
        widget=forms.TextInput(
            attrs={
                "inputmode": "decimal",
                "placeholder": "Ej. 50000",
                "data-money-input": "",
            }
        ),
    )
    same_day_first_due = forms.BooleanField(
        label="La cuota 1 vence el día de la entrega",
        required=False,
    )
    first_installment_delivery_status = forms.ChoiceField(
        label="Estado de la cuota 1 al entregar",
        required=False,
        choices=(
            (
                FIRST_INSTALLMENT_PAID,
                "Pagó la cuota 1 al recibir el producto",
            ),
            (
                FIRST_INSTALLMENT_PENDING,
                "La cuota 1 quedó pendiente",
            ),
        ),
        widget=forms.RadioSelect,
    )
    first_installment_payment_method = forms.ChoiceField(
        label="Medio de pago de la cuota 1",
        required=False,
    )
    historical_paid_installments = forms.IntegerField(
        label="Cuotas anteriores ya pagadas",
        min_value=0,
        required=False,
        initial=0,
        widget=forms.NumberInput(
            attrs={
                "min": 0,
                "inputmode": "numeric",
                "placeholder": "Ej. 11",
            }
        ),
    )
    historical_payment_method = forms.ChoiceField(
        label="Medio de esos pagos",
        required=False,
    )
    historical_late_installments = forms.CharField(
        required=False,
        widget=forms.HiddenInput(
            attrs={
                "data-historical-late-installments": "",
            }
        ),
    )

    class Meta:
        model = Sale
        fields = [
            "operation_type",
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
        ]
        widgets = {
            "product_description": forms.TextInput(
                attrs={"placeholder": "Se completa con el producto seleccionado"}
            ),
            "delivery_date": forms.DateInput(attrs={"type": "date"}),
            "installment_count": forms.NumberInput(attrs={"min": 1, "inputmode": "numeric"}),
            "first_due_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "product_description": "Descripción en esta venta",
            "first_due_date": "Vencimiento de la cuota 1",
        }

    def __init__(
        self,
        *args,
        settings: BusinessSettings | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.settings = settings or BusinessSettings.get_solo()
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True)
        self.fields["product"].queryset = Product.objects.filter(is_active=True)
        self.fields["product"].required = False
        self.fields["customer"].empty_label = ""
        self.fields["product"].empty_label = ""
        self.fields["frequency"].choices = [
            choice
            for choice in Sale.Frequency.choices
            if choice[0] in self.settings.available_frequencies
        ]
        self.fields["down_payment_method"].choices = [
            ("", "Seleccionar medio"),
            *((method, method) for method in self.settings.payment_methods),
        ]
        self.fields["loan_disbursement_method"].choices = [
            ("", "Seleccionar medio"),
            *((method, method) for method in self.settings.payment_methods),
        ]
        self.fields["historical_payment_method"].choices = [
            ("", "Seleccionar medio"),
            *((method, method) for method in self.settings.payment_methods),
        ]
        self.fields["first_installment_payment_method"].choices = [
            ("", "Seleccionar medio"),
            *((method, method) for method in self.settings.payment_methods),
        ]
        if self.settings.payment_methods:
            self.fields["historical_payment_method"].initial = self.settings.payment_methods[0]
        self.fields["product_description"].required = False
        self.fields["installment_count"].widget.attrs["max"] = self.settings.max_installments
        self.fields[
            "installment_count"
        ].help_text = f"Máximo configurado: {self.settings.max_installments} cuotas."
        self._apply_styles()
        self.fields["customer"].label_from_instance = self._customer_choice_label
        self.fields["product"].label_from_instance = self._product_choice_label

    @staticmethod
    def _customer_choice_label(customer: Customer) -> str:
        details = [customer.full_name]
        if customer.dni:
            details.append(f"DNI {customer.dni}")
        if customer.address:
            details.append(customer.address)
        return " · ".join(details)

    @staticmethod
    def _product_choice_label(product: Product) -> str:
        description = " ".join((product.description or "").split())
        if description:
            return f"{product.name} · {description[:70]}"
        return product.name

    def clean_product_description(self):
        description = (self.cleaned_data.get("product_description") or "").strip()
        product = self.cleaned_data.get("product")
        return description or (product.name if product else "")

    def clean_installment_count(self):
        count = self.cleaned_data["installment_count"]
        if count > self.settings.max_installments:
            raise ValidationError(
                f"La configuración permite hasta {self.settings.max_installments} cuotas."
            )
        return count

    def clean_frequency(self):
        frequency = self.cleaned_data["frequency"]
        if frequency not in self.settings.available_frequencies:
            raise ValidationError("La frecuencia seleccionada no está habilitada.")
        return frequency

    def clean_down_payment(self):
        return self.cleaned_data.get("down_payment") or Decimal("0.00")

    def clean_historical_paid_installments(self):
        return self.cleaned_data.get("historical_paid_installments") or 0

    def clean_historical_late_installments(self):
        raw_value = (self.cleaned_data.get("historical_late_installments") or "").strip()
        if not raw_value:
            return {}
        try:
            parsed = json.loads(raw_value)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValidationError("No se pudo interpretar el detalle de atrasos.") from exc
        if not isinstance(parsed, dict):
            raise ValidationError("El detalle de atrasos no tiene un formato válido.")

        normalized: dict[int, int] = {}
        for raw_installment, raw_days in parsed.items():
            try:
                installment_number = int(raw_installment)
                late_days = int(raw_days)
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    "Cada atraso debe indicar una cuota y una cantidad de días."
                ) from exc
            if installment_number < 1 or late_days < 1:
                raise ValidationError("Los números de cuota y días deben ser mayores que cero.")
            normalized[installment_number] = late_days
        return normalized

    @staticmethod
    def _historical_due_count(
        *,
        first_due_date,
        frequency,
        installment_count,
        as_of,
    ) -> int:
        if not first_due_date or not frequency or not installment_count:
            return 0
        if frequency == Sale.Frequency.MONTHLY:
            due_dates = [
                add_months(first_due_date, offset) for offset in range(installment_count)
            ]
        else:
            intervals = {
                Sale.Frequency.WEEKLY: 7,
                Sale.Frequency.BIWEEKLY: 14,
            }
            interval = intervals.get(frequency)
            if interval is None:
                return 0
            due_dates = [
                first_due_date + timedelta(days=offset * interval)
                for offset in range(installment_count)
            ]
        return sum(due_date <= as_of for due_date in due_dates)

    def clean(self):
        cleaned = super().clean()
        operation_type = cleaned.get("operation_type") or Sale.OperationType.PRODUCT
        is_loan = operation_type == Sale.OperationType.LOAN
        delivery_date = cleaned.get("delivery_date")
        if cleaned.get("same_day_first_due") and delivery_date:
            cleaned["first_due_date"] = delivery_date
        first_due_date = cleaned.get("first_due_date")
        product_price = cleaned.get("cash_price")
        down_payment = cleaned.get("down_payment") or Decimal("0.00")
        payment_method = cleaned.get("down_payment_method")
        custom_installment_total = cleaned.get("custom_installment_total", False)
        financed_amount = cleaned.get("financed_amount")
        installment_amount = cleaned.get("installment_amount")
        historical_count = cleaned.get("historical_paid_installments") or 0
        historical_method = cleaned.get("historical_payment_method")
        historical_late_installments = cleaned.get("historical_late_installments") or {}
        same_day_first_due = cleaned.get("same_day_first_due", False)
        first_installment_status = cleaned.get("first_installment_delivery_status")
        first_installment_method = cleaned.get("first_installment_payment_method")
        installment_count = cleaned.get("installment_count")
        frequency = cleaned.get("frequency")

        if is_loan:
            cleaned["product"] = None
            cleaned["down_payment"] = ZERO
            cleaned["down_payment_method"] = ""
            down_payment = ZERO
            cleaned["product_description"] = (
                cleaned.get("product_description") or "Préstamo de dinero"
            )

            if product_price is None:
                self.add_error("cash_price", "Indicá cuánto dinero se prestó.")
            if not cleaned.get("loan_disbursement_method"):
                self.add_error(
                    "loan_disbursement_method",
                    "Elegí cómo se entregó el dinero al cliente.",
                )

            if installment_amount is not None and installment_count:
                financed_amount = installment_amount * installment_count
                cleaned["financed_amount"] = financed_amount
            elif custom_installment_total:
                if financed_amount is None or financed_amount <= ZERO:
                    self.add_error(
                        "financed_amount",
                        "Indicá el total acordado que el cliente devolverá.",
                    )
            elif product_price is not None:
                interest_rate = cleaned.get("loan_interest_rate") or ZERO
                financed_amount = (
                    product_price * (Decimal("1.00") + interest_rate / Decimal("100"))
                ).quantize(Decimal("0.01"))
                cleaned["financed_amount"] = financed_amount

            if (
                product_price is not None
                and financed_amount is not None
                and financed_amount < product_price
            ):
                self.add_error(
                    "financed_amount",
                    "El total a devolver no puede ser menor al dinero prestado.",
                )
            elif product_price and financed_amount is not None:
                cleaned["loan_interest_rate"] = (
                    (financed_amount - product_price)
                    * Decimal("100")
                    / product_price
                ).quantize(Decimal("0.01"))
        else:
            cleaned["loan_disbursement_method"] = ""
            cleaned["loan_interest_rate"] = ZERO
            if not cleaned.get("product"):
                self.add_error("product", "Elegí el producto vendido.")

            if installment_amount is not None and installment_count:
                calculated_installment_total = installment_amount * installment_count
                cleaned["financed_amount"] = calculated_installment_total
                financed_amount = calculated_installment_total
                if not custom_installment_total:
                    product_price = down_payment + calculated_installment_total
                    cleaned["cash_price"] = product_price

            if product_price is None:
                self.add_error(
                    "cash_price",
                    (
                        "Indicá el precio del producto o calculalo con la cantidad "
                        "de cuotas y el monto de cada cuota."
                    ),
                )

        if delivery_date and first_due_date and first_due_date < delivery_date:
            self.add_error(
                "first_due_date",
                "El vencimiento de la cuota 1 no puede ser anterior a la entrega.",
            )
        if not is_loan and product_price is not None and down_payment >= product_price:
            self.add_error(
                "down_payment",
                "Debe ser menor al precio del producto porque quedará un saldo en cuotas.",
            )
        elif not is_loan and product_price is not None:
            base_installment_total = product_price - down_payment
            if custom_installment_total:
                if financed_amount is None or financed_amount <= ZERO:
                    self.add_error(
                        "financed_amount",
                        "Indicá el total acordado que se dividirá entre las cuotas.",
                    )
            else:
                # The server is the final source of truth. Ignore any stale value
                # posted by the browser while automatic calculation is selected.
                cleaned["financed_amount"] = base_installment_total
        if not is_loan and down_payment > ZERO and not payment_method:
            self.add_error(
                "down_payment_method",
                "Elegí cómo se recibió el pago inicial aparte.",
            )
        if (
            not is_loan
            and down_payment > ZERO
            and delivery_date
            and delivery_date > timezone.localdate()
        ):
            self.add_error(
                "delivery_date",
                "Una venta con pago inicial aparte no puede tener una fecha de entrega futura.",
            )
        if same_day_first_due:
            if not first_installment_status:
                self.add_error(
                    "first_installment_delivery_status",
                    "Indicá si la cuota 1 fue pagada o quedó pendiente al entregar.",
                )
            elif first_installment_status == self.FIRST_INSTALLMENT_PAID:
                if not first_installment_method:
                    self.add_error(
                        "first_installment_payment_method",
                        "Elegí cómo se recibió el pago de la cuota 1.",
                    )
                if delivery_date and delivery_date > timezone.localdate():
                    self.add_error(
                        "delivery_date",
                        "No se puede registrar la cuota 1 como pagada en una fecha futura.",
                    )
            elif historical_count:
                self.add_error(
                    "first_installment_delivery_status",
                    (
                        "Las cuotas anteriores se cuentan desde la cuota 1. "
                        "No puede quedar pendiente si indicás cuotas ya pagadas."
                    ),
                )
        else:
            cleaned["first_installment_delivery_status"] = ""
            cleaned["first_installment_payment_method"] = ""
        if historical_count:
            already_recorded_at_delivery = (
                same_day_first_due
                and first_installment_status == self.FIRST_INSTALLMENT_PAID
            )
            historical_payments_needed = historical_count - int(
                already_recorded_at_delivery
            )
            if historical_payments_needed > 0 and not historical_method:
                self.add_error(
                    "historical_payment_method",
                    "Elegí el medio usado para las cuotas ya pagadas.",
                )
            if installment_count and historical_count > installment_count:
                self.add_error(
                    "historical_paid_installments",
                    f"La venta tiene solamente {installment_count} cuotas.",
                )
            else:
                due_count = self._historical_due_count(
                    first_due_date=first_due_date,
                    frequency=frequency,
                    installment_count=installment_count,
                    as_of=timezone.localdate(),
                )
                if historical_count > due_count:
                    self.add_error(
                        "historical_paid_installments",
                        (
                            f"Hasta hoy vencieron {due_count} cuotas. "
                            "Las cuotas futuras no pueden marcarse como pagadas "
                            "desde la carga histórica."
                        ),
                    )
        if historical_late_installments:
            if not historical_count:
                self.add_error(
                    "historical_late_installments",
                    "Primero indicá cuántas cuotas anteriores ya fueron pagadas.",
                )
            due_dates = []
            if first_due_date and frequency and installment_count:
                if frequency == Sale.Frequency.MONTHLY:
                    due_dates = [
                        add_months(first_due_date, offset)
                        for offset in range(installment_count)
                    ]
                else:
                    interval_days = (
                        7 if frequency == Sale.Frequency.WEEKLY else 14
                    )
                    due_dates = [
                        first_due_date + timedelta(days=interval_days * offset)
                        for offset in range(installment_count)
                    ]

            for installment_number, late_days in historical_late_installments.items():
                if installment_number > historical_count:
                    self.add_error(
                        "historical_late_installments",
                        (
                            f"La cuota {installment_number} no está dentro de las "
                            f"{historical_count} cuotas indicadas como pagadas."
                        ),
                    )
                    continue
                if (
                    installment_number == 1
                    and same_day_first_due
                    and first_installment_status == self.FIRST_INSTALLMENT_PAID
                ):
                    self.add_error(
                        "historical_late_installments",
                        "La cuota 1 figura pagada al entregar, por lo que no puede tener atraso.",
                    )
                    continue
                if installment_number <= len(due_dates):
                    payment_date = due_dates[installment_number - 1] + timedelta(
                        days=late_days
                    )
                    if payment_date > timezone.localdate():
                        maximum_days = max(
                            0,
                            (
                                timezone.localdate()
                                - due_dates[installment_number - 1]
                            ).days,
                        )
                        self.add_error(
                            "historical_late_installments",
                            (
                                f"La cuota {installment_number} admite como máximo "
                                f"{maximum_days} días de atraso hasta hoy."
                            ),
                        )
        return cleaned


class SaleCancellationForm(forms.Form):
    reason = forms.CharField(
        label="Motivo de cancelación",
        min_length=3,
        max_length=500,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Explicá brevemente por qué se cancela la venta",
                "autofocus": True,
            }
        ),
    )


class PaymentForm(forms.Form):
    operation_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    amount = forms.DecimalField(
        label="Monto abonado",
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
        localize=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "inputmode": "decimal",
                "data-payment-amount": "",
                "autofocus": True,
            }
        ),
    )
    payment_date = forms.DateField(
        label="Fecha",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    payment_method = forms.ChoiceField(
        label="Medio de pago",
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    notes = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Opcional",
            }
        ),
    )

    def __init__(
        self,
        *args,
        settings: BusinessSettings,
        sale: Sale,
        due_amount: Decimal,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.settings = settings
        self.sale = sale
        self.fields["payment_method"].choices = [
            (method, method) for method in settings.payment_methods
        ]
        if not self.is_bound:
            self.initial["amount"] = due_amount

    def clean_payment_date(self):
        payment_date = self.cleaned_data["payment_date"]
        if payment_date < self.sale.delivery_date:
            raise ValidationError("La fecha no puede ser anterior a la entrega.")
        if payment_date > timezone.localdate():
            raise ValidationError("No se puede registrar un pago futuro.")
        return payment_date


class PaymentVoidForm(forms.Form):
    reason = forms.CharField(
        label="Motivo de anulación",
        min_length=3,
        max_length=500,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "autofocus": True,
                "placeholder": "Ej. pago cargado dos veces o importe incorrecto",
            }
        ),
    )


class CollectionAttemptForm(forms.Form):
    attempt_date = forms.DateField(
        label="Fecha",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    result = forms.ChoiceField(
        label="Resultado",
        choices=CollectionAttempt.Result.choices,
        initial=CollectionAttempt.Result.DID_NOT_PAY,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    notes = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Ej. pidió que vuelva el viernes",
            }
        ),
    )

    def __init__(self, *args, sale: Sale, **kwargs):
        super().__init__(*args, **kwargs)
        self.sale = sale

    def clean_attempt_date(self):
        attempt_date = self.cleaned_data["attempt_date"]
        if attempt_date < self.sale.delivery_date:
            raise ValidationError("La fecha no puede ser anterior a la entrega.")
        if attempt_date > timezone.localdate():
            raise ValidationError("No se puede registrar una visita futura.")
        return attempt_date
