from __future__ import annotations

import os
import signal
import sys
import threading
import webbrowser
from pathlib import Path
from socketserver import ThreadingMixIn
from tkinter import BOTH, LEFT, Button, Frame, Label, StringVar, Tk, messagebox
from urllib.error import URLError
from urllib.request import urlopen
from wsgiref.simple_server import WSGIServer, make_server

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from launcher.backup import BackupError, create_backup

HOST = "127.0.0.1"
PORT = 8765


class ThreadingServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


def portable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def application_code_root(root: Path) -> Path:
    if getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS) / "app"
    return root / "app"


class LocalApplication:
    def __init__(self) -> None:
        self.root_path = portable_root()
        self.app_path = application_code_root(self.root_path)
        self.data_path = self.root_path / "data"
        self.backup_path = self.root_path / "backups"
        self.export_path = self.root_path / "exports"
        self.media_path = self.root_path / "media"
        self.database_path = self.data_path / "gestion_financiera.sqlite3"

        self.server = None
        self.server_thread = None
        self.window = None
        self.status = None
        self.closing = False

    def configure_django(self) -> None:
        for directory in (
            self.data_path,
            self.backup_path,
            self.export_path,
            self.media_path,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        sys.path.insert(0, str(self.app_path))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        os.environ["GESTION_DATA_DIR"] = str(self.data_path)
        os.environ["GESTION_BACKUP_DIR"] = str(self.backup_path)
        os.environ["GESTION_EXPORT_DIR"] = str(self.export_path)
        os.environ["GESTION_MEDIA_DIR"] = str(self.media_path)
        os.environ.setdefault("DJANGO_DEBUG", "0")

        import django
        from django.core.management import call_command

        if self.database_path.exists():
            create_backup(
                self.database_path,
                self.backup_path,
                label="pre_migration",
                retention=5,
            )

        django.setup()
        call_command("migrate", interactive=False, verbosity=0)
        call_command("update_late_fees", verbosity=0)
        create_backup(
            self.database_path,
            self.backup_path,
            label="startup",
            retention=5,
        )

    def start_server(self) -> None:
        from config.wsgi import application

        self.server = make_server(
            HOST,
            PORT,
            application,
            server_class=ThreadingServer,
        )
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            name="gestion-financiera-server",
            daemon=True,
        )
        self.server_thread.start()

    def wait_until_ready(self) -> bool:
        url = f"http://{HOST}:{PORT}/health/"
        for _ in range(40):
            try:
                with urlopen(url, timeout=0.25) as response:
                    return response.status == 200
            except (URLError, TimeoutError):
                threading.Event().wait(0.1)
        return False

    def open_browser(self) -> None:
        webbrowser.open(f"http://{HOST}:{PORT}/")

    def create_manual_backup(self) -> None:
        try:
            backup = create_backup(
                self.database_path,
                self.backup_path,
                label="manual",
                retention=30,
            )
        except BackupError as exc:
            messagebox.showerror("No se pudo respaldar", str(exc))
            return

        if backup:
            self.status.set(f"Backup creado: {backup.name}")
            messagebox.showinfo("Backup completo", f"Se creó:\n{backup}")

    def close_and_backup(self) -> None:
        if self.closing:
            return
        self.closing = True
        self.status.set("Cerrando y creando backup…")

        try:
            if self.server:
                self.server.shutdown()
                self.server.server_close()
            if self.server_thread:
                self.server_thread.join(timeout=5)
            backup = create_backup(
                self.database_path,
                self.backup_path,
                label="close",
                retention=30,
            )
            if backup:
                self.status.set(f"Backup final: {backup.name}")
        except BackupError as exc:
            self.closing = False
            messagebox.showerror(
                "No se pudo cerrar",
                f"El programa sigue abierto porque falló el backup:\n\n{exc}",
            )
            return

        self.window.destroy()

    def build_window(self) -> None:
        self.window = Tk()
        self.window.title("Gestión Financiera")
        self.window.geometry("470x220")
        self.window.minsize(420, 210)
        self.window.protocol("WM_DELETE_WINDOW", self.close_and_backup)

        self.status = StringVar(value="Sistema local en funcionamiento")

        content = Frame(self.window, padx=24, pady=22)
        content.pack(fill=BOTH, expand=True)

        Label(
            content,
            text="Gestión Financiera",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w")
        Label(
            content,
            text=f"Disponible solo en este equipo: http://{HOST}:{PORT}",
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(4, 18))

        actions = Frame(content)
        actions.pack(anchor="w")
        Button(actions, text="Abrir sistema", command=self.open_browser, width=16).pack(
            side=LEFT, padx=(0, 8)
        )
        Button(actions, text="Crear backup", command=self.create_manual_backup, width=16).pack(
            side=LEFT, padx=(0, 8)
        )
        Button(
            actions,
            text="Cerrar y respaldar",
            command=self.close_and_backup,
            width=18,
        ).pack(side=LEFT)

        Label(
            content,
            textvariable=self.status,
            font=("Segoe UI", 9),
            fg="#475467",
        ).pack(anchor="w", pady=(20, 0))

    def run(self) -> None:
        self.configure_django()
        self.start_server()
        if not self.wait_until_ready():
            raise RuntimeError("El servidor local no respondió a tiempo")
        self.build_window()
        self.open_browser()

        signal.signal(signal.SIGINT, lambda *_: self.window.after(0, self.close_and_backup))
        self.window.mainloop()


def main() -> None:
    app = LocalApplication()
    try:
        app.run()
    except Exception as exc:
        try:
            root = Tk()
            root.withdraw()
            messagebox.showerror("No se pudo iniciar Gestión Financiera", str(exc))
            root.destroy()
        except Exception:
            print(f"No se pudo iniciar Gestión Financiera: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
