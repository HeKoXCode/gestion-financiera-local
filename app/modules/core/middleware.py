from __future__ import annotations

import hashlib
import hmac
import ipaddress
from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

MOBILE_SESSION_KEY = "gestion_mobile_access"


def mobile_token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _is_loopback(remote_address: str) -> bool:
    try:
        return ipaddress.ip_address(remote_address).is_loopback
    except ValueError:
        return False


def has_mobile_access(request) -> bool:
    token = getattr(settings, "GESTION_MOBILE_ACCESS_TOKEN", "")
    saved_digest = request.session.get(MOBILE_SESSION_KEY, "")
    return bool(
        token
        and saved_digest
        and hmac.compare_digest(saved_digest, mobile_token_digest(token))
    )


class MobileAccessMiddleware:
    """Require temporary pairing for every request arriving from another device."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        remote_address = request.META.get("REMOTE_ADDR", "")
        if _is_loopback(remote_address):
            return self.get_response(request)

        pairing_path = reverse("core:mobile_access")
        if request.path == pairing_path:
            return self.get_response(request)

        enabled = getattr(settings, "GESTION_MOBILE_ACCESS_ENABLED", False)
        if enabled and has_mobile_access(request):
            return self.get_response(request)

        query = urlencode({"continuar": request.get_full_path()})
        return redirect(f"{pairing_path}?{query}")
