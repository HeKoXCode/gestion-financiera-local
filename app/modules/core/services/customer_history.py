from __future__ import annotations

from datetime import date

from modules.core.models import Customer, Payment, Sale
from modules.core.services.balances import (
    get_installment_balance,
    get_sale_balance,
    installment_balance_prefetches,
)
from modules.core.services.money import ZERO, as_money


def build_customer_history(*, customer: Customer, as_of: date) -> dict:
    sales = list(
        customer.sales.select_related("product")
        .prefetch_related(
            "installments",
            *installment_balance_prefetches("installments"),
        )
        .order_by("-delivery_date", "-pk")
    )
    sale_rows = []
    installment_rows = []
    total_installments = ZERO
    total_balance = ZERO
    overdue_installments = 0
    paid_installments = 0

    for sale in sales:
        balance = get_sale_balance(sale, as_of=as_of)
        is_cancelled = sale.status == Sale.Status.CANCELLED
        exigible_total = ZERO if is_cancelled else balance.total_due
        if not is_cancelled:
            total_installments += sale.financed_amount
            total_balance += balance.total_due

        sale_rows.append(
            {
                "sale": sale,
                "balance": balance,
                "exigible_total": as_money(exigible_total),
            }
        )
        for installment in sale.installments.all():
            installment_balance = get_installment_balance(installment, as_of=as_of)
            if is_cancelled:
                status = "cancelled"
                status_label = "Cancelada"
            elif installment_balance.total_due <= ZERO:
                status = "paid"
                status_label = "Pagada"
                paid_installments += 1
            elif installment.due_date < as_of:
                status = "overdue"
                day_word = "día" if installment_balance.days_overdue == 1 else "días"
                status_label = f"{installment_balance.days_overdue} {day_word} de atraso"
                overdue_installments += 1
            elif installment.due_date == as_of:
                status = "today"
                status_label = "Vence hoy"
            else:
                status = "pending"
                status_label = "Pendiente"

            installment_rows.append(
                {
                    "sale": sale,
                    "installment": installment,
                    "balance": installment_balance,
                    "status": status,
                    "status_label": status_label,
                }
            )

    payments = list(
        customer.payments.select_related("sale").order_by("-payment_date", "-created_at", "-pk")
    )
    attempts = list(
        customer.collection_attempts.select_related("sale").order_by(
            "-attempt_date", "-created_at", "-pk"
        )
    )
    total_paid = as_money(
        sum(
            (payment.amount for payment in payments if payment.status == Payment.Status.REGISTERED),
            ZERO,
        )
    )

    events = []
    for sale in sales:
        events.append(
            {
                "date": sale.delivery_date,
                "kind": "sale",
                "title": "Venta entregada",
                "detail": sale.product_description,
                "amount": sale.operation_total,
                "sale": sale,
            }
        )
        if sale.status == Sale.Status.CANCELLED and sale.cancelled_on:
            events.append(
                {
                    "date": sale.cancelled_on,
                    "kind": "cancelled",
                    "title": "Venta cancelada",
                    "detail": sale.cancellation_reason,
                    "amount": None,
                    "sale": sale,
                }
            )
    for payment in payments:
        is_initial = payment.kind == Payment.Kind.INITIAL
        events.append(
            {
                "date": payment.payment_date,
                "kind": (
                    "payment" if payment.status == Payment.Status.REGISTERED else "payment_voided"
                ),
                "title": (
                    ("Pago inicial" if is_initial else "Pago de cuota")
                    if payment.status == Payment.Status.REGISTERED
                    else ("Pago inicial anulado" if is_initial else "Pago de cuota anulado")
                ),
                "detail": payment.notes or payment.payment_method,
                "amount": payment.amount,
                "sale": payment.sale,
            }
        )
    for attempt in attempts:
        events.append(
            {
                "date": attempt.attempt_date,
                "kind": "attempt",
                "title": attempt.get_result_display(),
                "detail": attempt.notes or "Sin observaciones",
                "amount": None,
                "sale": attempt.sale,
            }
        )
    events.sort(key=lambda event: (event["date"], event["kind"]), reverse=True)

    return {
        "sale_rows": sale_rows,
        "installment_rows": installment_rows,
        "payments": payments,
        "attempts": attempts,
        "events": events,
        "total_installments": as_money(total_installments),
        # Kept temporarily for compatibility with older integrations.
        "total_financed": as_money(total_installments),
        "total_paid": total_paid,
        "total_balance": as_money(total_balance),
        "overdue_installments": overdue_installments,
        "paid_installments": paid_installments,
        "active_sales": sum(sale.status == Sale.Status.ACTIVE for sale in sales),
        "product_count": len(
            {sale.product_id for sale in sales if sale.status != Sale.Status.CANCELLED}
        ),
    }
