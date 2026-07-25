import logging
from collections import Counter
from datetime import timedelta
from pathlib import Path

from django.conf import settings as django_settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from launcher.backup import (
    BackupError,
    create_backup,
    list_backups,
    resolve_backup_path,
    validate_application_backup,
)
from modules.core.forms import (
    BusinessSettingsForm,
    CollectionAttemptForm,
    CustomerForm,
    PaymentForm,
    PaymentVoidForm,
    ProductForm,
    SaleCancellationForm,
    SaleForm,
)
from modules.core.models import (
    BusinessSettings,
    CollectionAttempt,
    Customer,
    Installment,
    Payment,
    Product,
    Sale,
)
from modules.core.services.balances import (
    get_due_sale_balance,
    get_installment_balance,
    get_sale_balance,
)
from modules.core.services.collection import build_collection_rows
from modules.core.services.customer_history import build_customer_history
from modules.core.services.dashboard import build_dashboard
from modules.core.services.export_data import (
    ExportError,
    create_data_export,
    list_exports,
    resolve_export_path,
)
from modules.core.services.installments import create_installments
from modules.core.services.late_fees import generate_missing_late_fees
from modules.core.services.money import ZERO, as_money, format_ars
from modules.core.services.payments import register_payment, void_payment
from modules.core.services.recovery import refresh_recovery_backup
from modules.core.services.reports import build_reports

logger = logging.getLogger(__name__)
PAGE_SIZE = 20
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
    return requested or timezone.localdate()


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
    generate_missing_late_fees(as_of=min(selected_date, today))
    rows = build_collection_rows(as_of=selected_date)
    scheduled_rows = [row for row in rows if row["has_installment_today"]]
    carryover_rows = [
        row for row in rows if not row["has_installment_today"] and row["days_overdue"] > 0
    ]

    exact_installments = (
        Installment.objects.select_related("sale", "sale__customer")
        .filter(due_date=selected_date)
        .exclude(sale__status=Sale.Status.CANCELLED)
    )
    scheduled_amount = ZERO
    scheduled_installments = 0
    for installment in exact_installments:
        balance = get_installment_balance(installment, as_of=selected_date)
        if balance.total_due > ZERO:
            scheduled_amount += balance.total_due
            scheduled_installments += 1

    neighborhood_counts = Counter(
        (row["customer"].neighborhood or "Sin barrio") for row in rows
    )
    neighborhoods = [
        {"name": name, "count": count}
        for name, count in sorted(
            neighborhood_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]

    return render(
        request,
        "core/agenda.html",
        {
            "selected_date": selected_date,
            "today": today,
            "week_days": _week_days(selected_date),
            "previous_week": selected_date - timedelta(days=7),
            "next_week": selected_date + timedelta(days=7),
            "rows": rows,
            "scheduled_rows": scheduled_rows,
            "carryover_rows": carryover_rows,
            "scheduled_installments": scheduled_installments,
            "scheduled_amount": as_money(scheduled_amount),
            "route_total": as_money(sum((row["total_due"] for row in rows), ZERO)),
            "client_count": len({row["customer"].pk for row in rows}),
            "neighborhoods": neighborhoods,
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
def collection_print(request):
    selected_date = _selected_date(request)
    today = timezone.localdate()
    generate_missing_late_fees(as_of=min(selected_date, today))
    rows = build_collection_rows(as_of=selected_date)
    return render(
        request,
        "core/print/daily_collection.html",
        {
            "selected_date": selected_date,
            "today": today,
            "rows": rows,
            "client_count": len({row["customer"].pk for row in rows}),
            "total_expected": as_money(
                sum((row["total_due"] for row in rows), ZERO)
            ),
        },
    )


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
def data_management(request):
    backup_directory = Path(django_settings.BACKUP_DIR)
    export_directory = Path(django_settings.EXPORT_DIR)
    database_path = Path(django_settings.DATABASES["default"]["NAME"])
    all_backups = [
        {
            "backup": backup,
            "label": BACKUP_LABELS.get(backup.label, backup.label.replace("_", " ").title()),
        }
        for backup in list_backups(backup_directory)
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
            "database_size": database_path.stat().st_size if database_path.is_file() else 0,
            "database_exists": database_path.is_file(),
        },
    )


@require_POST
def backup_create(request):
    try:
        backup = create_backup(
            Path(django_settings.DATABASES["default"]["NAME"]),
            Path(django_settings.BACKUP_DIR),
            label="manual",
            retention=30,
        )
    except BackupError as exc:
        messages.error(request, str(exc))
    else:
        if backup:
            messages.success(request, f"Backup creado: {backup.name}")
        else:
            messages.error(request, "Todavía no existe una base para respaldar.")
    return redirect("core:data_management")


@require_GET
def backup_download(request, name):
    try:
        backup = resolve_backup_path(Path(django_settings.BACKUP_DIR), name)
        validate_application_backup(backup)
    except BackupError as exc:
        raise Http404(str(exc)) from exc
    return FileResponse(
        backup.open("rb"),
        as_attachment=True,
        filename=backup.name,
        content_type=(
            "application/zip"
            if backup.name.endswith(".zip")
            else "application/vnd.sqlite3"
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
    customers = Customer.objects.annotate(sales_count=Count("sales", distinct=True)).order_by(
        "last_name", "first_name", "pk"
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
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        customer = form.save()
        refresh_recovery_backup()
        messages.success(request, f"Cliente {customer.full_name} creado correctamente.")
        return redirect("core:customer_detail", pk=customer.pk)

    return render(
        request,
        "core/customers/form.html",
        {
            "form": form,
            "title": "Nuevo cliente",
            "subtitle": "Guardá los datos necesarios para encontrar y cobrar al cliente.",
            "submit_label": "Guardar cliente",
        },
    )


@require_GET
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    today = timezone.localdate()
    generate_missing_late_fees(as_of=today)
    history = build_customer_history(customer=customer, as_of=today)
    return render(
        request,
        "core/customers/detail.html",
        {
            "customer": customer,
            "today": today,
            **history,
        },
    )


@require_http_methods(["GET", "POST"])
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        customer = form.save()
        refresh_recovery_backup()
        messages.success(request, f"Datos de {customer.full_name} actualizados.")
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
    customer.is_active = not customer.is_active
    customer.save(update_fields=["is_active", "updated_at"])
    refresh_recovery_backup()
    action = "reactivado" if customer.is_active else "archivado"
    messages.success(request, f"{customer.full_name} fue {action}.")
    return redirect("core:customer_detail", pk=customer.pk)


@require_GET
def product_list(request):
    query = request.GET.get("q", "").strip()
    state = request.GET.get("estado", "active")
    products = Product.objects.annotate(sales_count=Count("sales", distinct=True)).order_by(
        "name", "pk"
    )

    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )
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
    form = ProductForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        product = form.save()
        refresh_recovery_backup()
        messages.success(request, f"Producto {product.name} creado correctamente.")
        return redirect("core:product_list")

    return render(
        request,
        "core/products/form.html",
        {
            "form": form,
            "title": "Nuevo producto",
            "subtitle": "Creá un artículo reutilizable al registrar ventas.",
            "submit_label": "Guardar producto",
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
    sales = Sale.objects.select_related("customer", "product").annotate(
        generated_installments=Count("installments")
    ).order_by("-delivery_date", "-pk")

    if query:
        sales = sales.filter(
            Q(customer__first_name__icontains=query)
            | Q(customer__last_name__icontains=query)
            | Q(customer__dni__icontains=query)
            | Q(product__name__icontains=query)
            | Q(product_description__icontains=query)
        )
    valid_states = {choice for choice, _ in Sale.Status.choices}
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
    if request.method == "GET" and requested_customer:
        customer = Customer.objects.filter(pk=requested_customer, is_active=True).first()
        if customer:
            initial["customer"] = customer
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
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            refresh_recovery_backup()
            messages.success(
                request,
                f"Venta registrada con {sale.installment_count} cuotas.",
            )
            return redirect("core:sale_detail", pk=sale.pk)

    return render(
        request,
        "core/sales/form.html",
        {
            "form": form,
            "settings": settings,
        },
    )


@require_GET
def sale_detail(request, pk):
    sale = get_object_or_404(
        Sale.objects.select_related("customer", "product").prefetch_related(
            "installments",
            "installments__late_fees",
            "installments__payment_allocations",
        ),
        pk=pk,
    )
    today = timezone.localdate()
    if sale.status == Sale.Status.ACTIVE:
        generate_missing_late_fees(as_of=today, sale=sale)
    installment_rows = [
        {
            "installment": installment,
            "balance": get_installment_balance(installment, as_of=today),
        }
        for installment in sale.installments.all()
    ]
    return render(
        request,
        "core/sales/detail.html",
        {
            "sale": sale,
            "balance": get_sale_balance(sale, as_of=today),
            "due_balance": get_due_sale_balance(sale, as_of=today),
            "installment_rows": installment_rows,
            "payments": sale.payments.prefetch_related("allocations").all(),
            "collection_attempts": sale.collection_attempts.all()[:10],
            "today": today,
        },
    )


@require_http_methods(["GET", "POST"])
def sale_cancel(request, pk):
    sale = get_object_or_404(Sale.objects.select_related("customer"), pk=pk)
    if sale.status != Sale.Status.ACTIVE:
        messages.error(request, "Solo se puede cancelar una venta activa.")
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
        messages.success(request, "La venta fue cancelada sin eliminar su historial.")
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
    generate_missing_late_fees(as_of=min(selected_date, today))
    rows = build_collection_rows(as_of=selected_date)
    total_expected = as_money(sum((row["total_due"] for row in rows), ZERO))
    overdue_rows = [row for row in rows if row["days_overdue"] > 0]
    overdue_total = as_money(sum((row["total_due"] for row in overdue_rows), ZERO))
    collected = Payment.objects.filter(
        payment_date=selected_date,
        status=Payment.Status.REGISTERED,
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
    if sale.status != Sale.Status.ACTIVE:
        messages.error(request, "Esta venta no admite nuevos pagos.")
        return redirect("core:sale_detail", pk=sale.pk)

    generate_missing_late_fees(as_of=today, settings=settings, sale=sale)
    due_balance = get_due_sale_balance(sale, as_of=today)
    if due_balance.total_due <= ZERO:
        messages.info(request, "La venta no tiene deuda exigible hoy.")
        return redirect("core:sale_detail", pk=sale.pk)

    form = PaymentForm(
        request.POST or None,
        settings=settings,
        sale=sale,
        due_amount=due_balance.total_due,
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
            return redirect("core:sale_detail", pk=sale.pk)

    first_due = sale.installments.filter(due_date__lte=today).order_by("due_date").first()
    return render(
        request,
        "core/collection/payment_form.html",
        {
            "sale": sale,
            "form": form,
            "due_balance": due_balance,
            "first_due": first_due,
        },
    )


@require_POST
def collection_did_not_pay(request, pk):
    sale = get_object_or_404(Sale.objects.select_related("customer"), pk=pk)
    if sale.status != Sale.Status.ACTIVE:
        messages.error(request, "Solo se registran visitas en ventas activas.")
        return redirect("core:sale_detail", pk=sale.pk)
    selected_date = parse_date(request.POST.get("fecha", "")) or timezone.localdate()
    if selected_date > timezone.localdate() or selected_date < sale.delivery_date:
        messages.error(request, "La fecha del intento de cobranza no es válida.")
        return _collection_redirect(timezone.localdate())

    _, created = CollectionAttempt.objects.get_or_create(
        sale=sale,
        customer=sale.customer,
        attempt_date=selected_date,
        result=CollectionAttempt.Result.DID_NOT_PAY,
        defaults={"notes": ""},
    )
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
        messages.error(request, "Solo se registran visitas en ventas activas.")
        return redirect("core:sale_detail", pk=sale.pk)
    form = CollectionAttemptForm(request.POST or None, sale=sale)
    if request.method == "POST" and form.is_valid():
        attempt, created = CollectionAttempt.objects.get_or_create(
            sale=sale,
            customer=sale.customer,
            attempt_date=form.cleaned_data["attempt_date"],
            result=form.cleaned_data["result"],
            defaults={"notes": form.cleaned_data["notes"].strip()},
        )
        if not created and form.cleaned_data["notes"].strip():
            attempt.notes = form.cleaned_data["notes"].strip()
            attempt.save(update_fields=["notes", "updated_at"])
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
