import hmac
import logging
from datetime import date, timedelta
from pathlib import Path

from django.conf import settings as django_settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import OperationalError, connection, transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from modules.core.forms import (
    BusinessSettingsForm,
    CollectionAttemptForm,
    CollectorArchiveForm,
    CollectorForm,
    CustomerDeletionForm,
    CustomerEditForm,
    CustomerForm,
    LateFeePauseForm,
    PaymentForm,
    PaymentVoidForm,
    ProductForm,
    SaleCancellationForm,
    SaleEditForm,
    SaleForm,
)
from modules.core.middleware import MOBILE_SESSION_KEY, mobile_token_digest
from modules.core.models import (
    AuditEvent,
    BusinessSettings,
    CollectionAssignment,
    CollectionAttempt,
    CollectionRoute,
    Collector,
    Customer,
    CustomerCollectorLink,
    CustomerRevision,
    Payment,
    Product,
    Sale,
    SaleRevision,
)
from modules.core.services.agenda import build_weekly_agenda
from modules.core.services.analytics import build_analytics
from modules.core.services.balances import (
    get_due_sale_balance,
    get_installment_balance,
    get_installment_payment_timing,
    get_oldest_open_installment,
    get_sale_balance,
    installment_balance_prefetches,
)
from modules.core.services.collection import (
    build_collection_rows,
    build_customer_collection_rows,
)
from modules.core.services.collectors import (
    assignment_print_row,
    build_collector_detail,
    build_collector_overview,
    build_date_route_summaries,
    delete_collection_route,
    get_collection_assignment,
    move_collector_to_safe_archive,
    save_collection_route,
)
from modules.core.services.customer_history import build_customer_history
from modules.core.services.customer_statement_pdf import (
    build_customer_statement_pdf,
    customer_statement_filename,
)
from modules.core.services.dashboard import build_dashboard
from modules.core.services.database_backup import (
    DatabaseBackupError,
    create_deployment_backup,
    list_deployment_backups,
    resolve_deployment_backup,
)
from modules.core.services.export_data import (
    ExportError,
    create_data_export,
    list_exports,
    resolve_export_path,
)
from modules.core.services.installments import create_installments
from modules.core.services.late_fees import (
    generate_missing_late_fees,
    pause_late_fee_generation,
    resume_late_fee_generation,
)
from modules.core.services.money import ZERO, as_money, format_ars
from modules.core.services.payments import (
    register_delivery_installment_payment,
    register_historical_installment_payments,
    register_initial_payment,
    register_payment,
    void_payment,
)
from modules.core.services.recovery import refresh_recovery_backup
from modules.core.services.reporting_export import (
    ReportingExportError,
    create_reporting_export,
)
from modules.core.services.reports import build_reports
from modules.core.services.safe_archive import (
    customer_deletion_block_reason,
    edit_customer_with_revision,
    edit_sale_with_revision,
    move_customer_to_safe_archive,
    sale_edit_block_reason,
    sale_has_protected_activity,
)
from modules.core.services.whatsapp import build_customer_statement_whatsapp_url

logger = logging.getLogger(__name__)
PAGE_SIZE = 20
DAILY_COLLECTION_ENTRIES_PER_PAGE = 10
MIN_NAVIGATION_DATE = date(1900, 1, 15)
MAX_NAVIGATION_DATE = date(9999, 12, 15)
BACKUP_LABELS = {
    "startup": "Inicio",
    "close": "Cierre",
    "manual": "Manual",
    "recovery": "Recuperación",
    "pre_migration": "Antes de actualizar",
    "pre_restore": "Antes de restaurar",
}


def _selected_date(request):
    requested = parse_date(request.GET.get("fecha", ""))
    if requested is None or requested < MIN_NAVIGATION_DATE or requested > MAX_NAVIGATION_DATE:
        return timezone.localdate()
    return requested


def _paginate(request, queryset):
    return Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("pagina"))


def _week_days(selected_date):
    monday = selected_date - timedelta(days=selected_date.weekday())
    return [
        {
            "date": monday + timedelta(days=offset),
            "is_selected": monday + timedelta(days=offset) == selected_date,
        }
        for offset in range(6)
    ]


def _add_validation_error(form, error: ValidationError) -> None:
    if hasattr(error, "message_dict"):
        for field, field_messages in error.message_dict.items():
            target = field if field in form.fields else None
            for message in field_messages:
                form.add_error(target, message)
        return
    for message in error.messages:
        form.add_error(None, message)


def _collection_redirect(selected_date):
    return redirect(f"/cobranza/?fecha={selected_date:%Y-%m-%d}")


def _customer_statement_context(*, customer, as_of, include_cancelled_sales=False):
    business_settings = BusinessSettings.get_solo()
    return {
        "customer": customer,
        "today": as_of,
        "statement_filename": customer_statement_filename(customer, as_of),
        "statement_whatsapp_url": build_customer_statement_whatsapp_url(
            customer=customer,
            as_of=as_of,
            settings=business_settings,
        ),
        **build_customer_history(
            customer=customer,
            as_of=as_of,
            include_cancelled_sales=include_cancelled_sales,
        ),
    }


@require_GET
def mobile_access(request):
    expected_token = getattr(
        django_settings,
        "GESTION_MOBILE_ACCESS_TOKEN",
        "",
    )
    supplied_token = request.GET.get("clave", "")
    enabled = getattr(
        django_settings,
        "GESTION_MOBILE_ACCESS_ENABLED",
        False,
    )
    if (
        enabled
        and expected_token
        and hmac.compare_digest(
            supplied_token,
            expected_token,
        )
    ):
        request.session[MOBILE_SESSION_KEY] = mobile_token_digest(expected_token)
        request.session.set_expiry(0)
        destination = request.GET.get("continuar", "/")
        if not url_has_allowed_host_and_scheme(
            destination,
            allowed_hosts={request.get_host()},
            require_https=False,
        ):
            destination = "/"
        return redirect(destination)

    return render(
        request,
        "core/mobile_access.html",
        status=403,
    )


@require_GET
def home(request):
    selected_date = _selected_date(request)
    today = timezone.localdate()
    generate_missing_late_fees(as_of=min(selected_date, today))
    dashboard = build_dashboard(as_of=selected_date)

    return render(
        request,
        "core/home.html",
        {
            "selected_date": selected_date,
            "today": today,
            "week_days": _week_days(selected_date),
            **dashboard,
        },
    )


@require_GET
def agenda(request):
    selected_date = _selected_date(request)
    today = timezone.localdate()
    week_days = _week_days(selected_date)
    generate_missing_late_fees(as_of=min(week_days[-1]["date"], today))
    weekly_agenda = build_weekly_agenda(
        containing_date=selected_date,
        today=today,
    )

    return render(
        request,
        "core/agenda.html",
        {
            "selected_date": selected_date,
            "today": today,
            **weekly_agenda,
        },
    )


@require_GET
def reports(request):
    selected_date = _selected_date(request)
    today = timezone.localdate()
    generate_missing_late_fees(as_of=min(selected_date, today))
    report_data = build_reports(as_of=selected_date)
    return render(
        request,
        "core/reports/index.html",
        {
            "selected_date": selected_date,
            "today": today,
            **report_data,
        },
    )


@require_GET
def analytics(request):
    selected_date = _selected_date(request)
    today = timezone.localdate()
    generate_missing_late_fees(as_of=min(selected_date, today))
    return render(
        request,
        "core/analytics/index.html",
        {
            "selected_date": selected_date,
            "today": today,
            **build_analytics(as_of=selected_date),
        },
    )


@require_POST
def reporting_export_create(request):
    selected_date = _selected_date(request)
    try:
        export = create_reporting_export(as_of=selected_date)
    except ReportingExportError:
        logger.exception("No se pudo crear la exportación analítica.")
        messages.error(request, "No se pudo crear la exportación analítica.")
        return redirect(f"{reverse('core:analytics')}?fecha={selected_date:%Y-%m-%d}")
    return FileResponse(
        export.open("rb"),
        as_attachment=True,
        filename=export.name,
        content_type="application/zip",
    )


@require_GET
def audit_events(request):
    events = AuditEvent.objects.select_related("actor").all()
    return render(
        request,
        "core/audit/index.html",
        {"events": _paginate(request, events)},
    )


@require_GET
def collection_print(request):
    selected_date = _selected_date(request)
    today = timezone.localdate()
    generate_missing_late_fees(as_of=min(selected_date, today))
    rows = build_collection_rows(as_of=selected_date)
    numbered_rows = [{**row, "print_number": index} for index, row in enumerate(rows, start=1)]
    page_rows = [
        numbered_rows[index : index + DAILY_COLLECTION_ENTRIES_PER_PAGE]
        for index in range(0, len(numbered_rows), DAILY_COLLECTION_ENTRIES_PER_PAGE)
    ] or [[]]
    print_pages = [
        {
            "number": page_number,
            "rows": page,
        }
        for page_number, page in enumerate(page_rows, start=1)
    ]
    return render(
        request,
        "core/print/daily_collection.html",
        {
            "selected_date": selected_date,
            "today": today,
            "rows": rows,
            "print_pages": print_pages,
            "print_page_count": len(print_pages),
            "entries_per_page": DAILY_COLLECTION_ENTRIES_PER_PAGE,
            "client_count": len({row["customer"].pk for row in rows}),
            "collection_count": len(rows),
            "total_expected": as_money(sum((row["total_due"] for row in rows), ZERO)),
        },
    )


def _collection_route_print_pages(routes):
    print_pages = []
    for route in routes:
        assignments = list(route.assignments.all())
        route_rows = [assignment_print_row(assignment) for assignment in assignments]
        numbered_rows = [
            {**row, "print_number": index} for index, row in enumerate(route_rows, start=1)
        ]
        chunks = [
            numbered_rows[index : index + DAILY_COLLECTION_ENTRIES_PER_PAGE]
            for index in range(0, len(numbered_rows), DAILY_COLLECTION_ENTRIES_PER_PAGE)
        ] or [[]]
        route_expected = as_money(
            sum((assignment.expected_amount for assignment in assignments), ZERO)
        )
        for page_number, chunk in enumerate(chunks, start=1):
            print_pages.append(
                {
                    "route": route,
                    "rows": chunk,
                    "number": page_number,
                    "page_count": len(chunks),
                    "client_count": len(assignments),
                    "total_expected": route_expected,
                }
            )
    return print_pages


@require_http_methods(["GET", "POST"])
def collection_routes(request):
    requested_date = (
        parse_date(request.POST.get("fecha", ""))
        if request.method == "POST"
        else _selected_date(request)
    )
    selected_date = requested_date or timezone.localdate()
    if selected_date < MIN_NAVIGATION_DATE or selected_date > MAX_NAVIGATION_DATE:
        messages.error(request, "La fecha elegida no es válida.")
        return redirect("core:collection_routes")

    today = timezone.localdate()
    generate_missing_late_fees(as_of=min(selected_date, today))
    selected_route = None
    route_id = request.POST.get("route_id") or request.GET.get("recorrido")
    if route_id:
        selected_route = get_object_or_404(
            CollectionRoute.objects.select_related("collector"),
            pk=route_id,
            collection_date=selected_date,
        )

    is_collector_creation = (
        request.method == "POST" and request.POST.get("action") == "create_collector"
    )
    collector_form = CollectorForm(request.POST if is_collector_creation else None)
    if is_collector_creation and collector_form.is_valid():
        collector = collector_form.save()
        refresh_recovery_backup()
        messages.success(
            request,
            f"Cobrador {collector.name} creado. Ahora elegí los clientes de su planilla.",
        )
        return redirect(
            f"{reverse('core:collection_routes')}?fecha={selected_date:%Y-%m-%d}"
            f"&cobrador={collector.pk}#elegir-clientes"
        )

    if request.method == "POST" and request.POST.get("action") == "delete_route":
        if selected_route is None:
            messages.error(request, "No se encontró el recorrido que querés descartar.")
        else:
            try:
                collector_name = selected_route.collector.name
                delete_collection_route(route=selected_route)
            except ValidationError as exc:
                for message in exc.messages:
                    messages.error(request, message)
            else:
                refresh_recovery_backup()
                messages.success(request, f"Se descartó el recorrido de {collector_name}.")
                return redirect(
                    f"{reverse('core:collection_routes')}?fecha={selected_date:%Y-%m-%d}"
                )

    if request.method == "POST" and request.POST.get("action") == "save_route":
        try:
            if selected_route is not None:
                collector = selected_route.collector
            else:
                collector = Collector.objects.get(
                    pk=request.POST.get("collector"),
                    is_active=True,
                )
            route = save_collection_route(
                collection_date=selected_date,
                collector=collector,
                customer_ids=request.POST.getlist("customers"),
                route=selected_route,
            )
        except (Collector.DoesNotExist, TypeError, ValueError):
            messages.error(request, "Elegí un cobrador válido.")
        except ValidationError as exc:
            for message in exc.messages:
                messages.error(request, message)
        else:
            refresh_recovery_backup()
            messages.success(
                request,
                f"Recorrido de {route.collector.name} guardado con "
                f"{route.assignments.count()} cliente(s).",
            )
            if request.POST.get("after_save") == "print":
                return redirect("core:collection_route_print", pk=route.pk)
            return redirect(
                f"{reverse('core:collection_routes')}?fecha={selected_date:%Y-%m-%d}"
                f"&recorrido={route.pk}"
            )

    customer_rows = build_customer_collection_rows(as_of=selected_date)
    day_assignments = list(
        CollectionAssignment.objects.select_related(
            "route",
            "route__collector",
            "customer",
        ).filter(assigned_date=selected_date)
    )
    assignment_by_customer = {assignment.customer_id: assignment for assignment in day_assignments}
    planner_rows = []
    current_customer_ids = set()
    for row in customer_rows:
        customer_id = row["customer"].pk
        current_customer_ids.add(customer_id)
        row["product_summary"] = " · ".join(
            sale_row["sale"].product_description for sale_row in row["sale_rows"]
        )
        row["assignment"] = assignment_by_customer.get(customer_id)
        row["selected_for_route"] = bool(
            selected_route and row["assignment"] and row["assignment"].route_id == selected_route.pk
        )
        planner_rows.append(row)

    if selected_route is not None:
        for assignment in selected_route.assignments.select_related("customer"):
            if assignment.customer_id in current_customer_ids:
                continue
            snapshot = assignment.snapshot or {}
            planner_rows.append(
                {
                    "customer": assignment.customer,
                    "product_summary": " · ".join(
                        item.get("product", "")
                        for item in snapshot.get("items", [])
                        if item.get("product")
                    )
                    or "Cobranza asignada",
                    "total_due": assignment.expected_amount,
                    "days_overdue": int(snapshot.get("days_overdue") or 0),
                    "assignment": assignment,
                    "selected_for_route": True,
                    "already_processed": True,
                }
            )

    route_summaries = build_date_route_summaries(collection_date=selected_date)
    collector_ids_with_route = {summary["route"].collector_id for summary in route_summaries}
    active_collectors = Collector.objects.filter(is_active=True)
    unprepared_collectors = list(active_collectors.exclude(pk__in=collector_ids_with_route))
    if selected_route is None:
        available_collectors = unprepared_collectors
    else:
        available_collectors = list(active_collectors.filter(pk=selected_route.collector_id))

    selected_collector = None
    requested_collector_id = request.GET.get("cobrador")
    if selected_route is None and requested_collector_id:
        try:
            requested_collector_id = int(requested_collector_id)
        except (TypeError, ValueError):
            requested_collector_id = None
        if requested_collector_id is not None:
            selected_collector = next(
                (
                    collector
                    for collector in available_collectors
                    if collector.pk == requested_collector_id
                ),
                None,
            )

    active_links = {
        link.customer_id: link
        for link in CustomerCollectorLink.objects.select_related("collector").filter(
            customer_id__in=[row["customer"].pk for row in planner_rows],
            ended_at__isnull=True,
        )
    }
    for row in planner_rows:
        habitual_link = active_links.get(row["customer"].pk)
        row["habitual_collector"] = habitual_link.collector if habitual_link else None
        if (
            selected_route is None
            and selected_collector is not None
            and row.get("assignment") is None
            and habitual_link is not None
            and habitual_link.collector_id == selected_collector.pk
        ):
            row["selected_for_route"] = True

    planner_rows.sort(
        key=lambda row: (
            not row["selected_for_route"],
            -row["days_overdue"],
            row["customer"].last_name,
            row["customer"].first_name,
        )
    )
    collector_stats = {row["collector"].pk: row for row in build_collector_overview()}
    for summary in route_summaries:
        summary["collector_stats"] = collector_stats.get(
            summary["route"].collector_id,
            {},
        )
    unprepared_collector_rows = [
        {
            "collector": collector,
            "stats": collector_stats.get(collector.pk, {}),
        }
        for collector in unprepared_collectors
    ]

    return render(
        request,
        "core/collection/routes.html",
        {
            "selected_date": selected_date,
            "previous_date": selected_date - timedelta(days=1),
            "next_date": selected_date + timedelta(days=1),
            "today": today,
            "planner_return_url": (
                f"{reverse('core:collection_routes')}?fecha={selected_date:%Y-%m-%d}"
            ),
            "collector_form": collector_form,
            "unprepared_collector_rows": unprepared_collector_rows,
            "selected_collector": selected_collector,
            "planner_rows": planner_rows,
            "route_summaries": route_summaries,
            "selected_route": selected_route,
            "unassigned_count": sum(
                1 for row in customer_rows if row["customer"].pk not in assignment_by_customer
            ),
            "assigned_client_count": len(assignment_by_customer),
            "due_client_count": len(customer_rows),
        },
    )


@require_GET
def collection_route_print(request, pk):
    route = get_object_or_404(
        CollectionRoute.objects.select_related("collector").prefetch_related(
            "assignments",
            "assignments__customer",
        ),
        pk=pk,
    )
    return render(
        request,
        "core/print/collector_routes.html",
        {
            "selected_date": route.collection_date,
            "print_pages": _collection_route_print_pages([route]),
            "entries_per_page": DAILY_COLLECTION_ENTRIES_PER_PAGE,
            "back_url": (
                f"{reverse('core:collection_routes')}?fecha={route.collection_date:%Y-%m-%d}"
                f"&recorrido={route.pk}"
            ),
        },
    )


@require_GET
def collection_routes_print(request):
    selected_date = _selected_date(request)
    routes = list(
        CollectionRoute.objects.select_related("collector")
        .prefetch_related("assignments", "assignments__customer")
        .filter(collection_date=selected_date)
        .order_by("collector__name", "pk")
    )
    if not routes:
        messages.info(request, "Primero prepará al menos un recorrido para esa fecha.")
        return redirect(f"{reverse('core:collection_routes')}?fecha={selected_date:%Y-%m-%d}")
    return render(
        request,
        "core/print/collector_routes.html",
        {
            "selected_date": selected_date,
            "print_pages": _collection_route_print_pages(routes),
            "entries_per_page": DAILY_COLLECTION_ENTRIES_PER_PAGE,
            "back_url": f"{reverse('core:collection_routes')}?fecha={selected_date:%Y-%m-%d}",
        },
    )


@require_GET
def collector_list(request):
    return render(
        request,
        "core/collection/collectors.html",
        {"collector_rows": build_collector_overview()},
    )


@require_GET
def collector_detail(request, pk):
    collector = get_object_or_404(Collector, pk=pk)
    return render(
        request,
        "core/collection/collector_detail.html",
        {
            "collector": collector,
            "archive_form": CollectorArchiveForm(),
            **build_collector_detail(collector=collector),
        },
    )


@require_POST
def collector_toggle(request, pk):
    collector = get_object_or_404(Collector, pk=pk)
    form = CollectorArchiveForm(request.POST)
    return_url = request.POST.get("next", "")
    if collector.archived_at is not None:
        messages.info(request, "Este cobrador ya está guardado en el Archivo seguro.")
        return redirect("core:collector_detail", pk=collector.pk)
    if not form.is_valid():
        messages.error(request, "Indicá un motivo válido para borrar al cobrador.")
        return redirect("core:collector_detail", pk=collector.pk)
    try:
        move_collector_to_safe_archive(
            collector=collector,
            reason=form.cleaned_data["reason"],
        )
    except ValidationError as exc:
        for message in exc.messages:
            messages.error(request, message)
        return redirect("core:collector_detail", pk=collector.pk)
    refresh_recovery_backup()
    messages.success(
        request,
        f"{collector.name} fue enviado al Archivo seguro.",
    )
    if return_url and url_has_allowed_host_and_scheme(
        return_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(return_url)
    return redirect(f"{reverse('core:secure_archive')}?tipo=collectors")


@require_http_methods(["GET", "POST"])
def configuration(request):
    business_settings = BusinessSettings.get_solo()
    form = BusinessSettingsForm(
        request.POST or None,
        request.FILES or None,
        instance=business_settings,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        refresh_recovery_backup()
        messages.success(request, "La configuración fue actualizada.")
        return redirect("core:configuration")
    return render(
        request,
        "core/configuration/form.html",
        {
            "form": form,
            "business_settings": business_settings,
        },
    )


@require_GET
def secure_archive(request):
    section = request.GET.get("tipo", "customers")
    query = request.GET.get("q", "").strip()
    valid_sections = {
        "customers",
        "customer_revisions",
        "cancelled",
        "revisions",
        "collectors",
    }
    if section not in valid_sections:
        section = "customers"

    deleted_customers = Customer.objects.filter(deleted_at__isnull=False)
    customer_revisions = CustomerRevision.objects.select_related("customer")
    cancelled_sales = Sale.objects.filter(status=Sale.Status.CANCELLED)
    sale_revisions = SaleRevision.objects.select_related(
        "sale",
        "sale__customer",
        "sale__product",
    )
    archived_collectors = Collector.objects.filter(archived_at__isnull=False)
    counts = {
        "customers": deleted_customers.count(),
        "customer_revisions": customer_revisions.count(),
        "cancelled": cancelled_sales.count(),
        "revisions": sale_revisions.count(),
        "collectors": archived_collectors.count(),
    }

    if section == "customers":
        records = deleted_customers.order_by("-deleted_at", "-pk")
        if query:
            records = records.filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(dni__icontains=query)
                | Q(address__icontains=query)
                | Q(deletion_reason__icontains=query)
            )
    elif section == "customer_revisions":
        records = customer_revisions.order_by("-archived_at", "-pk")
        if query:
            customer_revision_query = (
                Q(customer__first_name__icontains=query)
                | Q(customer__last_name__icontains=query)
                | Q(reason__icontains=query)
            )
            if query.isdigit():
                customer_revision_query |= Q(customer_id=int(query))
            records = records.filter(customer_revision_query)
    elif section == "cancelled":
        records = cancelled_sales.select_related("customer", "product").order_by(
            "-cancelled_on",
            "-pk",
        )
        if query:
            records = records.filter(
                Q(customer__first_name__icontains=query)
                | Q(customer__last_name__icontains=query)
                | Q(product_description__icontains=query)
                | Q(cancellation_reason__icontains=query)
            )
    elif section == "revisions":
        records = sale_revisions.order_by("-archived_at", "-pk")
        if query:
            revision_query = (
                Q(sale__customer__first_name__icontains=query)
                | Q(sale__customer__last_name__icontains=query)
                | Q(sale__product_description__icontains=query)
                | Q(reason__icontains=query)
            )
            if query.isdigit():
                revision_query |= Q(sale_id=int(query))
            records = records.filter(revision_query)
    else:
        records = archived_collectors.order_by("-archived_at", "-pk")
        if query:
            records = records.filter(Q(name__icontains=query) | Q(archive_reason__icontains=query))

    return render(
        request,
        "core/configuration/archive.html",
        {
            "section": section,
            "query": query,
            "counts": counts,
            "page": _paginate(request, records),
        },
    )


@require_GET
def sale_revision_detail(request, pk):
    revision = get_object_or_404(
        SaleRevision.objects.select_related("sale", "sale__customer"),
        pk=pk,
    )
    return render(
        request,
        "core/configuration/sale_revision_detail.html",
        {
            "revision": revision,
            "snapshot_sale": revision.snapshot.get("sale", {}),
            "snapshot_installments": revision.snapshot.get("installments", []),
            "snapshot_payments": revision.snapshot.get("payments", []),
            "snapshot_attempts": revision.snapshot.get("collection_attempts", []),
            "snapshot_pause_periods": revision.snapshot.get(
                "late_fee_pause_periods",
                [],
            ),
        },
    )


@require_GET
def customer_revision_detail(request, pk):
    revision = get_object_or_404(
        CustomerRevision.objects.select_related("customer"),
        pk=pk,
    )
    return render(
        request,
        "core/configuration/customer_revision_detail.html",
        {"revision": revision, "snapshot": revision.snapshot},
    )


@require_GET
def data_management(request):
    backup_directory = Path(django_settings.BACKUP_DIR)
    export_directory = Path(django_settings.EXPORT_DIR)
    database_is_sqlite = connection.vendor == "sqlite"
    database_path = (
        Path(django_settings.DATABASES["default"]["NAME"])
        if database_is_sqlite
        else None
    )
    all_backups = [
        {
            "backup": backup,
            "label": BACKUP_LABELS.get(backup.label, backup.label.replace("_", " ").title()),
        }
        for backup in list_deployment_backups(backup_directory)
    ]
    all_exports = list_exports(export_directory)
    recovery = next(
        (row for row in all_backups if row["backup"].is_recovery),
        None,
    )
    return render(
        request,
        "core/data/management.html",
        {
            "backups": all_backups,
            "backup_count": len(all_backups),
            "exports": all_exports[:20],
            "export_count": len(all_exports),
            "recovery_backup": recovery,
            "latest_backup": all_backups[0] if all_backups else None,
            "database_engine": "SQLite" if database_is_sqlite else "PostgreSQL",
            "database_is_sqlite": database_is_sqlite,
            "database_size": (
                database_path.stat().st_size
                if database_path is not None and database_path.is_file()
                else None
            ),
            "database_exists": (
                database_path.is_file() if database_path is not None else True
            ),
        },
    )


@require_POST
def backup_create(request):
    try:
        backup = create_deployment_backup(
            output_directory=Path(django_settings.BACKUP_DIR),
            label="manual",
            retention=30,
        )
    except DatabaseBackupError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Copia de seguridad creada y verificada: {backup.name}")
    return redirect("core:data_management")


@require_GET
def backup_download(request, name):
    try:
        backup = resolve_deployment_backup(
            name,
            output_directory=Path(django_settings.BACKUP_DIR),
        )
    except DatabaseBackupError as exc:
        raise Http404(str(exc)) from exc
    return FileResponse(
        backup.open("rb"),
        as_attachment=True,
        filename=backup.name,
        content_type=(
            "application/zip"
            if backup.name.endswith(".zip")
            else "application/octet-stream"
        ),
    )


@require_POST
def data_export_create(request):
    try:
        export = create_data_export()
    except ExportError as exc:
        messages.error(request, str(exc))
        return redirect("core:data_management")
    return FileResponse(
        export.open("rb"),
        as_attachment=True,
        filename=export.name,
        content_type="application/zip",
    )


@require_GET
def data_export_download(request, name):
    try:
        export = resolve_export_path(Path(django_settings.EXPORT_DIR), name)
    except ExportError as exc:
        raise Http404(str(exc)) from exc
    return FileResponse(
        export.open("rb"),
        as_attachment=True,
        filename=export.name,
        content_type="application/zip",
    )


@require_GET
def customer_list(request):
    query = request.GET.get("q", "").strip()
    state = request.GET.get("estado", "active")
    customers = (
        Customer.objects.filter(deleted_at__isnull=True)
        .annotate(
            sales_count=Count(
                "sales",
                filter=Q(sales__status__in=[Sale.Status.ACTIVE, Sale.Status.COMPLETED]),
                distinct=True,
            )
        )
        .order_by("last_name", "first_name", "pk")
    )

    if query:
        customers = customers.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(dni__icontains=query)
            | Q(phone__icontains=query)
            | Q(address__icontains=query)
            | Q(neighborhood__icontains=query)
        )
    if state == "active":
        customers = customers.filter(is_active=True)
    elif state == "archived":
        customers = customers.filter(is_active=False)
    else:
        state = "all"

    return render(
        request,
        "core/customers/list.html",
        {
            "page": _paginate(request, customers),
            "query": query,
            "state": state,
        },
    )


@require_http_methods(["GET", "POST"])
def customer_create(request):
    return_to_sale = request.GET.get("volver") == "venta"
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        customer = form.save()
        refresh_recovery_backup()
        messages.success(request, f"Cliente {customer.full_name} creado correctamente.")
        if return_to_sale:
            destination = reverse("core:sale_create")
            return redirect(f"{destination}?cliente={customer.pk}&restaurar=1")
        return redirect("core:customer_detail", pk=customer.pk)

    return render(
        request,
        "core/customers/form.html",
        {
            "form": form,
            "title": "Nuevo cliente",
            "subtitle": "Guardá los datos necesarios para encontrar y cobrar al cliente.",
            "submit_label": "Guardar cliente",
            "return_to_sale": return_to_sale,
        },
    )


@require_GET
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    today = timezone.localdate()
    generate_missing_late_fees(as_of=today)
    context = _customer_statement_context(
        customer=customer,
        as_of=today,
        include_cancelled_sales=customer.is_deleted,
    )
    context["deletion_block_reason"] = customer_deletion_block_reason(customer)
    context["customer_revision_count"] = customer.revisions.count()
    collector_link_history = list(
        customer.collector_links.select_related("collector").order_by("-started_at", "-pk")
    )
    context["collector_link_history"] = collector_link_history
    context["habitual_collector_link"] = next(
        (link for link in collector_link_history if link.ended_at is None),
        None,
    )
    return render(
        request,
        "core/customers/detail.html",
        context,
    )


@require_GET
def customer_print(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    today = timezone.localdate()
    generate_missing_late_fees(as_of=today)
    context = _customer_statement_context(customer=customer, as_of=today)
    context["auto_print"] = request.GET.get("imprimir") == "1"
    return render(
        request,
        "core/print/customer_summary.html",
        context,
    )


@require_GET
def customer_statement_pdf(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    today = timezone.localdate()
    generate_missing_late_fees(as_of=today)
    history = build_customer_history(customer=customer, as_of=today)
    business_settings = BusinessSettings.get_solo()
    filename = customer_statement_filename(customer, today)
    pdf = build_customer_statement_pdf(
        customer=customer,
        as_of=today,
        history=history,
        settings=business_settings,
    )
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "no-store"
    return response


@require_http_methods(["GET", "POST"])
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if customer.deleted_at is not None:
        messages.error(
            request,
            "Este cliente está en el Archivo seguro y no puede editarse.",
        )
        return redirect("core:customer_detail", pk=customer.pk)
    form = CustomerEditForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        changes = {
            field: form.cleaned_data[field]
            for field in (
                "first_name",
                "last_name",
                "dni",
                "phone",
                "address",
                "neighborhood",
                "address_reference",
                "notes",
            )
        }
        try:
            customer, revision, created = edit_customer_with_revision(
                customer=customer,
                changes=changes,
                reason=form.cleaned_data["edit_reason"],
                operation_key=form.cleaned_data["operation_key"],
            )
        except ValidationError as exc:
            _add_validation_error(form, exc)
        else:
            if created:
                refresh_recovery_backup()
            messages.success(
                request,
                f"Datos de {customer.full_name} actualizados. La versión anterior quedó protegida.",
            )
            return redirect("core:customer_detail", pk=customer.pk)

    return render(
        request,
        "core/customers/form.html",
        {
            "form": form,
            "customer": customer,
            "title": "Editar cliente",
            "subtitle": "Actualizá sus datos personales y de domicilio.",
            "submit_label": "Guardar cambios",
        },
    )


@require_POST
def customer_toggle(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if customer.deleted_at is not None:
        messages.error(
            request,
            "Un cliente del Archivo seguro no puede reactivarse ni modificarse.",
        )
        return redirect("core:customer_detail", pk=customer.pk)
    customer.is_active = not customer.is_active
    customer.save(update_fields=["is_active", "updated_at"])
    refresh_recovery_backup()
    action = "reactivado" if customer.is_active else "archivado"
    messages.success(request, f"{customer.full_name} fue {action}.")
    return redirect("core:customer_detail", pk=customer.pk)


@require_http_methods(["GET", "POST"])
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    blocked = customer_deletion_block_reason(customer)
    active_sales = customer.sales.filter(status=Sale.Status.ACTIVE).select_related("product")
    form = CustomerDeletionForm(request.POST or None)

    if request.method == "POST" and form.is_valid() and not blocked:
        try:
            move_customer_to_safe_archive(
                customer=customer,
                reason=form.cleaned_data["reason"],
            )
        except ValidationError as exc:
            _add_validation_error(form, exc)
        else:
            refresh_recovery_backup()
            messages.success(
                request,
                f"{customer.full_name} fue enviado al Archivo seguro.",
            )
            destination = reverse("core:secure_archive")
            return redirect(f"{destination}?tipo=customers")

    return render(
        request,
        "core/customers/delete.html",
        {
            "customer": customer,
            "form": form,
            "blocked": blocked,
            "active_sales": active_sales,
        },
    )


@require_GET
def product_list(request):
    query = request.GET.get("q", "").strip()
    state = request.GET.get("estado", "active")
    products = Product.objects.annotate(
        sales_count=Count(
            "sales",
            filter=Q(sales__status__in=[Sale.Status.ACTIVE, Sale.Status.COMPLETED]),
            distinct=True,
        )
    ).order_by("name", "pk")

    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if state == "active":
        products = products.filter(is_active=True)
    elif state == "archived":
        products = products.filter(is_active=False)
    else:
        state = "all"

    return render(
        request,
        "core/products/list.html",
        {
            "page": _paginate(request, products),
            "query": query,
            "state": state,
        },
    )


@require_http_methods(["GET", "POST"])
def product_create(request):
    return_to_sale = request.GET.get("volver") == "venta"
    form = ProductForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        product = form.save()
        refresh_recovery_backup()
        messages.success(request, f"Producto {product.name} creado correctamente.")
        if return_to_sale:
            destination = reverse("core:sale_create")
            return redirect(f"{destination}?producto={product.pk}&restaurar=1")
        return redirect("core:product_list")

    return render(
        request,
        "core/products/form.html",
        {
            "form": form,
            "title": "Nuevo producto",
            "subtitle": "Creá un artículo reutilizable al registrar ventas.",
            "submit_label": "Guardar producto",
            "return_to_sale": return_to_sale,
        },
    )


@require_http_methods(["GET", "POST"])
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == "POST" and form.is_valid():
        product = form.save()
        refresh_recovery_backup()
        messages.success(request, f"Producto {product.name} actualizado.")
        return redirect("core:product_list")

    return render(
        request,
        "core/products/form.html",
        {
            "form": form,
            "product": product,
            "title": "Editar producto",
            "subtitle": "Los cambios no modifican la descripción guardada en ventas anteriores.",
            "submit_label": "Guardar cambios",
        },
    )


@require_POST
def product_toggle(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.is_active = not product.is_active
    product.save(update_fields=["is_active", "updated_at"])
    refresh_recovery_backup()
    action = "reactivado" if product.is_active else "archivado"
    messages.success(request, f"{product.name} fue {action}.")
    return redirect("core:product_list")


@require_GET
def sale_list(request):
    query = request.GET.get("q", "").strip()
    state = request.GET.get("estado", "active")
    sales = (
        Sale.objects.filter(customer__deleted_at__isnull=True)
        .exclude(status=Sale.Status.CANCELLED)
        .select_related("customer", "product")
        .annotate(generated_installments=Count("installments"))
        .order_by("-delivery_date", "-pk")
    )

    if query:
        sales = sales.filter(
            Q(customer__first_name__icontains=query)
            | Q(customer__last_name__icontains=query)
            | Q(customer__dni__icontains=query)
            | Q(product__name__icontains=query)
            | Q(product_description__icontains=query)
        )
    valid_states = {Sale.Status.ACTIVE, Sale.Status.COMPLETED}
    if state in valid_states:
        sales = sales.filter(status=state)
    else:
        state = "all"

    return render(
        request,
        "core/sales/list.html",
        {
            "page": _paginate(request, sales),
            "query": query,
            "state": state,
            "status_choices": Sale.Status.choices,
        },
    )


@require_http_methods(["GET", "POST"])
def sale_create(request):
    settings = BusinessSettings.get_solo()
    initial = {}
    requested_customer = request.GET.get("cliente")
    requested_product = request.GET.get("producto")
    if request.method == "GET" and requested_customer:
        customer = Customer.objects.filter(pk=requested_customer, is_active=True).first()
        if customer:
            initial["customer"] = customer
    if request.method == "GET" and requested_product:
        product = Product.objects.filter(pk=requested_product, is_active=True).first()
        if product:
            initial["product"] = product
    form = SaleForm(request.POST or None, settings=settings, initial=initial)

    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                sale = form.save(commit=False)
                sale.daily_late_fee = settings.daily_late_fee
                sale.status = Sale.Status.ACTIVE
                sale.full_clean()
                sale.save()
                create_installments(sale)
                register_initial_payment(
                    sale=sale,
                    payment_method=form.cleaned_data.get("down_payment_method", ""),
                    settings=settings,
                )
                if (
                    form.cleaned_data.get("first_installment_delivery_status")
                    == SaleForm.FIRST_INSTALLMENT_PAID
                ):
                    register_delivery_installment_payment(
                        sale=sale,
                        payment_method=form.cleaned_data.get(
                            "first_installment_payment_method",
                            "",
                        ),
                        settings=settings,
                    )
                register_historical_installment_payments(
                    sale=sale,
                    paid_installment_count=form.cleaned_data.get(
                        "historical_paid_installments",
                        0,
                    ),
                    payment_method=form.cleaned_data.get(
                        "historical_payment_method",
                        "",
                    ),
                    late_installments=form.cleaned_data.get(
                        "historical_late_installments",
                        {},
                    ),
                    settings=settings,
                )
        except ValidationError as exc:
            _add_validation_error(form, exc)
        except OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            logger.exception("SQLite estaba ocupado al registrar una operación.")
            form.add_error(
                None,
                (
                    "Otra ventana estaba terminando de guardar información. "
                    "Los datos de esta operación siguen en pantalla; esperá unos segundos "
                    "y volvé a confirmar."
                ),
            )
        else:
            refresh_recovery_backup()
            logger.info(
                "Operación registrada correctamente: id=%s, cuotas=%s.",
                sale.pk,
                sale.installment_count,
            )
            messages.success(
                request,
                f"{sale.operation_name} "
                f"{'registrado' if sale.is_loan else 'registrada'} "
                f"con {sale.installment_count} cuotas.",
            )
            return redirect("core:sale_detail", pk=sale.pk)

    return render(
        request,
        "core/sales/form.html",
        {
            "form": form,
            "settings": settings,
            "today": timezone.localdate(),
        },
    )


@require_GET
def sale_detail(request, pk):
    sale = get_object_or_404(
        Sale.objects.select_related("customer", "product"),
        pk=pk,
    )
    today = timezone.localdate()
    settings = BusinessSettings.get_solo()
    if sale.status == Sale.Status.ACTIVE:
        generate_missing_late_fees(as_of=today, sale=sale)
    sale = (
        Sale.objects.select_related("customer", "product")
        .prefetch_related(
            "installments",
            "late_fee_pause_periods",
            "revisions",
            *installment_balance_prefetches("installments"),
        )
        .get(pk=sale.pk)
    )
    installment_rows = [
        {
            "installment": installment,
            "balance": get_installment_balance(installment, as_of=today),
            "payment_timing": get_installment_payment_timing(
                installment,
                as_of=today,
            ),
            "can_advance": False,
            "advance_locked": False,
        }
        for installment in sale.installments.all()
    ]
    due_balance = get_due_sale_balance(sale, as_of=today)
    future_open_rows = [
        row
        for row in installment_rows
        if row["installment"].due_date > today and row["balance"].principal_due > ZERO
    ]
    can_advance_sale = (
        sale.status == Sale.Status.ACTIVE
        and settings.allow_advance_payments
        and due_balance.total_due <= ZERO
        and bool(future_open_rows)
    )
    if can_advance_sale:
        future_open_rows[0]["can_advance"] = True
        for row in future_open_rows[1:]:
            row["advance_locked"] = True
    payments = list(sale.payments.prefetch_related("allocations").all())
    total_received = as_money(
        sum(
            (payment.amount for payment in payments if payment.status == Payment.Status.REGISTERED),
            ZERO,
        )
    )
    initial_payment = next(
        (payment for payment in payments if payment.kind == Payment.Kind.INITIAL),
        None,
    )
    late_fee_pause_periods = list(sale.late_fee_pause_periods.all())
    active_late_fee_pause = next(
        (period for period in late_fee_pause_periods if period.resumed_at is None),
        None,
    )
    return render(
        request,
        "core/sales/detail.html",
        {
            "sale": sale,
            "balance": get_sale_balance(sale, as_of=today),
            "due_balance": due_balance,
            "installment_rows": installment_rows,
            "payments": payments,
            "total_received": total_received,
            "initial_payment": initial_payment,
            "collection_attempts": sale.collection_attempts.all()[:10],
            "today": today,
            "edit_block_reason": sale_edit_block_reason(sale, settings),
            "exceptional_edit_available": (
                settings.allow_exceptional_sale_edits and sale_has_protected_activity(sale)
            ),
            "remaining_edits": max(0, 2 - sale.edit_count),
            "can_advance_sale": can_advance_sale,
            "late_fee_pause_periods": late_fee_pause_periods,
            "active_late_fee_pause": active_late_fee_pause,
        },
    )


@require_http_methods(["GET", "POST"])
def sale_edit(request, pk):
    sale = get_object_or_404(
        Sale.objects.select_related("customer", "product"),
        pk=pk,
    )
    settings = BusinessSettings.get_solo()
    blocked = sale_edit_block_reason(sale, settings)
    if blocked:
        messages.error(request, blocked)
        return redirect("core:sale_detail", pk=sale.pk)

    exceptional_mode = sale_has_protected_activity(sale)
    form = SaleEditForm(
        request.POST or None,
        instance=sale,
        settings=settings,
        exceptional_mode=exceptional_mode,
    )
    if request.method == "POST" and form.is_valid():
        changes = {
            field: form.cleaned_data[field]
            for field in (
                "customer",
                "product",
                "product_description",
                "delivery_date",
                "cash_price",
                "loan_disbursement_method",
                "loan_interest_rate",
                "down_payment",
                "financed_amount",
                "frequency",
                "installment_count",
                "first_due_date",
            )
        }
        try:
            edited_sale, revision, created = edit_sale_with_revision(
                sale=sale,
                changes=changes,
                reason=form.cleaned_data["edit_reason"],
                down_payment_method=form.cleaned_data.get(
                    "down_payment_method",
                    "",
                ),
                operation_key=form.cleaned_data["operation_key"],
                settings=settings,
            )
        except ValidationError as exc:
            _add_validation_error(form, exc)
        else:
            if created:
                refresh_recovery_backup()
            messages.success(
                request,
                (
                    f"{edited_sale.operation_name} "
                    f"{'corregido' if edited_sale.is_loan else 'corregida'}. "
                    f"La versión anterior {revision.revision_number} "
                    "quedó guardada en el Archivo seguro."
                ),
            )
            return redirect("core:sale_detail", pk=edited_sale.pk)

    return render(
        request,
        "core/sales/form.html",
        {
            "form": form,
            "settings": settings,
            "today": timezone.localdate(),
            "editing": True,
            "sale": sale,
            "next_edit_number": sale.edit_count + 1,
            "remaining_after_save": max(0, 1 - sale.edit_count),
            "exceptional_mode": exceptional_mode,
        },
    )


@require_http_methods(["GET", "POST"])
def sale_cancel(request, pk):
    sale = get_object_or_404(Sale.objects.select_related("customer"), pk=pk)
    if sale.status != Sale.Status.ACTIVE:
        messages.error(request, "Solo se puede cancelar una operación activa.")
        return redirect("core:sale_detail", pk=sale.pk)

    form = SaleCancellationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        sale.status = Sale.Status.CANCELLED
        sale.cancelled_on = timezone.localdate()
        sale.cancellation_reason = form.cleaned_data["reason"].strip()
        sale.full_clean()
        sale.save(
            update_fields=[
                "status",
                "cancelled_on",
                "cancellation_reason",
                "updated_at",
            ]
        )
        refresh_recovery_backup()
        messages.success(request, "La operación fue cancelada sin eliminar su historial.")
        return redirect("core:sale_detail", pk=sale.pk)

    return render(
        request,
        "core/sales/cancel.html",
        {
            "sale": sale,
            "form": form,
        },
    )


@require_GET
def collection_list(request):
    selected_date = _selected_date(request)
    today = timezone.localdate()
    settings = BusinessSettings.get_solo()
    generate_missing_late_fees(as_of=min(selected_date, today))
    rows = build_collection_rows(as_of=selected_date)
    assignments_by_customer = {
        assignment.customer_id: assignment
        for assignment in CollectionAssignment.objects.select_related(
            "route",
            "route__collector",
        ).filter(assigned_date=selected_date)
    }
    habitual_by_customer = {
        link.customer_id: link.collector
        for link in CustomerCollectorLink.objects.select_related("collector").filter(
            customer_id__in={row["customer"].pk for row in rows},
            ended_at__isnull=True,
        )
    }
    for row in rows:
        row["collection_assignment"] = assignments_by_customer.get(row["customer"].pk)
        row["habitual_collector"] = habitual_by_customer.get(row["customer"].pk)
        row["show_habitual_collector"] = bool(
            row["habitual_collector"]
            and (
                row["collection_assignment"] is None
                or row["collection_assignment"].route.collector_id != row["habitual_collector"].pk
            )
        )
    total_expected = as_money(sum((row["total_due"] for row in rows), ZERO))
    overdue_rows = [row for row in rows if row["days_overdue"] > 0]
    overdue_total = as_money(sum((row["total_due"] for row in overdue_rows), ZERO))
    collected = Payment.objects.filter(
        payment_date=selected_date,
        status=Payment.Status.REGISTERED,
        kind=Payment.Kind.INSTALLMENT,
        sale__status__in=[Sale.Status.ACTIVE, Sale.Status.COMPLETED],
    )
    collected_amount = as_money(sum(collected.values_list("amount", flat=True), ZERO))

    return render(
        request,
        "core/collection/list.html",
        {
            "selected_date": selected_date,
            "previous_date": selected_date - timedelta(days=1),
            "next_date": selected_date + timedelta(days=1),
            "today": today,
            "rows": rows,
            "client_count": len({row["customer"].pk for row in rows}),
            "total_expected": total_expected,
            "overdue_count": len({row["customer"].pk for row in overdue_rows}),
            "overdue_total": overdue_total,
            "collected_amount": collected_amount,
            "allow_advance_payments": settings.allow_advance_payments,
            "route_summaries": build_date_route_summaries(collection_date=selected_date),
            "assigned_client_count": len(assignments_by_customer),
        },
    )


def _collection_return(request, sale: Sale):
    return_url = request.POST.get("next", "")
    if return_url and url_has_allowed_host_and_scheme(
        return_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(return_url)
    return redirect("core:sale_detail", pk=sale.pk)


@require_POST
def late_fee_pause(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    form = LateFeePauseForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Indicá un motivo breve para pausar el interés diario.")
        return _collection_return(request, sale)
    try:
        period, created = pause_late_fee_generation(
            sale=sale,
            reason=form.cleaned_data["reason"],
        )
    except ValidationError as exc:
        for message in exc.messages:
            messages.error(request, message)
    else:
        if created:
            refresh_recovery_backup()
            messages.success(
                request,
                (
                    "Interés diario pausado. La deuda y los recargos anteriores se "
                    "mantienen; hoy no producirá un recargo para mañana."
                ),
            )
        else:
            messages.info(
                request,
                f"El interés diario ya estaba pausado desde el {period.paused_from:%d/%m/%Y}.",
            )
    return _collection_return(request, sale)


@require_POST
def late_fee_resume(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    try:
        period, changed = resume_late_fee_generation(sale=sale)
    except ValidationError as exc:
        for message in exc.messages:
            messages.error(request, message)
    else:
        if changed:
            refresh_recovery_backup()
            messages.success(
                request,
                (
                    "Interés diario reactivado. Si la deuda sigue impaga, hoy volverá "
                    "a producir el recargo de mañana."
                ),
            )
        else:
            messages.info(
                request,
                f"El interés diario ya había sido reactivado el {period.resumed_at:%d/%m/%Y}.",
            )
    return _collection_return(request, sale)


def _advance_payment_summary(sale: Sale, *, as_of: date):
    due_balance = get_due_sale_balance(sale, as_of=as_of)
    future_rows = []
    for installment in sale.installments.all():
        if installment.due_date <= as_of:
            continue
        balance = get_installment_balance(installment, as_of=as_of)
        if balance.principal_due > ZERO:
            future_rows.append(
                {
                    "installment": installment,
                    "balance": balance,
                }
            )
    future_total = as_money(sum((row["balance"].principal_due for row in future_rows), ZERO))
    return {
        "due_balance": due_balance,
        "future_rows": future_rows,
        "future_total": future_total,
        "next_future": future_rows[0] if future_rows else None,
        "can_advance": due_balance.total_due <= ZERO and future_total > ZERO,
    }


@require_GET
def advance_payment_list(request):
    settings = BusinessSettings.get_solo()
    if not settings.allow_advance_payments:
        messages.info(
            request,
            "Los pagos adelantados están deshabilitados en Configuración.",
        )
        return redirect("core:collection_list")

    today = timezone.localdate()
    generate_missing_late_fees(as_of=today)
    query = request.GET.get("q", "").strip()
    sales = (
        Sale.objects.filter(
            status=Sale.Status.ACTIVE,
            customer__deleted_at__isnull=True,
        )
        .select_related("customer", "product")
        .prefetch_related(
            "installments",
            *installment_balance_prefetches("installments"),
        )
        .order_by("customer__last_name", "customer__first_name", "pk")
    )
    for term in query.split():
        sales = sales.filter(
            Q(customer__first_name__icontains=term)
            | Q(customer__last_name__icontains=term)
            | Q(customer__dni__icontains=term)
            | Q(product_description__icontains=term)
            | Q(product__name__icontains=term)
        )

    rows = []
    for sale in sales[:100]:
        summary = _advance_payment_summary(sale, as_of=today)
        if summary["future_total"] <= ZERO:
            continue
        rows.append({"sale": sale, **summary})

    return render(
        request,
        "core/collection/advance_payment_list.html",
        {
            "rows": rows,
            "query": query,
            "today": today,
        },
    )


@require_http_methods(["GET", "POST"])
def advance_payment_create(request, pk):
    settings = BusinessSettings.get_solo()
    if not settings.allow_advance_payments:
        messages.error(
            request,
            "Los pagos adelantados están deshabilitados en Configuración.",
        )
        return redirect("core:collection_list")

    sale = get_object_or_404(
        Sale.objects.select_related("customer", "product"),
        pk=pk,
    )
    origin = (
        request.POST.get("origin", "")
        if request.method == "POST"
        else request.GET.get("origen", "")
    )
    return_to_sale = origin == "venta"
    return_url = (
        reverse("core:sale_detail", args=[sale.pk])
        if return_to_sale
        else reverse("core:advance_payment_list")
    )
    today = timezone.localdate()
    if sale.status != Sale.Status.ACTIVE or sale.customer.deleted_at is not None:
        messages.error(request, "Esta operación no admite pagos adelantados.")
        return redirect("core:advance_payment_list")

    generate_missing_late_fees(as_of=today, settings=settings, sale=sale)
    summary = _advance_payment_summary(sale, as_of=today)
    if summary["due_balance"].total_due > ZERO:
        messages.error(
            request,
            "Primero registrá el pago pendiente de hoy o de días anteriores. "
            "Después vas a poder adelantar la próxima cuota.",
        )
        return redirect("core:payment_create", pk=sale.pk)
    if summary["future_total"] <= ZERO or summary["next_future"] is None:
        messages.info(request, "Esta operación no tiene cuotas futuras pendientes.")
        return redirect("core:advance_payment_list")

    form = PaymentForm(
        request.POST or None,
        settings=settings,
        sale=sale,
        due_amount=summary["next_future"]["balance"].principal_due,
        expected_payment_date=today,
    )
    if request.method == "POST" and form.is_valid():
        try:
            result = register_payment(
                sale=sale,
                amount=form.cleaned_data["amount"],
                payment_date=form.cleaned_data["payment_date"],
                payment_method=form.cleaned_data["payment_method"],
                notes=form.cleaned_data["notes"],
                operation_key=form.cleaned_data["operation_key"],
                settings=settings,
                advance=True,
            )
        except ValidationError as exc:
            _add_validation_error(form, exc)
        else:
            if result.created:
                refresh_recovery_backup()
                messages.success(
                    request,
                    f"Pago adelantado de {format_ars(result.payment.amount)} registrado. "
                    "Las fechas de las cuotas no se modificaron.",
                )
            else:
                messages.info(request, "Ese pago adelantado ya había sido registrado.")
            return redirect(return_url)

    return render(
        request,
        "core/collection/advance_payment_form.html",
        {
            "sale": sale,
            "form": form,
            "today": today,
            "origin": origin,
            "return_url": return_url,
            **summary,
        },
    )


@require_http_methods(["GET", "POST"])
def payment_create(request, pk):
    sale = get_object_or_404(
        Sale.objects.select_related("customer", "product"),
        pk=pk,
    )
    today = timezone.localdate()
    settings = BusinessSettings.get_solo()
    raw_selected_date = (
        request.POST.get("selected_date", "")
        if request.method == "POST"
        else request.GET.get("fecha", "")
    )
    selected_date = parse_date(raw_selected_date) if raw_selected_date else today
    from_collection = (
        request.POST.get("from_collection") == "1"
        if request.method == "POST"
        else bool(raw_selected_date)
    )
    if (
        selected_date is None
        or selected_date < MIN_NAVIGATION_DATE
        or selected_date > today
        or selected_date < sale.delivery_date
    ):
        messages.error(request, "La fecha elegida para el pago no es válida.")
        return _collection_redirect(today)
    is_retroactive = selected_date < today
    return_to_collection = f"/cobranza/?fecha={selected_date:%Y-%m-%d}"
    request_stage = request.POST.get("stage", "")
    is_payment_submission = request.method == "POST" and (
        request_stage == "payment" or (not is_retroactive and not request_stage)
    )

    if sale.status != Sale.Status.ACTIVE:
        messages.error(request, "Esta operación no admite nuevos pagos.")
        return redirect("core:sale_detail", pk=sale.pk)

    collection_assignment = get_collection_assignment(
        customer_id=sale.customer_id,
        collection_date=selected_date,
    )
    generate_missing_late_fees(as_of=selected_date, settings=settings, sale=sale)
    due_balance = get_due_sale_balance(sale, as_of=selected_date)
    if due_balance.total_due <= ZERO:
        messages.info(
            request,
            f"La operación no tenía cuotas pendientes al {selected_date:%d/%m/%Y}.",
        )
        return _collection_redirect(selected_date)

    later_payment = None
    if is_retroactive:
        later_payment = (
            sale.payments.filter(
                status=Payment.Status.REGISTERED,
                kind=Payment.Kind.INSTALLMENT,
                payment_date__gt=selected_date,
            )
            .order_by("payment_date", "created_at", "pk")
            .first()
        )
        confirmation_requested = request.method == "POST" and request_stage == "confirm"
        if request.method == "GET" or (not confirmation_requested and not is_payment_submission):
            return render(
                request,
                "core/collection/retroactive_payment_confirm.html",
                {
                    "sale": sale,
                    "selected_date": selected_date,
                    "due_balance": due_balance,
                    "later_payment": later_payment,
                    "return_to_collection": return_to_collection,
                },
            )
        if later_payment is not None:
            messages.error(
                request,
                "No se registró el pago anterior porque esta operación ya tiene un "
                "pago posterior que debe revisarse primero.",
            )
            return _collection_redirect(selected_date)

    payment_form_data = request.POST if is_payment_submission else None
    form = PaymentForm(
        payment_form_data,
        settings=settings,
        sale=sale,
        due_amount=due_balance.total_due,
        expected_payment_date=selected_date,
    )
    if is_payment_submission and form.is_valid():
        try:
            result = register_payment(
                sale=sale,
                amount=form.cleaned_data["amount"],
                payment_date=form.cleaned_data["payment_date"],
                payment_method=form.cleaned_data["payment_method"],
                notes=form.cleaned_data["notes"],
                operation_key=form.cleaned_data["operation_key"],
                settings=settings,
                collection_assignment=collection_assignment,
            )
        except ValidationError as exc:
            _add_validation_error(form, exc)
        else:
            if result.created:
                refresh_recovery_backup()
                messages.success(
                    request,
                    f"Pago de {format_ars(result.payment.amount)} registrado correctamente.",
                )
            else:
                messages.info(request, "Ese pago ya había sido registrado.")
            if from_collection:
                return _collection_redirect(selected_date)
            return redirect("core:sale_detail", pk=sale.pk)

    current_installment = get_oldest_open_installment(sale, as_of=selected_date)
    first_due = current_installment[0] if current_installment is not None else None
    return render(
        request,
        "core/collection/payment_form.html",
        {
            "sale": sale,
            "form": form,
            "due_balance": due_balance,
            "first_due": first_due,
            "selected_date": selected_date,
            "today": today,
            "is_retroactive": is_retroactive,
            "from_collection": from_collection,
            "return_to_collection": return_to_collection,
            "collection_assignment": collection_assignment,
        },
    )


@require_POST
def collection_did_not_pay(request, pk):
    sale = get_object_or_404(Sale.objects.select_related("customer"), pk=pk)
    if sale.status != Sale.Status.ACTIVE:
        messages.error(request, "Solo se registran visitas en operaciones activas.")
        return redirect("core:sale_detail", pk=sale.pk)
    selected_date = parse_date(request.POST.get("fecha", "")) or timezone.localdate()
    if selected_date > timezone.localdate() or selected_date < sale.delivery_date:
        messages.error(request, "La fecha de la visita de cobranza no es válida.")
        return _collection_redirect(timezone.localdate())

    collection_assignment = get_collection_assignment(
        customer_id=sale.customer_id,
        collection_date=selected_date,
    )
    attempt, created = CollectionAttempt.objects.get_or_create(
        sale=sale,
        customer=sale.customer,
        attempt_date=selected_date,
        result=CollectionAttempt.Result.DID_NOT_PAY,
        defaults={
            "notes": "",
            "collector": (
                collection_assignment.route.collector if collection_assignment is not None else None
            ),
            "collection_assignment": collection_assignment,
        },
    )
    if not created and collection_assignment is not None and attempt.collector_id is None:
        attempt.collector = collection_assignment.route.collector
        attempt.collection_assignment = collection_assignment
        attempt.full_clean()
        attempt.save(update_fields=["collector", "collection_assignment", "updated_at"])
    if created:
        refresh_recovery_backup()
        messages.warning(request, f"Se registró que {sale.customer.full_name} no pagó.")
    else:
        messages.info(request, "Ese resultado ya estaba registrado para la fecha.")
    return _collection_redirect(selected_date)


@require_http_methods(["GET", "POST"])
def collection_attempt_create(request, pk):
    sale = get_object_or_404(Sale.objects.select_related("customer"), pk=pk)
    if sale.status != Sale.Status.ACTIVE:
        messages.error(request, "Solo se registran visitas en operaciones activas.")
        return redirect("core:sale_detail", pk=sale.pk)
    requested_date = parse_date(request.GET.get("fecha", ""))
    form = CollectionAttemptForm(
        request.POST or None,
        sale=sale,
        initial={"attempt_date": requested_date or timezone.localdate()},
    )
    if request.method == "POST" and form.is_valid():
        collection_assignment = get_collection_assignment(
            customer_id=sale.customer_id,
            collection_date=form.cleaned_data["attempt_date"],
        )
        attempt, created = CollectionAttempt.objects.get_or_create(
            sale=sale,
            customer=sale.customer,
            attempt_date=form.cleaned_data["attempt_date"],
            result=form.cleaned_data["result"],
            defaults={
                "notes": form.cleaned_data["notes"].strip(),
                "collector": (
                    collection_assignment.route.collector
                    if collection_assignment is not None
                    else None
                ),
                "collection_assignment": collection_assignment,
            },
        )
        update_fields = []
        if not created and form.cleaned_data["notes"].strip():
            attempt.notes = form.cleaned_data["notes"].strip()
            update_fields.append("notes")
        if not created and collection_assignment is not None and attempt.collector_id is None:
            attempt.collector = collection_assignment.route.collector
            attempt.collection_assignment = collection_assignment
            update_fields.extend(["collector", "collection_assignment"])
        if update_fields:
            attempt.full_clean()
            attempt.save(update_fields=[*update_fields, "updated_at"])
        refresh_recovery_backup()
        messages.success(request, "Resultado de la visita guardado.")
        return redirect("core:sale_detail", pk=sale.pk)

    return render(
        request,
        "core/collection/attempt_form.html",
        {
            "sale": sale,
            "form": form,
        },
    )


@require_http_methods(["GET", "POST"])
def payment_void(request, pk):
    payment = get_object_or_404(
        Payment.objects.select_related("customer", "sale"),
        pk=pk,
    )
    if payment.status == Payment.Status.VOIDED:
        messages.info(request, "El pago ya se encuentra anulado.")
        return redirect("core:sale_detail", pk=payment.sale_id)
    if payment.sale.status == Sale.Status.CANCELLED or payment.customer.deleted_at is not None:
        messages.error(request, "Este movimiento pertenece al Archivo seguro y no puede cambiarse.")
        return redirect("core:sale_detail", pk=payment.sale_id)

    form = PaymentVoidForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            void_payment(payment=payment, reason=form.cleaned_data["reason"])
        except ValidationError as exc:
            _add_validation_error(form, exc)
        else:
            refresh_recovery_backup()
            messages.success(request, "El pago fue anulado y el saldo se recalculó.")
            return redirect("core:sale_detail", pk=payment.sale_id)

    return render(
        request,
        "core/collection/payment_void.html",
        {
            "payment": payment,
            "form": form,
        },
    )


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.exception("Falló la comprobación de SQLite")
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)

    return JsonResponse({"status": "ok", "database": "ok"})
