import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from modules.core.models import Customer, LateFee, Payment, Product, Sale
from modules.core.services.balances import get_installment_balance
from modules.core.services.installments import add_months, create_installments
from modules.core.services.late_fees import generate_missing_late_fees
from modules.core.services.payments import register_payment
from modules.core.tests.factories import make_customer, make_product, make_sale

pytestmark = pytest.mark.django_db


def sale_post_data(customer, product, **overrides):
    today = timezone.localdate()
    values = {
        "customer": customer.pk,
        "product": product.pk,
        "product_description": "",
        "delivery_date": today.isoformat(),
        "cash_price": "480000",
        "down_payment": "0",
        "down_payment_method": "",
        "custom_installment_total": "on",
        "financed_amount": "480000",
        "frequency": Sale.Frequency.WEEKLY,
        "installment_count": "12",
        "first_due_date": today.isoformat(),
        "first_installment_delivery_status": "",
        "first_installment_payment_method": "",
        "historical_paid_installments": "0",
        "historical_payment_method": "Efectivo",
    }
    values.update(overrides)
    return values


def test_customer_summary_is_printable_and_contains_account_history(client):
    today = timezone.localdate()
    sale = make_sale(
        delivery_date=today,
        first_due_date=today,
        installment_count=2,
        cash_price=Decimal("40000.00"),
        financed_amount=Decimal("40000.00"),
        daily_late_fee=Decimal("0.00"),
    )
    create_installments(sale)
    customer = sale.customer
    customer.dni = "3099911122"
    customer.phone = "11 2233-4455"
    customer.address = "Domicilio interno 887"
    customer.neighborhood = "Barrio interno 887"
    customer.address_reference = "Portón rojo interno"
    customer.notes = "Observación reservada del cobrador"
    customer.save()
    payment = register_payment(
        sale=sale,
        amount=Decimal("20000.00"),
        payment_date=today,
        payment_method="Transferencia",
        notes="Nota interna del pago",
        operation_key=uuid.uuid4(),
    ).payment
    payment.status = Payment.Status.VOIDED
    payment.void_reason = "Motivo interno de anulación"
    payment.save(update_fields=["status", "void_reason", "updated_at"])

    detail = client.get(reverse("core:customer_detail", args=[sale.customer_id]))
    response = client.get(reverse("core:customer_print", args=[sale.customer_id]))
    pdf_response = client.get(
        reverse("core:customer_statement_pdf", args=[sale.customer_id])
    )
    detail_content = detail.content.decode()
    content = response.content.decode()

    assert detail.status_code == 200
    assert reverse("core:customer_print", args=[sale.customer_id]) in detail_content
    assert reverse("core:customer_statement_pdf", args=[sale.customer_id]) in detail_content
    assert response.status_code == 200
    assert sale.customer.full_name in content
    assert sale.product_description in content
    assert "Resumen del cliente" in content
    assert "Estado de todas las cuotas" in content
    assert "Historial de pagos" in content
    assert "$ 20.000,00" in content
    assert "customer-print.css" in content
    assert "Compartir por WhatsApp" in content
    assert "Guardar PDF" in content
    assert "customer-statement-share.js" in content
    assert "wa.me/5491122334455" in detail_content

    # El historial interno conserva estos datos; el resumen compartible no los revela.
    for private_value in (
        customer.dni,
        customer.phone,
        customer.address,
        customer.neighborhood,
        customer.address_reference,
        customer.notes,
        payment.payment_method,
        payment.notes,
        payment.void_reason,
    ):
        assert private_value in detail_content
        assert private_value not in content

    assert pdf_response.status_code == 200
    assert pdf_response["Content-Type"] == "application/pdf"
    assert pdf_response["Cache-Control"] == "no-store"
    assert "attachment;" in pdf_response["Content-Disposition"]
    assert pdf_response.content.startswith(b"%PDF-")


def test_customer_without_phone_keeps_pdf_actions_and_disables_whatsapp(client):
    customer = make_customer(phone="")

    response = client.get(reverse("core:customer_detail", args=[customer.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "WhatsApp (sin teléfono)" in content
    assert "Guardar resumen PDF" in content
    assert "Imprimir resumen" in content
    assert "data-statement-share" not in content


def test_historical_weekly_sale_marks_eleven_of_twelve_installments_paid(client):
    today = timezone.localdate()
    first_due = today - timedelta(weeks=11)
    customer = make_customer()
    product = make_product()

    response = client.post(
        reverse("core:sale_create"),
        sale_post_data(
            customer,
            product,
            delivery_date=first_due.isoformat(),
            first_due_date=(today + timedelta(days=30)).isoformat(),
            same_day_first_due="on",
            first_installment_delivery_status="paid",
            first_installment_payment_method="Efectivo",
            historical_paid_installments="11",
        ),
    )
    sale = Sale.objects.get()
    installments = list(sale.installments.order_by("number"))
    historical_payments = list(
        sale.payments.filter(kind=Payment.Kind.INSTALLMENT).order_by("payment_date")
    )

    assert response.status_code == 302
    assert sale.first_due_date == first_due
    assert len(historical_payments) == 11
    assert [payment.payment_date for payment in historical_payments] == [
        installment.due_date for installment in installments[:11]
    ]
    assert {payment.amount for payment in historical_payments} == {Decimal("40000.00")}
    assert historical_payments[0].notes == "Cuota 1 pagada al recibir el producto."
    assert all(
        "Carga histórica" in payment.notes for payment in historical_payments[1:]
    )
    assert all(
        get_installment_balance(installment, as_of=today).total_due == Decimal("0.00")
        for installment in installments[:11]
    )
    last_balance = get_installment_balance(installments[11], as_of=today)
    assert last_balance.total_due == Decimal("40000.00")
    assert last_balance.days_overdue == 0
    assert LateFee.objects.filter(installment__sale=sale).count() == 0


def test_historical_import_records_exact_late_installments_and_days(client):
    today = timezone.localdate()
    first_due = today - timedelta(days=70)
    customer = make_customer()
    product = make_product()

    response = client.post(
        reverse("core:sale_create"),
        sale_post_data(
            customer,
            product,
            delivery_date=first_due.isoformat(),
            first_due_date=first_due.isoformat(),
            cash_price="120000",
            financed_amount="120000",
            installment_count="12",
            historical_paid_installments="10",
            historical_late_installments='{"2": 10, "6": 1, "10": 4}',
        ),
    )

    assert response.status_code == 302
    sale = Sale.objects.get()
    installments = list(sale.installments.order_by("number"))
    payments_by_installment = {
        payment.allocations.filter(component="principal").get().installment.number: payment
        for payment in sale.payments.filter(kind=Payment.Kind.INSTALLMENT)
    }

    assert len(payments_by_installment) == 10
    assert payments_by_installment[2].payment_date == installments[1].due_date + timedelta(
        days=10
    )
    assert payments_by_installment[3].payment_date == installments[2].due_date
    assert payments_by_installment[6].payment_date == installments[5].due_date + timedelta(
        days=1
    )
    assert payments_by_installment[10].payment_date == installments[9].due_date + timedelta(
        days=4
    )
    assert payments_by_installment[2].amount == Decimal("60000.00")
    assert payments_by_installment[6].amount == Decimal("15000.00")
    assert payments_by_installment[10].amount == Decimal("30000.00")
    assert "10 días de atraso" in payments_by_installment[2].notes
    assert "pagada en fecha" in payments_by_installment[3].notes
    assert LateFee.objects.filter(installment__sale=sale).count() == 15
    assert all(
        get_installment_balance(installment, as_of=today).total_due == Decimal("0.00")
        for installment in installments[:10]
    )

    detail = client.get(reverse("core:customer_detail", args=[customer.pk]))
    printable = client.get(reverse("core:customer_print", args=[customer.pk]))
    detail_content = detail.content.decode()
    printable_content = printable.content.decode()
    assert "Pagada con 10 días de atraso" in detail_content
    assert "Pagada con 4 días de atraso" in printable_content
    assert detail.context["paid_late_installments"] == 3
    assert "$ 50.000,00" in detail_content


def test_historical_late_days_cannot_create_a_future_payment(client):
    today = timezone.localdate()
    customer = make_customer()
    product = make_product()

    response = client.post(
        reverse("core:sale_create"),
        sale_post_data(
            customer,
            product,
            delivery_date=(today - timedelta(days=7)).isoformat(),
            first_due_date=(today - timedelta(days=7)).isoformat(),
            installment_count="2",
            cash_price="80000",
            financed_amount="80000",
            historical_paid_installments="2",
            historical_late_installments='{"2": 1}',
        ),
    )

    assert response.status_code == 200
    assert "La cuota 2 admite como máximo 0 días de atraso hasta hoy" in response.content.decode()
    assert Sale.objects.count() == 0


@pytest.mark.parametrize(
    ("frequency", "first_due"),
    [
        (Sale.Frequency.BIWEEKLY, lambda today: today - timedelta(days=28)),
        (
            Sale.Frequency.MONTHLY,
            lambda today: add_months(date(today.year, today.month, 1), -2),
        ),
    ],
)
def test_historical_import_preserves_biweekly_and_monthly_payment_dates(
    client,
    frequency,
    first_due,
):
    today = timezone.localdate()
    first_due = first_due(today)
    customer = make_customer()
    product = make_product()

    response = client.post(
        reverse("core:sale_create"),
        sale_post_data(
            customer,
            product,
            delivery_date=first_due.isoformat(),
            first_due_date=first_due.isoformat(),
            frequency=frequency,
            installment_count="3",
            cash_price="90000",
            financed_amount="90000",
            historical_paid_installments="2",
        ),
    )
    sale = Sale.objects.get()
    installments = list(sale.installments.order_by("number"))
    payments = list(
        sale.payments.filter(kind=Payment.Kind.INSTALLMENT).order_by("payment_date")
    )

    assert response.status_code == 302
    assert [payment.payment_date for payment in payments] == [
        installment.due_date for installment in installments[:2]
    ]
    assert all(payment.amount == Decimal("30000.00") for payment in payments)
    assert get_installment_balance(installments[2], as_of=today).total_due == Decimal(
        "30000.00"
    )


def test_historical_import_rejects_installments_that_have_not_yet_become_due(client):
    today = timezone.localdate()
    customer = make_customer()
    product = make_product()

    response = client.post(
        reverse("core:sale_create"),
        sale_post_data(
            customer,
            product,
            delivery_date=today.isoformat(),
            first_due_date=today.isoformat(),
            historical_paid_installments="2",
        ),
    )

    assert response.status_code == 200
    assert "Hasta hoy vencieron 1 cuotas" in response.content.decode()
    assert Sale.objects.count() == 0
    assert Payment.objects.count() == 0


def test_same_day_checkbox_recalculates_dates_amounts_and_first_daily_fee(client):
    today = timezone.localdate()
    customer = make_customer()
    product = make_product()

    response = client.post(
        reverse("core:sale_create"),
        sale_post_data(
            customer,
            product,
            delivery_date=today.isoformat(),
            first_due_date=(today + timedelta(days=7)).isoformat(),
            same_day_first_due="on",
            first_installment_delivery_status="pending",
            cash_price="600000",
            down_payment="200000",
            down_payment_method="Efectivo",
            custom_installment_total="",
            financed_amount="999999",
            installment_count="10",
        ),
    )
    sale = Sale.objects.get()
    first_installment = sale.installments.order_by("number").first()

    assert response.status_code == 302
    assert sale.first_due_date == today
    assert sale.financed_amount == Decimal("400000.00")
    assert first_installment.due_date == today
    assert set(sale.installments.values_list("original_amount", flat=True)) == {
        Decimal("40000.00")
    }

    generate_missing_late_fees(as_of=today, sale=sale)
    assert first_installment.late_fees.count() == 0

    generate_missing_late_fees(as_of=today + timedelta(days=1), sale=sale)
    assert first_installment.late_fees.count() == 1
    assert first_installment.late_fees.get().fee_date == today + timedelta(days=1)
    assert first_installment.late_fees.get().amount == Decimal("5000.00")


def test_delivery_can_register_first_installment_and_initial_payment_separately(client):
    today = timezone.localdate()
    customer = make_customer()
    product = make_product()

    response = client.post(
        reverse("core:sale_create"),
        sale_post_data(
            customer,
            product,
            delivery_date=today.isoformat(),
            first_due_date=(today + timedelta(days=7)).isoformat(),
            same_day_first_due="on",
            first_installment_delivery_status="paid",
            first_installment_payment_method="Transferencia",
            cash_price="500000",
            down_payment="100000",
            down_payment_method="Efectivo",
            custom_installment_total="on",
            financed_amount="500000",
            installment_count="10",
        ),
    )
    sale = Sale.objects.get()
    payments = list(sale.payments.order_by("kind", "payment_date", "pk"))
    installment_payment = sale.payments.get(kind=Payment.Kind.INSTALLMENT)
    initial_payment = sale.payments.get(kind=Payment.Kind.INITIAL)
    first_installment = sale.installments.get(number=1)

    assert response.status_code == 302
    assert len(payments) == 2
    assert initial_payment.amount == Decimal("100000.00")
    assert initial_payment.payment_method == "Efectivo"
    assert installment_payment.amount == Decimal("50000.00")
    assert installment_payment.payment_method == "Transferencia"
    assert installment_payment.payment_date == today
    assert installment_payment.notes == "Cuota 1 pagada al recibir el producto."
    assert get_installment_balance(first_installment, as_of=today).total_due == Decimal(
        "0.00"
    )
    assert installment_payment.allocations.get().installment_id == first_installment.pk


def test_same_day_delivery_requires_explicit_first_installment_status(client):
    today = timezone.localdate()
    customer = make_customer()
    product = make_product()

    response = client.post(
        reverse("core:sale_create"),
        sale_post_data(
            customer,
            product,
            delivery_date=today.isoformat(),
            first_due_date=today.isoformat(),
            same_day_first_due="on",
        ),
    )

    assert response.status_code == 200
    assert "Indicá si la cuota 1 fue pagada o quedó pendiente" in response.content.decode()
    assert Sale.objects.count() == 0


def test_sale_form_has_searchable_customer_and_product_options(client):
    customers = [
        Customer(
            first_name=f"Nombre {number}",
            last_name=f"Apellido {number}",
            dni=f"30{number:06d}",
            address=f"Domicilio inventado {number}",
        )
        for number in range(205)
    ]
    Customer.objects.bulk_create(customers)
    Product.objects.create(
        name="Heladera Aurora",
        description="No frost con freezer superior",
    )

    response = client.get(reverse("core:sale_create"))
    content = response.content.decode()

    assert response.status_code == 200
    assert response.context["form"].fields["customer"].queryset.count() == 205
    assert "Buscar por nombre, DNI o domicilio" in content
    assert "Buscar por nombre o descripción" in content
    assert "La cuota 1 vence el día de la entrega" in content
    assert "Vencimiento de la cuota 1" in content
    assert "Fecha del primer cobro" not in content
    assert "Pago inicial aparte" in content
    assert "Pagó la cuota 1 al recibir el producto" in content
    assert 'id="historical-late-feedback"' in content
    assert "Pagada en fecha" in content
    assert "Con atraso" in content
    assert "Aún no venció" in content
    assert "DNI 30000204" in content
    assert "Domicilio inventado 204" in content
    assert "Heladera Aurora · No frost con freezer superior" in content
    assert 'data-select-search="#id_customer"' in content
    assert 'data-select-search="#id_product"' in content
    assert "Seleccionar cliente" not in content
    assert "Seleccionar producto" not in content
    assert "Monto de cada cuota" in content
    assert "OPCIONAL" in content
    assert response.context["form"]["down_payment"].value() in (None, "")


def test_installment_amount_can_calculate_product_price_and_total_on_server(client):
    today = timezone.localdate()
    customer = make_customer()
    product = make_product()

    response = client.post(
        reverse("core:sale_create"),
        sale_post_data(
            customer,
            product,
            delivery_date=today.isoformat(),
            first_due_date=today.isoformat(),
            cash_price="",
            down_payment="100000",
            down_payment_method="Efectivo",
            custom_installment_total="",
            financed_amount="1",
            installment_count="10",
            installment_amount="50000",
        ),
    )

    sale = Sale.objects.get()
    assert response.status_code == 302
    assert sale.cash_price == Decimal("600000.00")
    assert sale.financed_amount == Decimal("500000.00")
    assert set(sale.installments.values_list("original_amount", flat=True)) == {
        Decimal("50000.00")
    }


def test_create_customer_or_product_returns_to_preserved_sale(client):
    customer_response = client.post(
        f'{reverse("core:customer_create")}?volver=venta',
        {
            "first_name": "Cliente",
            "last_name": "Creado desde venta",
            "dni": "",
            "phone": "",
            "address": "Domicilio de prueba 1",
            "neighborhood": "",
            "address_reference": "",
            "notes": "",
        },
    )
    customer = Customer.objects.get(last_name="Creado desde venta")

    assert customer_response.status_code == 302
    assert customer_response["Location"] == (
        f'{reverse("core:sale_create")}?cliente={customer.pk}&restaurar=1'
    )

    product_response = client.post(
        f'{reverse("core:product_create")}?volver=venta',
        {"name": "Producto creado desde venta", "description": ""},
    )
    product = Product.objects.get(name="Producto creado desde venta")

    assert product_response.status_code == 302
    assert product_response["Location"] == (
        f'{reverse("core:sale_create")}?producto={product.pk}&restaurar=1'
    )
