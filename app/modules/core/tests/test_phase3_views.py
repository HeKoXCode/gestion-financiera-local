from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from modules.core.models import BusinessSettings, Customer, Payment, Product, Sale
from modules.core.services.installments import create_installments
from modules.core.tests.factories import make_customer, make_product, make_sale

pytestmark = pytest.mark.django_db


def sale_form_data(customer, product, **overrides):
    values = {
        "customer": customer.pk,
        "product": product.pk,
        "product_description": "Smart TV 50 pulgadas",
        "delivery_date": "2026-08-15",
        "cash_price": "400000",
        "financed_amount": "480000",
        "frequency": Sale.Frequency.WEEKLY,
        "installment_count": "12",
        "first_due_date": "2026-08-18",
    }
    values.update(overrides)
    return values


def test_daily_screen_is_available_without_records(client):
    response = client.get(reverse("core:home"), {"fecha": "2026-08-18"})

    assert response.status_code == 200
    assert "Resumen del 18/08/2026" in response.content.decode()
    assert "No queda cobranza pendiente" in response.content.decode()


def test_daily_screen_shows_due_and_overdue_installments(client):
    sale = make_sale(installment_count=2, financed_amount=Decimal("40000.00"))
    create_installments(sale)

    response = client.get(reverse("core:home"), {"fecha": "2026-08-25"})
    content = response.content.decode()

    assert response.status_code == 200
    assert sale.customer.full_name in content
    assert "7 días tarde" in content
    assert "$ 40.000,00" in content


def test_customer_can_be_created_searched_edited_and_archived(client):
    create_response = client.post(
        reverse("core:customer_create"),
        {
            "first_name": "María",
            "last_name": "Gómez",
            "dni": "",
            "phone": "1144556677",
            "address": "Belgrano 420",
            "neighborhood": "Centro",
            "address_reference": "",
            "notes": "Timbre de la derecha",
        },
    )
    customer = Customer.objects.get()

    assert create_response.status_code == 302
    assert create_response.url == reverse("core:customer_detail", args=[customer.pk])

    search_response = client.get(reverse("core:customer_list"), {"q": "Belgrano"})
    assert customer.full_name in search_response.content.decode()

    edit_response = client.post(
        reverse("core:customer_edit", args=[customer.pk]),
        {
            "first_name": "María",
            "last_name": "Gómez",
            "dni": "30111222",
            "phone": "1100000000",
            "address": "Belgrano 422",
            "neighborhood": "Centro",
            "address_reference": "",
            "notes": "",
        },
    )
    customer.refresh_from_db()

    assert edit_response.status_code == 302
    assert customer.address == "Belgrano 422"
    assert customer.dni == "30111222"

    toggle_response = client.post(reverse("core:customer_toggle", args=[customer.pk]))
    customer.refresh_from_db()

    assert toggle_response.status_code == 302
    assert customer.is_active is False


def test_product_can_be_created_edited_and_archived(client):
    create_response = client.post(
        reverse("core:product_create"),
        {"name": "Heladera", "description": "Con freezer"},
    )
    product = Product.objects.get()

    assert create_response.status_code == 302

    edit_response = client.post(
        reverse("core:product_edit", args=[product.pk]),
        {"name": "Heladera grande", "description": "Con freezer superior"},
    )
    product.refresh_from_db()

    assert edit_response.status_code == 302
    assert product.name == "Heladera grande"

    client.post(reverse("core:product_toggle", args=[product.pk]))
    product.refresh_from_db()
    assert product.is_active is False


def test_sale_form_explains_missing_dependencies(client):
    response = client.get(reverse("core:sale_create"))

    assert response.status_code == 200
    assert "necesitás un cliente y un producto activos" in response.content.decode()


def test_phase_three_pages_render_with_existing_records(client):
    sale = make_sale(installment_count=2, financed_amount=Decimal("40000.00"))
    create_installments(sale)
    urls = [
        reverse("core:customer_list"),
        reverse("core:customer_create"),
        reverse("core:customer_detail", args=[sale.customer.pk]),
        reverse("core:customer_edit", args=[sale.customer.pk]),
        reverse("core:product_list"),
        reverse("core:product_create"),
        reverse("core:product_edit", args=[sale.product.pk]),
        reverse("core:sale_list"),
        reverse("core:sale_create"),
        reverse("core:sale_detail", args=[sale.pk]),
        reverse("core:sale_cancel", args=[sale.pk]),
    ]

    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, url


def test_sale_creation_freezes_settings_and_generates_installments(client):
    customer = make_customer()
    product = make_product()

    response = client.post(
        reverse("core:sale_create"),
        sale_form_data(customer, product, product_description=""),
    )
    sale = Sale.objects.get()

    assert response.status_code == 302
    assert response.url == reverse("core:sale_detail", args=[sale.pk])
    assert sale.product_description == product.name
    assert sale.daily_late_fee == Decimal("5000.00")
    assert sale.installments.count() == 12
    assert sum(sale.installments.values_list("original_amount", flat=True)) == Decimal(
        "480000.00"
    )


def test_sale_creation_supports_monthly_installments(client):
    customer = make_customer()
    product = make_product()

    response = client.post(
        reverse("core:sale_create"),
        sale_form_data(
            customer,
            product,
            financed_amount="360000",
            frequency=Sale.Frequency.MONTHLY,
            installment_count="3",
            first_due_date="2026-08-31",
        ),
    )
    sale = Sale.objects.get()

    assert response.status_code == 302
    assert sale.frequency == Sale.Frequency.MONTHLY
    assert list(sale.installments.values_list("due_date", flat=True)) == [
        date(2026, 8, 31),
        date(2026, 9, 30),
        date(2026, 10, 31),
    ]
    assert list(sale.installments.values_list("original_amount", flat=True)) == [
        Decimal("120000.00"),
        Decimal("120000.00"),
        Decimal("120000.00"),
    ]


def test_sale_creation_records_initial_payment_and_finances_only_the_balance(client):
    customer = make_customer()
    product = make_product()

    response = client.post(
        reverse("core:sale_create"),
        sale_form_data(
            customer,
            product,
            delivery_date=timezone.localdate().isoformat(),
            cash_price="600000",
            down_payment="200000",
            down_payment_method="Efectivo",
            financed_amount="400000",
            installment_count="20",
            first_due_date=timezone.localdate().isoformat(),
        ),
    )

    sale = Sale.objects.get()
    initial_payment = Payment.objects.get(sale=sale)

    assert response.status_code == 302
    assert sale.cash_price == Decimal("600000.00")
    assert sale.down_payment == Decimal("200000.00")
    assert sale.financed_amount == Decimal("400000.00")
    assert sale.operation_total == Decimal("600000.00")
    assert sale.installments.count() == 20
    assert set(sale.installments.values_list("original_amount", flat=True)) == {
        Decimal("20000.00")
    }
    assert initial_payment.kind == Payment.Kind.INITIAL
    assert initial_payment.amount == Decimal("200000.00")
    assert initial_payment.payment_method == "Efectivo"
    assert initial_payment.allocations.count() == 0

    detail = client.get(response.url).content.decode()
    assert "Precio del producto" in detail
    assert "Entrega inicial" in detail
    assert "Total en cuotas" in detail


def test_initial_payment_requires_method_and_non_future_delivery(client):
    customer = make_customer()
    product = make_product()

    response = client.post(
        reverse("core:sale_create"),
        sale_form_data(
            customer,
            product,
            delivery_date="2099-01-01",
            first_due_date="2099-01-01",
            down_payment="100000",
            down_payment_method="",
        ),
    )

    assert response.status_code == 200
    assert Sale.objects.count() == 0
    assert "Elegí cómo se recibió la entrega inicial" in response.content.decode()
    assert "no puede tener una fecha de entrega futura" in response.content.decode()


def test_sale_creation_respects_maximum_installments(client):
    settings = BusinessSettings.get_solo()
    settings.max_installments = 6
    settings.save()
    customer = make_customer()
    product = make_product()

    response = client.post(
        reverse("core:sale_create"),
        sale_form_data(customer, product, installment_count="7"),
    )

    assert response.status_code == 200
    assert "permite hasta 6 cuotas" in response.content.decode()
    assert Sale.objects.count() == 0


def test_customer_query_parameter_preselects_sale_customer(client):
    customer = make_customer()
    make_product()

    response = client.get(reverse("core:sale_create"), {"cliente": customer.pk})

    assert response.status_code == 200
    assert response.context["form"].initial["customer"] == customer


def test_sale_detail_displays_full_schedule(client):
    sale = make_sale(installment_count=3, financed_amount=Decimal("30000.00"))
    create_installments(sale)

    response = client.get(reverse("core:sale_detail", args=[sale.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "3 cuotas generadas" in content
    assert "1 de 3" in content
    assert "3 de 3" in content


def test_sale_cancellation_requires_reason_and_preserves_history(client):
    sale = make_sale(installment_count=1, financed_amount=Decimal("20000.00"))
    create_installments(sale)

    invalid_response = client.post(reverse("core:sale_cancel", args=[sale.pk]), {"reason": ""})
    sale.refresh_from_db()
    assert invalid_response.status_code == 200
    assert sale.status == Sale.Status.ACTIVE

    response = client.post(
        reverse("core:sale_cancel", args=[sale.pk]),
        {"reason": "El cliente devolvió el producto"},
    )
    sale.refresh_from_db()

    assert response.status_code == 302
    assert sale.status == Sale.Status.CANCELLED
    assert sale.cancelled_on == timezone.localdate()
    assert sale.installments.count() == 1


def test_cancelled_sale_disappears_from_daily_screen(client):
    sale = make_sale(installment_count=1, financed_amount=Decimal("20000.00"))
    create_installments(sale)
    sale.status = Sale.Status.CANCELLED
    sale.cancelled_on = date(2026, 8, 16)
    sale.cancellation_reason = "Operación cancelada"
    sale.save()

    response = client.get(reverse("core:home"), {"fecha": "2026-08-18"})

    assert sale.customer.full_name not in response.content.decode()
