from urllib.parse import parse_qs, urlparse

import pytest
from django.core.cache import cache
from accounts.access import get_access_profile

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def feishu_auth_settings(settings):
    settings.ROOT_URLCONF = "object_storage.tests.urls_feishu"
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
def feishu_config(db):
    from django.contrib.auth.models import Group

    from accounts.models import Role
    from object_storage.models import PlatformFeishuConfig

    group = Group.objects.create(name="Feishu Users")
    role = Role.objects.create(
        name="Feishu Workspace",
        visible_features=["workspace_dashboard", "object_storage"],
    )
    group.platform_roles.add(role)
    return PlatformFeishuConfig.objects.create(
        singleton_key="default",
        app_id="cli_test_app",
        app_secret_encrypted="encrypted-feishu-secret",
        oauth_callback_url="https://hyperops.example.com/feishu/callback",
        access_group=group,
        validation_status=PlatformFeishuConfig.ValidationStatus.VALID,
        enabled=True,
    )


class FakeFeishuClient:
    def __init__(self, identity):
        self.identity = identity

    def build_authorization_url(self, *, app_id, state, callback_url):
        assert app_id
        assert callback_url
        return f"https://open.feishu.cn/auth?state={state}"

    def authenticate(self, *, code, app_config):
        assert code == "valid-code"
        assert app_config.singleton_key == "default"
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
        "status_reason": "",
    }
    values.update(overrides)
    return FeishuIdentity(**values)


def _payload(response):
    body = response.json()
    return body.get("data", body)


def _start_login(client, **payload):
    response = client.post(
        "/api/v1/object-storage/auth/feishu/start/",
        payload,
        content_type="application/json",
    )
    state = None
    if response.status_code == 200:
        state = parse_qs(urlparse(_payload(response)["authorization_url"]).query)[
            "state"
        ][0]
    return response, state


def _complete_callback(client, state, code="valid-code"):
    return client.get(
        "/api/v1/object-storage/auth/feishu/callback/",
        {"state": state, "code": code},
    )


def test_login_start_is_platform_singleton_and_rejects_tenant_input(
    client, feishu_config
):
    response, state = _start_login(client, tenant_code="legacy-tenant")

    assert response.status_code == 400
    assert _payload(response)["error_code"] == "TENANT_SCOPE_UNSUPPORTED"
    assert state is None

    response, state = _start_login(client)

    assert response.status_code == 200
    assert state
    assert response["Cache-Control"] == "no-store"


def test_oauth_state_is_short_lived_single_use_and_bound_to_config(
    client, feishu_config, monkeypatch
):
    from object_storage import views_auth
    from object_storage.services.identity import _cache_key

    monkeypatch.setattr(
        views_auth,
        "get_feishu_client",
        lambda: FakeFeishuClient(_identity()),
    )
    _, state = _start_login(client)
    cached = cache.get(_cache_key("oauth-state", state))

    assert cached["config_id"] == feishu_config.id
    assert cached["nonce"]

    first = _complete_callback(client, state)
    reused = _complete_callback(client, state)
    cache.delete(_cache_key("oauth-state", state))
    expired = _complete_callback(client, state)

    assert first.status_code == 200
    assert reused.status_code == 400
    assert expired.status_code == 400
    assert _payload(reused)["error_code"] == "FEISHU_STATE_INVALID"
    assert _payload(expired)["error_code"] == "FEISHU_STATE_INVALID"
    assert reused["Cache-Control"] == "no-store"


def test_first_login_creates_only_unusable_local_user_and_feishu_identity(
    client, feishu_config, django_user_model, monkeypatch
):
    from object_storage import views_auth
    from object_storage.models import (
        AccessKey,
        Bucket,
        CloudIdentity,
        FeishuIdentity,
    )

    monkeypatch.setattr(
        views_auth,
        "get_feishu_client",
        lambda: FakeFeishuClient(_identity()),
    )
    before_users = django_user_model.objects.count()

    _, state = _start_login(client)
    response = _complete_callback(client, state)

    assert response.status_code == 200
    identity = FeishuIdentity.objects.get(open_id="ou_employee_1")
    identity.user.refresh_from_db()
    assert django_user_model.objects.count() == before_users + 1
    assert identity.user.has_usable_password() is False
    assert identity.user.is_staff is False
    assert identity.user.is_superuser is False
    assert identity.user.groups.filter(pk=feishu_config.access_group_id).exists()
    assert not identity.user.platform_roles.exists()
    assert get_access_profile(identity.user)["visible_features"] == [
        "workspace_dashboard",
        "object_storage",
    ]
    assert CloudIdentity.objects.count() == 0
    assert Bucket.objects.count() == 0
    assert AccessKey.objects.count() == 0


def test_repeated_open_id_reuses_identity_and_does_not_merge_by_email(
    client, feishu_config, django_user_model, monkeypatch
):
    from object_storage import views_auth
    from object_storage.models import FeishuIdentity

    existing_local = django_user_model.objects.create_user(
        username="local-employee",
        email="employee@example.com",
    )
    monkeypatch.setattr(
        views_auth,
        "get_feishu_client",
        lambda: FakeFeishuClient(_identity()),
    )

    _, first_state = _start_login(client)
    first = _complete_callback(client, first_state)
    _, second_state = _start_login(client)
    second = _complete_callback(client, second_state)

    assert first.status_code == 200
    assert second.status_code == 200
    assert FeishuIdentity.objects.count() == 1
    identity = FeishuIdentity.objects.get()
    assert identity.user_id != existing_local.id
    assert django_user_model.objects.count() == 2


@pytest.mark.parametrize(
    ("status_reason", "expected_code"),
    [
        ("outside_scope", "FEISHU_IDENTITY_OUTSIDE_SCOPE"),
        ("deactivated", "FEISHU_IDENTITY_DEACTIVATED"),
        ("deleted", "FEISHU_IDENTITY_DELETED"),
    ],
)
def test_login_rejects_ineligible_identity_with_distinct_reason(
    client, feishu_config, monkeypatch, status_reason, expected_code
):
    from object_storage import views_auth

    monkeypatch.setattr(
        views_auth,
        "get_feishu_client",
        lambda: FakeFeishuClient(
            _identity(
                is_active=status_reason not in {"deactivated", "deleted"},
                is_eligible=status_reason == "",
                status_reason=status_reason,
            )
        ),
    )

    _, state = _start_login(client)
    response = _complete_callback(client, state)

    assert response.status_code == 403
    assert _payload(response)["error_code"] == expected_code
    assert response["Cache-Control"] == "no-store"


def test_disabled_or_invalid_singleton_blocks_login_start(client, feishu_config):
    feishu_config.enabled = False
    feishu_config.save(update_fields=("enabled",))

    response, _ = _start_login(client)

    assert response.status_code == 404
    assert _payload(response)["error_code"] == "FEISHU_LOGIN_UNAVAILABLE"
    assert response["Cache-Control"] == "no-store"


def test_login_callback_rejects_tenant_query_parameter(client, feishu_config):
    response = client.get(
        "/api/v1/object-storage/auth/feishu/callback/",
        {"tenant_id": "42", "state": "state", "code": "valid-code"},
    )

    assert response.status_code == 400
    assert _payload(response)["error_code"] == "TENANT_SCOPE_UNSUPPORTED"
    assert response["Cache-Control"] == "no-store"


def test_handoff_exchange_is_single_use_and_no_store(
    client, feishu_config, monkeypatch
):
    from object_storage import views_auth

    monkeypatch.setattr(
        views_auth,
        "get_feishu_client",
        lambda: FakeFeishuClient(_identity()),
    )
    _, state = _start_login(client)
    callback = _complete_callback(client, state)
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
    assert first["Cache-Control"] == "no-store"
    assert reused.status_code == 400
    assert _payload(reused)["error_code"] == "HANDOFF_CODE_INVALID"
    assert reused["Cache-Control"] == "no-store"


def test_management_role_updates_preserve_feishu_group_inheritance(
    client, feishu_config, django_user_model, monkeypatch
):
    from accounts.models import Role
    from object_storage import views_auth
    from object_storage.models import FeishuIdentity

    monkeypatch.setattr(
        views_auth,
        "get_feishu_client",
        lambda: FakeFeishuClient(_identity()),
    )
    _, state = _start_login(client)
    assert _complete_callback(client, state).status_code == 200
    feishu_user = FeishuIdentity.objects.get().user
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

    response = client.patch(
        f"/api/v1/management/users/{feishu_user.id}/",
        {"role_ids": [regular_role.id]},
        content_type="application/json",
    )

    feishu_user.refresh_from_db()
    assert response.status_code == 200
    assert feishu_user.groups.filter(pk=feishu_config.access_group_id).exists()
    assert set(feishu_user.platform_roles.values_list("pk", flat=True)) == {
        regular_role.id
    }
    assert get_access_profile(feishu_user)["visible_features"] == [
        "workspace_dashboard",
        "object_storage",
    ]
