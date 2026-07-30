import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from modules.core.forms import BusinessSettingsForm
from modules.core.models import BusinessSettings, Payment, Sale
from modules.core.services.installments import create_installments
from modules.core.services.payments import register_initial_payment, register_payment
from modules.core.services.reports import build_reports
from modules.core.tests.factories import make_customer, make_product, make_sale

pytestmark = pytest.mark.django_db


def make_report_sale(
    *,
    amount=Decimal("20000.00"),
    installment_count=1,
    first_due_offset=0,
    customer=None,
    product=None,
):
    today = timezone.localdate()
    sale = make_sale(
        customer=customer,
        product=product,
        delivery_date=today - timedelta(days=30),
        first_due_date=today + timedelta(days=first_due_offset),
        financed_amount=amount,
        installment_count=installment_count,
        daily_late_fee=Decimal("0.00"),
    )
    create_installments(sale)
    return sale


def test_report_payment_totals_use_day_week_and_month_periods():
    selected = date(2026, 8, 18)
    sale = make_sale(
        delivery_date=date(2026, 7, 1),
        first_due_date=date(2026, 7, 8),
    )
    values = [
        (selected, Decimal("100.00")),
        (selected - timedelta(days=1), Decimal("200.00")),
        (selected.replace(day=1), Decimal("300.00")),
    ]
    for payment_date, amount in values:
        Payment.objects.create(
            customer=sale.customer,
            sale=sale,
            payment_date=payment_date,
            amount=amount,
            payment_method="Efectivo",
        )

    report = build_reports(as_of=selected)

    assert report["collected_today"] == Decimal("100.00")
    assert report["collected_week"] == Decimal("300.00")
    assert report["collected_month"] == Decimal("600.00")


def test_reports_include_the_initial_payment_as_received_money():
    today = timezone.localdate()
    sale = make_sale(
        cash_price=Decimal("600000.00"),
        down_payment=Decimal("200000.00"),
        financed_amount=Decimal("400000.00"),
        delivery_date=today,
        first_due_date=today,
    )
    create_installments(sale)
    register_initial_payment(sale=sale, payment_method="Efectivo")

    report = build_reports(as_of=today)

    assert report["collected_today"] == Decimal("200000.00")
    assert report["payment_methods"] == [{"name": "Efectivo", "amount": Decimal("200000.00")}]


def test_reports_separate_portfolio_due_and_overdue_amounts():
    today = timezone.localdate()
    sale = make_report_sale(
        amount=Decimal("40000.00"),
        installment_count=2,
        first_due_offset=-7,
    )

    report = build_reports(as_of=today)

    assert report["portfolio_pending"] == Decimal("40000.00")
    assert report["due_total"] == Decimal("40000.00")
    assert report["overdue_total"] == Decimal("20000.00")
    assert report["overdue_clients"] == 1
    assert report["debtors"][0]["customer"] == sale.customer
    assert report["highest_debt"][0]["total_balance"] == Decimal("40000.00")


def test_reports_respect_partial_payments():
    sale = make_report_sale(first_due_offset=-1)
    register_payment(
        sale=sale,
        amount=Decimal("5000.00"),
        payment_date=timezone.localdate(),
        payment_method="Efectivo",
        operation_key=uuid.uuid4(),
    )

    report = build_reports(as_of=timezone.localdate())

    assert report["portfolio_pending"] == Decimal("15000.00")
    assert report["due_total"] == Decimal("15000.00")
    assert report["overdue_total"] == Decimal("15000.00")
    assert report["collected_today"] == Decimal("5000.00")


def test_cancelled_sales_are_excluded_from_reports():
    sale = make_report_sale()
    sale.status = Sale.Status.CANCELLED
    sale.cancelled_on = timezone.localdate()
    sale.cancellation_reason = "Operación cancelada"
    sale.full_clean()
    sale.save()

    report = build_reports(as_of=timezone.localdate())

    assert report["portfolio_pending"] == Decimal("0.00")
    assert report["products_most_sold"] == []
    assert report["highest_debt"] == []


def test_product_ranking_and_up_to_date_clients():
    television = make_product(name="Televisor")
    freezer = make_product(name="Freezer")
    first_customer = make_customer(first_name="Ana", last_name="López")
    second_customer = make_customer(first_name="Beto", last_name="Díaz")
    make_report_sale(
        customer=first_customer,
        product=television,
        first_due_offset=1,
    )
    make_report_sale(
        customer=second_customer,
        product=television,
        first_due_offset=1,
    )
    make_report_sale(
        customer=second_customer,
        product=freezer,
        first_due_offset=1,
    )

    report = build_reports(as_of=timezone.localdate())

    assert report["products_most_sold"][0]["product"] == television
    assert report["products_most_sold"][0]["units"] == 2
    assert report["up_to_date_clients"] == 2
    assert report["overdue_clients"] == 0


def test_reports_page_and_main_navigation_render(client):
    make_report_sale(first_due_offset=-1)
    response = client.get(reverse("core:reports"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Cobrado en la fecha" in content
    assert "Clientes morosos" in content
    assert "Productos más vendidos" in content
    assert reverse("core:reports") in content

    configuration_response = client.get(reverse("core:configuration"))
    assert configuration_response.status_code == 200
    assert "Vista de impresión" in configuration_response.content.decode()


def test_daily_print_sheet_contains_collection_fields(client):
    sale = make_report_sale()

    response = client.get(reverse("core:collection_print"))
    content = response.content.decode()

    assert response.status_code == 200
    assert sale.customer.full_name in content
    assert sale.customer.address in content
    assert "Firma" in content
    assert "Observaciones" in content
    assert "print.css" in content
    assert "$ 20.000,00" in content


def test_empty_daily_print_sheet_is_still_printable(client):
    response = client.get(
        reverse("core:collection_print"),
        {"fecha": "2026-01-01"},
    )

    assert response.status_code == 200
    assert "Sin cobranzas pendientes" in response.content.decode()


def test_configuration_updates_business_and_financial_preferences(client):
    response = client.post(
        reverse("core:configuration"),
        {
            "business_name": "Ventas del Sur",
            "daily_late_fee": "6500.00",
            "collection_days": ["0", "2", "5"],
            "payment_methods_text": "Efectivo\nTarjeta",
            "available_frequencies": [Sale.Frequency.WEEKLY],
            "max_installments": "24",
            "charge_sundays": "on",
            "late_fee_after_partial_payment": "on",
            "whatsapp_message": "Hola {nombre}, debés {monto}.",
        },
    )
    settings = BusinessSettings.get_solo()

    assert response.status_code == 302
    assert response.url == reverse("core:configuration")
    assert settings.business_name == "Ventas del Sur"
    assert settings.daily_late_fee == Decimal("6500.00")
    assert settings.collection_days == [0, 2, 5]
    assert settings.payment_methods == ["Efectivo", "Tarjeta"]
    assert settings.available_frequencies == [Sale.Frequency.WEEKLY]
    assert settings.max_installments == 24
    assert settings.allow_advance_payments is False


def test_configuration_rejects_unsafe_logo_type():
    form = BusinessSettingsForm(
        data={
            "business_name": "Ventas del Sur",
            "daily_late_fee": "5000.00",
            "collection_days": ["0"],
            "payment_methods_text": "Efectivo",
            "available_frequencies": [Sale.Frequency.WEEKLY],
            "max_installments": "12",
            "whatsapp_message": "Hola {nombre}",
        },
        files={
            "logo": SimpleUploadedFile(
                "logo.svg",
                b"<svg></svg>",
                content_type="image/svg+xml",
            )
        },
        instance=BusinessSettings.get_solo(),
    )

    assert form.is_valid() is False
    assert "logo" in form.errors


def test_uploaded_media_is_available_in_local_final_mode(client, settings, tmp_path):
    settings.DEBUG = False
    settings.MEDIA_ROOT = tmp_path
    logo_directory = tmp_path / "logos"
    logo_directory.mkdir()
    (logo_directory / "test-logo.png").write_bytes(b"fake-png-content")

    response = client.get("/media/logos/test-logo.png")
    body = b"".join(response.streaming_content)

    assert response.status_code == 200
    assert body == b"fake-png-content"
