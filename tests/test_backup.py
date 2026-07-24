import sqlite3
from pathlib import Path

import pytest

from launcher.backup import BackupError, create_backup, validate_sqlite_database


def create_sample_database(path: Path, value: str = "dato") -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample (value) VALUES (?)", [value])


def test_create_backup_preserves_data(tmp_path):
    source = tmp_path / "source.sqlite3"
    destination = tmp_path / "backups"
    create_sample_database(source, "cliente")

    backup = create_backup(source, destination, label="test", retention=3)

    assert backup is not None
    validate_sqlite_database(backup)
    with sqlite3.connect(backup) as connection:
        assert connection.execute("SELECT value FROM sample").fetchone() == ("cliente",)


def test_backup_returns_none_when_database_does_not_exist(tmp_path):
    backup = create_backup(
        tmp_path / "missing.sqlite3",
        tmp_path / "backups",
        label="test",
    )

    assert backup is None


def test_backup_rotation_keeps_requested_number(tmp_path):
    source = tmp_path / "source.sqlite3"
    destination = tmp_path / "backups"
    create_sample_database(source)

    for _ in range(4):
        create_backup(source, destination, label="close", retention=2)

    assert len(list(destination.glob("gestion_close_*.sqlite3"))) == 2


def test_validate_rejects_non_database(tmp_path):
    invalid = tmp_path / "invalid.sqlite3"
    invalid.write_text("esto no es sqlite", encoding="utf-8")

    with pytest.raises(BackupError):
        validate_sqlite_database(invalid)

