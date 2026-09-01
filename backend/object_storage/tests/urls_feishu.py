from django.urls import path

from accounts.views.management import ManagementUserDetailView
from object_storage.views_auth import (
    FeishuCallbackView,
    FeishuLoginStartView,
    HandoffExchangeView,
)
from object_storage.views_feishu_admin import (
    FeishuSyncConfirmView,
    FeishuSyncPreviewView,
)

urlpatterns = [
    path(
        "api/v1/object-storage/auth/feishu/start/",
        FeishuLoginStartView.as_view(),
    ),
    path(
        "api/v1/object-storage/auth/feishu/callback/",
        FeishuCallbackView.as_view(),
    ),
    path(
        "api/v1/object-storage/auth/handoff/exchange/",
        HandoffExchangeView.as_view(),
    ),
    path(
        "api/v1/object-storage/management/feishu/sync/preview/",
        FeishuSyncPreviewView.as_view(),
    ),
    path(
        "api/v1/object-storage/management/feishu/sync/confirm/",
        FeishuSyncConfirmView.as_view(),
    ),
    path(
        "api/v1/management/users/<int:user_id>/",
        ManagementUserDetailView.as_view(),
    ),
]
