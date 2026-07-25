from __future__ import annotations

import socket
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import BOTH, Button, Frame, Label, StringVar, Tk, filedialog, messagebox

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from launcher.backup import (
    BackupError,
    list_backups,
    restore_database,
    validate_application_backup,
    validate_application_database,
)

HOST = "127.0.0.1"
PORT = 8765


def portable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def local_application_is_running() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=0.25):
            return True
    except OSError:
        return False


def find_latest_valid_backup(
    backup_directory: Path,
    *,
    working_directory: Path,
) -> Path | None:
    for backup in list_backups(backup_directory):
        try:
            validate_application_backup(
                backup.path,
                working_directory=working_directory,
            )
        except BackupError:
            continue
        return backup.path
    return None


def launch_main_application(root_path: Path, *, frozen: bool | None = None) -> None:
    is_frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if is_frozen:
        executable = root_path / "GestionFinanciera.exe"
        if not executable.is_file():
            raise BackupError("No se encontró GestionFinanciera.exe.")
        command = [str(executable)]
    else:
        launcher = root_path / "scripts" / "Iniciar.bat"
        if not launcher.is_file():
            raise BackupError("No se encontró scripts\\Iniciar.bat.")
        command = ["cmd.exe", "/c", str(launcher)]

    try:
        subprocess.Popen(
            command,
            cwd=root_path,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        raise BackupError("No se pudo volver a abrir Gestión Financiera.") from exc


def run_smoke_test() -> None:
    """Validate and restore the isolated portable database without showing Tk."""
    root_path = portable_root()
    database_path = root_path / "data" / "gestion_financiera.sqlite3"
    backup_directory = root_path / "backups"
    recovery = backup_directory / "gestion_recovery.sqlite3.zip"
    validate_application_database(database_path)
    validate_application_backup(recovery, working_directory=database_path.parent)
    restore_database(recovery, database_path, backup_directory)
    validate_application_database(database_path)


class RestorerApplication:
    def __init__(self) -> None:
        self.root_path = portable_root()
        self.database_path = self.root_path / "data" / "gestion_financiera.sqlite3"
        self.backup_path = self.root_path / "backups"
        self.window = Tk()
        self.window.title("Restaurar Gestión Financiera")
        self.window.geometry("560x310")
        self.window.minsize(520, 290)
        self.selected_backup: Path | None = None
        self.selected_path = StringVar(value="Buscando la copia más reciente…")
        self.status = StringVar(value="El programa debe estar cerrado para restaurar.")
        self.select_latest_backup()

    def select_latest_backup(self) -> None:
        self.backup_path.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        selected = find_latest_valid_backup(
            self.backup_path,
            working_directory=self.database_path.parent,
        )
        if selected:
            self._set_selected_backup(
                selected,
                status="Se seleccionó automáticamente la copia más reciente.",
            )
            return
        self.selected_backup = None
        self.selected_path.set("No se encontró una copia válida")
        self.status.set("Usá “Elegir otra copia” para buscar un backup.")

    def choose_backup(self) -> None:
        self.backup_path.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        selected = filedialog.askopenfilename(
            title="Seleccionar backup",
            initialdir=self.backup_path,
            filetypes=[
                ("Backup comprimido", "*.sqlite3.zip"),
                ("Backup SQLite anterior", "*.sqlite3"),
                ("Archivos ZIP", "*.zip"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if not selected:
            return
        try:
            validate_application_backup(
                Path(selected),
                working_directory=self.database_path.parent,
            )
        except BackupError as exc:
            messagebox.showerror("Copia no válida", str(exc))
            return
        self._set_selected_backup(
            Path(selected),
            status="Copia validada. Ya puede restaurarse.",
        )

    def _set_selected_backup(self, backup: Path, *, status: str) -> None:
        self.selected_backup = backup.resolve()
        modified = datetime.fromtimestamp(self.selected_backup.stat().st_mtime)
        size_mb = self.selected_backup.stat().st_size / (1024 * 1024)
        self.selected_path.set(
            f"{self.selected_backup.name}\n"
            f"{modified:%d/%m/%Y %H:%M} · {size_mb:.2f} MB"
        )
        self.status.set(status)

    def restore(self) -> None:
        selected = self.selected_backup
        if selected is None or not selected.is_file():
            messagebox.showwarning("Falta una copia", "Seleccioná primero un backup válido.")
            return
        if local_application_is_running():
            messagebox.showerror(
                "El programa está abierto",
                "Cerrá Gestión Financiera con “Cerrar y respaldar” antes de restaurar.",
            )
            return
        if not messagebox.askyesno(
            "Confirmar restauración",
            (
                "Se reemplazarán los datos actuales por la copia seleccionada.\n\n"
                "Antes se creará automáticamente un backup preventivo.\n\n"
                "¿Deseás continuar?"
            ),
        ):
            return

        self.status.set("Validando y restaurando…")
        self.window.update_idletasks()
        try:
            preventive = restore_database(
                selected,
                self.database_path,
                self.backup_path,
            )
        except BackupError as exc:
            self.status.set("La restauración no pudo completarse.")
            messagebox.showerror("No se pudo restaurar", str(exc))
            return

        self.status.set("Restauración completada correctamente.")
        detail = (
            f"\n\nBackup preventivo: {preventive.name}" if preventive else ""
        )
        messagebox.showinfo(
            "Datos restaurados",
            (
                "La copia fue restaurada correctamente. "
                f"Gestión Financiera se abrirá ahora.{detail}"
            ),
        )
        try:
            launch_main_application(self.root_path)
        except BackupError as exc:
            self.status.set("Restauración completa; abrí el programa manualmente.")
            messagebox.showwarning(
                "Datos restaurados",
                f"{exc}\n\nLos datos ya fueron recuperados correctamente.",
            )
            return
        self.window.destroy()

    def build(self) -> None:
        content = Frame(self.window, padx=28, pady=24)
        content.pack(fill=BOTH, expand=True)

        Label(
            content,
            text="Restaurar datos",
            font=("Segoe UI", 19, "bold"),
        ).pack(anchor="w")
        Label(
            content,
            text=(
                "La copia más reciente se elige automáticamente. Al restaurar, "
                "el ZIP se valida y descomprime sin pasos adicionales."
            ),
            font=("Segoe UI", 9),
            fg="#52625c",
            justify="left",
            wraplength=485,
        ).pack(anchor="w", pady=(5, 18))

        Label(
            content,
            textvariable=self.selected_path,
            font=("Segoe UI", 8),
            fg="#66756f",
            wraplength=485,
            justify="left",
        ).pack(anchor="w", pady=(8, 18))
        Button(
            content,
            text="Restaurar la copia mostrada",
            command=self.restore,
            width=28,
        ).pack(anchor="w")
        Button(
            content,
            text="Elegir otra copia…",
            command=self.choose_backup,
            width=22,
        ).pack(anchor="w", pady=(8, 0))
        Label(
            content,
            textvariable=self.status,
            font=("Segoe UI", 9),
            fg="#475467",
        ).pack(anchor="w", pady=(18, 0))

    def run(self) -> None:
        self.build()
        self.window.mainloop()


def main() -> None:
    if "--smoke-test" in sys.argv:
        try:
            run_smoke_test()
        except Exception:
            failure_log = portable_root() / "smoke-test-restorer-error.txt"
            failure_log.write_text(traceback.format_exc(), encoding="utf-8")
            raise SystemExit(1) from None
        return
    try:
        RestorerApplication().run()
    except Exception as exc:
        try:
            root = Tk()
            root.withdraw()
            messagebox.showerror("No se pudo abrir el restaurador", str(exc))
            root.destroy()
        except Exception:
            if sys.stderr:
                print(f"No se pudo abrir el restaurador: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
