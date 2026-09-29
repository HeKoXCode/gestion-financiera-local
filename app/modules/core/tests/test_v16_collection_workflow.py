from datetime import date, timedelta
from decimal import Decimal
from zipfile import ZipFile

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from modules.core.models import (
    BusinessSettings,
    Collector,
    CustomerCollectorLink,
    Installment,
    LateFeePausePeriod,
    Sale,
)
from modules.core.services.collectors import (
    move_collector_to_safe_archive,
    save_collection_route,
)
from modules.core.services.export_data import create_data_export
from modules.core.services.installments import calculate_due_dates, create_installments
from modules.core.services.late_fees import (
    generate_missing_late_fees,
    pause_late_fee_generation,
    resume_late_fee_generation,
)
from modules.core.services.safe_archive import build_sale_snapshot
from modules.core.tests.factories import make_sale

pytestmark = pytest.mark.django_db


def make_overdue_sale(*, due_date: date, late_fee: str = "5000.00") -> Sale:
    sale = make_sale(
        delivery_date=due_date,
        first_due_date=due_date,
        installment_count=1,
        financed_amount=Decimal("20000.00"),
        daily_late_fee=Decimal(late_fee),
    )
    Installment.objects.create(
        sale=sale,
        number=1,
        due_date=due_date,
        original_amount=Decimal("20000.00"),
    )
    return sale


def test_daily_schedule_skips_disabled_days_and_crosses_month_boundary():
    dates = calculate_due_dates(
        first_due_date=date(2026, 1, 31),
        frequency=Sale.Frequency.DAILY,
        installment_count=4,
        collection_days=[0, 1, 2, 3, 4, 5],
    )

    assert dates == [
        date(2026, 1, 31),
        date(2026, 2, 2),
        date(2026, 2, 3),
        date(2026, 2, 4),
    ]


def test_daily_schedule_requires_at_least_one_enabled_day():
    with pytest.raises(ValidationError, match="al menos un día"):
        calculate_due_dates(
            first_due_date=date(2026, 1, 1),
            frequency=Sale.Frequency.DAILY,
            installment_count=2,
            collection_days=[],
        )


def test_existing_daily_installments_do_not_move_when_configuration_changes():
    settings = BusinessSettings.get_solo()
    settings.collection_days = [0, 1, 2, 3, 4, 5]
    settings.available_frequencies = [
        Sale.Frequency.DAILY,
        Sale.Frequency.WEEKLY,
        Sale.Frequency.BIWEEKLY,
        Sale.Frequency.MONTHLY,
    ]
    settings.save()
    sale = make_sale(
        frequency=Sale.Frequency.DAILY,
        first_due_date=date(2026, 1, 31),
        installment_count=3,
        financed_amount=Decimal("30000.00"),
    )
    create_installments(sale)
    original_dates = list(sale.installments.values_list("due_date", flat=True))

    settings.collection_days = [0, 2, 4]
    settings.save()

    assert list(sale.installments.values_list("due_date", flat=True)) == original_dates


def test_pause_day_controls_tomorrows_fee_without_erasing_previous_fees():
    sale = make_overdue_sale(due_date=date(2026, 1, 1))
    installment = sale.installments.get()
    generate_missing_late_fees(as_of=date(2026, 1, 3), sale=sale)

    period, created = pause_late_fee_generation(
        sale=sale,
        reason="Acuerdo temporal con el cliente",
        action_date=date(2026, 1, 3),
    )
    during_pause = generate_missing_late_fees(as_of=date(2026, 1, 5), sale=sale)

    assert created is True
    assert period.paused_from == date(2026, 1, 3)
    assert during_pause.created == 0
    assert list(installment.late_fees.values_list("fee_date", flat=True)) == [
        date(2026, 1, 2),
        date(2026, 1, 3),
    ]

    resumed, changed = resume_late_fee_generation(
        sale=sale,
        action_date=date(2026, 1, 5),
    )
    after_resume = generate_missing_late_fees(as_of=date(2026, 1, 6), sale=sale)

    assert changed is True
    assert resumed.resumed_at == date(2026, 1, 5)
    assert after_resume.created == 1
    assert list(installment.late_fees.values_list("fee_date", flat=True)) == [
        date(2026, 1, 2),
        date(2026, 1, 3),
        date(2026, 1, 6),
    ]


def test_pause_and_resume_are_idempotent_and_keep_auditable_periods():
    sale = make_overdue_sale(due_date=date(2026, 1, 1))
    first, first_created = pause_late_fee_generation(
        sale=sale,
        reason="Primera pausa",
        action_date=date(2026, 1, 3),
    )
    repeated, repeated_created = pause_late_fee_generation(
        sale=sale,
        reason="Intento repetido",
        action_date=date(2026, 1, 4),
    )
    resumed, changed = resume_late_fee_generation(
        sale=sale,
        action_date=date(2026, 1, 5),
    )
    repeated_resume, repeated_changed = resume_late_fee_generation(
        sale=sale,
        action_date=date(2026, 1, 6),
    )

    assert first_created is True
    assert repeated_created is False
    assert repeated.pk == first.pk
    assert changed is True
    assert repeated_changed is False
    assert repeated_resume.pk == resumed.pk
    assert LateFeePausePeriod.objects.count() == 1


def test_multiple_pause_periods_only_skip_their_own_accrual_days():
    sale = make_overdue_sale(due_date=date(2026, 1, 1))
    installment = sale.installments.get()
    pause_late_fee_generation(
        sale=sale,
        reason="Pausa uno",
        action_date=date(2026, 1, 3),
    )
    resume_late_fee_generation(sale=sale, action_date=date(2026, 1, 5))
    pause_late_fee_generation(
        sale=sale,
        reason="Pausa dos",
        action_date=date(2026, 1, 6),
    )
    resume_late_fee_generation(sale=sale, action_date=date(2026, 1, 7))

    generate_missing_late_fees(as_of=date(2026, 1, 8), sale=sale)

    assert list(installment.late_fees.values_list("fee_date", flat=True)) == [
        date(2026, 1, 2),
        date(2026, 1, 3),
        date(2026, 1, 6),
        date(2026, 1, 8),
    ]


def test_cancelled_sale_cannot_start_a_pause():
    sale = make_overdue_sale(due_date=date(2026, 1, 1))
    sale.status = Sale.Status.CANCELLED
    sale.cancelled_on = date(2026, 1, 2)
    sale.cancellation_reason = "Operación cancelada"
    sale.save()

    with pytest.raises(ValidationError, match="operación activa"):
        pause_late_fee_generation(
            sale=sale,
            reason="No corresponde",
            action_date=date(2026, 1, 3),
        )


def test_pause_actions_are_post_only_and_render_without_hiding_debt(client):
    today = timezone.localdate()
    sale = make_overdue_sale(due_date=today - timedelta(days=2))
    generate_missing_late_fees(as_of=today, sale=sale)
    debt_before = sum(
        sale.installments.get().late_fees.values_list("amount", flat=True),
        Decimal("0.00"),
    )

    assert client.get(reverse("core:late_fee_pause", args=[sale.pk])).status_code == 405
    response = client.post(
        reverse("core:late_fee_pause", args=[sale.pk]),
        {"reason": "Acuerdo de espera", "next": reverse("core:collection_list")},
    )
    page = client.get(reverse("core:collection_list"), {"fecha": today.isoformat()})

    assert response.status_code == 302
    assert "Interés diario pausado" in page.content.decode()
    assert (
        sum(
            sale.installments.get().late_fees.values_list("amount", flat=True),
            Decimal("0.00"),
        )
        == debt_before
    )

    printed = client.get(reverse("core:collection_print"), {"fecha": today.isoformat()})
    assert "Interés diario pausado" in printed.content.decode()


def test_route_assignment_creates_and_reassigns_habitual_collector():
    today = timezone.localdate()
    sale = make_overdue_sale(due_date=today)
    first = Collector.objects.create(name="Esteban")
    second = Collector.objects.create(name="María")
    save_collection_route(
        collection_date=today,
        collector=first,
        customer_ids=[sale.customer_id],
    )

    current = CustomerCollectorLink.objects.get(ended_at__isnull=True)
    assert current.collector == first

    save_collection_route(
        collection_date=today + timedelta(days=1),
        collector=second,
        customer_ids=[sale.customer_id],
    )

    first_link = CustomerCollectorLink.objects.get(collector=first)
    current = CustomerCollectorLink.objects.get(ended_at__isnull=True)
    assert first_link.ended_at is not None
    assert current.collector == second
    assert CustomerCollectorLink.objects.count() == 2


def test_next_plan_preselects_habitual_clients_from_collector_card(client):
    today = timezone.localdate()
    sale = make_overdue_sale(due_date=today)
    collector = Collector.objects.create(name="Esteban habitual")
    save_collection_route(
        collection_date=today,
        collector=collector,
        customer_ids=[sale.customer_id],
    )
    next_day = today + timedelta(days=1)

    response = client.get(
        reverse("core:collection_routes"),
        {"fecha": next_day.isoformat(), "cobrador": collector.pk},
    )
    customer_row = next(
        row for row in response.context["planner_rows"] if row["customer"].pk == sale.customer_id
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert customer_row["selected_for_route"] is True
    assert customer_row["habitual_collector"] == collector
    assert "Cobrador habitual: Esteban habitual" in content
    assert 'select class="form-control" name="collector"' not in content


def test_collection_does_not_repeat_same_collector_as_plan_and_habitual(client):
    today = timezone.localdate()
    sale = make_overdue_sale(due_date=today)
    collector = Collector.objects.create(name="Esteban sin duplicar")
    save_collection_route(
        collection_date=today,
        collector=collector,
        customer_ids=[sale.customer_id],
    )

    response = client.get(
        reverse("core:collection_list"),
        {"fecha": today.isoformat()},
    )
    content = response.content.decode()

    assert "Planilla: Esteban sin duplicar" in content
    assert "Cobrador: Esteban sin duplicar" not in content


def test_archiving_collector_closes_habitual_links():
    today = timezone.localdate()
    sale = make_overdue_sale(due_date=today)
    collector = Collector.objects.create(name="Cobrador a archivar")
    save_collection_route(
        collection_date=today,
        collector=collector,
        customer_ids=[sale.customer_id],
    )

    move_collector_to_safe_archive(
        collector=collector,
        reason="Ya no realiza recorridos",
    )

    link = CustomerCollectorLink.objects.get()
    assert link.ended_at is not None
    assert CustomerCollectorLink.objects.filter(ended_at__isnull=True).count() == 0


def test_invalid_hidden_collector_cannot_create_a_route(client):
    today = timezone.localdate()
    sale = make_overdue_sale(due_date=today)

    response = client.post(
        reverse("core:collection_routes"),
        {
            "action": "save_route",
            "fecha": today.isoformat(),
            "collector": "999999",
            "customers": [sale.customer_id],
        },
    )

    assert response.status_code == 200
    assert "Elegí un cobrador válido" in response.content.decode()
    assert CustomerCollectorLink.objects.count() == 0


def test_export_and_safe_snapshot_include_new_audit_records(tmp_path):
    today = timezone.localdate()
    sale = make_overdue_sale(due_date=today - timedelta(days=1))
    collector = Collector.objects.create(name="Exportable v1.6")
    save_collection_route(
        collection_date=today,
        collector=collector,
        customer_ids=[sale.customer_id],
    )
    pause_late_fee_generation(sale=sale, reason="Pausa exportable", action_date=today)

    archive_path = create_data_export(tmp_path)
    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        pause_csv = archive.read("pausas_recargo_diario.csv").decode("utf-8-sig")
        collector_csv = archive.read("cobradores_habituales.csv").decode("utf-8-sig")
    snapshot = build_sale_snapshot(
        Sale.objects.prefetch_related(
            "installments__late_fees",
            "payments__allocations__installment",
            "collection_attempts",
            "late_fee_pause_periods",
        ).get(pk=sale.pk)
    )

    assert {"pausas_recargo_diario.csv", "cobradores_habituales.csv"} <= names
    assert "Pausa exportable" in pause_csv
    assert f";{collector.pk};" in collector_csv
    assert snapshot["late_fee_pause_periods"][0]["reason"] == "Pausa exportable"
