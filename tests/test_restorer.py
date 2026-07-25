import os
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from launcher.backup import create_backup
from launcher.restorer import find_latest_valid_backup, launch_main_application


def create_application_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        for table in (
            "django_migrations",
            "core_customer",
            "core_sale",
            "core_payment",
        ):
            connection.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")
        connection.commit()


def test_latest_valid_backup_is_selected_and_corrupt_newer_file_is_skipped(tmp_path):
    database = tmp_path / "database.sqlite3"
    backup_directory = tmp_path / "backups"
    work_directory = tmp_path / "work"
    create_application_database(database)
    valid = create_backup(database, backup_directory, label="close")
    corrupt = backup_directory / "gestion_close_2099-01-01.sqlite3.zip"
    corrupt.write_text("archivo dañado", encoding="utf-8")
    future = valid.stat().st_mtime + 100
    os.utime(corrupt, (future, future))

    selected = find_latest_valid_backup(
        backup_directory,
        working_directory=work_directory,
    )

    assert selected == valid


def test_latest_valid_backup_returns_none_when_folder_is_empty(tmp_path):
    selected = find_latest_valid_backup(
        tmp_path / "missing",
        working_directory=tmp_path / "work",
    )

    assert selected is None


@pytest.mark.parametrize(
    ("frozen", "relative_launcher", "expected_start"),
    [
        (True, "GestionFinanciera.exe", "GestionFinanciera.exe"),
        (False, "scripts/Iniciar.bat", "cmd.exe"),
    ],
)
def test_main_application_can_be_reopened_after_restore(
    tmp_path,
    monkeypatch,
    frozen,
    relative_launcher,
    expected_start,
):
    launcher = tmp_path / relative_launcher
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.touch()
    captured = {}

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["cwd"] = kwargs["cwd"]

    monkeypatch.setattr("launcher.restorer.subprocess.Popen", fake_popen)

    launch_main_application(tmp_path, frozen=frozen)

    assert captured["cwd"] == tmp_path
    assert captured["command"][0].endswith(expected_start)
