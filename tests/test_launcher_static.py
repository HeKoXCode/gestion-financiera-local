import re
from pathlib import Path
from types import SimpleNamespace
from wsgiref.util import setup_testing_defaults

import pytest
from modules.core.models import BusinessSettings
from modules.core.templatetags.finance import versioned_static

from launcher.launcher import (
    COLOR_ACCENT,
    COLOR_BACKGROUND,
    COLOR_HEADER,
    COLOR_PRIMARY,
    LocalApplication,
    build_local_wsgi_application,
    reopen_existing_system,
)
from launcher.mobile_access import build_mobile_access_url, build_qr_image


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "marker"),
    [
        ("/static/css/app.css", b"--primary:"),
        ("/static/css/print.css", b"@page"),
    ],
)
def test_local_launcher_serves_bundled_css_with_debug_disabled(settings, path, marker):
    settings.DEBUG = False
    captured = {}
    environ = {}
    setup_testing_defaults(environ)
    environ.update(
        {
            "HTTP_HOST": "127.0.0.1",
            "PATH_INFO": path,
            "REQUEST_METHOD": "GET",
        }
    )

    def start_response(status, headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = dict(headers)

    response = build_local_wsgi_application()(environ, start_response)
    try:
        body = b"".join(response)
    finally:
        if hasattr(response, "close"):
            response.close()

    assert captured["status"].startswith("200 ")
    assert captured["headers"]["Content-Type"].startswith("text/css")
    assert marker in body


def test_static_asset_url_changes_with_bundled_content():
    asset_url = versioned_static("css/app.css")

    assert re.fullmatch(r"/static/css/app\.css\?v=[0-9a-f]{12}", asset_url)


@pytest.mark.django_db
def test_home_uses_versioned_css_url(client):
    response = client.get("/")

    assert response.status_code == 200
    assert f'href="{versioned_static("css/app.css")}"'.encode() in response.content


def test_launcher_accepts_an_ephemeral_port_for_portable_tests(monkeypatch):
    monkeypatch.setenv("GESTION_PORT", "0")

    application = LocalApplication()

    assert application.port == 0


def test_launcher_waits_for_the_user_before_opening_the_browser(monkeypatch):
    application = LocalApplication()
    calls = []
    fake_window = SimpleNamespace(mainloop=lambda: calls.append("mainloop"))

    monkeypatch.setattr(application, "configure_django", lambda: calls.append("configure"))
    monkeypatch.setattr(application, "start_server", lambda: calls.append("server"))
    monkeypatch.setattr(application, "wait_until_ready", lambda: True)

    def build_fake_window():
        calls.append("window")
        application.window = fake_window

    monkeypatch.setattr(application, "build_window", build_fake_window)
    monkeypatch.setattr(application, "open_browser", lambda: calls.append("browser"))
    monkeypatch.setattr("launcher.launcher.signal.signal", lambda *_args: None)

    application.run()

    assert calls == ["configure", "server", "window", "mainloop"]


def test_open_browser_updates_the_launcher_message(monkeypatch):
    application = LocalApplication()
    recorded = {}
    application.status = SimpleNamespace(set=lambda value: recorded.update(status=value))
    application.open_button = SimpleNamespace(configure=lambda **values: recorded.update(values))
    monkeypatch.setattr("launcher.launcher.webbrowser.open_new_tab", lambda _url: True)

    application.open_browser()

    assert recorded["text"] == "Sistema abierto"
    assert "abierto en el navegador" in recorded["status"]
    assert application.browser_opened is True


def test_open_browser_does_not_create_another_tab_without_confirmation(monkeypatch):
    application = LocalApplication()
    application.browser_opened = True
    recorded = {}
    opened = []
    application.status = SimpleNamespace(set=lambda value: recorded.update(status=value))
    application.open_button = SimpleNamespace(configure=lambda **_values: None)
    monkeypatch.setattr("launcher.launcher.messagebox.askyesno", lambda *_args: False)
    monkeypatch.setattr(
        "launcher.launcher.webbrowser.open_new_tab",
        lambda url: opened.append(url) or True,
    )

    application.open_browser()

    assert opened == []
    assert "continúa abierto" in recorded["status"]


def test_open_browser_can_reopen_a_closed_tab_after_confirmation(monkeypatch):
    application = LocalApplication()
    application.browser_opened = True
    opened = []
    application.status = SimpleNamespace(set=lambda _value: None)
    application.open_button = SimpleNamespace(configure=lambda **_values: None)
    monkeypatch.setattr("launcher.launcher.messagebox.askyesno", lambda *_args: True)
    monkeypatch.setattr(
        "launcher.launcher.webbrowser.open_new_tab",
        lambda url: opened.append(url) or True,
    )

    application.open_browser()

    assert opened == ["http://127.0.0.1:8765/"]


def test_second_launcher_focuses_existing_launcher_without_opening_browser(monkeypatch):
    focused = []

    class HealthyResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr("launcher.launcher.urlopen", lambda *_args, **_kwargs: HealthyResponse())
    monkeypatch.setattr(
        "launcher.launcher.focus_existing_launcher_window",
        lambda: focused.append(True) or True,
    )

    assert reopen_existing_system(8765) is True
    assert focused == [True]


def test_launcher_includes_creator_signature():
    launcher_source = (Path(__file__).resolve().parents[1] / "launcher" / "launcher.py").read_text(
        encoding="utf-8"
    )

    assert "Creado por Percy I. Marzoratti Hill." in launcher_source


def test_launcher_and_mobile_qr_share_the_blue_visual_identity():
    assert COLOR_HEADER == "#123F4B"
    assert COLOR_PRIMARY == "#187F94"
    assert COLOR_ACCENT == "#43C7BC"
    assert COLOR_BACKGROUND == "#EEF4F7"

    qr_image = build_qr_image(
        build_mobile_access_url("192.168.1.8", 8765, "visual-identity-test")
    )
    assert (13, 98, 116) in set(qr_image.getdata())


@pytest.mark.django_db
def test_launcher_loads_configured_business_name_and_logo(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    logo_directory = tmp_path / "logos"
    logo_directory.mkdir()
    logo_path = logo_directory / "marca.png"
    logo_path.write_bytes(b"logo-de-prueba")
    business_settings = BusinessSettings.get_solo()
    business_settings.business_name = "Comercio de prueba"
    business_settings.logo.name = "logos/marca.png"
    business_settings.save()
    application = LocalApplication()

    application.load_branding()

    assert application.business_name == "Comercio de prueba"
    assert application.business_logo_path == logo_path.resolve()


def test_visual_system_includes_gradients_and_warning_action():
    project_root = Path(__file__).resolve().parents[1]
    css = (project_root / "app" / "static" / "css" / "app.css").read_text(encoding="utf-8")
    collection_template = (
        project_root / "app" / "templates" / "core" / "collection" / "list.html"
    ).read_text(encoding="utf-8")

    assert "--gradient-primary:" in css
    assert ".btn-warning" in css
    assert 'class="btn btn-warning"' in collection_template
