from __future__ import annotations

from datetime import date
from decimal import Decimal

from modules.core.models import Sale
from modules.core.services.balances import get_installment_balance
from modules.core.services.money import ZERO, as_money
from modules.core.services.whatsapp import build_payment_reminder_url


def build_collection_rows(*, as_of: date) -> list[dict]:
    sales = (
        Sale.objects.filter(installments__due_date__lte=as_of)
        .exclude(status=Sale.Status.CANCELLED)
        .select_related("customer", "product")
        .prefetch_related("installments")
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
            key=lambda part: (part[0].due_date, part[0].number),
        )
        total_due = as_money(
            sum((balance.total_due for _, balance in due_parts), Decimal("0.00"))
        )
        capital_due = as_money(
            sum((balance.principal_due for _, balance in due_parts), Decimal("0.00"))
        )
        late_fees_due = as_money(
            sum((balance.late_fees_due for _, balance in due_parts), Decimal("0.00"))
        )
        days_overdue = max(balance.days_overdue for _, balance in due_parts)
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
                "whatsapp_url": build_payment_reminder_url(
                    customer=sale.customer,
                    amount=total_due,
                    due_date=oldest_installment.due_date,
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
