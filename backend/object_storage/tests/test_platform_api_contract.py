import inspect

import pytest
from django.urls import get_resolver

pytestmark = pytest.mark.django_db


def test_runtime_api_modules_do_not_import_removed_enterprise_models():
    from object_storage import (
        serializers,
        serializers_admin,
        views_admin,
        views_employee,
    )

    source = "\n".join(
        inspect.getsource(module)
        for module in (serializers, serializers_admin, views_admin, views_employee)
    )
    for removed_name in (
        "StorageTenant",
        "StorageMembership",
        "FeishuAppConfig",
        "StorageApplication",
        "tenant_id",
    ):
        assert removed_name not in source


def test_url_contract_has_no_tenant_or_enterprise_routes(settings):
    settings.ENABLE_OBJECT_STORAGE = True
    routes = [str(pattern.pattern) for pattern in get_resolver().url_patterns]
    object_storage = next(
        pattern
        for pattern in get_resolver().url_patterns
        if "object-storage" in str(pattern.pattern)
    )
    nested = [str(pattern.pattern) for pattern in object_storage.url_patterns]

    assert routes
    assert all("tenant" not in route and "enterprise" not in route for route in nested)
    assert "workspace/overview/" in nested
    assert "management/settings/" in nested


def test_every_platform_api_mutation_view_requires_idempotency_mixin():
    from object_storage.permissions import RequireIdempotencyKeyMixin
    from object_storage.urls import urlpatterns

    exempt_names = {
        "feishu_login_start",
        "feishu_callback",
        "handoff_exchange",
    }
    for pattern in urlpatterns:
        callback = pattern.callback
        view_class = getattr(callback, "view_class", None)
        if view_class is None or pattern.name in exempt_names:
            continue
        methods = {
            method
            for method in ("post", "put", "patch", "delete")
            if hasattr(view_class, method)
        }
        if methods:
            assert issubclass(view_class, RequireIdempotencyKeyMixin), pattern.name
