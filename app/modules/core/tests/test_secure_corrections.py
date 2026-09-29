import uuid
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from modules.core.models import (
    BusinessSettings,
    CollectionAttempt,
    CustomerRevision,
    Payment,
    PaymentAllocation,
    Sale,
    SaleRevision,
)
from modules.core.services.installments import create_installments
from modules.core.services.payments import register_payment, void_payment
from modules.core.tests.factories import make_customer, make_product, make_sale

pytestmark = pytest.mark.django_db


def sale_edit_data(sale, *, operation_key=None, **overrides):
    values = {
        "operation_key": str(operation_key or uuid.uuid4()),
        "customer": str(sale.customer_id),
        "product": str(sale.product_id),
        "product_description": sale.product_description,
        "delivery_date": sale.delivery_date.isoformat(),
        "cash_price": str(sale.cash_price),
        "down_payment": str(sale.down_payment),
        "custom_installment_total": "on",
        "financed_amount": str(sale.financed_amount),
        "frequency": sale.frequency,
        "installment_count": str(sale.installment_count),
        "first_due_date": sale.first_due_date.isoformat(),
        "edit_reason": "Corrección controlada",
    }
    values.update(overrides)
    return values


def customer_edit_data(customer, *, operation_key=None, **overrides):
    values = {
        "operation_key": str(operation_key or uuid.uuid4()),
        "first_name": customer.first_name,
        "last_name": customer.last_name,
        "dni": customer.dni or "",
        "phone": customer.phone,
        "address": customer.address,
        "neighborhood": customer.neighborhood,
        "address_reference": customer.address_reference,
        "notes": customer.notes,
        "edit_reason": "Se corrigió un dato informado",
    }
    values.update(overrides)
    return values


def sale_with_partial_payment():
    sale = make_sale(
        cash_price=Decimal("40000.00"),
        financed_amount=Decimal("40000.00"),
        installment_count=2,
        first_due_date=date(2026, 8, 18),
    )
    create_installments(sale)
    registration = register_payment(
        sale=sale,
        amount=Decimal("10000.00"),
        payment_date=date(2026, 8, 18),
        payment_method="Efectivo",
        operation_key=uuid.uuid4(),
    )
    return sale, registration.payment


def test_customer_edit_archives_original_and_duplicate_post_is_idempotent(client):
    customer = make_customer(phone="111")
    operation_key = uuid.uuid4()
    data = customer_edit_data(customer, operation_key=operation_key, phone="222")

    first = client.post(reverse("core:customer_edit", args=[customer.pk]), data)
    second = client.post(reverse("core:customer_edit", args=[customer.pk]), data)
    customer.refresh_from_db()

    assert first.status_code == 302
    assert second.status_code == 302
    assert customer.phone == "222"
    assert CustomerRevision.objects.filter(customer=customer).count() == 1
    revision = CustomerRevision.objects.get(customer=customer)
    assert revision.snapshot["phone"] == "111"
    assert revision.operation_key == operation_key


def test_customer_revision_is_immutable_and_html_escapes_stored_text(client):
    customer = make_customer(first_name="<script>alert(1)</script>")
    client.post(
        reverse("core:customer_edit", args=[customer.pk]),
        customer_edit_data(customer, first_name="Nombre corregido"),
    )
    revision = CustomerRevision.objects.get()

    detail = client.get(reverse("core:customer_revision_detail", args=[revision.pk]))
    content = detail.content.decode()

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in content
    assert "<script>alert(1)</script>" not in content
    revision.reason = "Intento de cambio"
    with pytest.raises(ValidationError, match="no puede modificarse"):
        revision.save()
    with pytest.raises(ValidationError, match="no puede eliminarse"):
        revision.delete()


def test_delete_block_page_links_every_active_sale(client):
    customer = make_customer()
    first = make_sale(customer=customer, product=make_product(name="Producto A"))
    second = make_sale(customer=customer, product=make_product(name="Producto B"))
    create_installments(first)
    create_installments(second)

    response = client.get(reverse("core:customer_delete", args=[customer.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert reverse("core:sale_detail", args=[first.pk]) in content
    assert reverse("core:sale_detail", args=[second.pk]) in content
    assert "2 operaciones activas" in content


def test_exceptional_edit_requires_unlock_and_exact_second_confirmation(client):
    sale, _ = sale_with_partial_payment()
    blocked = client.get(reverse("core:sale_edit", args=[sale.pk]))
    assert blocked.status_code == 302

    settings = BusinessSettings.get_solo()
    settings.allow_exceptional_sale_edits = True
    settings.save()
    page = client.get(reverse("core:sale_edit", args=[sale.pk]))
    assert page.status_code == 200
    assert "Corrección excepcional habilitada" in page.content.decode()

    rejected = client.post(
        reverse("core:sale_edit", args=[sale.pk]),
        sale_edit_data(sale, exceptional_confirmation="incorrecto"),
    )
    sale.refresh_from_db()
    settings.refresh_from_db()
    assert rejected.status_code == 200
    assert sale.edit_count == 0
    assert settings.allow_exceptional_sale_edits is True
    assert SaleRevision.objects.count() == 0


def test_exceptional_edit_preserves_payment_and_rebuilds_allocations_then_self_disables(client):
    sale, payment = sale_with_partial_payment()
    old_allocation_ids = set(payment.allocations.values_list("pk", flat=True))
    settings = BusinessSettings.get_solo()
    settings.allow_exceptional_sale_edits = True
    settings.save()

    response = client.post(
        reverse("core:sale_edit", args=[sale.pk]),
        sale_edit_data(
            sale,
            product_description="Producto corregido con movimientos",
            exceptional_confirmation="RECALCULAR",
        ),
    )
    sale.refresh_from_db()
    payment.refresh_from_db()
    settings.refresh_from_db()

    assert response.status_code == 302
    assert sale.edit_count == 1
    assert sale.product_description == "Producto corregido con movimientos"
    assert Payment.objects.filter(pk=payment.pk, amount=Decimal("10000.00")).exists()
    assert PaymentAllocation.objects.filter(payment=payment).count() == 1
    assert not old_allocation_ids.intersection(
        PaymentAllocation.objects.filter(payment=payment).values_list("pk", flat=True)
    )
    assert settings.allow_exceptional_sale_edits is False
    revision = SaleRevision.objects.get(sale=sale)
    assert revision.snapshot["payments"][0]["allocations"][0]["installment_number"] == 1


def test_exceptional_edit_rolls_back_everything_when_old_payment_no_longer_fits(client):
    sale, payment = sale_with_partial_payment()
    original_installments = list(sale.installments.values_list("pk", flat=True))
    original_allocations = list(payment.allocations.values_list("pk", flat=True))
    settings = BusinessSettings.get_solo()
    settings.allow_exceptional_sale_edits = True
    settings.save()

    response = client.post(
        reverse("core:sale_edit", args=[sale.pk]),
        sale_edit_data(
            sale,
            first_due_date="2026-08-22",
            exceptional_confirmation="RECALCULAR",
        ),
    )
    sale.refresh_from_db()
    settings.refresh_from_db()

    assert response.status_code == 200
    assert "no entra en el plan corregido" in response.content.decode()
    assert sale.first_due_date == date(2026, 8, 18)
    assert sale.edit_count == 0
    assert list(sale.installments.values_list("pk", flat=True)) == original_installments
    assert list(payment.allocations.values_list("pk", flat=True)) == original_allocations
    assert SaleRevision.objects.count() == 0
    assert settings.allow_exceptional_sale_edits is True


def test_exceptional_customer_correction_moves_related_records_and_snapshot_keeps_original(client):
    sale, payment = sale_with_partial_payment()
    CollectionAttempt.objects.create(
        customer=sale.customer,
        sale=sale,
        attempt_date=date(2026, 8, 19),
        result=CollectionAttempt.Result.PROMISED,
    )
    original_customer_id = sale.customer_id
    corrected_customer = make_customer(first_name="Cliente", last_name="Correcto")
    settings = BusinessSettings.get_solo()
    settings.allow_exceptional_sale_edits = True
    settings.save()

    response = client.post(
        reverse("core:sale_edit", args=[sale.pk]),
        sale_edit_data(
            sale,
            customer=str(corrected_customer.pk),
            exceptional_confirmation="RECALCULAR",
        ),
    )
    sale.refresh_from_db()
    payment.refresh_from_db()
    attempt = sale.collection_attempts.get()

    assert response.status_code == 302
    assert sale.customer_id == corrected_customer.pk
    assert payment.customer_id == corrected_customer.pk
    assert attempt.customer_id == corrected_customer.pk
    archived_customer_id = SaleRevision.objects.get(sale=sale).snapshot["sale"]["customer_id"]
    assert archived_customer_id == original_customer_id


def test_csrf_and_http_method_protections_cover_sensitive_actions():
    customer = make_customer()
    sale = make_sale(customer=customer)
    create_installments(sale)
    csrf_client = Client(enforce_csrf_checks=True)

    delete_without_csrf = csrf_client.post(
        reverse("core:customer_delete", args=[customer.pk]),
        {},
    )
    assert delete_without_csrf.status_code == 403
    assert csrf_client.post(reverse("core:sale_edit", args=[sale.pk]), {}).status_code == 403
    assert csrf_client.get(reverse("core:customer_toggle", args=[customer.pk])).status_code == 405
    assert csrf_client.get(reverse("core:sale_cancel", args=[sale.pk])).status_code == 200


def test_configuration_unlock_needs_exact_confirmation(client):
    settings = BusinessSettings.get_solo()
    base_data = {
        "business_name": settings.business_name,
        "daily_late_fee": str(settings.daily_late_fee),
        "collection_days": [str(day) for day in settings.collection_days],
        "payment_methods_text": "\n".join(settings.payment_methods),
        "available_frequencies": settings.available_frequencies,
        "max_installments": str(settings.max_installments),
        "late_fee_after_partial_payment": "on",
        "whatsapp_message": settings.whatsapp_message,
        "allow_exceptional_sale_edits": "on",
    }

    rejected = client.post(
        reverse("core:configuration"),
        {**base_data, "exceptional_edit_unlock_confirmation": "habilitar"},
    )
    settings.refresh_from_db()
    assert rejected.status_code == 200
    assert settings.allow_exceptional_sale_edits is False

    accepted = client.post(
        reverse("core:configuration"),
        {**base_data, "exceptional_edit_unlock_confirmation": "HABILITAR"},
    )
    settings.refresh_from_db()
    assert accepted.status_code == 302
    assert settings.allow_exceptional_sale_edits is True


def test_noop_sale_edit_does_not_consume_an_edit(client):
    sale = make_sale()
    create_installments(sale)

    response = client.post(
        reverse("core:sale_edit", args=[sale.pk]),
        sale_edit_data(sale),
    )
    sale.refresh_from_db()

    assert response.status_code == 200
    assert "No cambiaste ningún dato" in response.content.decode()
    assert sale.edit_count == 0
    assert SaleRevision.objects.count() == 0


def test_deleted_customer_cannot_be_forged_into_a_sale_edit(client):
    sale = make_sale()
    create_installments(sale)
    deleted_customer = make_customer(
        first_name="Borrado",
        last_name="Protegido",
        deleted_at=timezone.now(),
        deletion_reason="Registro de prueba",
        is_active=False,
    )

    response = client.post(
        reverse("core:sale_edit", args=[sale.pk]),
        sale_edit_data(
            sale,
            customer=str(deleted_customer.pk),
            product_description="Intento malicioso",
        ),
    )
    sale.refresh_from_db()

    assert response.status_code == 200
    assert sale.customer_id != deleted_customer.pk
    assert sale.edit_count == 0


def test_cancelled_sale_payments_are_read_only_even_through_direct_url(client):
    sale, payment = sale_with_partial_payment()
    sale.status = Sale.Status.CANCELLED
    sale.cancelled_on = timezone.localdate()
    sale.cancellation_reason = "Registro protegido"
    sale.save()

    direct_get = client.get(reverse("core:payment_void", args=[payment.pk]))
    direct_post = client.post(
        reverse("core:payment_void", args=[payment.pk]),
        {"reason": "Intento de cambio"},
    )
    payment.refresh_from_db()

    assert direct_get.status_code == 302
    assert direct_post.status_code == 302
    assert payment.status == Payment.Status.REGISTERED
    with pytest.raises(ValidationError, match="Archivo seguro"):
        void_payment(payment=payment, reason="Intento interno")
