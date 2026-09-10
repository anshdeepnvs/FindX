from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

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
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
