from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from modules.core.services.installments import (
    calculate_installment_amounts,
    calculate_installment_schedule,
    create_installments,
)
from modules.core.tests.factories import make_sale

pytestmark = pytest.mark.django_db


def test_twelve_weekly_installments_match_financed_amount():
    sale = make_sale()

    schedule = calculate_installment_schedule(sale)

    assert len(schedule) == 12
    assert all(item.amount == Decimal("40000.00") for item in schedule)
    assert schedule[0].due_date == date(2026, 8, 18)
    assert schedule[1].due_date == date(2026, 8, 25)
    assert sum(item.amount for item in schedule) == sale.financed_amount


def test_last_installment_absorbs_cent_difference():
    amounts = calculate_installment_amounts(Decimal("100.00"), 3)

    assert amounts == [
        Decimal("33.33"),
        Decimal("33.33"),
        Decimal("33.34"),
    ]


def test_biweekly_schedule_uses_fourteen_day_interval():
    sale = make_sale(
        frequency="biweekly",
        installment_count=3,
        financed_amount=Decimal("30000.00"),
    )

    schedule = calculate_installment_schedule(sale)

    assert [item.due_date for item in schedule] == [
        date(2026, 8, 18),
        date(2026, 9, 1),
        date(2026, 9, 15),
    ]


def test_installments_are_created_only_once():
    sale = make_sale(installment_count=2, financed_amount=Decimal("20000.00"))

    created = create_installments(sale)

    assert len(created) == 2
    assert sale.installments.count() == 2
    with pytest.raises(ValidationError):
        create_installments(sale)

