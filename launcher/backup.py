from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path


class BackupError(RuntimeError):
    """El backup no pudo crearse o validarse."""


def validate_sqlite_database(database_path: Path) -> None:
    database_path = database_path.resolve()
    if not database_path.is_file():
        raise BackupError(f"No existe la base: {database_path}")

    try:
        with closing(sqlite3.connect(database_path)) as connection:
            result = connection.execute("PRAGMA quick_check").fetchone()
    except sqlite3.Error as exc:
        raise BackupError(f"No se pudo abrir la base: {database_path}") from exc

    if not result or result[0] != "ok":
        detail = result[0] if result else "sin resultado"
        raise BackupError(f"La base no superó la validación: {detail}")


def create_backup(
    database_path: Path,
    backup_directory: Path,
    *,
    label: str,
    retention: int | None = None,
    fixed_name: str | None = None,
) -> Path | None:
    database_path = database_path.resolve()
    backup_directory = backup_directory.resolve()

    if not database_path.exists():
        return None

    backup_directory.mkdir(parents=True, exist_ok=True)

    if fixed_name:
        destination = backup_directory / fixed_name
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")
        destination = backup_directory / f"gestion_{label}_{timestamp}.sqlite3"

    temporary = destination.with_suffix(destination.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()

    try:
        with (
            closing(sqlite3.connect(database_path)) as source,
            closing(sqlite3.connect(temporary)) as target,
        ):
            source.backup(target)
            target.commit()
        validate_sqlite_database(temporary)
        temporary.replace(destination)
    except (OSError, sqlite3.Error, BackupError) as exc:
        if temporary.exists():
            temporary.unlink()
        raise BackupError(f"No se pudo crear el backup {destination.name}") from exc

    if retention is not None and fixed_name is None:
        _rotate_backups(backup_directory, label=label, retention=retention)

    return destination


def _rotate_backups(backup_directory: Path, *, label: str, retention: int) -> None:
    if retention < 1:
        raise ValueError("La retención debe ser al menos 1")

    backups = sorted(
        backup_directory.glob(f"gestion_{label}_*.sqlite3"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for obsolete in backups[retention:]:
        obsolete.unlink()
