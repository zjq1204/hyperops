"""
Jenkins Trigger URL configuration.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    JenkinsInstanceViewSet,
    TriggerEntryViewSet,
    TriggerRecordViewSet,
    UserNotificationPreferencesView,
    UserTriggerEntriesView,
)

router = DefaultRouter()
router.register(r"instances", JenkinsInstanceViewSet, basename="jenkins-instance")
router.register(r"entries", TriggerEntryViewSet, basename="jenkins-entry")
router.register(r"records", TriggerRecordViewSet, basename="jenkins-record")

urlpatterns = [
    path("", include(router.urls)),
    path("user/entries/", UserTriggerEntriesView.as_view(), name="user-entries"),
    path(
        "user/notification-preferences/",
        UserNotificationPreferencesView.as_view(),
        name="user-notification-preferences",
    ),
]
