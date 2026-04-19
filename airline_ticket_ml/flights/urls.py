from django.urls import path
from . import views

app_name = "flights"

urlpatterns = [
    path("", views.home, name="home"),
    path("results/", views.search_results, name="results"),
    path("ml/", views.flight_list, name="flight_list"),

    # Airport route reference
    path("route/", views.route_reference, name="route_reference"),

    # ✅ Only ONE destination route
    path("destination/<slug:slug>/", views.destination_detail, name="destination_detail"),

    # Voice command parser
    path("voice/parse/", views.voice_parse, name="voice_parse"),
]
