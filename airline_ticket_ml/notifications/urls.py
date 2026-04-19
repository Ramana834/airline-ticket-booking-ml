from django.urls import path
from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.my_notifications, name="my_notifications"),
    path("check-now/", views.check_now, name="check_now"),
    path("mark-all-read/", views.mark_all_read, name="mark_all_read"),
    path("read/<int:pk>/", views.mark_notification_read, name="read"),
    path("create-alert/", views.create_price_alert, name="create_price_alert"),
    path("unread-count/", views.unread_count, name="unread_count"),
    path("latest/", views.latest_unread, name="latest_unread"),
]