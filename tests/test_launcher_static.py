from wsgiref.util import setup_testing_defaults

import pytest

from launcher.launcher import build_local_wsgi_application


@pytest.mark.django_db
def test_local_launcher_serves_bundled_css_with_debug_disabled(settings):
    settings.DEBUG = False
    captured = {}
    environ = {}
    setup_testing_defaults(environ)
    environ.update(
        {
            "HTTP_HOST": "127.0.0.1",
            "PATH_INFO": "/static/css/app.css",
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
    assert b"--primary:" in body
