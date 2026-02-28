from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.web_urls")),
    path("api/", include("core.urls")),
]

handler404 = "core.views.custom_page_not_found"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()
