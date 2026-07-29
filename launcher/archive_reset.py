from __future__ import annotations

import argparse
import hashlib
import os
import re
import socket
import sys
import unicodedata
from datetime import datetime
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

HOST = "127.0.0.1"
PORT = 8765
MAX_ARCHIVE_LABEL_LENGTH = 60


def normalize_archive_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip())
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    label = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return label[:MAX_ARCHIVE_LABEL_LENGTH].rstrip("-") or "datos"


def local_application_is_running() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=0.25):
            return True
    except OSError:
        return False


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def configure_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault("DJANGO_DEBUG", "0")

    import django

    django.setup()

    from django.conf import settings

    return settings


def business_counts() -> dict[str, int]:
    from modules.core.models import (
        BusinessSettings,
        CollectionAttempt,
        Customer,
        Installment,
        LateFee,
        Payment,
        PaymentAllocation,
        Product,
        Sale,
    )

    return {
        "clientes": Customer.objects.count(),
        "productos": Product.objects.count(),
        "ventas": Sale.objects.count(),
        "cuotas": Installment.objects.count(),
        "recargos": LateFee.objects.count(),
        "pagos": Payment.objects.count(),
        "imputaciones": PaymentAllocation.objects.count(),
        "visitas": CollectionAttempt.objects.count(),
        "configuraciones": BusinessSettings.objects.count(),
    }


def format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{name}: {amount}" for name, amount in counts.items())


def archive_and_reset(label: str) -> tuple[Path, dict[str, int], Path]:
    if local_application_is_running():
        raise BackupError(
            "Gestión Financiera está abierta. Cerrala con “Cerrar y respaldar” antes de continuar."
        )

    settings = configure_django()
    database_path = Path(settings.DATABASES["default"]["NAME"]).resolve()
    backup_directory = Path(settings.BACKUP_DIR).resolve()
    storage_directory = Path(
        os.environ.get("GESTION_STORAGE_DIR", settings.PROJECT_DIR / "storage")
    ).resolve()

    if not database_path.is_file():
        raise BackupError("No existen datos actuales para archivar.")

    validate_application_database(database_path)
    before_counts = business_counts()
    safe_label = normalize_archive_label(label)
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S_%f")
    archive_name = f"gestion_{safe_label}_{timestamp}.sqlite3.zip"
    archive = create_backup(
        database_path,
        storage_directory,
        label="archive",
        fixed_name=archive_name,
    )
    if archive is None:
        raise BackupError("No se pudo crear la copia histórica.")
    validate_application_backup(archive, working_directory=database_path.parent)

    reset_started = False
    try:
        from django.core.management import call_command

        reset_started = True
        call_command("flush", interactive=False, verbosity=0)
        call_command("migrate", interactive=False, verbosity=0)
        validate_application_database(database_path)

        after_counts = business_counts()
        if any(after_counts.values()):
            raise BackupError("La nueva base no quedó vacía: " + format_counts(after_counts))

        recovery = create_backup(
            database_path,
            backup_directory,
            label="recovery",
            fixed_name="gestion_recovery.sqlite3.zip",
        )
        if recovery is None:
            raise BackupError("No se pudo actualizar la copia de recuperación.")
        validate_application_backup(recovery, working_directory=database_path.parent)
    except Exception as exc:
        if reset_started:
            from django.db import connections

            connections.close_all()
            try:
                restore_database(archive, database_path, backup_directory)
                create_backup(
                    database_path,
                    backup_directory,
                    label="recovery",
                    fixed_name="gestion_recovery.sqlite3.zip",
                )
            except BackupError as restore_exc:
                raise BackupError(
                    "El reinicio falló y tampoco pudo recuperarse automáticamente. "
                    f"La copia intacta está en: {archive}"
                ) from restore_exc
        if isinstance(exc, BackupError):
            raise
        raise BackupError(
            "No se pudo limpiar la base. Los datos fueron restaurados desde el archivo."
        ) from exc

    return archive, before_counts, recovery


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Archiva los datos actuales y deja el programa vacío."
    )
    parser.add_argument(
        "--name",
        default="",
        help="Nombre descriptivo para reconocer el archivo.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Omite la confirmación interactiva.",
    )
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    label = arguments.name.strip()
    if not label:
        label = input("Nombre para reconocer estos datos [datos]: ").strip() or "datos"

    if not arguments.yes:
        print()
        print("Se guardará una copia completa y el programa quedará sin datos.")
        confirmation = input("Escribí ARCHIVAR para continuar: ").strip().upper()
        if confirmation != "ARCHIVAR":
            print("Operación cancelada. No se modificó ningún dato.")
            return 2

    try:
        archive, counts, recovery = archive_and_reset(label)
    except BackupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print()
    print("ARCHIVO Y REINICIO COMPLETADOS")
    print(f"Datos archivados: {format_counts(counts)}")
    print(f"Archivo: {archive}")
    print(f"SHA256: {file_sha256(archive)}")
    print(f"Recuperación vacía actualizada: {recovery}")
    print("El programa está limpio y listo para comenzar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
