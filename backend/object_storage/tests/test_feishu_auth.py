from urllib.parse import parse_qs, urlparse

import pytest
from django.core.cache import cache

from accounts.access import get_access_profile

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_auth_cache(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "object-storage-auth-tests",
        }
    }
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def enabled_feishu_tenant(storage_tenant_factory):
    from object_storage.models import FeishuAppConfig

    tenant = storage_tenant_factory(enabled=True)
    FeishuAppConfig.objects.create(
        tenant=tenant,
        app_id="cli_test_app",
        app_secret_encrypted="encrypted-feishu-secret",
        oauth_callback_url="https://hyperops.example.com/feishu/callback",
        validation_status=FeishuAppConfig.ValidationStatus.VALID,
        enabled=True,
    )
    return tenant


class FakeFeishuClient:
    def __init__(self, identity):
        self.identity = identity

    def build_authorization_url(self, *, app_id, state, callback_url):
        assert app_id
        return f"https://open.feishu.cn/auth?state={state}"

    def authenticate(self, *, code, app_config):
        assert code == "valid-code"
        return self.identity


def _identity(**overrides):
    from object_storage.feishu import FeishuIdentity

    values = {
        "open_id": "ou_employee_1",
        "union_id": "on_employee_1",
        "display_name": "Employee One",
        "email": "employee@example.com",
        "department_ids": ("department-1",),
        "is_active": True,
        "is_eligible": True,
    }
    values.update(overrides)
    return FeishuIdentity(**values)


def _payload(response):
    body = response.json()
    return body.get("data", body)


def _start_login(client, tenant):
    response = client.post(
        "/api/v1/object-storage/auth/feishu/start/",
        {"tenant_code": tenant.code},
        content_type="application/json",
    )
    assert response.status_code == 200
    authorization_url = _payload(response)["authorization_url"]
    return parse_qs(urlparse(authorization_url).query)["state"][0]


def _complete_callback(client, state):
    return client.get(
        "/api/v1/object-storage/auth/feishu/callback/",
        {"state": state, "code": "valid-code"},
    )


def test_feishu_callback_rejects_unknown_reused_and_expired_state(
    client, enabled_feishu_tenant, monkeypatch
):
    from object_storage import views_auth
    from object_storage.services.tenant import _cache_key

    monkeypatch.setattr(
        views_auth,
        "get_feishu_client",
        lambda: FakeFeishuClient(_identity()),
    )
    unknown = _complete_callback(client, "unknown-state")
    state = _start_login(client, enabled_feishu_tenant)
    first = _complete_callback(client, state)
    reused = _complete_callback(client, state)
    expired_state = _start_login(client, enabled_feishu_tenant)
    cache.delete(_cache_key("oauth-state", expired_state))
    expired = _complete_callback(client, expired_state)

    assert unknown.status_code == 400
    assert _payload(unknown)["error_code"] == "FEISHU_STATE_INVALID"
    assert first.status_code == 200
    assert reused.status_code == 400
    assert _payload(reused)["error_code"] == "FEISHU_STATE_INVALID"
    assert expired.status_code == 400
    assert _payload(expired)["error_code"] == "FEISHU_STATE_INVALID"


def test_feishu_callback_creates_one_unusable_password_user(
    client, enabled_feishu_tenant, monkeypatch
):
    from object_storage import views_auth
    from object_storage.models import StorageMembership

    monkeypatch.setattr(
        views_auth,
        "get_feishu_client",
        lambda: FakeFeishuClient(_identity()),
    )
    state = _start_login(client, enabled_feishu_tenant)

    response = _complete_callback(client, state)

    assert response.status_code == 200
    assert "handoff_code" in _payload(response)
    membership = StorageMembership.objects.get(
        tenant=enabled_feishu_tenant,
        feishu_open_id="ou_employee_1",
    )
    assert membership.user.has_usable_password() is False
    assert membership.user.is_staff is False
    assert membership.user.is_superuser is False
    role = membership.user.platform_roles.get()
    assert role.name == "Object Storage User"
    assert role.is_system is True
    access = get_access_profile(membership.user)
    assert access["visible_features"] == ["object_storage"]


def test_same_tenant_and_open_id_is_idempotent(
    client, enabled_feishu_tenant, monkeypatch
):
    from object_storage import views_auth
    from object_storage.models import StorageMembership

    monkeypatch.setattr(
        views_auth,
        "get_feishu_client",
        lambda: FakeFeishuClient(_identity()),
    )
    first = _complete_callback(client, _start_login(client, enabled_feishu_tenant))
    second = _complete_callback(client, _start_login(client, enabled_feishu_tenant))

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        StorageMembership.objects.filter(
            tenant=enabled_feishu_tenant,
            feishu_open_id="ou_employee_1",
        ).count()
        == 1
    )


def test_same_open_id_in_another_tenant_creates_a_distinct_user(
    client, storage_tenant_factory, monkeypatch
):
    from object_storage import views_auth
    from object_storage.models import FeishuAppConfig, StorageMembership

    tenants = [storage_tenant_factory(code=f"tenant-{index}") for index in (1, 2)]
    for index, tenant in enumerate(tenants, start=1):
        FeishuAppConfig.objects.create(
            tenant=tenant,
            app_id=f"app-{index}",
            app_secret_encrypted="encrypted",
            oauth_callback_url=f"https://example.com/callback/{index}",
            validation_status=FeishuAppConfig.ValidationStatus.VALID,
            enabled=True,
        )
    monkeypatch.setattr(
        views_auth,
        "get_feishu_client",
        lambda: FakeFeishuClient(_identity()),
    )

    for tenant in tenants:
        response = _complete_callback(client, _start_login(client, tenant))
        assert response.status_code == 200

    memberships = StorageMembership.objects.filter(feishu_open_id="ou_employee_1")
    assert memberships.count() == 2
    assert len({membership.user_id for membership in memberships}) == 2


def test_feishu_name_email_never_merges_existing_local_user(
    client, enabled_feishu_tenant, django_user_model, monkeypatch
):
    from object_storage import views_auth
    from object_storage.models import StorageMembership

    existing = django_user_model.objects.create_user(
        username="Employee One",
        email="employee@example.com",
    )
    monkeypatch.setattr(
        views_auth,
        "get_feishu_client",
        lambda: FakeFeishuClient(_identity()),
    )

    response = _complete_callback(client, _start_login(client, enabled_feishu_tenant))

    assert response.status_code == 200
    membership = StorageMembership.objects.get(tenant=enabled_feishu_tenant)
    assert membership.user_id != existing.id


@pytest.mark.parametrize("disabled_part", ["tenant", "app"])
def test_disabled_tenant_or_app_rejects_login(
    client, enabled_feishu_tenant, disabled_part
):
    if disabled_part == "tenant":
        enabled_feishu_tenant.enabled = False
        enabled_feishu_tenant.save(update_fields=("enabled",))
    else:
        config = enabled_feishu_tenant.feishu_app_config
        config.enabled = False
        config.save(update_fields=("enabled",))

    response = client.post(
        "/api/v1/object-storage/auth/feishu/start/",
        {"tenant_code": enabled_feishu_tenant.code},
        content_type="application/json",
    )

    assert response.status_code == 404
    assert _payload(response)["error_code"] == "FEISHU_LOGIN_UNAVAILABLE"


def test_inactive_or_ineligible_feishu_identity_is_rejected(
    client, enabled_feishu_tenant, monkeypatch
):
    from object_storage import views_auth

    monkeypatch.setattr(
        views_auth,
        "get_feishu_client",
        lambda: FakeFeishuClient(_identity(is_active=False)),
    )

    response = _complete_callback(client, _start_login(client, enabled_feishu_tenant))

    assert response.status_code == 403
    assert _payload(response)["error_code"] == "FEISHU_IDENTITY_INELIGIBLE"


def test_handoff_code_is_single_use_and_returns_normal_jwt_response(
    client, enabled_feishu_tenant, monkeypatch
):
    from object_storage import views_auth

    monkeypatch.setattr(
        views_auth,
        "get_feishu_client",
        lambda: FakeFeishuClient(_identity()),
    )
    callback = _complete_callback(client, _start_login(client, enabled_feishu_tenant))
    handoff_code = _payload(callback)["handoff_code"]

    first = client.post(
        "/api/v1/object-storage/auth/handoff/exchange/",
        {"handoff_code": handoff_code},
        content_type="application/json",
    )
    reused = client.post(
        "/api/v1/object-storage/auth/handoff/exchange/",
        {"handoff_code": handoff_code},
        content_type="application/json",
    )

    assert first.status_code == 200
    assert set(_payload(first)) == {"access", "refresh", "user"}
    assert reused.status_code == 400
    assert _payload(reused)["error_code"] == "HANDOFF_CODE_INVALID"


def test_system_role_is_hidden_and_preserved_by_management_role_updates(
    client,
    enabled_feishu_tenant,
    django_user_model,
    monkeypatch,
):
    from accounts.models import Role
    from object_storage import views_auth
    from object_storage.models import StorageMembership

    monkeypatch.setattr(
        views_auth,
        "get_feishu_client",
        lambda: FakeFeishuClient(_identity()),
    )
    _complete_callback(client, _start_login(client, enabled_feishu_tenant))
    storage_user = StorageMembership.objects.get(tenant=enabled_feishu_tenant).user
    regular_role = Role.objects.create(
        name="Regular Workspace Role",
        visible_features=["workspace_dashboard"],
    )
    administrator = django_user_model.objects.create_superuser(
        username="role-administrator",
        email="admin@example.com",
        password="secret123",
    )
    client.force_login(administrator)

    role_list = client.get("/api/v1/management/roles/")
    update = client.patch(
        f"/api/v1/management/users/{storage_user.id}/",
        {"role_ids": [regular_role.id]},
        content_type="application/json",
    )

    assert role_list.status_code == 200
    listed_names = {role["name"] for role in _payload(role_list).get("results", [])}
    assert "Object Storage User" not in listed_names
    assert update.status_code == 200
    assert set(storage_user.platform_roles.values_list("name", flat=True)) == {
        "Object Storage User",
        "Regular Workspace Role",
    }
