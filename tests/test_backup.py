import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from launcher.backup import (
    BackupError,
    create_backup,
    list_backups,
    resolve_backup_path,
    restore_database,
    validate_application_database,
    validate_sqlite_database,
)


def create_sample_database(path: Path, value: str = "dato") -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample (value) VALUES (?)", [value])
        connection.commit()


def create_application_database(path: Path, value: str) -> None:
    with closing(sqlite3.connect(path)) as connection:
        for table in (
            "django_migrations",
            "core_customer",
            "core_sale",
            "core_payment",
        ):
            connection.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample (value) VALUES (?)", [value])
        connection.commit()


def test_create_backup_preserves_data(tmp_path):
    source = tmp_path / "source.sqlite3"
    destination = tmp_path / "backups"
    create_sample_database(source, "cliente")

    backup = create_backup(source, destination, label="test", retention=3)

    assert backup is not None
    validate_sqlite_database(backup)
    with closing(sqlite3.connect(backup)) as connection:
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


def test_application_validation_rejects_unrelated_sqlite_database(tmp_path):
    unrelated = tmp_path / "unrelated.sqlite3"
    create_sample_database(unrelated)

    with pytest.raises(BackupError, match="no pertenece"):
        validate_application_database(unrelated)


def test_backup_catalog_identifies_labels_and_recovery_copy(tmp_path):
    source = tmp_path / "source.sqlite3"
    destination = tmp_path / "backups"
    create_sample_database(source)
    create_backup(source, destination, label="manual")
    create_backup(
        source,
        destination,
        label="recovery",
        fixed_name="gestion_recovery.sqlite3",
    )

    backups = list_backups(destination)

    assert {backup.label for backup in backups} == {"manual", "recovery"}
    assert sum(backup.is_recovery for backup in backups) == 1
    assert all(backup.size > 0 for backup in backups)


def test_backup_path_resolution_rejects_traversal(tmp_path):
    destination = tmp_path / "backups"
    destination.mkdir()

    with pytest.raises(BackupError):
        resolve_backup_path(destination, "../gestion_stolen.sqlite3")


def test_restore_recovers_data_and_preserves_previous_database(tmp_path):
    source = tmp_path / "chosen-backup.sqlite3"
    database = tmp_path / "data" / "gestion_financiera.sqlite3"
    backup_directory = tmp_path / "backups"
    database.parent.mkdir()
    create_application_database(source, "datos respaldados")
    create_application_database(database, "datos anteriores")

    preventive = restore_database(source, database, backup_directory)

    assert preventive is not None
    validate_application_database(database)
    validate_application_database(preventive)
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("SELECT value FROM sample").fetchone() == (
            "datos respaldados",
        )
    with closing(sqlite3.connect(preventive)) as connection:
        assert connection.execute("SELECT value FROM sample").fetchone() == (
            "datos anteriores",
        )


def test_restore_does_not_touch_database_when_source_is_invalid(tmp_path):
    source = tmp_path / "invalid.sqlite3"
    database = tmp_path / "gestion_financiera.sqlite3"
    create_sample_database(source, "no es la app")
    create_application_database(database, "base intacta")

    with pytest.raises(BackupError):
        restore_database(source, database, tmp_path / "backups")

    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("SELECT value FROM sample").fetchone() == (
            "base intacta",
        )
