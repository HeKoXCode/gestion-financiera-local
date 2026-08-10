from __future__ import annotations

import ipaddress
import os
import secrets
import socket
from urllib.parse import urlencode

import qrcode
from PIL import Image

LOOPBACK_HOST = "127.0.0.1"
MOBILE_BIND_HOST = "0.0.0.0"
LAN_IP_OVERRIDE_VARIABLE = "GESTION_LAN_IP_OVERRIDE"


def is_usable_lan_address(value: str) -> bool:
    """Accept private LAN addresses and reject loopback or automatic fallback IPs."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return bool(
        address.version == 4
        and address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_unspecified
    )


def detect_lan_ip() -> str | None:
    """Find the address selected by Windows for the current local network."""
    override = os.environ.get(LAN_IP_OVERRIDE_VARIABLE, "").strip()
    if override:
        return override if is_usable_lan_address(override) else None

    candidates: list[str] = []
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # UDP connect chooses a route without sending application data.
        probe.connect(("192.0.2.1", 9))
        candidates.append(probe.getsockname()[0])
    except OSError:
        pass
    finally:
        probe.close()

    try:
        _hostname, _aliases, addresses = socket.gethostbyname_ex(socket.gethostname())
        candidates.extend(addresses)
    except OSError:
        pass

    for candidate in candidates:
        if is_usable_lan_address(candidate):
            return candidate
    return None


def create_mobile_token() -> str:
    """Create an unguessable token that is valid only for the current run."""
    return secrets.token_urlsafe(32)


def build_mobile_access_url(ip_address: str, port: int, token: str) -> str:
    query = urlencode({"clave": token})
    return f"http://{ip_address}:{port}/acceso-celular/?{query}"


def build_qr_image(value: str, *, target_size: int = 230) -> Image.Image:
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1,
        border=4,
    )
    qr.add_data(value)
    qr.make(fit=True)
    module_count = qr.modules_count + (qr.border * 2)
    qr.box_size = max(3, target_size // module_count)
    image = qr.make_image(
        fill_color="#123D31",
        back_color="#FFFFFF",
    ).convert("RGB")
    return image
