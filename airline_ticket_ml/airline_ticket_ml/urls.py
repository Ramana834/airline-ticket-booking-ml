from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    path("", include(("flights.urls", "flights"), namespace="flights")),
    path("accounts/", include(("users.urls", "users"), namespace="users")),
    path("bookings/", include(("bookings.urls", "bookings"), namespace="bookings")),
    path("ml/", include(("ml_features.urls", "ml"), namespace="ml")),
    path("notifications/", include(("notifications.urls", "notifications"), namespace="notifications")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
