from django.urls import path

from object_storage.views import ObjectStorageOverviewView
from object_storage.views_auth import (
    FeishuCallbackView,
    FeishuLoginStartView,
    HandoffExchangeView,
)
from object_storage.views_admin import (
    FeishuAppConfigView,
    FeishuAppValidationView,
    StorageResourcePoolDetailView,
    StorageResourcePoolListCreateView,
    StorageResourcePoolValidationView,
    StorageTenantDetailView,
    StorageTenantListCreateView,
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
    path(
        "management/tenants/",
        StorageTenantListCreateView.as_view(),
        name="management_tenants",
    ),
    path(
        "management/tenants/<int:tenant_id>/",
        StorageTenantDetailView.as_view(),
        name="management_tenant_detail",
    ),
    path(
        "management/tenants/<int:tenant_id>/feishu/",
        FeishuAppConfigView.as_view(),
        name="management_feishu_config",
    ),
    path(
        "management/tenants/<int:tenant_id>/feishu/validate/",
        FeishuAppValidationView.as_view(),
        name="management_feishu_validate",
    ),
    path(
        "management/tenants/<int:tenant_id>/resource-pools/",
        StorageResourcePoolListCreateView.as_view(),
        name="management_resource_pools",
    ),
    path(
        "management/resource-pools/<int:pool_id>/",
        StorageResourcePoolDetailView.as_view(),
        name="management_resource_pool_detail",
    ),
    path(
        "management/resource-pools/<int:pool_id>/validate/",
        StorageResourcePoolValidationView.as_view(),
        name="management_resource_pool_validate",
    ),
]
