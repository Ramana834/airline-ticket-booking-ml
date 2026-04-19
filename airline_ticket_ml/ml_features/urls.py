from django.urls import path
from . import views

app_name = "ml"   # ✅ namespace name

urlpatterns = [
    path("fare-trend/", views.fare_trend, name="fare_trend"),
    path("recommendations/", views.recommendations, name="recommendations"),
    path("delay/", views.delay_prediction, name="delay"),
    path("assistant/", views.chatbot, name="chatbot"),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
]
