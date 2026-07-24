from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from modules.core.models import CollectionAttempt
from modules.core.services.collection import build_collection_rows
from modules.core.services.installments import create_installments
from modules.core.services.whatsapp import (
    build_payment_reminder_url,
    normalize_argentina_whatsapp_number,
)
from modules.core.tests.factories import make_sale

pytestmark = pytest.mark.django_db


def test_collection_groups_due_installments_by_sale():
    today = timezone.localdate()
    sale = make_sale(
        delivery_date=today - timedelta(days=30),
        first_due_date=today - timedelta(days=14),
        financed_amount=Decimal("40000.00"),
        installment_count=2,
        daily_late_fee=Decimal("0.00"),
    )
    create_installments(sale)

    rows = build_collection_rows(as_of=today)

    assert len(rows) == 1
    assert rows[0]["sale"] == sale
    assert rows[0]["due_installment_count"] == 2
    assert rows[0]["total_due"] == Decimal("40000.00")
    assert rows[0]["days_overdue"] == 14


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("11 2233-4455", "5491122334455"),
        ("011 2233 4455", "5491122334455"),
        ("+54 9 11 2233 4455", "5491122334455"),
        ("", ""),
    ],
)
def test_argentina_whatsapp_number_normalization(raw, expected):
    assert normalize_argentina_whatsapp_number(raw) == expected


def test_whatsapp_link_contains_prefilled_payment_message():
    sale = make_sale()

    url = build_payment_reminder_url(
        customer=sale.customer,
        amount=Decimal("25000.00"),
        due_date=sale.first_due_date,
    )

    assert url.startswith("https://wa.me/5491122334455?text=")
    assert "Juan" in url
    assert "%24%2025.000%2C00" in url


def test_collection_attempt_is_unique_per_sale_date_and_result():
    sale = make_sale()
    values = {
        "sale": sale,
        "customer": sale.customer,
        "attempt_date": timezone.localdate(),
        "result": CollectionAttempt.Result.DID_NOT_PAY,
    }
    CollectionAttempt.objects.create(**values)

    with pytest.raises(IntegrityError), transaction.atomic():
        CollectionAttempt.objects.create(**values)

