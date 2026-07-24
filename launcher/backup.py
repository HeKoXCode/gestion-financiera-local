from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

APPLICATION_TABLES = {
    "django_migrations",
    "core_customer",
    "core_sale",
    "core_payment",
}


class BackupError(RuntimeError):
    """El backup no pudo crearse o validarse."""


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    name: str
    label: str
    created_at: datetime
    size: int
    is_recovery: bool


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


def validate_application_database(database_path: Path) -> None:
    validate_sqlite_database(database_path)
    try:
        with closing(sqlite3.connect(database_path)) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
    except sqlite3.Error as exc:
        raise BackupError("No se pudo revisar la estructura de la base.") from exc

    missing = APPLICATION_TABLES - tables
    if missing:
        raise BackupError(
            "La copia no pertenece a Gestión Financiera o está incompleta."
        )


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


def list_backups(backup_directory: Path) -> list[BackupInfo]:
    backup_directory = backup_directory.resolve()
    if not backup_directory.is_dir():
        return []

    backups = []
    for path in backup_directory.glob("gestion_*.sqlite3"):
        if not path.is_file():
            continue
        name = path.name
        is_recovery = name == "gestion_recovery.sqlite3"
        if is_recovery:
            label = "recovery"
        else:
            remainder = name.removeprefix("gestion_").removesuffix(".sqlite3")
            label = remainder.rsplit("_", 3)[0]
        stat = path.stat()
        backups.append(
            BackupInfo(
                path=path,
                name=name,
                label=label,
                created_at=datetime.fromtimestamp(stat.st_mtime),
                size=stat.st_size,
                is_recovery=is_recovery,
            )
        )
    return sorted(backups, key=lambda backup: backup.created_at, reverse=True)


def resolve_backup_path(backup_directory: Path, name: str) -> Path:
    backup_directory = backup_directory.resolve()
    if Path(name).name != name or not name.startswith("gestion_"):
        raise BackupError("El nombre del backup no es válido.")
    candidate = (backup_directory / name).resolve()
    if candidate.parent != backup_directory or candidate.suffix != ".sqlite3":
        raise BackupError("La ruta del backup no es válida.")
    if not candidate.is_file():
        raise BackupError("El backup solicitado no existe.")
    return candidate


def restore_database(
    backup_path: Path,
    database_path: Path,
    backup_directory: Path,
) -> Path | None:
    backup_path = backup_path.resolve()
    database_path = database_path.resolve()
    backup_directory = backup_directory.resolve()
    if backup_path == database_path:
        raise BackupError("La copia seleccionada no puede ser la base activa.")

    validate_application_database(backup_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = database_path.with_suffix(database_path.suffix + ".restore.tmp")
    if temporary.exists():
        temporary.unlink()

    try:
        with (
            closing(sqlite3.connect(backup_path)) as source,
            closing(sqlite3.connect(temporary)) as target,
            ):
            source.backup(target)
            target.commit()
        validate_application_database(temporary)
        preventive = create_backup(
            database_path,
            backup_directory,
            label="pre_restore",
            retention=10,
        )
        temporary.replace(database_path)
        validate_application_database(database_path)
    except (OSError, sqlite3.Error, BackupError) as exc:
        if temporary.exists():
            temporary.unlink()
        raise BackupError("No se pudo restaurar la base seleccionada.") from exc

    return preventive


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
