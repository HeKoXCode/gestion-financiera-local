from __future__ import annotations

from datetime import date
from decimal import Decimal

from modules.core.models import BusinessSettings, Sale
from modules.core.services.balances import (
    get_installment_balance,
    installment_balance_prefetches,
    sale_effective_filter,
)
from modules.core.services.money import ZERO, as_money
from modules.core.services.whatsapp import build_payment_reminder_url


def build_collection_rows(*, as_of: date) -> list[dict]:
    settings = BusinessSettings.get_solo()
    sales = (
        Sale.objects.filter(installments__due_date__lte=as_of)
        .filter(sale_effective_filter(as_of))
        .select_related("customer", "product")
        .prefetch_related(
            "installments",
            "late_fee_pause_periods",
            *installment_balance_prefetches("installments"),
        )
        .distinct()
    )

    rows = []
    for sale in sales:
        due_parts = []
        for installment in sale.installments.all():
            if installment.due_date > as_of:
                continue
            balance = get_installment_balance(installment, as_of=as_of)
            if balance.total_due > ZERO:
                due_parts.append((installment, balance))

        if not due_parts:
            continue
        oldest_installment, oldest_balance = min(
            due_parts,
            key=lambda item: (item[0].due_date, item[0].number, item[0].pk),
        )
        total_due = as_money(sum((balance.total_due for _, balance in due_parts), Decimal("0.00")))
        capital_due = as_money(
            sum((balance.principal_due for _, balance in due_parts), Decimal("0.00"))
        )
        late_fees_due = as_money(
            sum((balance.late_fees_due for _, balance in due_parts), Decimal("0.00"))
        )
        days_overdue = max(balance.days_overdue for _, balance in due_parts)
        pause_periods = list(sale.late_fee_pause_periods.all())
        pause_period = next(
            (
                period
                for period in pause_periods
                if period.paused_from <= as_of
                and (period.resumed_at is None or as_of < period.resumed_at)
            ),
            None,
        )
        active_pause = next(
            (period for period in pause_periods if period.resumed_at is None),
            None,
        )
        rows.append(
            {
                "sale": sale,
                "customer": sale.customer,
                "oldest_installment": oldest_installment,
                "oldest_balance": oldest_balance,
                "due_installment_count": len(due_parts),
                "total_due": total_due,
                "capital_due": capital_due,
                "late_fees_due": late_fees_due,
                "days_overdue": days_overdue,
                "has_installment_today": any(
                    installment.due_date == as_of for installment, _ in due_parts
                ),
                "late_fee_pause_period": pause_period,
                "active_late_fee_pause": active_pause,
                "whatsapp_url": build_payment_reminder_url(
                    customer=sale.customer,
                    amount=total_due,
                    due_date=oldest_installment.due_date,
                    settings=settings,
                ),
            }
        )

    return sorted(
        rows,
        key=lambda row: (
            -row["days_overdue"],
            row["customer"].last_name,
            row["customer"].first_name,
            row["sale"].pk,
        ),
    )


def group_collection_rows_by_customer(rows: list[dict]) -> list[dict]:
    """Collapse sale-level collection rows into one selectable/printable customer row."""
    grouped: dict[int, dict] = {}
    for row in rows:
        customer = row["customer"]
        customer_row = grouped.setdefault(
            customer.pk,
            {
                "customer": customer,
                "sale_rows": [],
                "total_due": ZERO,
                "capital_due": ZERO,
                "late_fees_due": ZERO,
                "days_overdue": 0,
                "has_installment_today": False,
            },
        )
        customer_row["sale_rows"].append(row)
        customer_row["total_due"] = as_money(customer_row["total_due"] + row["total_due"])
        customer_row["capital_due"] = as_money(customer_row["capital_due"] + row["capital_due"])
        customer_row["late_fees_due"] = as_money(
            customer_row["late_fees_due"] + row["late_fees_due"]
        )
        customer_row["days_overdue"] = max(
            customer_row["days_overdue"],
            row["days_overdue"],
        )
        customer_row["has_installment_today"] = (
            customer_row["has_installment_today"] or row["has_installment_today"]
        )

    return sorted(
        grouped.values(),
        key=lambda row: (
            -row["days_overdue"],
            row["customer"].last_name,
            row["customer"].first_name,
            row["customer"].pk,
        ),
    )


def build_customer_collection_rows(*, as_of: date) -> list[dict]:
    return group_collection_rows_by_customer(build_collection_rows(as_of=as_of))
