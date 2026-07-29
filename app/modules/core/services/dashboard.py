from __future__ import annotations

from datetime import date, timedelta

from modules.core.models import CollectionAttempt, Installment, Payment, Sale
from modules.core.services.balances import (
    get_sale_balance,
    installment_balance_prefetches,
    registered_payment_filter,
    sale_effective_filter,
)
from modules.core.services.collection import build_collection_rows
from modules.core.services.money import ZERO, as_money


def build_dashboard(*, as_of: date) -> dict:
    collection_rows = build_collection_rows(as_of=as_of)
    overdue_rows = [row for row in collection_rows if row["days_overdue"] > 0]
    registered_payments = Payment.objects.filter(
        registered_payment_filter(as_of),
        payment_date=as_of,
    )
    installment_payments = registered_payments.filter(
        kind=Payment.Kind.INSTALLMENT,
    )
    initial_payments = registered_payments.filter(
        kind=Payment.Kind.INITIAL,
    )

    remaining_to_collect = as_money(
        sum((row["total_due"] for row in collection_rows), ZERO)
    )
    collected_amount = as_money(
        sum(registered_payments.values_list("amount", flat=True), ZERO)
    )
    installment_collected_amount = as_money(
        sum(installment_payments.values_list("amount", flat=True), ZERO)
    )
    initial_collected_amount = as_money(
        sum(initial_payments.values_list("amount", flat=True), ZERO)
    )
    day_target = as_money(remaining_to_collect + installment_collected_amount)
    collection_progress = (
        min(100, round((installment_collected_amount / day_target) * 100))
        if day_target > ZERO
        else 0
    )

    portfolio_sales = (
        Sale.objects.filter(
            sale_effective_filter(as_of),
            delivery_date__lte=as_of,
        )
        .prefetch_related(
            "installments",
            *installment_balance_prefetches("installments"),
        )
    )
    portfolio_balances = [
        get_sale_balance(sale, as_of=as_of)
        for sale in portfolio_sales
    ]
    open_portfolio = [
        balance for balance in portfolio_balances if balance.total_due > ZERO
    ]
    portfolio_total = as_money(sum((balance.total_due for balance in open_portfolio), ZERO))
    upcoming_until = as_of + timedelta(days=7)

    return {
        "collection_rows": collection_rows,
        "priority_rows": collection_rows[:8],
        "clients_to_collect": len({row["customer"].pk for row in collection_rows}),
        "remaining_to_collect": remaining_to_collect,
        "overdue_clients": len({row["customer"].pk for row in overdue_rows}),
        "overdue_total": as_money(sum((row["total_due"] for row in overdue_rows), ZERO)),
        "collected_amount": collected_amount,
        "installment_collected_amount": installment_collected_amount,
        "initial_collected_amount": initial_collected_amount,
        "day_target": day_target,
        "collection_progress": collection_progress,
        "portfolio_total": portfolio_total,
        "active_sales_count": len(open_portfolio),
        "scheduled_today_count": sum(
            1 for row in collection_rows if row["has_installment_today"]
        ),
        "upcoming_installments": Installment.objects.filter(
            sale_effective_filter(as_of, "sale"),
            due_date__gt=as_of,
            due_date__lte=upcoming_until,
        ).count(),
        "visits_today": CollectionAttempt.objects.filter(attempt_date=as_of).count(),
        "recent_payments": Payment.objects.select_related("customer", "sale")
        .filter(
            registered_payment_filter(as_of),
            payment_date__lte=as_of,
        )
        .order_by("-payment_date", "-created_at")[:5],
    }
