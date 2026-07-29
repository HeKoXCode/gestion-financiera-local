from __future__ import annotations

import sqlite3
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

APPLICATION_TABLES = {
    "django_migrations",
    "core_customer",
    "core_sale",
    "core_payment",
}
ARCHIVE_SUFFIX = ".sqlite3.zip"
LEGACY_SUFFIX = ".sqlite3"
MAX_UNCOMPRESSED_BACKUP_BYTES = 16 * 1024 * 1024 * 1024
COPY_CHUNK_SIZE = 1024 * 1024


class BackupError(RuntimeError):
    """La copia de seguridad no pudo crearse o validarse."""


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    name: str
    label: str
    created_at: datetime
    size: int
    is_recovery: bool
    is_compressed: bool


def validate_sqlite_database(database_path: Path) -> None:
    database_path = database_path.resolve()
    if not database_path.is_file():
        raise BackupError(f"No existe el archivo de datos: {database_path}")

    try:
        with closing(sqlite3.connect(database_path)) as connection:
            result = connection.execute("PRAGMA quick_check").fetchone()
    except sqlite3.Error as exc:
        raise BackupError(f"No se pudo abrir el archivo de datos: {database_path}") from exc

    if not result or result[0] != "ok":
        detail = result[0] if result else "sin resultado"
        raise BackupError(f"Los datos no superaron la validación: {detail}")


def validate_application_database(database_path: Path) -> None:
    validate_sqlite_database(database_path)
    try:
        with closing(sqlite3.connect(database_path)) as connection:
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
    except sqlite3.Error as exc:
        raise BackupError("No se pudo revisar la estructura de los datos.") from exc

    missing = APPLICATION_TABLES - tables
    if missing:
        raise BackupError("La copia no pertenece a Gestión Financiera o está incompleta.")


def validate_backup_archive(archive_path: Path) -> None:
    """Validate the ZIP structure and CRC without publishing its contents."""
    archive_path = archive_path.resolve()
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            _archive_database_member(archive)
            corrupted = archive.testzip()
    except BackupError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        raise BackupError(f"La copia comprimida no es válida: {archive_path.name}") from exc

    if corrupted:
        raise BackupError(f"El archivo comprimido está dañado: {corrupted}")


@contextmanager
def materialize_backup(
    backup_path: Path,
    *,
    working_directory: Path | None = None,
) -> Iterator[Path]:
    """Yield a validated application database from ZIP or legacy SQLite input."""
    backup_path = backup_path.resolve()
    if not backup_path.is_file():
        raise BackupError(f"No existe la copia: {backup_path}")

    if _is_legacy_backup(backup_path):
        validate_application_database(backup_path)
        yield backup_path
        return

    if not _is_archive_backup(backup_path):
        raise BackupError("La copia debe ser un archivo .sqlite3.zip o .sqlite3.")

    temporary_directory = (working_directory or backup_path.parent).resolve()
    temporary_directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix="gestion_restore_source_",
        suffix=LEGACY_SUFFIX,
        dir=temporary_directory,
        delete=False,
    ) as temporary_file:
        temporary = Path(temporary_file.name)
    try:
        _extract_archive_database(backup_path, temporary)
        validate_application_database(temporary)
        yield temporary
    finally:
        if temporary.exists():
            temporary.unlink()


def validate_application_backup(
    backup_path: Path,
    *,
    working_directory: Path | None = None,
) -> None:
    with materialize_backup(backup_path, working_directory=working_directory):
        return


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
        destination = backup_directory / _archive_name(fixed_name)
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")
        destination = backup_directory / f"gestion_{label}_{timestamp}{ARCHIVE_SUFFIX}"

    temporary_database = destination.with_name(f".{destination.name}.building{LEGACY_SUFFIX}")
    temporary_archive = destination.with_name(f".{destination.name}.tmp")
    for temporary in (temporary_database, temporary_archive):
        if temporary.exists():
            temporary.unlink()

    try:
        with (
            closing(sqlite3.connect(database_path)) as source,
            closing(sqlite3.connect(temporary_database)) as target,
        ):
            source.backup(target)
            target.commit()
        validate_sqlite_database(temporary_database)
        with zipfile.ZipFile(
            temporary_archive,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
            allowZip64=True,
        ) as archive:
            archive.write(
                temporary_database,
                arcname=destination.name.removesuffix(".zip"),
            )
        validate_backup_archive(temporary_archive)
        temporary_archive.replace(destination)
    except (OSError, sqlite3.Error, BackupError) as exc:
        raise BackupError(f"No se pudo crear la copia de seguridad {destination.name}") from exc
    finally:
        for temporary in (temporary_database, temporary_archive):
            if temporary.exists():
                temporary.unlink()

    if retention is not None:
        _rotate_backups(backup_directory, label=label, retention=retention)

    return destination


def create_daily_backup(
    database_path: Path,
    backup_directory: Path,
    *,
    label: str,
    retention_days: int,
    day: date | None = None,
) -> Path | None:
    """Create or update one backup per calendar day."""
    backup_day = day or date.today()
    return create_backup(
        database_path,
        backup_directory,
        label=label,
        retention=retention_days,
        fixed_name=f"gestion_{label}_{backup_day.isoformat()}{LEGACY_SUFFIX}",
    )


def compress_legacy_backups(backup_directory: Path) -> list[Path]:
    """Convert valid legacy backups to ZIP, leaving any unreadable file untouched."""
    backup_directory = backup_directory.resolve()
    if not backup_directory.is_dir():
        return []

    converted: list[Path] = []
    for legacy in sorted(backup_directory.glob(f"gestion_*{LEGACY_SUFFIX}")):
        try:
            validate_application_database(legacy)
            archive = create_backup(
                legacy,
                backup_directory,
                label="legacy",
                fixed_name=legacy.name,
            )
            if archive is None:
                continue
            validate_application_backup(archive)
            legacy.unlink()
        except (OSError, BackupError):
            continue
        converted.append(archive)
    return converted


def list_backups(backup_directory: Path) -> list[BackupInfo]:
    backup_directory = backup_directory.resolve()
    if not backup_directory.is_dir():
        return []

    backups = []
    for path in backup_directory.glob("gestion_*"):
        if not path.is_file() or not _is_supported_backup(path):
            continue
        name = path.name
        is_recovery = name in {
            f"gestion_recovery{LEGACY_SUFFIX}",
            f"gestion_recovery{ARCHIVE_SUFFIX}",
        }
        if is_recovery:
            label = "recovery"
        else:
            remainder = name.removeprefix("gestion_")
            if name.endswith(ARCHIVE_SUFFIX):
                remainder = remainder.removesuffix(ARCHIVE_SUFFIX)
            else:
                remainder = remainder.removesuffix(LEGACY_SUFFIX)
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
                is_compressed=_is_archive_backup(path),
            )
        )
    return sorted(backups, key=lambda backup: backup.created_at, reverse=True)


def resolve_backup_path(backup_directory: Path, name: str) -> Path:
    backup_directory = backup_directory.resolve()
    if Path(name).name != name or not name.startswith("gestion_"):
        raise BackupError("El nombre de la copia no es válido.")
    candidate = (backup_directory / name).resolve()
    if candidate.parent != backup_directory or not _is_supported_backup(candidate):
        raise BackupError("La ubicación de la copia no es válida.")
    if not candidate.is_file():
        raise BackupError("La copia solicitada no existe.")
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
        raise BackupError("La copia seleccionada no puede ser el archivo de datos actual.")

    database_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = database_path.with_suffix(database_path.suffix + ".restore.tmp")
    if temporary.exists():
        temporary.unlink()

    try:
        with (
            materialize_backup(
                backup_path,
                working_directory=database_path.parent,
            ) as source_path,
            closing(sqlite3.connect(source_path)) as source,
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
        raise BackupError("No se pudieron restaurar los datos seleccionados.") from exc

    return preventive


def _rotate_backups(backup_directory: Path, *, label: str, retention: int) -> None:
    if retention < 1:
        raise ValueError("La retención debe ser al menos 1")

    backups = [backup for backup in list_backups(backup_directory) if backup.label == label]
    for obsolete in backups[retention:]:
        obsolete.path.unlink()


def _archive_name(name: str) -> str:
    if Path(name).name != name or not name.startswith("gestion_"):
        raise BackupError("El nombre de la copia no es válido.")
    if name.endswith(ARCHIVE_SUFFIX):
        return name
    if name.endswith(LEGACY_SUFFIX):
        return f"{name}.zip"
    raise BackupError("El nombre de la copia debe terminar en .sqlite3 o .sqlite3.zip.")


def _is_archive_backup(path: Path) -> bool:
    return path.name.lower().endswith(ARCHIVE_SUFFIX)


def _is_legacy_backup(path: Path) -> bool:
    return path.name.lower().endswith(LEGACY_SUFFIX) and not _is_archive_backup(path)


def _is_supported_backup(path: Path) -> bool:
    return _is_archive_backup(path) or _is_legacy_backup(path)


def _archive_database_member(archive: zipfile.ZipFile) -> zipfile.ZipInfo:
    members = [member for member in archive.infolist() if not member.is_dir()]
    if len(members) != 1:
        raise BackupError("La copia ZIP debe contener un único archivo de datos.")
    member = members[0]
    if (
        not member.filename.endswith(LEGACY_SUFFIX)
        or "/" in member.filename
        or "\\" in member.filename
    ):
        raise BackupError("El contenido de la copia ZIP no es válido.")
    if member.file_size < 1 or member.file_size > MAX_UNCOMPRESSED_BACKUP_BYTES:
        raise BackupError("El tamaño interno de la copia ZIP no es válido.")
    return member


def _extract_archive_database(archive_path: Path, destination: Path) -> None:
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            member = _archive_database_member(archive)
            written = 0
            with archive.open(member, "r") as source, destination.open("wb") as target:
                while chunk := source.read(COPY_CHUNK_SIZE):
                    written += len(chunk)
                    if written > MAX_UNCOMPRESSED_BACKUP_BYTES:
                        raise BackupError("La copia ZIP supera el tamaño permitido.")
                    target.write(chunk)
            if written != member.file_size:
                raise BackupError("La copia ZIP está incompleta.")
    except BackupError:
        if destination.exists():
            destination.unlink()
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        if destination.exists():
            destination.unlink()
        raise BackupError(f"No se pudo descomprimir {archive_path.name}.") from exc
