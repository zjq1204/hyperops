from django.urls import path

from object_storage.views import ObjectStorageOverviewView
from object_storage.views_auth import (
    FeishuCallbackView,
    FeishuLoginStartView,
    HandoffExchangeView,
)


app_name = "object_storage"

urlpatterns = [
    path("overview/", ObjectStorageOverviewView.as_view(), name="overview"),
    path(
        "auth/feishu/start/",
        FeishuLoginStartView.as_view(),
        name="feishu_login_start",
    ),
    path(
        "auth/feishu/callback/",
        FeishuCallbackView.as_view(),
        name="feishu_callback",
    ),
    path(
        "auth/handoff/exchange/",
        HandoffExchangeView.as_view(),
        name="handoff_exchange",
    ),
]
