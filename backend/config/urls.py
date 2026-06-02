from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "PartBridge administration"
admin.site.site_title = "PartBridge admin"
admin.site.index_title = "Operations"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("accounts.urls")),
    path("api/v1/", include("vehicles.urls")),
    path("api/v1/", include("messaging.urls")),
    path("api/v1/", include("orders.urls")),
    path("api/v1/analytics/", include("analytics.urls")),
    path("api/catalog/", include("catalog.urls")),
    path("api/parts/", include("parts.urls")),
    path("api/bundles/", include("bundles.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
