from __future__ import annotations

import os
import signal
import sys
import threading
import traceback
import webbrowser
from contextlib import suppress
from pathlib import Path
from socketserver import ThreadingMixIn
from tkinter import Button, Frame, Label, StringVar, Tk, Toplevel, messagebox
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
from launcher.mobile_access import (
    LOOPBACK_HOST,
    MOBILE_BIND_HOST,
    build_mobile_access_url,
    build_qr_image,
    create_mobile_token,
    detect_lan_ip,
)

HOST = LOOPBACK_HOST
DEFAULT_PORT = 8765
CLOSE_BACKUP_RETENTION_DAYS = 90
WINDOW_WIDTH = 620
WINDOW_HEIGHT = 450

COLOR_BACKGROUND = "#EEF4F6"
COLOR_SURFACE = "#FFFFFF"
COLOR_PRIMARY = "#123F4B"
COLOR_PRIMARY_HOVER = "#0B303B"
COLOR_ACCENT = "#43BFB7"
COLOR_TEXT = "#14282E"
COLOR_MUTED = "#61787E"
COLOR_BORDER = "#D3E0E3"
COLOR_SECONDARY_HOVER = "#E5EFF1"


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
        self.bind_host = HOST
        self.window = None
        self.status = None
        self.open_button = None
        self.mobile_button = None
        self.mobile_window = None
        self.mobile_qr_image = None
        self.mobile_access_enabled = False
        self.mobile_ip = None
        self.mobile_token = None
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
        self.apply_mobile_settings()

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

    def apply_mobile_settings(self) -> None:
        enabled = bool(
            self.mobile_access_enabled
            and self.mobile_ip
            and self.mobile_token
        )
        os.environ["GESTION_MOBILE_ACCESS_ENABLED"] = "1" if enabled else "0"
        os.environ["GESTION_MOBILE_ACCESS_TOKEN"] = (
            self.mobile_token if enabled else ""
        )
        os.environ["GESTION_LAN_IP"] = self.mobile_ip if enabled else ""

        try:
            from django.conf import settings as django_settings

            if django_settings.configured:
                django_settings.GESTION_MOBILE_ACCESS_ENABLED = enabled
                django_settings.GESTION_MOBILE_ACCESS_TOKEN = (
                    self.mobile_token if enabled else ""
                )
                django_settings.GESTION_LAN_IP = self.mobile_ip if enabled else ""
                allowed_hosts = [HOST, "localhost"]
                if "testserver" in django_settings.ALLOWED_HOSTS:
                    allowed_hosts.append("testserver")
                if enabled:
                    allowed_hosts.append(self.mobile_ip)
                django_settings.ALLOWED_HOSTS = allowed_hosts
        except ImportError:
            pass

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
            self.bind_host,
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
                "El sistema está abierto en el navegador. "
                "Dejá esta ventana abierta mientras trabajás."
            )
            self.open_button.configure(text="Volver a abrir el sistema")
            return

        self.status.set("No se pudo abrir el navegador automáticamente.")
        messagebox.showwarning(
            "Abrir Gestión Financiera",
            (
                "No se pudo abrir el sistema en el navegador automáticamente.\n\n"
                f"Abrí esta dirección manualmente:\nhttp://{HOST}:{self.port}/"
            ),
        )

    def restart_server(self) -> None:
        self.stop_server()
        self.apply_mobile_settings()
        self.start_server()
        if not self.wait_until_ready():
            raise RuntimeError("El servidor local no respondió después del cambio")

    def activate_mobile_access(self) -> None:
        if self.mobile_access_enabled:
            self.show_mobile_access()
            return

        lan_ip = detect_lan_ip()
        if lan_ip is None:
            messagebox.showwarning(
                "Acceso desde celular",
                (
                    "No se encontró una red local disponible.\n\n"
                    "Conectá la computadora a la misma red Wi-Fi que usará "
                    "el celular e intentá nuevamente."
                ),
            )
            return

        self.mobile_access_enabled = True
        self.mobile_ip = lan_ip
        self.mobile_token = create_mobile_token()
        self.bind_host = MOBILE_BIND_HOST
        try:
            self.restart_server()
        except Exception as exc:
            self.mobile_access_enabled = False
            self.mobile_ip = None
            self.mobile_token = None
            self.bind_host = HOST
            with suppress(Exception):
                self.restart_server()
            messagebox.showerror(
                "No se pudo activar",
                f"No se pudo habilitar el acceso desde el celular:\n\n{exc}",
            )
            return

        self.mobile_button.configure(text="Ver acceso celular")
        self.status.set(
            f"Acceso celular activo en {self.mobile_ip}. "
            "Se cerrará junto con el sistema."
        )
        self.show_mobile_access()

    def deactivate_mobile_access(self) -> None:
        if not self.mobile_access_enabled:
            return

        self.mobile_access_enabled = False
        self.mobile_ip = None
        self.mobile_token = None
        self.bind_host = HOST
        try:
            self.restart_server()
        except Exception as exc:
            messagebox.showerror(
                "No se pudo desactivar",
                (
                    "El acceso desde el celular se cerró, pero el servidor "
                    f"local no pudo reiniciarse:\n\n{exc}"
                ),
            )
            return

        if self.mobile_window is not None and self.mobile_window.winfo_exists():
            self.mobile_window.destroy()
        self.mobile_window = None
        self.mobile_qr_image = None
        self.mobile_button.configure(text="Usar desde celular")
        self.status.set("Acceso celular desactivado. El sistema sigue abierto en esta PC.")

    def mobile_access_url(self) -> str:
        if not self.mobile_ip or not self.mobile_token:
            raise RuntimeError("El acceso desde celular no está activo")
        return build_mobile_access_url(
            self.mobile_ip,
            self.port,
            self.mobile_token,
        )

    def copy_mobile_link(self) -> None:
        self.window.clipboard_clear()
        self.window.clipboard_append(self.mobile_access_url())
        self.status.set("Enlace protegido copiado.")

    def firewall_script_path(self) -> Path | None:
        candidates = (
            self.root_path / "HABILITAR_ACCESO_CELULAR.bat",
            self.root_path / "scripts" / "HabilitarAccesoCelular.bat",
        )
        return next((path for path in candidates if path.is_file()), None)

    def open_firewall_setup(self) -> None:
        script = self.firewall_script_path()
        if script is None:
            messagebox.showwarning(
                "Configurar acceso",
                "No se encontró el asistente del Firewall en esta copia.",
            )
            return
        try:
            os.startfile(script)  # type: ignore[attr-defined]
        except OSError as exc:
            messagebox.showerror(
                "Configurar acceso",
                f"No se pudo abrir el asistente del Firewall:\n\n{exc}",
            )
            return
        messagebox.showinfo(
            "Configurar acceso",
            (
                "Windows solicitará permiso de administrador. Aceptalo y, "
                "cuando termine, volvé a escanear el QR."
            ),
        )

    def close_mobile_window(self) -> None:
        if self.mobile_window is not None and self.mobile_window.winfo_exists():
            self.mobile_window.destroy()
        self.mobile_window = None
        self.mobile_qr_image = None

    def show_mobile_access(self) -> None:
        if self.mobile_window is not None and self.mobile_window.winfo_exists():
            self.mobile_window.lift()
            self.mobile_window.focus_force()
            return

        access_url = self.mobile_access_url()
        dialog = Toplevel(self.window)
        self.mobile_window = dialog
        dialog.title("Acceso desde celular · Gestión Financiera")
        dialog.configure(background=COLOR_BACKGROUND)
        dialog.resizable(False, False)
        dialog.transient(self.window)
        dialog.protocol("WM_DELETE_WINDOW", self.close_mobile_window)

        dialog.update_idletasks()
        width = 540
        height = 600
        dpi_scale = max(float(dialog.winfo_fpixels("1i")) / 96.0, 1.0)
        screen_width = int(dialog.winfo_screenwidth() / dpi_scale)
        screen_height = int(dialog.winfo_screenheight() / dpi_scale)
        desired_x = self.window.winfo_rootx() + (WINDOW_WIDTH - width) // 2
        desired_y = self.window.winfo_rooty() - 80
        position_x = min(
            max(desired_x, 0),
            max(screen_width - width - 20, 0),
        )
        position_y = min(
            max(desired_y, 0),
            max(screen_height - height - 35, 0),
        )
        dialog.geometry(f"{width}x{height}+{position_x}+{position_y}")

        header = Frame(dialog, background=COLOR_PRIMARY, padx=28, pady=18)
        header.pack(fill="x")
        Label(
            header,
            text="ACCESO TEMPORAL PROTEGIDO",
            font=("Segoe UI Semibold", 9),
            foreground="#A9E2E7",
            background=COLOR_PRIMARY,
        ).pack(anchor="w")
        Label(
            header,
            text="Usar desde el celular",
            font=("Segoe UI Semibold", 20),
            foreground="#FFFFFF",
            background=COLOR_PRIMARY,
        ).pack(anchor="w", pady=(3, 0))
        Label(
            header,
            text="El acceso se cerrará automáticamente al cerrar el sistema.",
            font=("Segoe UI", 9),
            foreground="#D2E8EB",
            background=COLOR_PRIMARY,
        ).pack(anchor="w", pady=(5, 0))

        content = Frame(
            dialog,
            background=COLOR_BACKGROUND,
            padx=28,
            pady=16,
        )
        content.pack(fill="both", expand=True)

        Label(
            content,
            text=(
                "1. Conectá el celular a la misma red Wi-Fi.\n"
                "2. Escaneá este código con la cámara."
            ),
            font=("Segoe UI", 10),
            foreground=COLOR_TEXT,
            background=COLOR_BACKGROUND,
            justify="left",
        ).pack(anchor="w")

        qr_card = Frame(
            content,
            background=COLOR_SURFACE,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            padx=14,
            pady=12,
        )
        qr_card.pack(pady=(11, 8))
        self.mobile_qr_image = ImageTk.PhotoImage(
            build_qr_image(access_url, target_size=180)
        )
        Label(
            qr_card,
            image=self.mobile_qr_image,
            background=COLOR_SURFACE,
            borderwidth=0,
        ).pack()

        Label(
            content,
            text=f"Dirección de esta PC: http://{self.mobile_ip}:{self.port}",
            font=("Segoe UI Semibold", 10),
            foreground=COLOR_TEXT,
            background=COLOR_BACKGROUND,
        ).pack()
        Label(
            content,
            text=(
                "La clave segura está incluida en el QR y cambia cada vez. "
                "La dirección sola no permite entrar."
            ),
            font=("Segoe UI", 8),
            foreground=COLOR_MUTED,
            background=COLOR_BACKGROUND,
            justify="center",
            wraplength=455,
        ).pack(pady=(5, 0))

        actions = Frame(content, background=COLOR_BACKGROUND)
        actions.pack(pady=(12, 0))
        copy_button = Button(
            actions,
            text="Copiar enlace",
            command=self.copy_mobile_link,
            font=("Segoe UI Semibold", 9),
            foreground=COLOR_TEXT,
            background=COLOR_SURFACE,
            activebackground=COLOR_SECONDARY_HOVER,
            relief="solid",
            borderwidth=1,
            cursor="hand2",
            padx=15,
            pady=9,
        )
        copy_button.pack(side="left")
        firewall_button = Button(
            actions,
            text="Configurar Firewall",
            command=self.open_firewall_setup,
            font=("Segoe UI Semibold", 9),
            foreground="#FFFFFF",
            background=COLOR_PRIMARY,
            activeforeground="#FFFFFF",
            activebackground=COLOR_PRIMARY_HOVER,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=15,
            pady=10,
        )
        firewall_button.pack(side="left", padx=(10, 0))
        disable_button = Button(
            actions,
            text="Desactivar",
            command=self.deactivate_mobile_access,
            font=("Segoe UI Semibold", 9),
            foreground="#A33C38",
            background=COLOR_BACKGROUND,
            activeforeground="#8D302D",
            activebackground="#F7EAE8",
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=12,
            pady=9,
        )
        disable_button.pack(side="left", padx=(8, 0))

        Label(
            content,
            text=(
                "Si el QR no abre en una PC nueva, usá “Configurar Firewall” "
                "una sola vez y aceptá el permiso de Windows."
            ),
            font=("Segoe UI", 8),
            foreground=COLOR_MUTED,
            background=COLOR_BACKGROUND,
            justify="center",
            wraplength=460,
        ).pack(pady=(10, 0))

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
                f"El sistema sigue abierto porque falló la copia de seguridad:\n\n{exc}",
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

        self.status = StringVar(value="Todo está listo. Presioná “Abrir sistema” para comenzar.")

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
                foreground="#083642",
                background="#52C7C1",
                width=4,
                height=2,
            )
        logo_widget.pack(side="left", padx=(0, 16))

        brand_copy = Frame(brand_row, background=COLOR_PRIMARY)
        brand_copy.pack(side="left", fill="x", expand=True)
        Label(
            brand_copy,
            text="GESTIÓN FINANCIERA · SISTEMA LOCAL",
            font=("Segoe UI Semibold", 9),
            foreground="#A9E2E7",
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
            foreground="#D2E8EB",
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
            text="Sistema listo",
            font=("Segoe UI Semibold", 11),
            foreground=COLOR_TEXT,
            background=COLOR_SURFACE,
        ).pack(side="left")
        Label(
            status_card,
            text=(
                "Tus datos permanecen en este equipo. Abrí el sistema para "
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
            text="Abrir sistema",
            command=self.open_browser,
            font=("Segoe UI Semibold", 10),
            foreground="#FFFFFF",
            background=COLOR_PRIMARY,
            activeforeground="#FFFFFF",
            activebackground=COLOR_PRIMARY_HOVER,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=18,
            pady=11,
        )
        self.open_button.pack(side="left")
        self._add_hover(
            self.open_button,
            normal=COLOR_PRIMARY,
            hover=COLOR_PRIMARY_HOVER,
        )

        self.mobile_button = Button(
            actions,
            text="Usar desde celular",
            command=self.activate_mobile_access,
            font=("Segoe UI Semibold", 9),
            foreground=COLOR_TEXT,
            background=COLOR_BACKGROUND,
            activeforeground=COLOR_TEXT,
            activebackground=COLOR_SECONDARY_HOVER,
            relief="solid",
            borderwidth=1,
            cursor="hand2",
            padx=14,
            pady=11,
        )
        self.mobile_button.pack(side="left", padx=(10, 0))
        self._add_hover(
            self.mobile_button,
            normal=COLOR_BACKGROUND,
            hover=COLOR_SECONDARY_HOVER,
        )

        close_button = Button(
            actions,
            text="Cerrar y respaldar",
            command=self.close_and_backup,
            font=("Segoe UI Semibold", 9),
            foreground=COLOR_TEXT,
            background=COLOR_BACKGROUND,
            activeforeground=COLOR_TEXT,
            activebackground=COLOR_SECONDARY_HOVER,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            padx=10,
            pady=11,
        )
        close_button.pack(side="left", padx=(6, 0))
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
