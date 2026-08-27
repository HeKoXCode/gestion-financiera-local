from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from modules.core.models import Payment, PaymentAllocation, Sale
from modules.core.services.balances import (
    get_installment_balance,
    get_installment_payment_timing,
    installment_balance_prefetches,
    sale_effective_filter,
)
from modules.core.services.money import ZERO, as_money

AGING_BUCKETS = (
    ("not_due", "Al día / no vencido", None, 0),
    ("1_30", "1–30 días", 1, 30),
    ("31_60", "31–60 días", 31, 60),
    ("61_90", "61–90 días", 61, 90),
    ("90_plus", "Más de 90 días", 91, None),
)


def _aging_key(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "not_due"
    if days_overdue <= 30:
        return "1_30"
    if days_overdue <= 60:
        return "31_60"
    if days_overdue <= 90:
        return "61_90"
    return "90_plus"


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= ZERO:
        return ZERO
    return (numerator / denominator * Decimal("100")).quantize(Decimal("0.01"))


def build_analytics(*, as_of: date) -> dict:
    """Build one reconciled portfolio snapshot for dashboard and BI exports."""
    sales = list(
        Sale.objects.filter(sale_effective_filter(as_of))
        .filter(delivery_date__lte=as_of)
        .select_related("customer", "product")
        .prefetch_related(
            "installments",
            *installment_balance_prefetches("installments"),
        )
        .order_by("delivery_date", "pk")
    )

    aging = {
        key: {
            "key": key,
            "label": label,
            "minimum_days": minimum,
            "maximum_days": maximum,
            "installments": 0,
            "customers": set(),
            "principal_due": ZERO,
            "late_fees_due": ZERO,
            "total_due": ZERO,
        }
        for key, label, minimum, maximum in AGING_BUCKETS
    }
    cohorts = defaultdict(
        lambda: {
            "sales": 0,
            "customers": set(),
            "principal_originated": ZERO,
            "principal_collected": ZERO,
            "principal_outstanding": ZERO,
            "principal_overdue": ZERO,
        }
    )
    portfolio_principal = ZERO
    portfolio_late_fees = ZERO
    portfolio_total = ZERO
    principal_originated = ZERO
    principal_collected = ZERO
    overdue_total = ZERO
    installment_count = 0
    paid_installments = 0
    on_time_installments = 0
    late_paid_installments = 0
    overdue_installments = 0

    for sale in sales:
        cohort_key = sale.delivery_date.replace(day=1)
        cohort = cohorts[cohort_key]
        cohort["sales"] += 1
        cohort["customers"].add(sale.customer_id)
        cohort["principal_originated"] += sale.financed_amount
        principal_originated += sale.financed_amount

        for installment in sale.installments.all():
            installment_count += 1
            balance = get_installment_balance(installment, as_of=as_of)
            timing = get_installment_payment_timing(installment, as_of=as_of)
            principal_collected += balance.principal_paid
            cohort["principal_collected"] += balance.principal_paid
            cohort["principal_outstanding"] += balance.principal_due
            portfolio_principal += balance.principal_due
            portfolio_late_fees += balance.late_fees_due
            portfolio_total += balance.total_due

            if timing.paid_on is not None:
                paid_installments += 1
                if timing.days_late == 0:
                    on_time_installments += 1
                else:
                    late_paid_installments += 1

            if balance.total_due <= ZERO:
                continue
            days_overdue = max(0, (as_of - installment.due_date).days)
            key = _aging_key(days_overdue)
            bucket = aging[key]
            bucket["installments"] += 1
            bucket["customers"].add(sale.customer_id)
            bucket["principal_due"] += balance.principal_due
            bucket["late_fees_due"] += balance.late_fees_due
            bucket["total_due"] += balance.total_due
            if days_overdue > 0:
                overdue_installments += 1
                overdue_total += balance.total_due
                cohort["principal_overdue"] += balance.principal_due

    aging_rows = []
    for key, *_ in AGING_BUCKETS:
        row = aging[key]
        total_due = as_money(row["total_due"])
        aging_rows.append(
            {
                **row,
                "customers": len(row["customers"]),
                "principal_due": as_money(row["principal_due"]),
                "late_fees_due": as_money(row["late_fees_due"]),
                "total_due": total_due,
                "share": _ratio(total_due, portfolio_total),
                "bar_width": max(2, int(_ratio(total_due, portfolio_total)))
                if total_due > ZERO
                else 0,
            }
        )

    cohort_rows = []
    for cohort_month, row in sorted(cohorts.items(), reverse=True):
        origin = as_money(row["principal_originated"])
        collected = as_money(row["principal_collected"])
        outstanding = as_money(row["principal_outstanding"])
        overdue = as_money(row["principal_overdue"])
        cohort_rows.append(
            {
                **row,
                "cohort_month": cohort_month,
                "customers": len(row["customers"]),
                "principal_originated": origin,
                "principal_collected": collected,
                "principal_outstanding": outstanding,
                "principal_overdue": overdue,
                "recovery_rate": _ratio(collected, origin),
                "overdue_rate": _ratio(overdue, origin),
            }
        )

    collected_payments = as_money(
        sum(
            Payment.objects.filter(
                sale_effective_filter(as_of, "sale"),
                status=Payment.Status.REGISTERED,
                kind=Payment.Kind.INSTALLMENT,
                payment_date__lte=as_of,
            ).values_list("amount", flat=True),
            ZERO,
        )
    )
    allocated_collections = as_money(
        sum(
            PaymentAllocation.objects.filter(
                sale_effective_filter(as_of, "payment__sale"),
                payment__status=Payment.Status.REGISTERED,
                payment__kind=Payment.Kind.INSTALLMENT,
                payment__payment_date__lte=as_of,
            ).values_list("amount", flat=True),
            ZERO,
        )
    )
    reconciliation = {
        "aging_vs_portfolio": as_money(
            sum((row["total_due"] for row in aging_rows), ZERO) - portfolio_total
        ),
        "cohorts_vs_principal": as_money(
            sum((row["principal_outstanding"] for row in cohort_rows), ZERO)
            - portfolio_principal
        ),
        "payments_vs_allocations": as_money(collected_payments - allocated_collections),
    }
    reconciliation["passed"] = all(value == ZERO for value in reconciliation.values())

    return {
        "as_of": as_of,
        "aging_rows": aging_rows,
        "cohort_rows": cohort_rows,
        "portfolio_principal": as_money(portfolio_principal),
        "portfolio_late_fees": as_money(portfolio_late_fees),
        "portfolio_total": as_money(portfolio_total),
        "overdue_total": as_money(overdue_total),
        "principal_originated": as_money(principal_originated),
        "principal_collected": as_money(principal_collected),
        "recovery_rate": _ratio(principal_collected, principal_originated),
        "overdue_rate": _ratio(overdue_total, portfolio_total),
        "installment_count": installment_count,
        "paid_installments": paid_installments,
        "on_time_installments": on_time_installments,
        "late_paid_installments": late_paid_installments,
        "overdue_installments": overdue_installments,
        "on_time_rate": _ratio(Decimal(on_time_installments), Decimal(paid_installments)),
        "active_customers": len({sale.customer_id for sale in sales}),
        "reconciliation": reconciliation,
    }
