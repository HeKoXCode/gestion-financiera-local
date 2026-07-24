import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from launcher import launcher, restorer
from modules.core.models import Sale
from modules.core.services.installments import create_installments
from modules.core.tests.factories import make_customer, make_product, make_sale

pytestmark = pytest.mark.django_db


def test_daily_a4_sheet_handles_eighteen_clients_and_long_addresses(client):
    today = timezone.localdate()
    product = make_product(name="Heladera familiar")
    expected_names = []
    for number in range(1, 19):
        customer = make_customer(
            first_name=f"Cliente {number:02d}",
            last_name=("Apellido compuesto muy extenso " + str(number)).ljust(70, "x"),
            address=(f"Avenida de prueba número {number} ").ljust(160, "y"),
            neighborhood="Barrio de prueba",
        )
        sale = make_sale(
            customer=customer,
            product=product,
            delivery_date=today - timedelta(days=30),
            first_due_date=today,
            financed_amount=Decimal("20000.00"),
            installment_count=1,
            daily_late_fee=Decimal("0.00"),
        )
        create_installments(sale)
        expected_names.append(customer.full_name)

    response = client.get(reverse("core:collection_print"))
    content = response.content.decode()

    assert response.status_code == 200
    assert response.context["client_count"] == 18
    assert len(response.context["rows"]) == 18
    assert response.context["total_expected"] == Decimal("360000.00")
    assert all(name in content for name in expected_names)
    assert "size: A4 portrait" in Path("app/static/css/print.css").read_text(encoding="utf-8")


def test_sale_and_installments_roll_back_together_on_generation_error(
    client,
    monkeypatch,
):
    customer = make_customer()
    product = make_product()
    today = timezone.localdate()

    def fail_installment_generation(_sale):
        raise ValidationError("Fallo simulado antes de completar las cuotas.")

    monkeypatch.setattr(
        "modules.core.views.create_installments",
        fail_installment_generation,
    )

    response = client.post(
        reverse("core:sale_create"),
        {
            "customer": customer.pk,
            "product": product.pk,
            "product_description": product.name,
            "delivery_date": (today - timedelta(days=1)).isoformat(),
            "cash_price": "18000.00",
            "financed_amount": "20000.00",
            "frequency": Sale.Frequency.WEEKLY,
            "installment_count": "1",
            "first_due_date": today.isoformat(),
        },
    )

    assert response.status_code == 200
    assert Sale.objects.count() == 0
    assert "Fallo simulado" in response.content.decode()


def test_user_interface_has_no_external_asset_dependency():
    external_markers = (
        "http://",
        "https://",
        "//cdn",
        "unpkg.com",
        "jsdelivr.net",
        "fonts.googleapis.com",
    )
    checked_files = [
        *Path("app/templates").rglob("*.html"),
        *Path("app/static").rglob("*.css"),
        *Path("app/static").rglob("*.js"),
    ]

    assert checked_files
    for path in checked_files:
        content = path.read_text(encoding="utf-8").lower()
        assert not any(marker in content for marker in external_markers), path


def test_frozen_launchers_keep_data_beside_executables(monkeypatch, tmp_path):
    executable = tmp_path / "copia portable" / "GestionFinanciera.exe"
    internal = executable.parent / "_internal"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    monkeypatch.setattr(sys, "_MEIPASS", str(internal), raising=False)

    assert launcher.portable_root() == executable.parent
    assert launcher.application_code_root(executable.parent) == internal
    assert restorer.portable_root() == executable.parent
