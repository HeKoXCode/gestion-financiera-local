import uuid
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
        label="Métodos de pago",
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
            self.initial["payment_methods_text"] = "\n".join(
                self.instance.payment_methods
            )
            self.initial["available_frequencies"] = (
                self.instance.available_frequencies
            )

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
            if method and method.casefold() not in {
                existing.casefold() for existing in methods
            }:
                methods.append(method)
        if not methods:
            raise ValidationError("Indicá al menos un método de pago.")
        if len(methods) > 20:
            raise ValidationError("Podés configurar hasta 20 métodos de pago.")
        if any(len(method) > 40 for method in methods):
            raise ValidationError(
                "Cada método de pago puede tener hasta 40 caracteres."
            )
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
        settings.available_frequencies = self.cleaned_data[
            "available_frequencies"
        ]
        if commit:
            settings.save()
        return settings


class SaleForm(StyledModelForm):
    cash_price = forms.DecimalField(
        label="Precio del producto",
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
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
        label="Entrega inicial",
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        initial=Decimal("0.00"),
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
        label="Método de la entrega",
        required=False,
    )
    custom_installment_total = forms.BooleanField(
        label="Usar un total en cuotas diferente",
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

    class Meta:
        model = Sale
        fields = [
            "customer",
            "product",
            "product_description",
            "delivery_date",
            "cash_price",
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
            "first_due_date": "Primer día de cobro",
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
        self.fields["customer"].empty_label = "Seleccionar cliente"
        self.fields["product"].empty_label = "Seleccionar producto"
        self.fields["frequency"].choices = [
            choice
            for choice in Sale.Frequency.choices
            if choice[0] in self.settings.available_frequencies
        ]
        self.fields["down_payment_method"].choices = [
            ("", "Seleccionar método"),
            *((method, method) for method in self.settings.payment_methods),
        ]
        self.fields["product_description"].required = False
        self.fields["installment_count"].widget.attrs["max"] = self.settings.max_installments
        self.fields["installment_count"].help_text = (
            f"Máximo configurado: {self.settings.max_installments} cuotas."
        )
        self._apply_styles()
        self.fields["customer"].widget.attrs["autofocus"] = True

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

    def clean(self):
        cleaned = super().clean()
        delivery_date = cleaned.get("delivery_date")
        first_due_date = cleaned.get("first_due_date")
        product_price = cleaned.get("cash_price")
        down_payment = cleaned.get("down_payment") or Decimal("0.00")
        payment_method = cleaned.get("down_payment_method")
        custom_installment_total = cleaned.get("custom_installment_total", False)
        financed_amount = cleaned.get("financed_amount")

        if delivery_date and first_due_date and first_due_date < delivery_date:
            self.add_error(
                "first_due_date",
                "El primer cobro no puede ser anterior a la entrega.",
            )
        if product_price is not None and down_payment >= product_price:
            self.add_error(
                "down_payment",
                "Debe ser menor al precio del producto porque quedará un saldo en cuotas.",
            )
        elif product_price is not None:
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
        if down_payment > ZERO and not payment_method:
            self.add_error(
                "down_payment_method",
                "Elegí cómo se recibió la entrega inicial.",
            )
        if down_payment > ZERO and delivery_date and delivery_date > timezone.localdate():
            self.add_error(
                "delivery_date",
                "Una venta con entrega inicial no puede tener una fecha de entrega futura.",
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
                "placeholder": "Explicá brevemente por qué se cancela la operación",
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
        label="Método de pago",
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
