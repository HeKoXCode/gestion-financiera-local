import logging
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from modules.core.forms import (
    CustomerForm,
    ProductForm,
    SaleCancellationForm,
    SaleForm,
)
from modules.core.models import (
    BusinessSettings,
    Customer,
    Installment,
    Product,
    Sale,
)
from modules.core.services.balances import get_installment_balance, get_sale_balance
from modules.core.services.installments import create_installments
from modules.core.services.money import ZERO, as_money

logger = logging.getLogger(__name__)
PAGE_SIZE = 20


def _selected_date(request):
    requested = parse_date(request.GET.get("fecha", ""))
    return requested or timezone.localdate()


def _paginate(request, queryset):
    return Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("pagina"))


def _installment_row(installment: Installment, selected_date):
    balance = get_installment_balance(installment, as_of=selected_date)
    return {
        "installment": installment,
        "sale": installment.sale,
        "customer": installment.sale.customer,
        "balance": balance,
        "is_overdue": installment.due_date < selected_date,
    }


@require_GET
def home(request):
    selected_date = _selected_date(request)
    active_installments = Installment.objects.select_related(
        "sale",
        "sale__customer",
        "sale__product",
    ).filter(sale__status=Sale.Status.ACTIVE, due_date__lte=selected_date)

    due_rows = []
    overdue_rows = []
    for installment in active_installments:
        row = _installment_row(installment, selected_date)
        if row["balance"].total_due <= ZERO:
            continue
        if installment.due_date == selected_date:
            due_rows.append(row)
        else:
            overdue_rows.append(row)

    overdue_rows.sort(
        key=lambda row: (
            -row["balance"].days_overdue,
            row["customer"].last_name,
            row["customer"].first_name,
        )
    )
    collection_rows = overdue_rows + due_rows
    expected_amount = as_money(
        sum((row["balance"].total_due for row in due_rows), Decimal("0.00"))
    )
    overdue_amount = as_money(
        sum((row["balance"].total_due for row in overdue_rows), Decimal("0.00"))
    )
    customer_ids = {row["customer"].pk for row in collection_rows}
    overdue_customer_ids = {row["customer"].pk for row in overdue_rows}

    monday = selected_date - timedelta(days=selected_date.weekday())
    week_days = [
        {
            "date": monday + timedelta(days=offset),
            "is_selected": monday + timedelta(days=offset) == selected_date,
        }
        for offset in range(6)
    ]

    return render(
        request,
        "core/home.html",
        {
            "selected_date": selected_date,
            "previous_date": selected_date - timedelta(days=1),
            "next_date": selected_date + timedelta(days=1),
            "week_days": week_days,
            "due_rows": due_rows,
            "overdue_rows": overdue_rows,
            "collection_rows": collection_rows,
            "clients_to_collect": len(customer_ids),
            "expected_amount": expected_amount,
            "overdue_customers": len(overdue_customer_ids),
            "overdue_amount": overdue_amount,
        },
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
    sale_rows = [
        {
            "sale": sale,
            "balance": get_sale_balance(sale, as_of=timezone.localdate()),
        }
        for sale in customer.sales.select_related("product").prefetch_related("installments")
    ]
    return render(
        request,
        "core/customers/detail.html",
        {
            "customer": customer,
            "sale_rows": sale_rows,
        },
    )


@require_http_methods(["GET", "POST"])
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        customer = form.save()
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
            "installment_rows": installment_rows,
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
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        logger.exception("Falló la comprobación de SQLite")
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)

    return JsonResponse({"status": "ok", "database": "ok"})
