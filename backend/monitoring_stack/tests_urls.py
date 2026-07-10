"""URL conf for monitoring_stack tests."""

from django.urls import include, path

urlpatterns = [
    path("api/v1/monitoring/", include("monitoring_stack.urls")),
]
