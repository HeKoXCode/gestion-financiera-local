import os

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def check_multiuser_deployment(app_configs, **kwargs):
    if settings.GESTION_DEPLOYMENT_MODE != "multiuser":
        return []

    findings = []
    if not settings.GESTION_AUTH_REQUIRED:
        findings.append(
            Error(
                "El modo multiusuario debe exigir autenticación.",
                id="gestion.E001",
            )
        )
    if settings.DEBUG:
        findings.append(
            Error("DEBUG debe estar desactivado en modo multiusuario.", id="gestion.E002")
        )
    if not getattr(settings, "BEHIND_HTTPS_PROXY", False):
        findings.append(
            Error(
                "El modo multiusuario debe publicarse detrás del proxy HTTPS configurado.",
                id="gestion.E003",
            )
        )
    if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
        findings.append(
            Error(
                "PostgreSQL es obligatorio para el perfil multiusuario soportado.",
                id="gestion.E004",
            )
        )
    if not os.environ.get("DJANGO_SECRET_KEY"):
        findings.append(
            Error(
                "Definí DJANGO_SECRET_KEY fuera del repositorio para el despliegue.",
                id="gestion.E005",
            )
        )
    if not os.environ.get("DJANGO_ALLOWED_HOSTS", "").strip():
        findings.append(
            Error(
                "Definí DJANGO_ALLOWED_HOSTS con el dominio productivo.",
                id="gestion.E006",
            )
        )
    if not settings.CSRF_TRUSTED_ORIGINS:
        findings.append(
            Error(
                "Definí DJANGO_CSRF_TRUSTED_ORIGINS con el origen HTTPS productivo.",
                id="gestion.E007",
            )
        )
    return findings
