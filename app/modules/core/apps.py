from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.core"

    def ready(self) -> None:
        from . import (
            checks,  # noqa: F401
            signals,  # noqa: F401
        )
