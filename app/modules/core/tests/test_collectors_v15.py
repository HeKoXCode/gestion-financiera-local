import uuid
from datetime import timedelta
from decimal import Decimal
from zipfile import ZipFile

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from modules.core.models import (
    CollectionAssignment,
    CollectionAttempt,
    CollectionRoute,
    Collector,
    Payment,
)
from modules.core.services.balances import get_due_sale_balance
from modules.core.services.collectors import (
    build_collector_detail,
    build_date_route_summaries,
    delete_collection_route,
    save_collection_route,
)
from modules.core.services.export_data import create_data_export
from modules.core.services.installments import create_installments
from modules.core.tests.factories import make_customer, make_product, make_sale

pytestmark = pytest.mark.django_db


def make_due_sale(*, customer=None, product=None, product_name="Producto de prueba"):
    today = timezone.localdate()
    product = product or make_product(name=product_name)
    sale = make_sale(
        customer=customer,
        product=product,
        product_description=product.name,
        delivery_date=today - timedelta(days=20),
        first_due_date=today,
        financed_amount=Decimal("20000.00"),
        installment_count=1,
        daily_late_fee=Decimal("0.00"),
    )
    create_installments(sale)
    return sale


def test_collector_can_be_created_inline_from_route_planner(client):
    today = timezone.localdate()

    response = client.post(
        reverse("core:collection_routes"),
        {
            "action": "create_collector",
            "fecha": today.isoformat(),
            "name": "  Martín   Norte  ",
        },
    )

    collector = Collector.objects.get()
    assert response.status_code == 302
    assert response.url == (
        f"{reverse('core:collection_routes')}?fecha={today:%Y-%m-%d}"
        f"&cobrador={collector.pk}#elegir-clientes"
    )
    assert collector.name == "Martín Norte"
    assert CollectionRoute.objects.count() == 0

    planner = client.get(response.url)
    content = planner.content.decode()
    assert "Cobrador · Sin planilla para este día" in content
    assert "Elegí clientes para Martín Norte" in content
    assert f'name="collector" value="{collector.pk}"' in content
    assert 'select class="form-control" name="collector"' not in content
    assert "clientes habituales" in content


def test_unprepared_collector_card_explains_customer_and_sales_grouping(client):
    today = timezone.localdate()
    customer = make_customer(first_name="Ana", last_name="Varias ventas")
    make_due_sale(customer=customer, product_name="Televisor")
    make_due_sale(customer=customer, product_name="Heladera")
    collector = Collector.objects.create(name="Cobrador disponible")

    planner = client.get(
        reverse("core:collection_routes"),
        {"fecha": today.isoformat(), "cobrador": collector.pk},
    )

    content = planner.content.decode()
    assert planner.status_code == 200
    assert "Cobrador disponible" in content
    assert "Sin planilla para este día" in content
    assert "La selección es por cliente." in content
    assert "Operaciones pendientes:" in content
    assert "Televisor" in content
    assert "Heladera" in content
    assert content.count(f'name="customers" value="{customer.pk}"') == 1


def test_invalid_collector_preselection_does_not_break_route_planner(client):
    today = timezone.localdate()
    make_due_sale()

    planner = client.get(
        reverse("core:collection_routes"),
        {"fecha": today.isoformat(), "cobrador": "no-valido"},
    )

    assert planner.status_code == 200
    assert planner.context["selected_collector"] is None


def test_collector_is_sent_to_safe_archive_without_losing_history(client):
    today = timezone.localdate()
    sale = make_due_sale()
    collector = Collector.objects.create(name="Cobrador histórico")
    route = save_collection_route(
        collection_date=today,
        collector=collector,
        customer_ids=[sale.customer_id],
    )

    response = client.post(
        reverse("core:collector_toggle", args=[collector.pk]),
        {"reason": "Ya no realiza cobranzas"},
    )

    collector.refresh_from_db()
    assert response.status_code == 302
    assert response.url.endswith("?tipo=collectors")
    assert collector.is_active is False
    assert collector.archived_at is not None
    assert collector.archive_reason == "Ya no realiza cobranzas"
    assert CollectionRoute.objects.get() == route
    assert route.assignments.count() == 1

    active_list = client.get(reverse("core:collector_list"))
    safe_archive = client.get(reverse("core:secure_archive"), {"tipo": "collectors"})
    detail = client.get(reverse("core:collector_detail", args=[collector.pk]))
    assert all(row["collector"].pk != collector.pk for row in active_list.context["collector_rows"])
    assert "Cobrador histórico" in safe_archive.content.decode()
    assert "Registro guardado en el Archivo seguro" in detail.content.decode()


def test_route_planner_can_archive_collector_and_return_to_same_day(client):
    today = timezone.localdate()
    sale = make_due_sale()
    collector = Collector.objects.create(name="Cobrador desde planillas")
    route = save_collection_route(
        collection_date=today,
        collector=collector,
        customer_ids=[sale.customer_id],
    )
    return_url = f"{reverse('core:collection_routes')}?fecha={today:%Y-%m-%d}"

    response = client.post(
        reverse("core:collector_toggle", args=[collector.pk]),
        {
            "reason": "Borrado desde Preparar planillas",
            "next": return_url,
        },
    )

    collector.refresh_from_db()
    assert response.status_code == 302
    assert response.url == return_url
    assert collector.is_archived is True
    assert CollectionRoute.objects.filter(pk=route.pk).exists()

    planner = client.get(return_url)
    content = planner.content.decode()
    assert "En Archivo seguro" in content
    assert "Borrar a Cobrador desde planillas" not in content


def test_collector_archive_rejects_external_return_url(client):
    collector = Collector.objects.create(name="Retorno protegido")

    response = client.post(
        reverse("core:collector_toggle", args=[collector.pk]),
        {
            "reason": "Borrado de prueba",
            "next": "https://example.invalid/salida",
        },
    )

    assert response.status_code == 302
    assert response.url.endswith("?tipo=collectors")


def test_collector_archive_requires_reason(client):
    collector = Collector.objects.create(name="Sin motivo")

    response = client.post(
        reverse("core:collector_toggle", args=[collector.pk]),
        {"reason": ""},
    )

    collector.refresh_from_db()
    assert response.status_code == 302
    assert collector.is_active is True
    assert collector.archived_at is None


def test_route_planner_and_collector_history_render(client):
    today = timezone.localdate()
    sale = make_due_sale()
    collector = Collector.objects.create(name="Elena")
    route = save_collection_route(
        collection_date=today,
        collector=collector,
        customer_ids=[sale.customer_id],
    )

    planner = client.get(
        reverse("core:collection_routes"),
        {"fecha": today.isoformat(), "recorrido": route.pk},
    )
    history = client.get(reverse("core:collector_list"))

    assert planner.status_code == 200
    assert "Buscar cliente" in planner.content.decode()
    assert "Elena" in planner.content.decode()
    assert history.status_code == 200
    assert "Días trabajados" in history.content.decode()


def test_route_groups_multiple_sales_for_one_customer_and_prints_only_selected(client):
    today = timezone.localdate()
    selected_customer = make_customer(first_name="Ana", last_name="Elegida")
    make_due_sale(customer=selected_customer, product_name="Televisor")
    make_due_sale(customer=selected_customer, product_name="Heladera")
    other_sale = make_due_sale(product_name="No seleccionado")
    collector = Collector.objects.create(name="Carlos")

    response = client.post(
        reverse("core:collection_routes"),
        {
            "action": "save_route",
            "fecha": today.isoformat(),
            "collector": collector.pk,
            "customers": [selected_customer.pk],
        },
    )

    route = CollectionRoute.objects.get()
    assignment = route.assignments.get()
    assert response.status_code == 302
    assert assignment.customer == selected_customer
    assert assignment.expected_amount == Decimal("40000.00")
    assert {item["product"] for item in assignment.snapshot["items"]} == {
        "Televisor",
        "Heladera",
    }

    printed = client.get(reverse("core:collection_route_print", args=[route.pk]))
    content = printed.content.decode()
    assert printed.status_code == 200
    assert "Carlos" in content
    assert "Ana Elegida" in content
    assert "Televisor" in content
    assert "Heladera" in content
    assert other_sale.customer.full_name not in content


def test_save_and_print_creates_route_before_opening_print_view(client):
    today = timezone.localdate()
    sale = make_due_sale(product_name="Producto para guardar e imprimir")
    collector = Collector.objects.create(name="Esteban")

    response = client.post(
        reverse("core:collection_routes"),
        {
            "action": "save_route",
            "after_save": "print",
            "fecha": today.isoformat(),
            "collector": collector.pk,
            "customers": [sale.customer_id],
        },
    )

    route = CollectionRoute.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("core:collection_route_print", args=[route.pk])
    assert route.assignments.get().customer_id == sale.customer_id

    printed = client.get(response.url)
    assert printed.status_code == 200
    assert "Esteban" in printed.content.decode()
    assert sale.customer.full_name in printed.content.decode()


def test_save_and_print_updates_same_day_route_before_reprinting(client):
    today = timezone.localdate()
    original_customer = make_customer(first_name="Ana", last_name="Original")
    replacement_customer = make_customer(first_name="Brenda", last_name="Reemplazo")
    original_sale = make_due_sale(
        customer=original_customer,
        product_name="Cliente originalmente asignado",
    )
    replacement_sale = make_due_sale(
        customer=replacement_customer,
        product_name="Cliente reasignado",
    )
    collector = Collector.objects.create(name="Esteban")
    route = save_collection_route(
        collection_date=today,
        collector=collector,
        customer_ids=[original_sale.customer_id],
    )

    response = client.post(
        reverse("core:collection_routes"),
        {
            "action": "save_route",
            "after_save": "print",
            "fecha": today.isoformat(),
            "route_id": route.pk,
            "collector": collector.pk,
            "customers": [replacement_sale.customer_id],
        },
    )

    route.refresh_from_db()
    assert response.status_code == 302
    assert response.url == reverse("core:collection_route_print", args=[route.pk])
    assert CollectionRoute.objects.count() == 1
    assert list(route.assignments.values_list("customer_id", flat=True)) == [
        replacement_sale.customer_id
    ]

    printed = client.get(response.url).content.decode()
    assert replacement_sale.customer.full_name in printed
    assert original_sale.customer.full_name not in printed


def test_same_customer_cannot_belong_to_two_collectors_on_same_day():
    today = timezone.localdate()
    sale = make_due_sale()
    first = Collector.objects.create(name="Primer cobrador")
    second = Collector.objects.create(name="Segundo cobrador")
    save_collection_route(
        collection_date=today,
        collector=first,
        customer_ids=[sale.customer_id],
    )

    second_route = save_collection_route(
        collection_date=today,
        collector=second,
        customer_ids=[sale.customer_id],
    )

    assert CollectionAssignment.objects.count() == 1
    assert CollectionAssignment.objects.get().route == second_route


def test_non_due_customer_cannot_be_injected_into_route():
    today = timezone.localdate()
    customer = make_customer(first_name="Sin", last_name="Deuda")
    collector = Collector.objects.create(name="Cobrador")

    with pytest.raises(ValidationError, match="cobros pendientes"):
        save_collection_route(
            collection_date=today,
            collector=collector,
            customer_ids=[customer.pk],
        )


def test_payment_from_collection_is_attributed_to_assigned_collector(client):
    today = timezone.localdate()
    sale = make_due_sale()
    collector = Collector.objects.create(name="Lucía")
    route = save_collection_route(
        collection_date=today,
        collector=collector,
        customer_ids=[sale.customer_id],
    )
    amount = get_due_sale_balance(sale, as_of=today).total_due

    response = client.post(
        reverse("core:payment_create", args=[sale.pk]),
        {
            "stage": "payment",
            "selected_date": today.isoformat(),
            "from_collection": "1",
            "operation_key": str(uuid.uuid4()),
            "amount": str(amount),
            "payment_date": today.isoformat(),
            "payment_method": "Efectivo",
            "notes": "Cobrado durante el recorrido",
        },
    )

    payment = Payment.objects.get(kind=Payment.Kind.INSTALLMENT)
    assert response.status_code == 302
    assert payment.collector == collector
    assert payment.collection_assignment == route.assignments.get()

    detail = client.get(reverse("core:collector_detail", args=[collector.pk]))
    assert detail.context["total_collected"] == amount
    assert detail.context["days_worked"] == 1


def test_no_payment_result_is_attributed_to_assigned_collector(client):
    today = timezone.localdate()
    sale = make_due_sale()
    collector = Collector.objects.create(name="Mariela")
    route = save_collection_route(
        collection_date=today,
        collector=collector,
        customer_ids=[sale.customer_id],
    )

    response = client.post(
        reverse("core:collection_did_not_pay", args=[sale.pk]),
        {"fecha": today.isoformat()},
    )

    attempt = CollectionAttempt.objects.get()
    assert response.status_code == 302
    assert attempt.collector == collector
    assert attempt.collection_assignment == route.assignments.get()


def test_collector_statistics_count_one_visited_customer_with_multiple_sales():
    today = timezone.localdate()
    customer = make_customer(first_name="Una", last_name="Persona")
    first_sale = make_due_sale(customer=customer, product_name="Producto uno")
    second_sale = make_due_sale(customer=customer, product_name="Producto dos")
    collector = Collector.objects.create(name="Cobrador preciso")
    route = save_collection_route(
        collection_date=today,
        collector=collector,
        customer_ids=[customer.pk],
    )
    assignment = route.assignments.get()
    for sale in (first_sale, second_sale):
        CollectionAttempt.objects.create(
            customer=customer,
            sale=sale,
            collector=collector,
            collection_assignment=assignment,
            attempt_date=today,
            result=CollectionAttempt.Result.DID_NOT_PAY,
        )

    date_summary = build_date_route_summaries(collection_date=today)[0]
    collector_detail = build_collector_detail(collector=collector)

    assert date_summary["visit_count"] == 1
    assert collector_detail["daily_rows"][0]["attempt_count"] == 1
    assert collector_detail["frequent_customers"][0]["attempt_count"] == 1


def test_assignment_with_activity_cannot_be_removed_or_reassigned(client):
    today = timezone.localdate()
    first_sale = make_due_sale(product_name="Producto uno")
    second_sale = make_due_sale(product_name="Producto dos")
    first = Collector.objects.create(name="Titular")
    second = Collector.objects.create(name="Reemplazo")
    route = save_collection_route(
        collection_date=today,
        collector=first,
        customer_ids=[first_sale.customer_id, second_sale.customer_id],
    )
    assignment = route.assignments.get(customer=first_sale.customer)
    CollectionAttempt.objects.create(
        customer=first_sale.customer,
        sale=first_sale,
        collector=first,
        collection_assignment=assignment,
        attempt_date=today,
        result=CollectionAttempt.Result.DID_NOT_PAY,
    )

    with pytest.raises(ValidationError, match="pagos o visitas"):
        save_collection_route(
            collection_date=today,
            collector=first,
            customer_ids=[second_sale.customer_id],
            route=route,
        )
    with pytest.raises(ValidationError, match="actividad registrada"):
        save_collection_route(
            collection_date=today,
            collector=second,
            customer_ids=[first_sale.customer_id],
        )
    with pytest.raises(ValidationError, match="debe conservarse"):
        delete_collection_route(route=route)


def test_route_without_activity_can_be_discarded(client):
    today = timezone.localdate()
    sale = make_due_sale()
    collector = Collector.objects.create(name="Corrección")
    route = save_collection_route(
        collection_date=today,
        collector=collector,
        customer_ids=[sale.customer_id],
    )

    response = client.post(
        reverse("core:collection_routes"),
        {
            "action": "delete_route",
            "fecha": today.isoformat(),
            "route_id": route.pk,
        },
    )

    assert response.status_code == 302
    assert CollectionRoute.objects.count() == 0
    assert CollectionAssignment.objects.count() == 0


def test_dashboard_and_weekly_agenda_show_light_route_summary(client):
    today = timezone.localdate()
    sale = make_due_sale()
    collector = Collector.objects.create(name="Daniel")
    save_collection_route(
        collection_date=today,
        collector=collector,
        customer_ids=[sale.customer_id],
    )

    dashboard = client.get(reverse("core:home"))
    agenda = client.get(reverse("core:agenda"), {"fecha": today.isoformat()})
    agenda_day = next(day for day in agenda.context["week_days"] if day["date"] == today)

    assert dashboard.context["collector_count"] == 1
    assert dashboard.context["assigned_collection_clients"] == 1
    assert "Daniel" in dashboard.content.decode()
    assert agenda_day["collector_count"] == 1
    assert agenda_day["assigned_client_count"] == 1


def test_export_includes_collector_route_assignment_and_links(tmp_path):
    today = timezone.localdate()
    sale = make_due_sale()
    collector = Collector.objects.create(name="Exportable")
    save_collection_route(
        collection_date=today,
        collector=collector,
        customer_ids=[sale.customer_id],
    )

    archive_path = create_data_export(tmp_path)
    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        payments_header = archive.read("pagos.csv").decode("utf-8-sig").splitlines()[0]

    assert {
        "cobradores.csv",
        "recorridos_cobranza.csv",
        "asignaciones_cobranza.csv",
    } <= names
    assert "cobrador_id" in payments_header
    assert "asignacion_cobranza_id" in payments_header
