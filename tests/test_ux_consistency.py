from html.parser import HTMLParser
from pathlib import Path

import pytest
from django.urls import reverse
from modules.core.models import Collector

pytestmark = pytest.mark.django_db

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _NavigationParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._current = None

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attributes = dict(attrs)
        classes = set(attributes.get("class", "").split())
        if "nav-link" in classes:
            self._current = {"attrs": attributes, "text": []}

    def handle_data(self, data):
        if self._current is not None:
            self._current["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._current is not None:
            self._current["text"] = " ".join("".join(self._current["text"]).split())
            self.links.append(self._current)
            self._current = None


def _active_navigation_label(response):
    parser = _NavigationParser()
    parser.feed(response.content.decode())
    active = [link for link in parser.links if "is-active" in link["attrs"]["class"]]
    assert len(active) == 1
    assert active[0]["attrs"].get("aria-current") == "page"
    return active[0]["text"]


def test_collector_pages_keep_cobranza_visibly_active(client):
    collector = Collector.objects.create(name="Cobrador de interfaz")

    listing = client.get(reverse("core:collector_list"))
    detail = client.get(reverse("core:collector_detail", args=[collector.pk]))

    assert _active_navigation_label(listing) == "$ Cobranza"
    assert _active_navigation_label(detail) == "$ Cobranza"


def test_collector_tables_keep_the_mobile_card_contract():
    listing = (PROJECT_ROOT / "app/templates/core/collection/collectors.html").read_text(
        encoding="utf-8"
    )
    detail = (PROJECT_ROOT / "app/templates/core/collection/collector_detail.html").read_text(
        encoding="utf-8"
    )

    assert 'class="data-table responsive-table collector-table"' in listing
    assert 'data-label="Visitas asignadas"' in listing
    assert 'data-label="Acción"' in listing
    assert 'class="data-table responsive-table collector-payments-table"' in detail
    assert 'data-label="Medio de pago"' in detail


def test_route_cards_and_quick_create_have_bounded_layout_rules():
    css = (PROJECT_ROOT / "app/static/css/app.css").read_text(encoding="utf-8")

    assert ".route-card-actions .btn" in css
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in css
    assert "grid-template-columns: minmax(0, 1fr);" in css
    assert ".collector-quick-create .form-control" in css
    assert ".collector-history-panel .table-wrap" in css
    assert ".collector-day-panel" in css
    assert ".collector-day-list .mini-action" in css
    assert ".route-card-delete" in css
    assert ".route-assigned-badge.is-other" in css
    assert ".route-summary-card.is-unprepared" in css
    assert ".route-selection-note" in css
    assert ".route-client-option[hidden]" in css
    assert "display: none !important;" in css
    assert ".route-client-main em span" in css
    assert "overflow-wrap: anywhere;" in css


def test_plain_language_replaces_ambiguous_date_and_route_actions(client):
    agenda = client.get(reverse("core:agenda")).content.decode()
    collection = client.get(reverse("core:collection_list")).content.decode()
    routes = client.get(reverse("core:collection_routes")).content.decode()

    assert "Mostrar semana" in agenda
    assert "Mostrar día" in collection
    assert "Mostrar fecha" in routes
    assert "Día anterior" in routes
    assert "Día siguiente" in routes
    assert "Cada cliente puede quedar en una sola planilla por día" in routes
    assert ">Ver</button>" not in collection
    assert ">Ver</button>" not in routes


def test_route_planner_uses_clear_actions_and_two_archive_warnings():
    template = (PROJECT_ROOT / "app/templates/core/collection/routes.html").read_text(
        encoding="utf-8"
    )

    assert "Cambiar clientes" in template
    assert "Imprimir planilla" in template
    assert "Editar selección" not in template
    assert "Abrir planilla" not in template
    assert "Asignado a cobrador“" not in template
    assert "Asignado a cobrador “" in template
    assert "Sin planilla para este día" in template
    assert "La selección es por cliente." in template
    assert "Operaciones pendientes:" in template
    assert "Guardar e imprimir" in template
    assert 'name="after_save" value="print"' in template
    assert "Imprimir planillas guardadas" in template
    assert "Imprimir todas las planillas" not in template
    assert template.count("confirm(") >= 3
    assert "Confirmación final" in template
    assert "if (count)" in template


def test_compact_navigation_reveals_the_active_section():
    script = (PROJECT_ROOT / "app/static/js/ui.js").read_text(encoding="utf-8")
    base = (PROJECT_ROOT / "app/templates/base.html").read_text(encoding="utf-8")

    assert ".nav-link.is-active" in script
    assert "scrollIntoView" in script
    assert 'aria-current="page"' in base
    assert "js/ui.js" in base


def test_sale_preview_has_a_caption_for_every_frequency_without_stale_variables():
    script = (PROJECT_ROOT / "app/static/js/sale-form.js").read_text(encoding="utf-8")

    assert 'daily: `${count} cuotas · días de cobranza habilitados`' in script
    assert 'weekly: `${count} cuotas · una por semana`' in script
    assert 'biweekly: `${count} cuotas · cada 2 semanas`' in script
    assert 'monthly: `${count} cuotas · una por mes`' in script
    assert "captionOutput.textContent = isMonthly" not in script


def test_multiuser_and_analytics_styles_survive_release_merges():
    css = (PROJECT_ROOT / "app/static/css/app.css").read_text(encoding="utf-8")

    for selector in (
        ".auth-page",
        ".auth-layout",
        ".analytics-kpis",
        ".analytics-grid",
        ".aging-row",
        ".aging-track span",
        ".metric-list",
        ".cohort-table",
        ".reconciliation-strip.is-success",
    ):
        assert selector in css

    assert "grid-template-columns: repeat(4, minmax(0, 1fr));" in css
    assert "grid-template-columns: minmax(150px, 1fr) minmax(120px, 2fr)" in css
