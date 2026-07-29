from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

from modules.core.models import Installment, Sale
from modules.core.services.balances import (
    get_installment_balance,
    installment_balance_prefetches,
)
from modules.core.services.collection import build_collection_rows
from modules.core.services.money import ZERO, as_money


def week_dates(containing_date: date) -> list[date]:
    monday = containing_date - timedelta(days=containing_date.weekday())
    return [monday + timedelta(days=offset) for offset in range(6)]


def build_weekly_agenda(*, containing_date: date, today: date) -> dict:
    dates = week_dates(containing_date)
    installments_by_date: dict[date, list[Installment]] = defaultdict(list)
    exact_installments = (
        Installment.objects.select_related("sale", "sale__customer")
        .prefetch_related(*installment_balance_prefetches())
        .filter(due_date__range=(dates[0], dates[-1]))
    )
    for installment in exact_installments:
        installments_by_date[installment.due_date].append(installment)

    days = []
    weekly_scheduled_amount = ZERO
    weekly_scheduled_installments = 0
    weekly_scheduled_customers: set[int] = set()

    for current_date in dates:
        rows = build_collection_rows(as_of=current_date)
        route_customers = {row["customer"].pk: row["customer"] for row in rows}
        overdue_customer_ids = {
            row["customer"].pk for row in rows if row["days_overdue"] > 0
        }
        carryover_customer_ids = {
            row["customer"].pk
            for row in rows
            if not row["has_installment_today"] and row["days_overdue"] > 0
        }

        scheduled_amount = ZERO
        scheduled_installments = 0
        scheduled_customer_ids: set[int] = set()
        for installment in installments_by_date[current_date]:
            if (
                installment.sale.status == Sale.Status.CANCELLED
                and installment.sale.cancelled_on <= current_date
            ):
                continue
            balance = get_installment_balance(installment, as_of=current_date)
            if balance.total_due <= ZERO:
                continue
            scheduled_amount += balance.total_due
            scheduled_installments += 1
            scheduled_customer_ids.add(installment.sale.customer_id)

        neighborhood_counts = Counter(
            customer.neighborhood or "Sin barrio"
            for customer in route_customers.values()
        )
        neighborhoods = [
            {"name": name, "count": count}
            for name, count in sorted(
                neighborhood_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        route_total = as_money(sum((row["total_due"] for row in rows), ZERO))

        days.append(
            {
                "date": current_date,
                "is_selected": current_date == containing_date,
                "is_today": current_date == today,
                "is_past": current_date < today,
                "client_count": len(route_customers),
                "scheduled_client_count": len(scheduled_customer_ids),
                "scheduled_installments": scheduled_installments,
                "scheduled_amount": as_money(scheduled_amount),
                "overdue_client_count": len(overdue_customer_ids),
                "carryover_client_count": len(carryover_customer_ids),
                "route_total": route_total,
                "neighborhoods": neighborhoods,
                "has_collection": bool(rows),
            }
        )
        weekly_scheduled_amount += scheduled_amount
        weekly_scheduled_installments += scheduled_installments
        weekly_scheduled_customers.update(scheduled_customer_ids)

    busiest_day = max(days, key=lambda day: day["client_count"])
    if busiest_day["client_count"] == 0:
        busiest_day = None

    return {
        "week_days": days,
        "week_start": dates[0],
        "week_end": dates[-1],
        "previous_week": dates[0] - timedelta(days=7),
        "next_week": dates[0] + timedelta(days=7),
        "weekly_scheduled_customers": len(weekly_scheduled_customers),
        "weekly_scheduled_installments": weekly_scheduled_installments,
        "weekly_scheduled_amount": as_money(weekly_scheduled_amount),
        "busiest_day": busiest_day,
    }
