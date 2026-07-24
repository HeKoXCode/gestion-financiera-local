import uuid
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from modules.core.models import (
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
            if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect)):
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


class SaleForm(StyledModelForm):
    cash_price = forms.DecimalField(
        label="Precio contado",
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
    financed_amount = forms.DecimalField(
        label="Monto financiado",
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
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

    def clean(self):
        cleaned = super().clean()
        delivery_date = cleaned.get("delivery_date")
        first_due_date = cleaned.get("first_due_date")
        if delivery_date and first_due_date and first_due_date < delivery_date:
            self.add_error(
                "first_due_date",
                "El primer cobro no puede ser anterior a la entrega.",
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
