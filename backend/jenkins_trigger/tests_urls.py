"""URL conf for jenkins_trigger tests."""

from django.urls import include, path

urlpatterns = [
    path("api/v1/jenkins/", include("jenkins_trigger.urls")),
]
