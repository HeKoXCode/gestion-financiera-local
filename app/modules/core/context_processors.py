from modules.core.models import BusinessSettings


def application_settings(request):
    return {"app_settings": BusinessSettings.get_solo()}

