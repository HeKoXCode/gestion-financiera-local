from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
from datetime import date, datetime
from pathlib import Path

if not getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT / "app"))
else:
    PROJECT_ROOT = Path(sys.executable).resolve().parent

from launcher.backup import (
    BackupError,
    create_backup,
    restore_database,
    validate_application_backup,
    validate_application_database,
)

SESSION_FILENAME = "sesion_datos_ficticios.json"
HOST = "127.0.0.1"
try:
    PORT = int(os.environ.get("GESTION_PORT", "8765"))
except ValueError:
    PORT = 8765


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def local_application_is_running() -> bool:
    if PORT <= 0:
        return False
    try:
        with socket.create_connection((HOST, PORT), timeout=0.25):
            return True
    except OSError:
        return False


def configure_django():
    for variable, directory_name in (
        ("GESTION_DATA_DIR", "data"),
        ("GESTION_BACKUP_DIR", "backups"),
        ("GESTION_EXPORT_DIR", "exports"),
        ("GESTION_MEDIA_DIR", "media"),
        ("GESTION_STORAGE_DIR", "storage"),
    ):
        os.environ.setdefault(variable, str(PROJECT_ROOT / directory_name))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault("DJANGO_DEBUG", "0")

    import django

    django.setup()
    from django.conf import settings

    return settings


def _paths(settings):
    database_path = Path(settings.DATABASES["default"]["NAME"]).resolve()
    backup_directory = Path(settings.BACKUP_DIR).resolve()
    session_directory = (Path(settings.STORAGE_DIR) / "datos_prueba").resolve()
    session_directory.mkdir(parents=True, exist_ok=True)
    return (
        database_path,
        backup_directory,
        session_directory,
        session_directory / SESSION_FILENAME,
    )


def _timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S_%f")


def _write_session(session_path: Path, *, original_backup: Path) -> None:
    payload = {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(),
        "original_backup": original_backup.name,
        "original_sha256": file_sha256(original_backup),
    }
    temporary = session_path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(session_path)


def _read_session(session_path: Path, session_directory: Path) -> tuple[dict, Path]:
    if not session_path.is_file():
        raise BackupError("No hay una sesión de datos ficticios pendiente de restauración.")
    try:
        payload = json.loads(session_path.read_text(encoding="utf-8"))
        backup_name = str(payload["original_backup"])
        expected_hash = str(payload["original_sha256"]).upper()
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise BackupError("El registro de la prueba está dañado o incompleto.") from exc
    if Path(backup_name).name != backup_name or not backup_name.startswith("gestion_"):
        raise BackupError("La referencia a la base original no es válida.")
    original_backup = (session_directory / backup_name).resolve()
    if original_backup.parent != session_directory or not original_backup.is_file():
        raise BackupError("No se encontró la copia original de esta prueba.")
    validate_application_backup(original_backup, working_directory=session_directory)
    if file_sha256(original_backup) != expected_hash:
        raise BackupError("La copia original cambió desde que comenzó la prueba.")
    return payload, original_backup


def _ensure_database(database_path: Path) -> None:
    from django.core.management import call_command

    if not database_path.is_file():
        call_command("migrate", interactive=False, verbosity=0)
    validate_application_database(database_path)


def _refresh_recovery(database_path: Path, backup_directory: Path) -> Path:
    recovery = create_backup(
        database_path,
        backup_directory,
        label="recovery",
        fixed_name="gestion_recovery.sqlite3.zip",
    )
    if recovery is None:
        raise BackupError("No se pudo actualizar la copia de recuperación.")
    validate_application_backup(recovery, working_directory=database_path.parent)
    return recovery


def _demo_counts() -> dict[str, int]:
    from modules.core.models import (
        CollectionAssignment,
        CollectionRoute,
        Collector,
        Customer,
        Sale,
    )

    return {
        "clientes": Customer.objects.count(),
        "ventas": Sale.objects.count(),
        "cobradores": Collector.objects.count(),
        "recorridos": CollectionRoute.objects.count(),
        "asignaciones": CollectionAssignment.objects.count(),
    }


def load_demo_data(*, as_of: date | None = None) -> tuple[Path, dict[str, int]]:
    if local_application_is_running():
        raise BackupError(
            "El sistema está abierto. Usá “Cerrar y respaldar” antes de cargar la prueba."
        )
    settings = configure_django()
    database_path, backup_directory, session_directory, session_path = _paths(settings)

    from django.core.management import call_command
    from django.db import connections

    _ensure_database(database_path)
    connections.close_all()
    if session_path.is_file():
        _, original_backup = _read_session(session_path, session_directory)
    else:
        original_backup = create_backup(
            database_path,
            session_directory,
            label="demo_original",
            fixed_name=f"gestion_original_antes_demo_{_timestamp()}.sqlite3.zip",
        )
        if original_backup is None:
            raise BackupError("No se pudo guardar la base original.")
        validate_application_backup(original_backup, working_directory=database_path.parent)
        _write_session(session_path, original_backup=original_backup)

    try:
        call_command("migrate", interactive=False, verbosity=0)
        options = {"confirm_reset": True, "verbosity": 0}
        if as_of is not None:
            options["as_of"] = as_of
        call_command("seed_demo_data", **options)
        counts = _demo_counts()
        if counts["clientes"] < 50 or counts["ventas"] < 70 or counts["cobradores"] < 5:
            raise BackupError("La ingesta quedó incompleta.")
        connections.close_all()
        validate_application_database(database_path)
        _refresh_recovery(database_path, backup_directory)
    except Exception as exc:
        connections.close_all()
        try:
            restore_database(original_backup, database_path, backup_directory)
            _refresh_recovery(database_path, backup_directory)
            session_path.unlink(missing_ok=True)
        except BackupError as restore_exc:
            raise BackupError(
                "La ingesta falló y no se pudo restaurar automáticamente. "
                f"La copia original permanece en {original_backup}."
            ) from restore_exc
        if isinstance(exc, BackupError):
            raise
        raise BackupError(
            "La ingesta falló. La base original fue restaurada automáticamente."
        ) from exc
    return original_backup, counts


def clear_demo_data() -> tuple[Path, Path]:
    if local_application_is_running():
        raise BackupError(
            "El sistema está abierto. Usá “Cerrar y respaldar” antes de limpiar la prueba."
        )
    settings = configure_django()
    database_path, backup_directory, session_directory, session_path = _paths(settings)

    from django.core.management import call_command
    from django.db import connections

    _read_session(session_path, session_directory)
    _ensure_database(database_path)
    connections.close_all()
    demo_backup = create_backup(
        database_path,
        session_directory,
        label="demo_before_clear",
        fixed_name=f"gestion_datos_ficticios_antes_limpiar_{_timestamp()}.sqlite3.zip",
    )
    if demo_backup is None:
        raise BackupError("No se pudo respaldar la prueba antes de limpiarla.")
    validate_application_backup(demo_backup, working_directory=database_path.parent)

    try:
        call_command("flush", interactive=False, verbosity=0)
        call_command("migrate", interactive=False, verbosity=0)
        connections.close_all()
        validate_application_database(database_path)
        recovery = _refresh_recovery(database_path, backup_directory)
    except Exception as exc:
        connections.close_all()
        restore_database(demo_backup, database_path, backup_directory)
        if isinstance(exc, BackupError):
            raise
        raise BackupError(
            "No se pudo limpiar la prueba; los datos ficticios fueron recuperados."
        ) from exc
    return demo_backup, recovery


def restore_original_data() -> tuple[Path, Path | None, Path]:
    if local_application_is_running():
        raise BackupError("El sistema está abierto. Usá “Cerrar y respaldar” antes de restaurar.")
    settings = configure_django()
    database_path, backup_directory, session_directory, session_path = _paths(settings)

    from django.db import connections

    _, original_backup = _read_session(session_path, session_directory)
    connections.close_all()
    preventive = restore_database(original_backup, database_path, backup_directory)
    recovery = _refresh_recovery(database_path, backup_directory)
    session_path.unlink()
    return original_backup, preventive, recovery


def _confirm(action: str) -> bool:
    prompts = {
        "seed": (
            "Se guardará la base actual y se reemplazará temporalmente por datos ficticios.",
            "DATOS FICTICIOS",
        ),
        "clear": (
            "Se limpiarán los datos ficticios. La copia original seguirá protegida.",
            "LIMPIAR",
        ),
        "restore": (
            "Se reemplazará la base de prueba por la base original guardada.",
            "RESTAURAR",
        ),
    }
    message, expected = prompts[action]
    print(message)
    return input(f"Escribí {expected} para continuar: ").strip().upper() == expected


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Administra datos ficticios protegidos.")
    parser.add_argument("action", choices=("seed", "clear", "restore"))
    parser.add_argument("--yes", action="store_true", help="Omite la confirmación.")
    parser.add_argument("--as-of", type=date.fromisoformat, default=None)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    if not arguments.yes and not _confirm(arguments.action):
        print("Operación cancelada. No se modificó ningún dato.")
        return 2
    try:
        if arguments.action == "seed":
            original_backup, counts = load_demo_data(as_of=arguments.as_of)
            print("\nDATOS FICTICIOS CARGADOS")
            print(f"Base original protegida: {original_backup}")
            print(", ".join(f"{name}: {value}" for name, value in counts.items()))
        elif arguments.action == "clear":
            demo_backup, _ = clear_demo_data()
            print("\nBASE DE PRUEBA LIMPIA")
            print(f"Los datos ficticios anteriores se guardaron en: {demo_backup}")
            print("La base original sigue disponible para restaurarla.")
        else:
            original_backup, preventive, _ = restore_original_data()
            print("\nBASE ORIGINAL RESTAURADA")
            print(f"Origen verificado: {original_backup}")
            if preventive:
                print(f"Copia preventiva de lo reemplazado: {preventive}")
    except BackupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
