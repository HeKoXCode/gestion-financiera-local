from launcher import archive_reset
from launcher.archive_reset import normalize_archive_label


def test_archive_label_is_safe_and_readable():
    assert normalize_archive_label("Mudanza Córdoba 2026") == "mudanza-cordoba-2026"


def test_archive_label_cannot_escape_storage():
    assert normalize_archive_label("../../Datos importantes") == "datos-importantes"


def test_empty_archive_label_uses_default():
    assert normalize_archive_label(" ¿? ") == "datos"


def test_port_zero_disables_unrelated_running_app_detection(monkeypatch):
    monkeypatch.setattr(archive_reset, "PORT", 0)

    def unexpected_connection(*_args, **_kwargs):
        raise AssertionError("No debe consultar el puerto real durante una prueba aislada")

    monkeypatch.setattr(archive_reset.socket, "create_connection", unexpected_connection)

    assert archive_reset.local_application_is_running() is False
