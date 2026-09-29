from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from modules.core.models import Customer, Payment, Sale, SaleRevision
from modules.core.services.installments import create_installments
from modules.core.tests.factories import make_customer, make_product, make_sale

pytestmark = pytest.mark.django_db


def edit_post_data(sale, **overrides):
    values = {
        "customer": sale.customer_id,
        "product": sale.product_id,
        "product_description": "Producto corregido",
        "delivery_date": "2026-08-15",
        "cash_price": "60000",
        "down_payment": "0",
        "custom_installment_total": "on",
        "financed_amount": "60000",
        "frequency": Sale.Frequency.WEEKLY,
        "installment_count": "3",
        "first_due_date": "2026-08-18",
        "edit_reason": "Se corrigió la cantidad de cuotas",
    }
    values.update(overrides)
    return values


def test_customer_is_moved_to_safe_archive_and_becomes_read_only(client):
    customer = make_customer()

    response = client.post(
        reverse("core:customer_delete", args=[customer.pk]),
        {"reason": "Cliente duplicado"},
    )
    customer.refresh_from_db()

    assert response.status_code == 302
    assert customer.deleted_at is not None
    assert customer.deletion_reason == "Cliente duplicado"
    assert customer.is_active is False
    assert not Customer.objects.filter(
        pk=customer.pk,
        deleted_at__isnull=True,
    ).exists()

    archive = client.get(reverse("core:secure_archive"), {"tipo": "customers"})
    assert customer.full_name in archive.content.decode()
    assert "Cliente duplicado" in archive.content.decode()

    edit = client.get(reverse("core:customer_edit", args=[customer.pk]))
    assert edit.status_code == 302
    customer.first_name = "Cambio prohibido"
    with pytest.raises(ValidationError, match="Archivo seguro"):
        customer.save()
    with pytest.raises(ValidationError, match="no se eliminan físicamente"):
        customer.delete()


def test_customer_with_active_sale_cannot_be_deleted(client):
    sale = make_sale()
    create_installments(sale)

    response = client.post(
        reverse("core:customer_delete", args=[sale.customer_id]),
        {"reason": "Carga equivocada"},
    )
    sale.customer.refresh_from_db()

    assert response.status_code == 200
    assert sale.customer.deleted_at is None
    assert "tiene una operación activa" in response.content.decode()


def test_cancelled_sale_and_deleted_customer_appear_in_safe_archive(client):
    sale = make_sale()
    create_installments(sale)
    sale.status = Sale.Status.CANCELLED
    sale.cancelled_on = timezone.localdate()
    sale.cancellation_reason = "Venta duplicada"
    sale.save()

    client.post(
        reverse("core:customer_delete", args=[sale.customer_id]),
        {"reason": "Cliente duplicado"},
    )

    normal_sales = client.get(reverse("core:sale_list"), {"estado": "all"})
    cancelled_archive = client.get(
        reverse("core:secure_archive"),
        {"tipo": "cancelled"},
    )
    assert sale.product_description not in normal_sales.content.decode()
    assert sale.product_description in cancelled_archive.content.decode()
    assert "Venta duplicada" in cancelled_archive.content.decode()


def test_sale_can_be_edited_twice_and_each_previous_version_is_protected(client):
    sale = make_sale(
        cash_price=Decimal("40000.00"),
        financed_amount=Decimal("40000.00"),
        installment_count=2,
    )
    create_installments(sale)

    first_response = client.post(
        reverse("core:sale_edit", args=[sale.pk]),
        edit_post_data(sale),
    )
    sale.refresh_from_db()
    first_revision = SaleRevision.objects.get(sale=sale, revision_number=1)

    assert first_response.status_code == 302
    assert sale.edit_count == 1
    assert sale.product_description == "Producto corregido"
    assert sale.installments.count() == 3
    assert first_revision.snapshot["sale"]["financed_amount"] == "40000.00"
    assert len(first_revision.snapshot["installments"]) == 2

    second_response = client.post(
        reverse("core:sale_edit", args=[sale.pk]),
        edit_post_data(
            sale,
            product_description="Producto corregido por segunda vez",
            installment_count="4",
            financed_amount="80000",
            edit_reason="Segunda y última corrección",
        ),
    )
    sale.refresh_from_db()

    assert second_response.status_code == 302
    assert sale.edit_count == 2
    assert sale.installments.count() == 4
    assert SaleRevision.objects.filter(sale=sale).count() == 2

    third_attempt = client.get(reverse("core:sale_edit", args=[sale.pk]))
    assert third_attempt.status_code == 302

    first_revision.reason = "Intento de cambio"
    with pytest.raises(ValidationError, match="no puede modificarse"):
        first_revision.save()
    with pytest.raises(ValidationError, match="no puede eliminarse"):
        first_revision.delete()


def test_sale_edit_renders_dates_in_the_html_date_input_format(client):
    sale = make_sale(
        delivery_date=date(2026, 8, 15),
        first_due_date=date(2026, 8, 18),
    )
    create_installments(sale)

    content = client.get(reverse("core:sale_edit", args=[sale.pk])).content.decode()

    assert 'name="delivery_date" value="2026-08-15"' in content
    assert 'name="first_due_date" value="2026-08-18"' in content


def test_sale_edit_rebuilds_its_initial_payment_but_keeps_the_old_copy(client):
    customer = make_customer()
    product = make_product()
    sale = make_sale(
        customer=customer,
        product=product,
        cash_price=Decimal("100000.00"),
        down_payment=Decimal("10000.00"),
        financed_amount=Decimal("90000.00"),
        installment_count=3,
    )
    create_installments(sale)
    Payment.objects.create(
        customer=customer,
        sale=sale,
        payment_date=sale.delivery_date,
        amount=Decimal("10000.00"),
        payment_method="Efectivo",
        kind=Payment.Kind.INITIAL,
    )

    response = client.post(
        reverse("core:sale_edit", args=[sale.pk]),
        edit_post_data(
            sale,
            cash_price="120000",
            down_payment="20000",
            down_payment_method="Transferencia",
            custom_installment_total="",
            financed_amount="1",
            edit_reason="Se corrigió el pago inicial",
        ),
    )
    sale.refresh_from_db()
    current_initial = Payment.objects.get(sale=sale, kind=Payment.Kind.INITIAL)
    revision = SaleRevision.objects.get(sale=sale)

    assert response.status_code == 302
    assert sale.financed_amount == Decimal("100000.00")
    assert current_initial.amount == Decimal("20000.00")
    assert current_initial.payment_method == "Transferencia"
    assert revision.snapshot["payments"][0]["amount"] == "10000.00"


def test_sale_with_installment_payment_cannot_be_edited(client):
    sale = make_sale(installment_count=1, financed_amount=Decimal("20000.00"))
    create_installments(sale)
    Payment.objects.create(
        customer=sale.customer,
        sale=sale,
        payment_date=date(2026, 8, 18),
        amount=Decimal("10000.00"),
        payment_method="Efectivo",
        kind=Payment.Kind.INSTALLMENT,
    )

    response = client.get(reverse("core:sale_edit", args=[sale.pk]))

    assert response.status_code == 302
    assert SaleRevision.objects.count() == 0


def test_cancelled_sale_is_read_only():
    sale = make_sale()
    sale.status = Sale.Status.CANCELLED
    sale.cancelled_on = timezone.localdate()
    sale.cancellation_reason = "Carga equivocada"
    sale.save()

    sale.product_description = "Cambio prohibido"
    with pytest.raises(ValidationError, match="venta cancelada"):
        sale.save()
    with pytest.raises(ValidationError, match="no se eliminan físicamente"):
        sale.delete()
