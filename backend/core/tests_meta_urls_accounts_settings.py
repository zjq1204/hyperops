"""URL hook for PlatformMetaView test under accounts.tests.settings."""

from django.urls import path

from .views import PlatformMetaView


urlpatterns = [
    path("", PlatformMetaView.as_view(), name="platform_meta_test"),
]
