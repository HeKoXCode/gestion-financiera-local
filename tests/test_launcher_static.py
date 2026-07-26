import re
from wsgiref.util import setup_testing_defaults

import pytest
from modules.core.templatetags.finance import versioned_static

from launcher.launcher import LocalApplication, build_local_wsgi_application


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
