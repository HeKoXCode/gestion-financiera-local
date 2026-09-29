from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import threading
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse

logger = logging.getLogger(__name__)

MOBILE_SESSION_KEY = "gestion_mobile_access"
_WRITE_LOCK = threading.RLock()
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class LocalDataSafetyMiddleware:
    """Serialize writes to SQLite and prevent stale dynamic pages in the browser."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in _SAFE_METHODS or getattr(
            settings, "GESTION_DATABASE_ENGINE", "sqlite"
        ) != "sqlite":
            response = self.get_response(request)
        else:
            # The portable application uses one SQLite database.  Chrome tabs and
            # the optional phone view can submit at the same time, so only one
            # mutating request may enter the database workflow at once.
            with _WRITE_LOCK:
                response = self.get_response(request)

        content_type = response.get("Content-Type", "")
        if content_type.startswith("text/html"):
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
        return response


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
        token and saved_digest and hmac.compare_digest(saved_digest, mobile_token_digest(token))
    )


class MobileAccessMiddleware:
    """Require temporary pairing for every request arriving from another device."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "GESTION_DEPLOYMENT_MODE", "local") == "multiuser":
            return self.get_response(request)

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


ADMIN_GROUP = "Administradores"
COLLECTOR_GROUP = "Cobradores"
AUTH_EXEMPT_VIEWS = {"login", "logout", "core:health", "core:mobile_access"}
ADMIN_ONLY_VIEWS = {
    "core:audit_events",
    "core:backup_create",
    "core:backup_download",
    "core:collector_toggle",
    "core:configuration",
    "core:customer_create",
    "core:customer_delete",
    "core:customer_edit",
    "core:customer_revision_detail",
    "core:customer_toggle",
    "core:data_export_create",
    "core:data_export_download",
    "core:data_management",
    "core:late_fee_pause",
    "core:late_fee_resume",
    "core:product_create",
    "core:product_edit",
    "core:product_toggle",
    "core:reporting_export_create",
    "core:sale_cancel",
    "core:sale_create",
    "core:sale_edit",
    "core:sale_revision_detail",
    "core:secure_archive",
    "core:payment_void",
}
ADMIN_MUTATING_VIEWS = {
    "core:collection_routes",
}


def user_role(user) -> str | None:
    if not getattr(user, "is_authenticated", False):
        return None
    if user.is_superuser or user.groups.filter(name=ADMIN_GROUP).exists():
        return "admin"
    if user.groups.filter(name=COLLECTOR_GROUP).exists():
        return "collector"
    return None


class RoleAccessMiddleware:
    """Apply the opt-in multi-user access matrix without changing local mode."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "GESTION_AUTH_REQUIRED", False):
            return self.get_response(request)

        try:
            match = resolve(request.path_info)
            view_name = match.view_name
        except Resolver404:
            return self.get_response(request)

        if view_name in AUTH_EXEMPT_VIEWS:
            return self.get_response(request)
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)

        role = user_role(request.user)
        admin_mutation = (
            request.method not in _SAFE_METHODS and view_name in ADMIN_MUTATING_VIEWS
        )
        if role is None or (
            role != "admin" and (view_name in ADMIN_ONLY_VIEWS or admin_mutation)
        ):
            raise PermissionDenied("Tu rol no permite realizar esta operación.")
        return self.get_response(request)


class AuditTrailMiddleware:
    """Persist one append-only event for each successful mutating HTTP request."""

    MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method not in self.MUTATING_METHODS or response.status_code >= 400:
            return response

        try:
            from modules.core.models import AuditEvent

            match = getattr(request, "resolver_match", None)
            actor = request.user if getattr(request.user, "is_authenticated", False) else None
            AuditEvent.objects.create(
                actor=actor,
                action=match.view_name if match else request.path,
                path=request.path[:500],
                method=request.method,
                status_code=response.status_code,
                remote_address=request.META.get("REMOTE_ADDR") or None,
                metadata={
                    "deployment_mode": getattr(settings, "GESTION_DEPLOYMENT_MODE", "local"),
                },
            )
        except Exception:
            logger.exception("No se pudo registrar el evento de auditoría.")
        return response
