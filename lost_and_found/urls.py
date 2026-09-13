from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import serve_media

urlpatterns = [
    path("admin/", admin.site.urls),
    path("",         include("core.urls")),
    path("accounts/",      include("accounts.urls")),
    path("items/",         include("items.urls")),
    path("matching/",      include("matching.urls")),
    path("claims/",        include("claims.urls")),
    path("chat/",          include("chat.urls")),
    path("notifications/", include("notifications.urls")),
    path("panel/",         include("panel.urls")),
    # Serve media files directly from Database / Disk cache in both dev and production
    path("media/<path:path>", serve_media, name="serve_media"),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])

