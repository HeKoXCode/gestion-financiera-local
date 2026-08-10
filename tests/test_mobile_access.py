from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from django.conf import settings as django_settings
from django.urls import reverse

from launcher.launcher import LocalApplication
from launcher.mobile_access import (
    MOBILE_BIND_HOST,
    build_mobile_access_url,
    build_qr_image,
    create_mobile_token,
    detect_lan_ip,
    is_usable_lan_address,
)

pytestmark = pytest.mark.django_db

LAN_HOST = "192.168.50.20"
PHONE_ADDRESS = "192.168.50.31"
TOKEN = "clave-temporal-de-prueba"


def mobile_request_options():
    return {
        "HTTP_HOST": LAN_HOST,
        "REMOTE_ADDR": PHONE_ADDRESS,
    }


def enable_mobile_settings(settings, *, token=TOKEN):
    settings.ALLOWED_HOSTS = ["127.0.0.1", "localhost", LAN_HOST]
    settings.GESTION_MOBILE_ACCESS_ENABLED = True
    settings.GESTION_MOBILE_ACCESS_TOKEN = token
    settings.GESTION_LAN_IP = LAN_HOST


def test_loopback_keeps_working_without_mobile_mode(client, settings):
    settings.GESTION_MOBILE_ACCESS_ENABLED = False
    settings.GESTION_MOBILE_ACCESS_TOKEN = ""

    response = client.get("/", HTTP_HOST="127.0.0.1", REMOTE_ADDR="127.0.0.1")

    assert response.status_code == 200


def test_phone_requires_the_temporary_qr_token(client, settings):
    enable_mobile_settings(settings)
    options = mobile_request_options()

    blocked = client.get("/", **options)
    bad_token = client.get(
        reverse("core:mobile_access"),
        {"clave": "incorrecta"},
        **options,
    )
    paired = client.get(
        reverse("core:mobile_access"),
        {"clave": TOKEN},
        **options,
    )
    allowed = client.get("/", **options)

    assert blocked.status_code == 302
    assert blocked.url.startswith("/acceso-celular/?continuar=")
    assert bad_token.status_code == 403
    assert "No se reconoció este celular" in bad_token.content.decode()
    assert paired.status_code == 302
    assert paired.url == "/"
    assert allowed.status_code == 200
    assert "Así viene el día" in allowed.content.decode()


def test_old_phone_session_stops_working_when_token_rotates(client, settings):
    enable_mobile_settings(settings)
    options = mobile_request_options()
    client.get(
        reverse("core:mobile_access"),
        {"clave": TOKEN},
        **options,
    )
    assert client.get("/", **options).status_code == 200

    settings.GESTION_MOBILE_ACCESS_TOKEN = "otra-clave"

    blocked = client.get("/", **options)
    assert blocked.status_code == 302
    assert blocked.url.startswith("/acceso-celular/")


def test_pairing_returns_to_the_requested_page_and_preserves_query(client, settings):
    enable_mobile_settings(settings)
    options = mobile_request_options()
    requested_path = "/cobranza/?fecha=2026-07-29&barrio=Centro"

    blocked = client.get(requested_path, **options)
    continuing = parse_qs(urlparse(blocked.url).query)["continuar"][0]
    paired = client.get(
        reverse("core:mobile_access"),
        {"clave": TOKEN, "continuar": continuing},
        **options,
    )

    assert continuing == requested_path
    assert paired.status_code == 302
    assert paired.url == requested_path


def test_pairing_rejects_an_external_redirect(client, settings):
    enable_mobile_settings(settings)

    response = client.get(
        reverse("core:mobile_access"),
        {"clave": TOKEN, "continuar": "https://example.com/engaño"},
        **mobile_request_options(),
    )

    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("192.168.1.10", True),
        ("10.10.0.7", True),
        ("172.16.4.2", True),
        ("127.0.0.1", False),
        ("169.254.10.20", False),
        ("0.0.0.0", False),
        ("no-es-una-ip", False),
    ],
)
def test_lan_address_validation(address, expected):
    assert is_usable_lan_address(address) is expected


def test_lan_ip_can_be_overridden_for_portable_diagnostics(monkeypatch):
    monkeypatch.setenv("GESTION_LAN_IP_OVERRIDE", "192.168.77.5")

    assert detect_lan_ip() == "192.168.77.5"


def test_invalid_lan_override_is_rejected(monkeypatch):
    monkeypatch.setenv("GESTION_LAN_IP_OVERRIDE", "127.0.0.1")

    assert detect_lan_ip() is None


def test_mobile_link_contains_the_detected_pc_and_secret():
    url = build_mobile_access_url("192.168.1.8", 8765, "secreto con espacio")
    parsed = urlparse(url)

    assert parsed.hostname == "192.168.1.8"
    assert parsed.port == 8765
    assert parsed.path == "/acceso-celular/"
    assert parse_qs(parsed.query) == {"clave": ["secreto con espacio"]}


def test_generated_tokens_are_long_and_change_each_time():
    first = create_mobile_token()
    second = create_mobile_token()

    assert len(first) >= 40
    assert len(second) >= 40
    assert first != second


def test_qr_generator_returns_a_compact_readable_image():
    image = build_qr_image(
        build_mobile_access_url("192.168.1.8", 8765, create_mobile_token())
    )

    assert image.mode == "RGB"
    assert 100 <= image.width <= 230
    assert image.width == image.height


def test_launcher_activates_mobile_mode_with_detected_network(monkeypatch):
    application = LocalApplication()
    recorded = []
    application.mobile_button = SimpleNamespace(
        configure=lambda **values: recorded.append(values)
    )
    application.status = SimpleNamespace(set=lambda value: recorded.append(value))

    monkeypatch.setattr("launcher.launcher.detect_lan_ip", lambda: LAN_HOST)
    monkeypatch.setattr("launcher.launcher.create_mobile_token", lambda: TOKEN)
    monkeypatch.setattr(application, "restart_server", lambda: recorded.append("restart"))
    monkeypatch.setattr(
        application,
        "show_mobile_access",
        lambda: recorded.append("dialog"),
    )

    application.activate_mobile_access()

    assert application.mobile_access_enabled is True
    assert application.mobile_ip == LAN_HOST
    assert application.mobile_token == TOKEN
    assert application.bind_host == MOBILE_BIND_HOST
    assert "restart" in recorded
    assert "dialog" in recorded
    assert {"text": "Ver acceso celular"} in recorded


def test_launcher_updates_django_hosts_without_accepting_every_host(
    settings,
    monkeypatch,
):
    for variable in (
        "GESTION_MOBILE_ACCESS_ENABLED",
        "GESTION_MOBILE_ACCESS_TOKEN",
        "GESTION_LAN_IP",
    ):
        monkeypatch.delenv(variable, raising=False)
    application = LocalApplication()
    application.mobile_access_enabled = True
    application.mobile_ip = LAN_HOST
    application.mobile_token = TOKEN
    original_allowed_hosts = list(settings.ALLOWED_HOSTS)
    original_enabled = settings.GESTION_MOBILE_ACCESS_ENABLED
    original_token = settings.GESTION_MOBILE_ACCESS_TOKEN
    original_lan_ip = settings.GESTION_LAN_IP

    try:
        application.apply_mobile_settings()

        assert settings.GESTION_MOBILE_ACCESS_ENABLED is True
        assert settings.GESTION_MOBILE_ACCESS_TOKEN == TOKEN
        expected_hosts = ["127.0.0.1", "localhost"]
        if "testserver" in original_allowed_hosts:
            expected_hosts.append("testserver")
        expected_hosts.append(LAN_HOST)
        assert expected_hosts == settings.ALLOWED_HOSTS
        assert "*" not in settings.ALLOWED_HOSTS
    finally:
        django_settings.ALLOWED_HOSTS = original_allowed_hosts
        django_settings.GESTION_MOBILE_ACCESS_ENABLED = original_enabled
        django_settings.GESTION_MOBILE_ACCESS_TOKEN = original_token
        django_settings.GESTION_LAN_IP = original_lan_ip


def test_firewall_scripts_are_portable_and_restricted_to_the_local_subnet():
    project_root = Path(__file__).resolve().parents[1]
    scripts = (
        project_root / "scripts" / "HabilitarAccesoCelular.bat",
        project_root / "portable_assets" / "HABILITAR_ACCESO_CELULAR.bat",
    )

    for script in scripts:
        content = script.read_text(encoding="utf-8").lower()
        assert "localport=8765" in content
        assert "remoteip=localsubnet" in content
        assert "start-process" in content
        assert "action=allow" in content
