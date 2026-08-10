from django.conf import settings
from django.urls import include, path, re_path
from django.views.static import serve


def serve_local_media(request, path):
    """Serve user-owned media through the protected local application."""
    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    path("", include("modules.core.urls")),
    re_path(
        r"^media/(?P<path>.*)$",
        serve_local_media,
    ),
]
