from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.utils import timezone

from launcher.backup import (
    BackupError,
    BackupInfo,
    create_backup,
    list_backups,
    resolve_backup_path,
    validate_application_backup,
)


class DatabaseBackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class PostgreSQLBackupInfo:
    path: Path
    name: str
    label: str
    created_at: datetime
    size: int
    is_recovery: bool = False
    is_compressed: bool = False


def _rotate(directory: Path, pattern: str, retention: int) -> None:
    backups = sorted(
        (path for path in directory.glob(pattern) if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for obsolete in backups[retention:]:
        obsolete.unlink()


def _postgres_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PGPASSWORD"] = str(settings.DATABASES["default"].get("PASSWORD", ""))
    return environment


def _postgres_connection_arguments() -> list[str]:
    database = settings.DATABASES["default"]
    return [
        "--host",
        str(database["HOST"]),
        "--port",
        str(database["PORT"]),
        "--username",
        str(database["USER"]),
        "--dbname",
        str(database["NAME"]),
    ]


def _postgres_tools() -> tuple[str, str]:
    pg_dump = shutil.which("pg_dump")
    pg_restore = shutil.which("pg_restore")
    if not pg_dump or not pg_restore:
        raise DatabaseBackupError("pg_dump y pg_restore deben estar disponibles en PATH.")
    return pg_dump, pg_restore


def _safe_postgresql_path(directory: Path, name: str) -> Path:
    directory = directory.resolve()
    if (
        Path(name).name != name
        or not name.startswith("gestion_postgresql_")
        or not name.endswith(".dump")
    ):
        raise DatabaseBackupError("El nombre del backup PostgreSQL no es válido.")
    candidate = (directory / name).resolve()
    if candidate.parent != directory or not candidate.is_file():
        raise DatabaseBackupError("El backup PostgreSQL solicitado no existe.")
    return candidate


def validate_postgresql_backup(backup_path: Path) -> None:
    backup_path = backup_path.resolve()
    if not backup_path.is_file() or backup_path.stat().st_size == 0:
        raise DatabaseBackupError("El backup PostgreSQL está vacío o no existe.")
    _, pg_restore = _postgres_tools()
    try:
        subprocess.run(
            [pg_restore, "--list", str(backup_path)],
            check=True,
            capture_output=True,
            text=True,
            env=_postgres_environment(),
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise DatabaseBackupError("El backup PostgreSQL no superó la verificación.") from exc


def list_deployment_backups(
    output_directory: Path | None = None,
) -> list[BackupInfo | PostgreSQLBackupInfo]:
    directory = Path(output_directory or settings.BACKUP_DIR).resolve()
    if connection.vendor == "sqlite":
        return list_backups(directory)
    if connection.vendor != "postgresql":
        raise DatabaseBackupError(f"Motor no soportado: {connection.vendor}")
    if not directory.is_dir():
        return []

    backups: list[PostgreSQLBackupInfo] = []
    for path in directory.glob("gestion_postgresql_*.dump"):
        if not path.is_file():
            continue
        remainder = path.name.removeprefix("gestion_postgresql_").removesuffix(".dump")
        label = remainder.rsplit("_", 2)[0] if remainder.count("_") >= 2 else remainder
        stat = path.stat()
        backups.append(
            PostgreSQLBackupInfo(
                path=path,
                name=path.name,
                label=label,
                created_at=datetime.fromtimestamp(stat.st_mtime),
                size=stat.st_size,
            )
        )
    return sorted(backups, key=lambda backup: backup.created_at, reverse=True)


def resolve_deployment_backup(
    name: str,
    output_directory: Path | None = None,
) -> Path:
    directory = Path(output_directory or settings.BACKUP_DIR).resolve()
    if connection.vendor == "sqlite":
        try:
            backup = resolve_backup_path(directory, name)
            validate_application_backup(backup)
        except BackupError as exc:
            raise DatabaseBackupError(str(exc)) from exc
        return backup
    if connection.vendor == "postgresql":
        backup = _safe_postgresql_path(directory, name)
        validate_postgresql_backup(backup)
        return backup
    raise DatabaseBackupError(f"Motor no soportado: {connection.vendor}")


def create_deployment_backup(
    *,
    output_directory: Path | None = None,
    label: str = "scheduled",
    retention: int = 14,
    now: datetime | None = None,
) -> Path:
    """Create an atomic backup for SQLite or PostgreSQL in an external directory."""
    if retention < 1:
        raise DatabaseBackupError("La retención debe ser mayor que cero.")
    directory = Path(output_directory or settings.BACKUP_DIR).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    generated_at = now or timezone.localtime()

    if connection.vendor == "sqlite":
        database_path = Path(settings.DATABASES["default"]["NAME"]).resolve()
        try:
            backup = create_backup(
                database_path,
                directory,
                label=label,
                retention=retention,
            )
        except BackupError as exc:
            raise DatabaseBackupError(str(exc)) from exc
        if backup is None:
            raise DatabaseBackupError("Todavía no existe una base para respaldar.")
        return backup

    if connection.vendor != "postgresql":
        raise DatabaseBackupError(f"Motor no soportado: {connection.vendor}")

    pg_dump, _ = _postgres_tools()

    safe_label = "".join(
        character for character in label if character.isalnum() or character in "-_"
    )
    if not safe_label:
        raise DatabaseBackupError("La etiqueta del backup no es válida.")
    name = f"gestion_postgresql_{safe_label}_{generated_at:%Y-%m-%d_%H%M%S}.dump"
    destination = directory / name
    temporary = destination.with_suffix(".dump.tmp")
    command = [
        pg_dump,
        *_postgres_connection_arguments(),
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--file",
        str(temporary),
    ]
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            env=_postgres_environment(),
        )
        validate_postgresql_backup(temporary)
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise DatabaseBackupError("pg_dump no produjo un archivo válido.")
        temporary.replace(destination)
        _rotate(directory, "gestion_postgresql_*.dump", retention)
    except (OSError, subprocess.CalledProcessError) as exc:
        temporary.unlink(missing_ok=True)
        raise DatabaseBackupError("No se pudo crear o verificar el backup PostgreSQL.") from exc
    return destination
