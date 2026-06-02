from django.urls import path

from .views import AnalyticsHealthView

app_name = "analytics"

urlpatterns = [
    path("health/", AnalyticsHealthView.as_view(), name="health"),
]
