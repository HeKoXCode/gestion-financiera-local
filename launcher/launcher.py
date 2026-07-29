from __future__ import annotations

import os
import signal
import sys
import threading
import traceback
import webbrowser
from pathlib import Path
from socketserver import ThreadingMixIn
from tkinter import Button, Frame, Label, StringVar, Tk, messagebox
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from wsgiref.simple_server import WSGIServer, make_server

from PIL import Image, ImageOps, ImageTk

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from launcher.backup import (
    BackupError,
    compress_legacy_backups,
    create_backup,
    create_daily_backup,
    validate_application_database,
)

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
CLOSE_BACKUP_RETENTION_DAYS = 90
WINDOW_WIDTH = 620
WINDOW_HEIGHT = 450

COLOR_BACKGROUND = "#F3F6F4"
COLOR_SURFACE = "#FFFFFF"
COLOR_PRIMARY = "#0F4C3A"
COLOR_PRIMARY_HOVER = "#0B3D2E"
COLOR_ACCENT = "#42B883"
COLOR_TEXT = "#17211D"
COLOR_MUTED = "#607069"
COLOR_BORDER = "#D9E2DE"
COLOR_SECONDARY_HOVER = "#E9EFEC"


class ThreadingServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


def build_local_wsgi_application():
    """Serve Django and its bundled static assets from the same local process."""
    from config.wsgi import application
    from django.contrib.staticfiles.handlers import StaticFilesHandler

    return StaticFilesHandler(application)


def portable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def application_code_root(root: Path) -> Path:
    if getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS)
    return root / "app"


class LocalApplication:
    def __init__(self) -> None:
        self.root_path = portable_root()
        self.app_path = application_code_root(self.root_path)
        self.port = int(os.environ.get("GESTION_PORT", DEFAULT_PORT))
        self.data_path = self.root_path / "data"
        self.backup_path = self.root_path / "backups"
        self.export_path = self.root_path / "exports"
        self.media_path = self.root_path / "media"
        self.database_path = self.data_path / "gestion_financiera.sqlite3"

        self.server = None
        self.server_thread = None
        self.window = None
        self.status = None
        self.open_button = None
        self.business_name = "Gestión Financiera"
        self.business_logo_path = None
        self.logo_image = None
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

        compress_legacy_backups(self.backup_path)

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
        self.load_branding()
        create_backup(
            self.database_path,
            self.backup_path,
            label="startup",
            retention=5,
        )
        create_backup(
            self.database_path,
            self.backup_path,
            label="recovery",
            fixed_name="gestion_recovery.sqlite3.zip",
        )

    def load_branding(self) -> None:
        from modules.core.models import BusinessSettings

        settings = BusinessSettings.get_solo()
        self.business_name = settings.business_name.strip() or "Gestión Financiera"
        self.business_logo_path = None
        if settings.logo:
            try:
                logo_path = Path(settings.logo.path).resolve()
                if logo_path.is_file():
                    self.business_logo_path = logo_path
            except (OSError, ValueError):
                self.business_logo_path = None

    def build_logo_image(self):
        if self.business_logo_path is None:
            return None
        try:
            with Image.open(self.business_logo_path) as source:
                logo = ImageOps.exif_transpose(source).convert("RGBA")
                logo.thumbnail((58, 58), Image.Resampling.LANCZOS)
                canvas = Image.new("RGBA", (64, 64), "#FFFFFF")
                position = ((64 - logo.width) // 2, (64 - logo.height) // 2)
                canvas.alpha_composite(logo, position)
            return ImageTk.PhotoImage(canvas)
        except (OSError, ValueError):
            return None

    def start_server(self) -> None:
        self.server = make_server(
            HOST,
            self.port,
            build_local_wsgi_application(),
            server_class=ThreadingServer,
        )
        self.port = self.server.server_port
        self.server_thread = threading.Thread(
            target=self.server.serve_forever,
            name="gestion-financiera-server",
            daemon=True,
        )
        self.server_thread.start()

    def wait_until_ready(self) -> bool:
        url = f"http://{HOST}:{self.port}/health/"
        for _ in range(40):
            try:
                with urlopen(url, timeout=0.25) as response:
                    return response.status == 200
            except (URLError, TimeoutError):
                threading.Event().wait(0.1)
        return False

    def stop_server(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.server_thread:
            self.server_thread.join(timeout=5)
            self.server_thread = None

    def run_smoke_test(self) -> None:
        """Exercise the frozen application without opening windows or a browser."""
        self.configure_django()
        self.start_server()
        try:
            if not self.wait_until_ready():
                raise RuntimeError("El servidor portable no respondió a tiempo")
            for path in (
                "/",
                "/clientes/",
                "/cobranza/",
                "/reportes/",
                "/datos/",
                "/static/css/app.css",
            ):
                try:
                    with urlopen(f"http://{HOST}:{self.port}{path}", timeout=5) as response:
                        if response.status != 200 or not response.read(256):
                            raise RuntimeError(
                                f"La ruta portable no respondió correctamente: {path}"
                            )
                except HTTPError as exc:
                    raise RuntimeError(
                        f"La ruta portable devolvió HTTP {exc.code}: {path}"
                    ) from exc
        finally:
            self.stop_server()

        create_daily_backup(
            self.database_path,
            self.backup_path,
            label="close",
            retention_days=CLOSE_BACKUP_RETENTION_DAYS,
        )
        validate_application_database(self.database_path)

    def open_browser(self) -> None:
        opened = webbrowser.open_new_tab(f"http://{HOST}:{self.port}/")
        if opened:
            self.status.set(
                "El programa está abierto en el navegador. "
                "Dejá esta ventana abierta mientras trabajás."
            )
            self.open_button.configure(text="Volver a abrir el programa")
            return

        self.status.set("No se pudo abrir el navegador automáticamente.")
        messagebox.showwarning(
            "Abrir Gestión Financiera",
            (
                "No se pudo abrir el programa en el navegador automáticamente.\n\n"
                f"Abrí esta dirección manualmente:\nhttp://{HOST}:{self.port}/"
            ),
        )

    def close_and_backup(self) -> None:
        if self.closing:
            return
        self.closing = True
        self.status.set("Guardando los datos y cerrando de forma segura…")
        self.window.update_idletasks()

        try:
            self.stop_server()
            backup = create_daily_backup(
                self.database_path,
                self.backup_path,
                label="close",
                retention_days=CLOSE_BACKUP_RETENTION_DAYS,
            )
            if backup:
                self.status.set(f"Copia final: {backup.name}")
        except BackupError as exc:
            self.closing = False
            messagebox.showerror(
                "No se pudo cerrar",
                f"El programa sigue abierto porque falló la copia de seguridad:\n\n{exc}",
            )
            return

        self.window.destroy()

    @staticmethod
    def _add_hover(button: Button, *, normal: str, hover: str) -> None:
        button.bind("<Enter>", lambda _event: button.configure(background=hover))
        button.bind("<Leave>", lambda _event: button.configure(background=normal))

    def _center_window(self) -> None:
        self.window.update_idletasks()
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        position_x = max((screen_width - WINDOW_WIDTH) // 2, 0)
        position_y = max((screen_height - WINDOW_HEIGHT) // 2, 0)
        self.window.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{position_x}+{position_y}")

    def build_window(self) -> None:
        self.window = Tk()
        self.window.title(f"{self.business_name} · Gestión Financiera")
        self.window.configure(background=COLOR_BACKGROUND)
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.close_and_backup)
        self._center_window()

        self.status = StringVar(value="Todo está listo. Presioná “Abrir programa” para comenzar.")

        header = Frame(
            self.window,
            background=COLOR_PRIMARY,
            padx=38,
            pady=24,
        )
        header.pack(fill="x")

        brand_row = Frame(header, background=COLOR_PRIMARY)
        brand_row.pack(fill="x")
        self.logo_image = self.build_logo_image()
        if self.logo_image is not None:
            logo_widget = Label(
                brand_row,
                image=self.logo_image,
                background="#FFFFFF",
                borderwidth=0,
                padx=2,
                pady=2,
            )
        else:
            logo_widget = Label(
                brand_row,
                text="GF",
                font=("Segoe UI Semibold", 15),
                foreground="#18332B",
                background="#E7AA45",
                width=4,
                height=2,
            )
        logo_widget.pack(side="left", padx=(0, 16))

        brand_copy = Frame(brand_row, background=COLOR_PRIMARY)
        brand_copy.pack(side="left", fill="x", expand=True)
        Label(
            brand_copy,
            text="GESTIÓN FINANCIERA · PROGRAMA LOCAL",
            font=("Segoe UI Semibold", 9),
            foreground="#A9E7CD",
            background=COLOR_PRIMARY,
        ).pack(anchor="w")
        Label(
            brand_copy,
            text=self.business_name,
            font=(
                "Segoe UI Semibold",
                23 if len(self.business_name) <= 34 else 18,
            ),
            foreground="#FFFFFF",
            background=COLOR_PRIMARY,
            justify="left",
            wraplength=430,
        ).pack(anchor="w", pady=(2, 0))
        Label(
            brand_copy,
            text="Ventas financiadas y cobranza diaria",
            font=("Segoe UI", 10),
            foreground="#D3E9E0",
            background=COLOR_PRIMARY,
        ).pack(anchor="w")

        content = Frame(
            self.window,
            background=COLOR_BACKGROUND,
            padx=38,
            pady=28,
        )
        content.pack(fill="both", expand=True)

        status_card = Frame(
            content,
            background=COLOR_SURFACE,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            padx=20,
            pady=17,
        )
        status_card.pack(fill="x")

        ready_row = Frame(status_card, background=COLOR_SURFACE)
        ready_row.pack(fill="x")
        Label(
            ready_row,
            text="●",
            font=("Segoe UI", 10),
            foreground=COLOR_ACCENT,
            background=COLOR_SURFACE,
        ).pack(side="left", padx=(0, 8))
        Label(
            ready_row,
            text="Programa listo",
            font=("Segoe UI Semibold", 11),
            foreground=COLOR_TEXT,
            background=COLOR_SURFACE,
        ).pack(side="left")
        Label(
            status_card,
            text=(
                "Tus datos permanecen en este equipo. Abrí el programa para "
                "consultar clientes, ventas y cobranzas."
            ),
            font=("Segoe UI", 9),
            foreground=COLOR_MUTED,
            background=COLOR_SURFACE,
            justify="left",
            wraplength=495,
        ).pack(anchor="w", pady=(7, 0))

        actions = Frame(content, background=COLOR_BACKGROUND)
        actions.pack(fill="x", pady=(20, 0))

        self.open_button = Button(
            actions,
            text="Abrir programa",
            command=self.open_browser,
            font=("Segoe UI Semibold", 10),
            foreground="#FFFFFF",
            background=COLOR_PRIMARY,
            activeforeground="#FFFFFF",
            activebackground=COLOR_PRIMARY_HOVER,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=22,
            pady=11,
        )
        self.open_button.pack(side="left")
        self._add_hover(
            self.open_button,
            normal=COLOR_PRIMARY,
            hover=COLOR_PRIMARY_HOVER,
        )

        close_button = Button(
            actions,
            text="Cerrar y respaldar",
            command=self.close_and_backup,
            font=("Segoe UI Semibold", 10),
            foreground=COLOR_TEXT,
            background=COLOR_BACKGROUND,
            activeforeground=COLOR_TEXT,
            activebackground=COLOR_SECONDARY_HOVER,
            relief="solid",
            borderwidth=1,
            cursor="hand2",
            padx=18,
            pady=10,
        )
        close_button.pack(side="left", padx=(12, 0))
        self._add_hover(
            close_button,
            normal=COLOR_BACKGROUND,
            hover=COLOR_SECONDARY_HOVER,
        )

        footer = Frame(content, background=COLOR_BACKGROUND)
        footer.pack(fill="x", pady=(18, 0))

        Label(
            footer,
            textvariable=self.status,
            font=("Segoe UI", 9),
            foreground=COLOR_MUTED,
            background=COLOR_BACKGROUND,
            justify="left",
            wraplength=355,
        ).pack(side="left", anchor="w")
        Label(
            footer,
            text="Creado por Percy I. Marzoratti Hill.",
            font=("Segoe UI", 7, "italic"),
            foreground="#89958F",
            background=COLOR_BACKGROUND,
        ).pack(side="right", anchor="e", padx=(12, 0))

    def run(self) -> None:
        self.configure_django()
        self.start_server()
        if not self.wait_until_ready():
            raise RuntimeError("El servidor local no respondió a tiempo")
        self.build_window()

        signal.signal(signal.SIGINT, lambda *_: self.window.after(0, self.close_and_backup))
        self.window.mainloop()


def main() -> None:
    app = LocalApplication()
    if "--smoke-test" in sys.argv:
        try:
            app.run_smoke_test()
        except Exception:
            failure_log = app.root_path / "smoke-test-error.txt"
            failure_log.write_text(traceback.format_exc(), encoding="utf-8")
            raise SystemExit(1) from None
        return
    try:
        app.run()
    except Exception as exc:
        try:
            root = Tk()
            root.withdraw()
            messagebox.showerror("No se pudo iniciar Gestión Financiera", str(exc))
            root.destroy()
        except Exception:
            if sys.stderr:
                print(f"No se pudo iniciar Gestión Financiera: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
