from django.conf import settings
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.static import serve


def serve_local_media(request, path):
    """Serve user-owned media through the protected local application."""
    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    path(
        "cuenta/ingresar/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("cuenta/salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("modules.core.urls")),
    re_path(
        r"^media/(?P<path>.*)$",
        serve_local_media,
    ),
]
