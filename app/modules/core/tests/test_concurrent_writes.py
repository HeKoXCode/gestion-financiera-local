from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import OperationalError, close_old_connections
from django.test import Client
from django.urls import reverse

from modules.core.forms import SaleForm
from modules.core.models import Customer, Installment, Product, Sale


def _sale_payload(customer: Customer, product: Product, index: int) -> dict[str, str]:
    return {
        "operation_type": "product",
        "customer": str(customer.pk),
        "product": str(product.pk),
        "product_description": f"Venta concurrente {index}",
        "cash_price": "300000",
        "down_payment": "0",
        "down_payment_method": "",
        "financed_amount": "300000",
        "delivery_date": "2026-08-20",
        "first_due_date": "2026-08-27",
        "frequency": "weekly",
        "installment_count": "30",
        "installment_amount": "10000",
        "historical_paid_installments": "0",
        "historical_payment_method": "Efectivo",
        "historical_late_installments": "{}",
    }


@pytest.mark.django_db(transaction=True)
def test_simultaneous_sale_posts_from_separate_tabs_are_not_lost():
    customers = [
        Customer.objects.create(
            first_name=f"Cliente {index}",
            last_name="Concurrente",
            phone=f"000{index}",
            address=f"Calle {index}",
        )
        for index in range(4)
    ]
    products = [Product.objects.create(name=f"Producto concurrente {index}") for index in range(4)]
    barrier = Barrier(4)

    def submit(index: int) -> tuple[int, str]:
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            response = Client().post(
                reverse("core:sale_create"),
                _sale_payload(customers[index], products[index], index),
            )
            return response.status_code, response.url
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(submit, range(4)))

    assert all(status == 302 for status, _url in results)
    assert Sale.objects.count() == 4
    assert Installment.objects.count() == 120


@pytest.mark.django_db
def test_dynamic_pages_are_not_reused_stale_by_the_browser(client):
    response = client.get(reverse("core:sale_list"))

    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert response["Pragma"] == "no-cache"
    assert response["Expires"] == "0"


def test_sqlite_reserves_the_writer_at_the_start_of_atomic_operations(settings):
    assert settings.DATABASES["default"]["OPTIONS"]["timeout"] == 20
    assert settings.DATABASES["default"]["OPTIONS"]["transaction_mode"] == "IMMEDIATE"


@pytest.mark.django_db
def test_v17_accepts_product_sales_and_loans():
    assert list(SaleForm().fields["operation_type"].choices) == list(
        Sale.OperationType.choices
    )


@pytest.mark.django_db
def test_temporary_sqlite_lock_keeps_the_completed_form_visible(client, monkeypatch):
    customer = Customer.objects.create(
        first_name="Cliente",
        last_name="Ocupado",
        phone="0000",
        address="Calle 1",
    )
    product = Product.objects.create(name="Producto ocupado")

    def raise_locked(*_args, **_kwargs):
        raise OperationalError("database is locked")

    monkeypatch.setattr("modules.core.views.Sale.save", raise_locked)

    response = client.post(
        reverse("core:sale_create"),
        _sale_payload(customer, product, 1),
    )

    assert response.status_code == 200
    assert not Sale.objects.exists()
    assert "Otra ventana estaba terminando de guardar" in response.content.decode()
