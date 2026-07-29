from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from modules.core.models import (
    BusinessSettings,
    Installment,
    LateFee,
    Payment,
    PaymentAllocation,
    Sale,
)
from modules.core.tests.factories import make_customer, make_sale

pytestmark = pytest.mark.django_db


def test_default_settings_are_created_by_migration():
    settings = BusinessSettings.get_solo()

    assert settings.pk == 1
    assert settings.daily_late_fee == Decimal("5000.00")
    assert settings.collection_days == [0, 1, 2, 3, 4, 5]
    assert settings.available_frequencies == [
        Sale.Frequency.WEEKLY,
        Sale.Frequency.BIWEEKLY,
        Sale.Frequency.MONTHLY,
    ]
    assert settings.charge_sundays is True
    assert settings.late_fee_after_partial_payment is True
    assert settings.allow_advance_payments is False


def test_settings_reject_invalid_collection_days():
    settings = BusinessSettings.get_solo()
    settings.collection_days = [0, 0, 8]

    with pytest.raises(ValidationError):
        settings.save()


def test_settings_cannot_be_deleted():
    with pytest.raises(ValidationError):
        BusinessSettings.get_solo().delete()


def test_blank_dni_is_normalized_and_does_not_conflict():
    first = make_customer(dni="")
    second = make_customer(
        first_name="María",
        last_name="Gómez",
        dni=" ",
        address="Belgrano 420",
    )

    assert first.dni is None
    assert second.dni is None


def test_non_empty_dni_is_unique():
    make_customer(dni="12345678")

    with pytest.raises(IntegrityError), transaction.atomic():
        make_customer(
            first_name="Otro",
            last_name="Cliente",
            dni="12345678",
            address="Otra 10",
        )


def test_cancelled_sale_requires_date_and_reason():
    sale = make_sale()
    sale.status = Sale.Status.CANCELLED

    with pytest.raises(ValidationError) as error:
        sale.full_clean()

    assert {"cancelled_on", "cancellation_reason"}.issubset(error.value.message_dict)


def test_payment_customer_must_match_sale_customer():
    sale = make_sale()
    other_customer = make_customer(
        first_name="Ana",
        last_name="López",
        address="Mitre 10",
    )
    payment = Payment(
        customer=other_customer,
        sale=sale,
        payment_date=date(2026, 8, 18),
        amount=Decimal("10000.00"),
        payment_method="Efectivo",
    )

    with pytest.raises(ValidationError) as error:
        payment.full_clean()

    assert "customer" in error.value.message_dict


def test_voided_payment_requires_timestamp_and_reason():
    sale = make_sale()
    payment = Payment(
        customer=sale.customer,
        sale=sale,
        payment_date=date(2026, 8, 18),
        amount=Decimal("10000.00"),
        payment_method="Efectivo",
        status=Payment.Status.VOIDED,
    )

    with pytest.raises(ValidationError) as error:
        payment.full_clean()

    assert {"voided_at", "void_reason"}.issubset(error.value.message_dict)

    payment.voided_at = timezone.now()
    payment.void_reason = "Carga duplicada"
    payment.full_clean()


def test_allocation_installment_must_belong_to_payment_sale():
    first_sale = make_sale()
    second_sale = make_sale(
        customer=make_customer(
            first_name="Laura",
            last_name="Díaz",
            address="Rivadavia 22",
        ),
        product=first_sale.product,
    )
    installment = Installment.objects.create(
        sale=second_sale,
        number=1,
        due_date=date(2026, 8, 18),
        original_amount=Decimal("10000.00"),
    )
    payment = Payment.objects.create(
        customer=first_sale.customer,
        sale=first_sale,
        payment_date=date(2026, 8, 18),
        amount=Decimal("1000.00"),
        payment_method="Efectivo",
    )
    allocation = PaymentAllocation(
        payment=payment,
        installment=installment,
        component=PaymentAllocation.Component.PRINCIPAL,
        amount=Decimal("1000.00"),
    )

    with pytest.raises(ValidationError) as error:
        allocation.full_clean()

    assert "installment" in error.value.message_dict


def test_late_fee_cannot_be_duplicated_for_same_day():
    sale = make_sale(installment_count=1, financed_amount=Decimal("20000.00"))
    installment = Installment.objects.create(
        sale=sale,
        number=1,
        due_date=date(2026, 8, 18),
        original_amount=Decimal("20000.00"),
    )
    LateFee.objects.create(
        installment=installment,
        fee_date=date(2026, 8, 19),
        amount=Decimal("5000.00"),
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        LateFee.objects.create(
            installment=installment,
            fee_date=date(2026, 8, 19),
            amount=Decimal("5000.00"),
        )
