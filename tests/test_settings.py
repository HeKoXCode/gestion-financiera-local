from django.conf import settings


def test_application_uses_local_sqlite_database():
    database = settings.DATABASES["default"]

    assert database["ENGINE"] == "django.db.backends.sqlite3"
    assert settings.DATA_DIR.name == "data"


def test_application_accepts_only_local_hosts_outside_tests():
    assert {"127.0.0.1", "localhost"}.issubset(settings.ALLOWED_HOSTS)
    assert set(settings.ALLOWED_HOSTS).issubset({"127.0.0.1", "localhost", "testserver"})


def test_argentina_locale_and_timezone():
    assert settings.LANGUAGE_CODE == "es-ar"
    assert settings.TIME_ZONE == "America/Argentina/Buenos_Aires"
