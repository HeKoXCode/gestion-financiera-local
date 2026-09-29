from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.core.models import (
    CollectionAssignment,
    CollectionAttempt,
    CollectionRoute,
    Collector,
    CustomerCollectorLink,
    Payment,
)
from modules.core.services.collection import build_customer_collection_rows
from modules.core.services.money import ZERO, as_money


def create_collector(*, name: str) -> Collector:
    collector = Collector(name=" ".join(name.split()))
    collector.full_clean()
    collector.save()
    return collector


@transaction.atomic
def move_collector_to_safe_archive(*, collector: Collector, reason: str) -> Collector:
    collector = Collector.objects.select_for_update().get(pk=collector.pk)
    if collector.archived_at is not None:
        raise ValidationError("Este cobrador ya está guardado en el Archivo seguro.")
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValidationError("Indicá por qué se borra este cobrador.")

    collector.is_active = False
    collector.archived_at = timezone.now()
    collector.archive_reason = normalized_reason
    collector.save(
        update_fields=[
            "is_active",
            "archived_at",
            "archive_reason",
            "updated_at",
        ]
    )
    closed_on = timezone.localdate()
    active_links = list(
        CustomerCollectorLink.objects.select_for_update().filter(
            collector=collector,
            ended_at__isnull=True,
        )
    )
    updated_at = timezone.now()
    for link in active_links:
        link.ended_at = max(closed_on, link.started_at)
        link.reason = "Finalizado al archivar al cobrador"
        link.updated_at = updated_at
        link.full_clean()
    if active_links:
        CustomerCollectorLink.objects.bulk_update(
            active_links,
            ["ended_at", "reason", "updated_at"],
        )
    return collector


def _set_habitual_collector(
    *,
    customer_id: int,
    collector: Collector,
    source_route: CollectionRoute,
) -> CustomerCollectorLink:
    changed_on = timezone.localdate()
    current = (
        CustomerCollectorLink.objects.select_for_update()
        .filter(customer_id=customer_id, ended_at__isnull=True)
        .first()
    )
    if current and current.collector_id == collector.pk:
        if current.source_route_id != source_route.pk:
            current.source_route = source_route
            current.save(update_fields=["source_route", "updated_at"])
        return current
    if current:
        current.ended_at = max(changed_on, current.started_at)
        current.reason = f"{current.reason} · Reasignado desde Preparar planillas"
        current.full_clean()
        current.save(update_fields=["ended_at", "reason", "updated_at"])
    link = CustomerCollectorLink(
        customer_id=customer_id,
        collector=collector,
        started_at=changed_on,
        source_route=source_route,
        reason=f"Asignado al guardar la planilla del {source_route.collection_date:%d/%m/%Y}",
    )
    link.full_clean()
    link.save()
    return link


def build_assignment_snapshot(customer_row: dict) -> dict:
    customer = customer_row["customer"]
    items = []
    for row in customer_row["sale_rows"]:
        items.append(
            {
                "sale_id": row["sale"].pk,
                "product": row["sale"].product_description,
                "oldest_installment": row["oldest_installment"].number,
                "installment_count": row["sale"].installment_count,
                "due_installment_count": row["due_installment_count"],
                "total_due": str(row["total_due"]),
                "late_fees_due": str(row["late_fees_due"]),
                "late_fee_paused": bool(row.get("late_fee_pause_period")),
            }
        )
    return {
        "customer_name": customer.full_name,
        "phone": customer.phone,
        "address": customer.address,
        "neighborhood": customer.neighborhood,
        "address_reference": customer.address_reference,
        "days_overdue": customer_row["days_overdue"],
        "has_installment_today": customer_row["has_installment_today"],
        "capital_due": str(customer_row["capital_due"]),
        "late_fees_due": str(customer_row["late_fees_due"]),
        "items": items,
    }


def get_collection_assignment(*, customer_id: int, collection_date: date):
    return (
        CollectionAssignment.objects.select_related("route", "route__collector")
        .filter(customer_id=customer_id, assigned_date=collection_date)
        .first()
    )


def _has_recorded_activity(assignment: CollectionAssignment) -> bool:
    return assignment.payments.exists() or assignment.attempts.exists()


def _link_existing_activity(assignment: CollectionAssignment) -> None:
    Payment.objects.filter(
        customer_id=assignment.customer_id,
        payment_date=assignment.assigned_date,
        kind=Payment.Kind.INSTALLMENT,
        is_advance=False,
        collector__isnull=True,
        collection_assignment__isnull=True,
    ).update(
        collector=assignment.route.collector,
        collection_assignment=assignment,
    )
    CollectionAttempt.objects.filter(
        customer_id=assignment.customer_id,
        attempt_date=assignment.assigned_date,
        collector__isnull=True,
        collection_assignment__isnull=True,
    ).update(
        collector=assignment.route.collector,
        collection_assignment=assignment,
    )


@transaction.atomic
def delete_collection_route(*, route: CollectionRoute) -> None:
    route = CollectionRoute.objects.select_for_update().get(pk=route.pk)
    assignments = list(route.assignments.select_for_update().select_related("customer"))
    protected = [item for item in assignments if _has_recorded_activity(item)]
    if protected:
        raise ValidationError(
            "El recorrido ya tiene pagos o visitas registrados y debe conservarse."
        )
    route.assignments.all().delete()
    route.delete()


@transaction.atomic
def save_collection_route(
    *,
    collection_date: date,
    collector: Collector,
    customer_ids: list[int],
    route: CollectionRoute | None = None,
) -> CollectionRoute:
    collector = Collector.objects.select_for_update().get(pk=collector.pk)
    if not collector.is_active:
        raise ValidationError("El cobrador está archivado y no admite nuevos recorridos.")

    selected_ids = {int(customer_id) for customer_id in customer_ids}
    if not selected_ids:
        raise ValidationError("Seleccioná al menos un cliente para preparar la planilla.")

    customer_rows = {
        row["customer"].pk: row for row in build_customer_collection_rows(as_of=collection_date)
    }
    day_assignments = list(
        CollectionAssignment.objects.select_for_update()
        .select_related("route", "route__collector", "customer")
        .filter(assigned_date=collection_date)
    )
    assignments_by_customer = {assignment.customer_id: assignment for assignment in day_assignments}

    if route is not None:
        route = CollectionRoute.objects.select_for_update().get(pk=route.pk)
        if route.collection_date != collection_date:
            raise ValidationError("El recorrido no pertenece a la fecha elegida.")
        if route.collector_id != collector.pk:
            raise ValidationError("No se puede cambiar el cobrador de un recorrido existente.")
    else:
        existing_route = (
            CollectionRoute.objects.select_for_update()
            .filter(
                collection_date=collection_date,
                collector=collector,
            )
            .first()
        )
        if existing_route is not None:
            raise ValidationError(
                "Ese cobrador ya tiene una planilla para la fecha. "
                "Abrí su tarjeta con ‘Cambiar clientes’."
            )
        route = CollectionRoute.objects.create(
            collection_date=collection_date,
            collector=collector,
        )

    existing_for_route = {
        assignment.customer_id: assignment
        for assignment in day_assignments
        if assignment.route_id == route.pk
    }
    allowed_ids = set(customer_rows) | set(existing_for_route)
    invalid_ids = selected_ids - allowed_ids
    if invalid_ids:
        raise ValidationError(
            "Uno de los clientes seleccionados ya no tiene cobros pendientes para esa fecha."
        )

    for customer_id in selected_ids:
        conflict = assignments_by_customer.get(customer_id)
        if conflict is None or conflict.route_id == route.pk:
            continue
        if _has_recorded_activity(conflict):
            raise ValidationError(
                f"{conflict.customer.full_name} ya tiene actividad registrada con "
                f"{conflict.route.collector.name}; no se puede reasignar."
            )
        conflict.delete()

    for customer_id, assignment in existing_for_route.items():
        if customer_id in selected_ids:
            continue
        if _has_recorded_activity(assignment):
            raise ValidationError(
                f"{assignment.customer.full_name} ya tiene pagos o visitas en este "
                "recorrido y no puede quitarse."
            )
        assignment.delete()

    for customer_id in selected_ids:
        customer_row = customer_rows.get(customer_id)
        assignment = existing_for_route.get(customer_id)
        if assignment is None:
            if customer_row is None:
                raise ValidationError("No se pudo recuperar el detalle del cliente elegido.")
            assignment = CollectionAssignment(
                route=route,
                customer=customer_row["customer"],
                assigned_date=collection_date,
                expected_amount=customer_row["total_due"],
                snapshot=build_assignment_snapshot(customer_row),
            )
        elif customer_row is not None and not _has_recorded_activity(assignment):
            assignment.expected_amount = customer_row["total_due"]
            assignment.snapshot = build_assignment_snapshot(customer_row)
        assignment.full_clean()
        assignment.save()
        _link_existing_activity(assignment)
        _set_habitual_collector(
            customer_id=customer_id,
            collector=collector,
            source_route=route,
        )

    return route


def assignment_print_row(assignment: CollectionAssignment) -> dict:
    snapshot = assignment.snapshot or {}
    items = snapshot.get("items") or []
    product_summary = " · ".join(item.get("product", "") for item in items if item.get("product"))
    if not product_summary:
        product_summary = "Cobranza asignada"
    return {
        "assignment": assignment,
        "customer_name": snapshot.get("customer_name") or assignment.customer.full_name,
        "phone": snapshot.get("phone") or assignment.customer.phone,
        "address": snapshot.get("address") or assignment.customer.address,
        "neighborhood": snapshot.get("neighborhood") or assignment.customer.neighborhood,
        "address_reference": (
            snapshot.get("address_reference") or assignment.customer.address_reference
        ),
        "days_overdue": int(snapshot.get("days_overdue") or 0),
        "expected_amount": assignment.expected_amount,
        "late_fees_due": Decimal(str(snapshot.get("late_fees_due") or "0.00")),
        "late_fee_paused": any(item.get("late_fee_paused") for item in items),
        "product_summary": product_summary,
        "items": items,
    }


def build_date_route_summaries(*, collection_date: date) -> list[dict]:
    routes = list(
        CollectionRoute.objects.select_related("collector")
        .prefetch_related("assignments", "assignments__customer")
        .filter(collection_date=collection_date)
        .order_by("collector__name", "pk")
    )
    collected_by_collector: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for collector_id, amount in Payment.objects.filter(
        payment_date=collection_date,
        status=Payment.Status.REGISTERED,
        kind=Payment.Kind.INSTALLMENT,
        collector__isnull=False,
    ).values_list("collector_id", "amount"):
        collected_by_collector[collector_id] = as_money(
            collected_by_collector[collector_id] + amount
        )
    visits_by_collector: dict[int, set[int]] = defaultdict(set)
    for collector_id, customer_id in CollectionAttempt.objects.filter(
        attempt_date=collection_date,
        collector__isnull=False,
    ).values_list("collector_id", "customer_id"):
        visits_by_collector[collector_id].add(customer_id)

    summaries = []
    for route in routes:
        assignments = list(route.assignments.all())
        summaries.append(
            {
                "route": route,
                "assignment_count": len(assignments),
                "expected_amount": as_money(
                    sum((item.expected_amount for item in assignments), ZERO)
                ),
                "collected_amount": collected_by_collector[route.collector_id],
                "visit_count": len(visits_by_collector[route.collector_id]),
            }
        )
    return summaries


def build_collector_overview(*, include_archived: bool = False) -> list[dict]:
    collectors_query = Collector.objects.prefetch_related(
        "routes__assignments",
        "payments_collected",
        "customer_links",
    )
    if not include_archived:
        collectors_query = collectors_query.filter(archived_at__isnull=True)
    collectors = list(collectors_query.order_by("name", "pk"))
    rows = []
    for collector in collectors:
        routes = list(collector.routes.all())
        assignments = [assignment for route in routes for assignment in route.assignments.all()]
        payments = [
            payment
            for payment in collector.payments_collected.all()
            if payment.status == Payment.Status.REGISTERED
            and payment.kind == Payment.Kind.INSTALLMENT
        ]
        rows.append(
            {
                "collector": collector,
                "days_worked": len({route.collection_date for route in routes}),
                "assignment_count": len(assignments),
                "unique_clients": len({item.customer_id for item in assignments}),
                "habitual_client_count": sum(
                    link.ended_at is None for link in collector.customer_links.all()
                ),
                "total_collected": as_money(sum((payment.amount for payment in payments), ZERO)),
                "last_route_date": max(
                    (route.collection_date for route in routes),
                    default=None,
                ),
            }
        )
    return rows


def build_collector_detail(*, collector: Collector) -> dict:
    routes = list(
        collector.routes.prefetch_related("assignments", "assignments__customer")
        .all()
        .order_by("-collection_date", "-pk")
    )
    payments = list(
        collector.payments_collected.select_related("customer", "sale")
        .filter(
            status=Payment.Status.REGISTERED,
            kind=Payment.Kind.INSTALLMENT,
        )
        .order_by("-payment_date", "-created_at", "-pk")
    )
    attempts = list(
        collector.collection_attempts.select_related("customer", "sale")
        .all()
        .order_by("-attempt_date", "-created_at", "-pk")
    )

    payments_by_date: dict[date, Decimal] = defaultdict(lambda: ZERO)
    paid_customers_by_date: dict[date, set[int]] = defaultdict(set)
    for payment in payments:
        payments_by_date[payment.payment_date] = as_money(
            payments_by_date[payment.payment_date] + payment.amount
        )
        paid_customers_by_date[payment.payment_date].add(payment.customer_id)
    attempts_by_date: dict[date, set[int]] = defaultdict(set)
    for attempt in attempts:
        attempts_by_date[attempt.attempt_date].add(attempt.customer_id)

    daily_rows = []
    customer_frequency: dict[int, dict] = {}
    for route in routes:
        assignments = list(route.assignments.all())
        expected_amount = as_money(
            sum((assignment.expected_amount for assignment in assignments), ZERO)
        )
        daily_rows.append(
            {
                "route": route,
                "assignment_count": len(assignments),
                "expected_amount": expected_amount,
                "collected_amount": payments_by_date[route.collection_date],
                "paid_client_count": len(paid_customers_by_date[route.collection_date]),
                "attempt_count": len(attempts_by_date[route.collection_date]),
            }
        )
        for assignment in assignments:
            item = customer_frequency.setdefault(
                assignment.customer_id,
                {
                    "customer": assignment.customer,
                    "assignment_count": 0,
                    "paid_visit_count": 0,
                    "attempt_count": 0,
                    "total_collected": ZERO,
                },
            )
            item["assignment_count"] += 1

    for payment in payments:
        item = customer_frequency.get(payment.customer_id)
        if item is None:
            continue
        item["total_collected"] = as_money(item["total_collected"] + payment.amount)
    for customer_id, item in customer_frequency.items():
        item["paid_visit_count"] = len(
            {payment.payment_date for payment in payments if payment.customer_id == customer_id}
        )
        item["attempt_count"] = len(
            {attempt.attempt_date for attempt in attempts if attempt.customer_id == customer_id}
        )

    frequent_customers = sorted(
        customer_frequency.values(),
        key=lambda item: (
            -item["assignment_count"],
            item["customer"].last_name,
            item["customer"].first_name,
        ),
    )
    return {
        "daily_rows": daily_rows,
        "payments": payments,
        "frequent_customers": frequent_customers,
        "days_worked": len({route.collection_date for route in routes}),
        "assignment_count": sum(row["assignment_count"] for row in daily_rows),
        "unique_clients": len(customer_frequency),
        "habitual_client_count": collector.customer_links.filter(ended_at__isnull=True).count(),
        "total_expected": as_money(sum((row["expected_amount"] for row in daily_rows), ZERO)),
        "total_collected": as_money(sum((payment.amount for payment in payments), ZERO)),
    }
