from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings

from launcher.backup import BackupError, create_backup

logger = logging.getLogger(__name__)


def refresh_recovery_backup() -> Path | None:
    """Update the fixed recovery copy without breaking the completed operation."""
    database_path = Path(settings.DATABASES["default"]["NAME"])
    if not database_path.is_file():
        return None
    try:
        return create_backup(
            database_path,
            Path(settings.BACKUP_DIR),
            label="recovery",
            fixed_name="gestion_recovery.sqlite3",
        )
    except BackupError:
        logger.exception("No se pudo actualizar la copia de recuperación.")
        return None
