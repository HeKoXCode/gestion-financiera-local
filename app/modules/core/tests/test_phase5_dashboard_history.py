import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from modules.core.models import CollectionAttempt, Sale
from modules.core.services.installments import create_installments
from modules.core.services.payments import register_payment, void_payment
from modules.core.tests.factories import make_product, make_sale

pytestmark = pytest.mark.django_db


def make_todays_sale(
    *,
    amount=Decimal("20000.00"),
    installment_count=1,
    first_due_offset=0,
    **sale_overrides,
):
    today = timezone.localdate()
    sale = make_sale(
        delivery_date=today - timedelta(days=30),
        first_due_date=today + timedelta(days=first_due_offset),
        financed_amount=amount,
        installment_count=installment_count,
        daily_late_fee=Decimal("0.00"),
        **sale_overrides,
    )
    create_installments(sale)
    return sale


def pay(sale, amount=Decimal("5000.00")):
    return register_payment(
        sale=sale,
        amount=amount,
        payment_date=timezone.localdate(),
        payment_method="Efectivo",
        notes="Pago de prueba",
        operation_key=uuid.uuid4(),
    ).payment


def test_dashboard_combines_pending_collection_and_registered_payments(client):
    sale = make_todays_sale()
    pay(sale)

    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert response.context["clients_to_collect"] == 1
    assert response.context["remaining_to_collect"] == Decimal("15000.00")
    assert response.context["collected_amount"] == Decimal("5000.00")
    assert response.context["day_target"] == Decimal("20000.00")
    assert response.context["collection_progress"] == 25
    assert response.context["portfolio_total"] == Decimal("15000.00")


def test_dashboard_portfolio_includes_future_installments(client):
    make_todays_sale(amount=Decimal("40000.00"), installment_count=2)

    response = client.get(reverse("core:home"))

    assert response.context["remaining_to_collect"] == Decimal("20000.00")
    assert response.context["portfolio_total"] == Decimal("40000.00")
    assert response.context["scheduled_today_count"] == 1


def test_agenda_shows_programmed_installments_for_each_day_of_the_week(client):
    today = timezone.localdate()
    monday = today - timedelta(days=today.weekday()) + timedelta(days=7)
    thursday = monday + timedelta(days=3)
    product = make_product()
    make_todays_sale(
        amount=Decimal("20000.00"),
        first_due_offset=(monday - today).days,
        product=product,
    )
    make_todays_sale(
        amount=Decimal("30000.00"),
        first_due_offset=(thursday - today).days,
        product=product,
    )

    response = client.get(
        reverse("core:agenda"),
        {"fecha": monday.isoformat()},
    )
    days = {day["date"]: day for day in response.context["week_days"]}

    assert response.status_code == 200
    assert response.context["weekly_scheduled_customers"] == 2
    assert response.context["weekly_scheduled_installments"] == 2
    assert response.context["weekly_scheduled_amount"] == Decimal("50000.00")
    assert days[monday]["scheduled_amount"] == Decimal("20000.00")
    assert days[monday]["route_total"] == Decimal("20000.00")
    assert days[thursday]["scheduled_amount"] == Decimal("30000.00")
    assert days[thursday]["route_total"] == Decimal("50000.00")
    assert days[thursday]["overdue_client_count"] == 1
    assert "Vista semanal" in response.content.decode()


def test_agenda_week_covers_monday_through_saturday(client):
    response = client.get(reverse("core:agenda"))
    week_days = response.context["week_days"]

    assert len(week_days) == 6
    assert week_days[0]["date"].weekday() == 0
    assert week_days[-1]["date"].weekday() == 5


def test_customer_history_consolidates_sales_payments_and_visits(client):
    sale = make_todays_sale()
    pay(sale)
    CollectionAttempt.objects.create(
        customer=sale.customer,
        sale=sale,
        attempt_date=timezone.localdate(),
        result=CollectionAttempt.Result.PROMISED,
        notes="Completa el saldo por la tarde",
    )

    response = client.get(reverse("core:customer_detail", args=[sale.customer_id]))
    event_titles = {event["title"] for event in response.context["events"]}

    assert response.status_code == 200
    assert response.context["total_financed"] == Decimal("20000.00")
    assert response.context["total_paid"] == Decimal("5000.00")
    assert response.context["total_balance"] == Decimal("15000.00")
    assert response.context["active_sales"] == 1
    assert {"Venta entregada", "Pago registrado", "Prometió pagar"} <= event_titles


def test_voided_payment_is_excluded_from_total_but_stays_in_timeline(client):
    sale = make_todays_sale()
    payment = pay(sale)
    void_payment(payment=payment, reason="Transferencia rechazada")

    response = client.get(reverse("core:customer_detail", args=[sale.customer_id]))
    event_kinds = {event["kind"] for event in response.context["events"]}

    assert response.context["total_paid"] == Decimal("0.00")
    assert response.context["total_balance"] == Decimal("20000.00")
    assert "payment_voided" in event_kinds


def test_cancelled_sale_remains_visible_but_is_not_exigible(client):
    sale = make_todays_sale()
    sale.status = Sale.Status.CANCELLED
    sale.cancelled_on = timezone.localdate()
    sale.cancellation_reason = "Operación cancelada por el cliente"
    sale.full_clean()
    sale.save()

    response = client.get(reverse("core:customer_detail", args=[sale.customer_id]))

    assert len(response.context["sale_rows"]) == 1
    assert response.context["sale_rows"][0]["exigible_total"] == Decimal("0.00")
    assert response.context["total_financed"] == Decimal("0.00")
    assert response.context["total_balance"] == Decimal("0.00")
    assert any(event["kind"] == "cancelled" for event in response.context["events"])


def test_customer_history_marks_overdue_installments(client):
    sale = make_todays_sale(first_due_offset=-1)

    response = client.get(reverse("core:customer_detail", args=[sale.customer_id]))

    assert response.context["overdue_installments"] == 1
    assert response.context["installment_rows"][0]["status"] == "overdue"
    assert "1 día tarde" in response.context["installment_rows"][0]["status_label"]
