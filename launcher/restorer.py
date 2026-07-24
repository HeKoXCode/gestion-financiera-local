from __future__ import annotations

import socket
import sys
from pathlib import Path
from tkinter import BOTH, Button, Frame, Label, StringVar, Tk, filedialog, messagebox

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from launcher.backup import BackupError, restore_database, validate_application_database

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


class RestorerApplication:
    def __init__(self) -> None:
        self.root_path = portable_root()
        self.database_path = self.root_path / "data" / "gestion_financiera.sqlite3"
        self.backup_path = self.root_path / "backups"
        self.window = Tk()
        self.window.title("Restaurar Gestión Financiera")
        self.window.geometry("560x310")
        self.window.minsize(520, 290)
        self.selected_path = StringVar(value="Ninguna copia seleccionada")
        self.status = StringVar(value="El programa debe estar cerrado para restaurar.")

    def choose_backup(self) -> None:
        self.backup_path.mkdir(parents=True, exist_ok=True)
        selected = filedialog.askopenfilename(
            title="Seleccionar backup",
            initialdir=self.backup_path,
            filetypes=[("Backup SQLite", "*.sqlite3"), ("Todos los archivos", "*.*")],
        )
        if not selected:
            return
        try:
            validate_application_database(Path(selected))
        except BackupError as exc:
            messagebox.showerror("Copia no válida", str(exc))
            return
        self.selected_path.set(selected)
        self.status.set("Copia validada. Ya puede restaurarse.")

    def restore(self) -> None:
        selected = Path(self.selected_path.get())
        if not selected.is_file():
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
            f"La copia fue restaurada. Ya podés abrir Gestión Financiera.{detail}",
        )

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
                "Recuperá clientes, ventas, cuotas y pagos desde un backup SQLite. "
                "La base actual se protege antes del reemplazo."
            ),
            font=("Segoe UI", 9),
            fg="#52625c",
            justify="left",
            wraplength=485,
        ).pack(anchor="w", pady=(5, 18))

        Button(
            content,
            text="Seleccionar backup…",
            command=self.choose_backup,
            width=22,
        ).pack(anchor="w")
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
            text="Restaurar copia seleccionada",
            command=self.restore,
            width=28,
        ).pack(anchor="w")
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
    RestorerApplication().run()


if __name__ == "__main__":
    main()
