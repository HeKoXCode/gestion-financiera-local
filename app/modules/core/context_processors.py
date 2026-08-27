from django.conf import settings

from modules.core.middleware import user_role
from modules.core.models import BusinessSettings


def application_settings(request):
    return {
        "app_settings": BusinessSettings.get_solo(),
        "deployment_mode": settings.GESTION_DEPLOYMENT_MODE,
        "auth_required": settings.GESTION_AUTH_REQUIRED,
        "current_role": user_role(getattr(request, "user", None)),
    }
