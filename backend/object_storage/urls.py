from django.urls import path

from object_storage.views import ObjectStorageOverviewView


app_name = "object_storage"

urlpatterns = [
    path("overview/", ObjectStorageOverviewView.as_view(), name="overview"),
]
