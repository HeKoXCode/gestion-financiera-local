from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from modules.core.models import Payment, Sale
from modules.core.services.balances import get_installment_balance
from modules.core.services.money import ZERO, as_money


def _sum_payments(*, start: date, end: date):
    amounts = Payment.objects.filter(
        status=Payment.Status.REGISTERED,
        payment_date__gte=start,
        payment_date__lte=end,
    ).values_list("amount", flat=True)
    return as_money(sum(amounts, ZERO))


def build_reports(*, as_of: date) -> dict:
    """Build a financial snapshot using only information known by ``as_of``."""
    week_start = as_of - timedelta(days=as_of.weekday())
    month_start = as_of.replace(day=1)
    trend_start = as_of - timedelta(days=6)

    collected_today = _sum_payments(start=as_of, end=as_of)
    collected_week = _sum_payments(start=week_start, end=as_of)
    collected_month = _sum_payments(start=month_start, end=as_of)

    sales = list(
        Sale.objects.exclude(status=Sale.Status.CANCELLED)
        .filter(delivery_date__lte=as_of)
        .select_related("customer", "product")
        .prefetch_related(
            "installments",
            "installments__late_fees",
            "installments__payment_allocations",
        )
        .order_by("customer__last_name", "customer__first_name", "pk")
    )
    customer_rows = {}
    product_rows = {}
    portfolio_pending = ZERO
    due_total = ZERO
    overdue_total = ZERO
    open_sales = 0

    for sale in sales:
        balances = [
            (installment, get_installment_balance(installment, as_of=as_of))
            for installment in sale.installments.all()
        ]
        sale_balance = as_money(
            sum((balance.total_due for _, balance in balances), ZERO)
        )

        product_row = product_rows.setdefault(
            sale.product_id,
            {
                "product": sale.product,
                "units": 0,
                "financed": ZERO,
                "pending": ZERO,
            },
        )
        product_row["units"] += 1
        product_row["financed"] += sale.financed_amount
        product_row["pending"] += sale_balance

        if sale_balance <= ZERO:
            continue

        open_sales += 1
        portfolio_pending += sale_balance
        row = customer_rows.setdefault(
            sale.customer_id,
            {
                "customer": sale.customer,
                "total_balance": ZERO,
                "due_total": ZERO,
                "overdue_total": ZERO,
                "late_fees_due": ZERO,
                "max_days_overdue": 0,
                "open_sales": 0,
            },
        )
        row["total_balance"] += sale_balance
        row["open_sales"] += 1

        for installment, balance in balances:
            if installment.due_date <= as_of:
                row["due_total"] += balance.total_due
                due_total += balance.total_due
            if installment.due_date < as_of and balance.total_due > ZERO:
                row["overdue_total"] += balance.total_due
                row["late_fees_due"] += balance.late_fees_due
                row["max_days_overdue"] = max(
                    row["max_days_overdue"],
                    balance.days_overdue,
                )
                overdue_total += balance.total_due

    normalized_customers = []
    for row in customer_rows.values():
        normalized_customers.append(
            {
                **row,
                "total_balance": as_money(row["total_balance"]),
                "due_total": as_money(row["due_total"]),
                "overdue_total": as_money(row["overdue_total"]),
                "late_fees_due": as_money(row["late_fees_due"]),
            }
        )

    debtors = sorted(
        (
            row
            for row in normalized_customers
            if row["overdue_total"] > ZERO
        ),
        key=lambda row: (
            -row["overdue_total"],
            -row["total_balance"],
            row["customer"].last_name,
            row["customer"].first_name,
        ),
    )
    up_to_date = sorted(
        (
            row
            for row in normalized_customers
            if row["overdue_total"] <= ZERO
        ),
        key=lambda row: (
            row["customer"].last_name,
            row["customer"].first_name,
        ),
    )
    highest_debt = sorted(
        normalized_customers,
        key=lambda row: (
            -row["total_balance"],
            row["customer"].last_name,
            row["customer"].first_name,
        ),
    )

    products_most_sold = sorted(
        (
            {
                **row,
                "financed": as_money(row["financed"]),
                "pending": as_money(row["pending"]),
            }
            for row in product_rows.values()
        ),
        key=lambda row: (-row["units"], -row["financed"], row["product"].name),
    )

    trend_payments = Payment.objects.filter(
        status=Payment.Status.REGISTERED,
        payment_date__gte=trend_start,
        payment_date__lte=as_of,
    )
    trend_amounts = Counter()
    for payment_date, amount in trend_payments.values_list("payment_date", "amount"):
        trend_amounts[payment_date] += amount
    trend_max = max(trend_amounts.values(), default=ZERO)
    collection_trend = []
    for offset in range(7):
        current_date = trend_start + timedelta(days=offset)
        amount = as_money(trend_amounts[current_date])
        height = round((amount / trend_max) * 100) if trend_max > ZERO else 0
        collection_trend.append(
            {
                "date": current_date,
                "amount": amount,
                "height": max(4, height) if amount > ZERO else 0,
            }
        )

    method_amounts = Counter()
    month_payments = Payment.objects.filter(
        status=Payment.Status.REGISTERED,
        payment_date__gte=month_start,
        payment_date__lte=as_of,
    )
    for method, amount in month_payments.values_list("payment_method", "amount"):
        method_amounts[method] += amount
    payment_methods = [
        {"name": method, "amount": as_money(amount)}
        for method, amount in sorted(
            method_amounts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]

    return {
        "collected_today": collected_today,
        "collected_week": collected_week,
        "collected_month": collected_month,
        "portfolio_pending": as_money(portfolio_pending),
        "due_total": as_money(due_total),
        "overdue_total": as_money(overdue_total),
        "overdue_clients": len(debtors),
        "up_to_date_clients": len(up_to_date),
        "open_sales": open_sales,
        "debtors": debtors,
        "up_to_date": up_to_date,
        "highest_debt": highest_debt,
        "products_most_sold": products_most_sold,
        "collection_trend": collection_trend,
        "payment_methods": payment_methods,
        "week_start": week_start,
        "month_start": month_start,
    }
