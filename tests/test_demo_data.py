import json
import sys
from datetime import date
from types import SimpleNamespace

import pytest

from launcher import demo_data
from launcher.backup import BackupError


def test_demo_tool_port_zero_disables_running_application_check(monkeypatch):
    monkeypatch.setattr(demo_data, "PORT", 0)

    def unexpected_connection(*_args, **_kwargs):
        raise AssertionError("No debe consultar ningún puerto con GESTION_PORT=0")

    monkeypatch.setattr(demo_data.socket, "create_connection", unexpected_connection)
    assert demo_data.local_application_is_running() is False


def test_demo_session_rejects_backup_path_traversal(tmp_path):
    session_path = tmp_path / demo_data.SESSION_FILENAME
    session_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "original_backup": "../gestion_ajena.sqlite3.zip",
                "original_sha256": "A" * 64,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(BackupError, match="referencia"):
        demo_data._read_session(session_path, tmp_path)


def test_demo_session_round_trip_validates_name_and_hash(tmp_path, monkeypatch):
    original = tmp_path / "gestion_original_antes_demo_prueba.sqlite3.zip"
    original.write_bytes(b"copia-controlada")
    session_path = tmp_path / demo_data.SESSION_FILENAME
    monkeypatch.setattr(demo_data, "validate_application_backup", lambda *_a, **_k: None)

    demo_data._write_session(session_path, original_backup=original)
    payload, recovered = demo_data._read_session(session_path, tmp_path)

    assert recovered == original
    assert payload["original_sha256"] == demo_data.file_sha256(original)


def test_demo_path_helpers_and_existing_database(tmp_path, monkeypatch):
    settings = SimpleNamespace(
        DATABASES={"default": {"NAME": tmp_path / "data" / "gestion.sqlite3"}},
        BACKUP_DIR=tmp_path / "backups",
        STORAGE_DIR=tmp_path / "storage",
    )
    database, backups, session_directory, session = demo_data._paths(settings)
    database.parent.mkdir(parents=True)
    database.write_bytes(b"db")
    validated = []
    monkeypatch.setattr(
        demo_data,
        "validate_application_database",
        lambda path: validated.append(path),
    )

    demo_data._ensure_database(database)

    assert backups == (tmp_path / "backups").resolve()
    assert session == session_directory / demo_data.SESSION_FILENAME
    assert validated == [database]
    assert demo_data._timestamp()


def _fake_demo_paths(tmp_path):
    database = tmp_path / "data" / "gestion.sqlite3"
    backups = tmp_path / "backups"
    session_directory = tmp_path / "storage" / "datos_prueba"
    database.parent.mkdir(parents=True, exist_ok=True)
    backups.mkdir(parents=True, exist_ok=True)
    session_directory.mkdir(parents=True, exist_ok=True)
    database.write_bytes(b"base")
    return database, backups, session_directory, session_directory / demo_data.SESSION_FILENAME


def _patch_demo_runtime(monkeypatch, paths):
    monkeypatch.setattr(demo_data, "local_application_is_running", lambda: False)
    monkeypatch.setattr(demo_data, "configure_django", lambda: object())
    monkeypatch.setattr(demo_data, "_paths", lambda _settings: paths)
    monkeypatch.setattr(demo_data, "_ensure_database", lambda _path: None)
    monkeypatch.setattr(demo_data, "validate_application_database", lambda _path: None)
    monkeypatch.setattr(demo_data, "validate_application_backup", lambda *_a, **_k: None)
    monkeypatch.setattr(demo_data, "_refresh_recovery", lambda *_a: paths[1] / "recovery.zip")
    monkeypatch.setattr("django.core.management.call_command", lambda *_a, **_k: None)


def test_load_demo_protects_original_before_ingestion(tmp_path, monkeypatch):
    paths = _fake_demo_paths(tmp_path)
    _patch_demo_runtime(monkeypatch, paths)
    original = paths[2] / "gestion_original_antes_demo_prueba.sqlite3.zip"

    def fake_backup(*_args, **_kwargs):
        original.write_bytes(b"original")
        return original

    monkeypatch.setattr(demo_data, "create_backup", fake_backup)
    monkeypatch.setattr(
        demo_data,
        "_demo_counts",
        lambda: {
            "clientes": 50,
            "ventas": 70,
            "cobradores": 5,
            "recorridos": 8,
            "asignaciones": 50,
        },
    )

    backup, counts = demo_data.load_demo_data(as_of=date(2026, 9, 16))

    assert backup == original
    assert counts["ventas"] == 70
    assert paths[3].is_file()


def test_clear_demo_keeps_original_session_and_backs_up_demo(tmp_path, monkeypatch):
    paths = _fake_demo_paths(tmp_path)
    _patch_demo_runtime(monkeypatch, paths)
    original = paths[2] / "gestion_original_antes_demo_prueba.sqlite3.zip"
    original.write_bytes(b"original")
    demo_data._write_session(paths[3], original_backup=original)

    def fake_backup(*_args, **kwargs):
        destination = paths[2] / kwargs["fixed_name"]
        destination.write_bytes(b"demo")
        return destination

    monkeypatch.setattr(demo_data, "create_backup", fake_backup)

    demo_backup, _ = demo_data.clear_demo_data()

    assert "datos_ficticios_antes_limpiar" in demo_backup.name
    assert paths[3].is_file()
    assert original.is_file()


def test_restore_original_closes_demo_session(tmp_path, monkeypatch):
    paths = _fake_demo_paths(tmp_path)
    _patch_demo_runtime(monkeypatch, paths)
    original = paths[2] / "gestion_original_antes_demo_prueba.sqlite3.zip"
    original.write_bytes(b"original")
    demo_data._write_session(paths[3], original_backup=original)
    preventive = paths[1] / "preventive.zip"
    monkeypatch.setattr(
        demo_data,
        "restore_database",
        lambda *_a, **_k: preventive,
    )

    restored, created_preventive, _ = demo_data.restore_original_data()

    assert restored == original
    assert created_preventive == preventive
    assert not paths[3].exists()


@pytest.mark.parametrize("action", ["seed", "clear", "restore"])
def test_demo_main_success_actions(action, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["demo_data.py", action, "--yes"])
    monkeypatch.setattr(
        demo_data,
        "load_demo_data",
        lambda **_kwargs: (
            demo_data.PROJECT_ROOT / "original.zip",
            {"clientes": 50},
        ),
    )
    monkeypatch.setattr(
        demo_data,
        "clear_demo_data",
        lambda: (demo_data.PROJECT_ROOT / "demo.zip", demo_data.PROJECT_ROOT / "r.zip"),
    )
    monkeypatch.setattr(
        demo_data,
        "restore_original_data",
        lambda: (
            demo_data.PROJECT_ROOT / "original.zip",
            demo_data.PROJECT_ROOT / "preventive.zip",
            demo_data.PROJECT_ROOT / "r.zip",
        ),
    )

    assert demo_data.main() == 0
    assert capsys.readouterr().out


def test_demo_main_cancel_and_controlled_error(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["demo_data.py", "seed"])
    monkeypatch.setattr(demo_data, "_confirm", lambda _action: False)
    assert demo_data.main() == 2

    monkeypatch.setattr(sys, "argv", ["demo_data.py", "seed", "--yes"])
    monkeypatch.setattr(
        demo_data,
        "load_demo_data",
        lambda **_kwargs: (_ for _ in ()).throw(BackupError("fallo controlado")),
    )
    assert demo_data.main() == 1
