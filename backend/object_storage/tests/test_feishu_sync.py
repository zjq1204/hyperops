import pytest
from django.core.cache import cache

pytestmark = pytest.mark.django_db


class FakeFeishuSyncClient:
    def __init__(self, identities=None, error=None):
        self.identities = identities or []
        self.error = error

    def list_visible_users(self, *, app_config):
        assert app_config.singleton_key == "default"
        if self.error:
            raise self.error
        return list(self.identities)


def _identity(open_id, **overrides):
    from object_storage.feishu import FeishuIdentity

    values = {
        "open_id": open_id,
        "union_id": f"union-{open_id}",
        "display_name": f"User {open_id}",
        "email": f"{open_id}@example.com",
        "department_ids": ("department-1",),
        "is_active": True,
        "is_eligible": True,
        "status_reason": "",
    }
    values.update(overrides)
    return FeishuIdentity(**values)


@pytest.fixture(autouse=True)
def feishu_sync_settings(settings):
    settings.ROOT_URLCONF = "object_storage.tests.urls_feishu"
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "object-storage-sync-tests",
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


@pytest.fixture
def platform_admin(django_user_model):
    from accounts.models import Role

    user = django_user_model.objects.create_user(
        username="platform-admin",
        email="platform-admin@example.com",
        password="secret123",
    )
    role = Role.objects.create(
        name="Object Storage Platform Administrator",
        visible_features=["admin_object_storage"],
    )
    user.platform_roles.add(role)
    return user


def _payload(response):
    body = response.json()
    return body.get("data", body)


def _preview(client, monkeypatch, identities=None, error=None):
    from object_storage import views_feishu_admin

    monkeypatch.setattr(
        views_feishu_admin,
        "get_feishu_client",
        lambda: FakeFeishuSyncClient(identities, error=error),
    )
    return client.post(
        "/api/v1/object-storage/management/feishu/sync/preview/",
        {},
        content_type="application/json",
    )


def test_preview_requires_existing_platform_admin(
    client, feishu_config, django_user_model
):
    ordinary_user = django_user_model.objects.create_user(username="ordinary-user")
    client.force_login(ordinary_user)

    response = client.post(
        "/api/v1/object-storage/management/feishu/sync/preview/",
        {},
        content_type="application/json",
    )

    assert response.status_code == 403


def test_preview_reports_new_remote_and_eligible_counts(
    client, feishu_config, platform_admin, feishu_identity_factory, monkeypatch
):
    existing = feishu_identity_factory(open_id="ou_existing")
    client.force_login(platform_admin)

    response = _preview(
        client,
        monkeypatch,
        identities=[
            _identity("ou_new"),
            _identity("ou_existing", display_name="Updated Existing"),
            _identity(
                "ou_deactivated",
                is_active=False,
                is_eligible=False,
                status_reason="deactivated",
            ),
        ],
    )

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["new_remote"] == 2
    assert payload["eligible_count"] == 2
    statuses = {row["open_id"]: row["status"] for row in payload["items"]}
    assert statuses == {
        "ou_new": "new_remote",
        "ou_existing": "eligible",
        "ou_deactivated": "deactivated",
    }
    assert existing.user.feishu_identity.open_id == "ou_existing"


def test_confirm_only_updates_existing_identities_and_marks_missing_outside_scope(
    client,
    feishu_config,
    platform_admin,
    feishu_identity_factory,
    django_user_model,
    monkeypatch,
):
    existing = feishu_identity_factory(
        open_id="ou_existing",
        display_name="Old Name",
        profile_snapshot={"email": "old@example.com"},
    )
    missing = feishu_identity_factory(open_id="ou_missing")
    deactivated = feishu_identity_factory(open_id="ou_deactivated")
    feishu_config.access_group.user_set.add(
        existing.user, missing.user, deactivated.user
    )
    client.force_login(platform_admin)
    preview = _preview(
        client,
        monkeypatch,
        identities=[
            _identity("ou_existing", display_name="New Name"),
            _identity("ou_new"),
            _identity(
                "ou_deactivated",
                is_active=False,
                is_eligible=False,
                status_reason="deleted",
            ),
        ],
    )
    token = _payload(preview)["confirmation_token"]
    user_count = django_user_model.objects.count()
    identity_count = type(existing).objects.count()

    missing_confirmation_key = client.post(
        "/api/v1/object-storage/management/feishu/sync/confirm/",
        {"confirmation_token": token},
        content_type="application/json",
    )
    response = client.post(
        "/api/v1/object-storage/management/feishu/sync/confirm/",
        {"confirmation_token": token, "idempotency_key": "sync-1"},
        content_type="application/json",
    )

    existing.refresh_from_db()
    missing.refresh_from_db()
    deactivated.refresh_from_db()
    assert missing_confirmation_key.status_code == 400
    assert _payload(missing_confirmation_key)["error_code"] == (
        "IDEMPOTENCY_KEY_REQUIRED"
    )
    assert response.status_code == 200
    assert _payload(response)["updated_count"] == 1
    assert _payload(response)["deactivated_count"] == 1
    assert _payload(response)["skipped_new_remote"] == 1
    assert django_user_model.objects.count() == user_count
    assert type(existing).objects.count() == identity_count
    assert existing.display_name == "New Name"
    assert missing.is_active is False
    assert missing.profile_snapshot["risk_marker"]["reason"] == "outside_scope"
    assert deactivated.profile_snapshot["risk_marker"]["reason"] == "deleted"
    assert deactivated.is_active is False
    assert missing.user.is_active is True
    assert existing.user.groups.filter(pk=feishu_config.access_group_id).exists()
    assert not missing.user.groups.filter(pk=feishu_config.access_group_id).exists()
    assert not deactivated.user.groups.filter(pk=feishu_config.access_group_id).exists()


def test_contacts_client_uses_paginated_visible_user_contract(monkeypatch):
    from object_storage.feishu import FeishuClient

    client = FeishuClient()
    monkeypatch.setattr(client, "_tenant_token", lambda _config: "tenant-token")
    calls = []

    def request_json(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if len(calls) == 1:
            return {
                "data": {
                    "items": [
                        {
                            "open_id": "ou_first",
                            "name": "First User",
                            "status": {"is_activated": True},
                        }
                    ],
                    "has_more": True,
                    "page_token": "next-page",
                }
            }
        return {
            "data": {
                "items": [
                    {
                        "open_id": "ou_second",
                        "name": "Second User",
                        "status": {"is_resigned": True},
                    }
                ],
                "has_more": False,
            }
        }

    monkeypatch.setattr(client, "_request_json", request_json)

    identities = client.list_visible_users(app_config=object())

    assert [identity.open_id for identity in identities] == [
        "ou_first",
        "ou_second",
    ]
    assert identities[1].status_reason == "deactivated"
    assert calls[0][2]["params"] == {
        "department_id": "0",
        "department_id_type": "open_department_id",
        "user_id_type": "open_id",
        "page_size": 50,
    }
    assert calls[1][2]["params"]["page_token"] == "next-page"


def test_contacts_client_maps_invalid_pagination_to_stable_error(monkeypatch):
    from object_storage.feishu import FeishuClient, FeishuProviderError

    client = FeishuClient()
    monkeypatch.setattr(client, "_tenant_token", lambda _config: "tenant-token")
    monkeypatch.setattr(
        client,
        "_request_json",
        lambda *args, **kwargs: {
            "data": {"items": [], "has_more": True, "page_token": ""}
        },
    )

    with pytest.raises(FeishuProviderError) as exc_info:
        client.list_visible_users(app_config=object())

    assert exc_info.value.error_code == "FEISHU_CONTACTS_RESPONSE_INVALID"


def test_confirm_token_is_single_use_and_idempotency_is_required(
    client, feishu_config, platform_admin, monkeypatch
):
    client.force_login(platform_admin)
    preview = _preview(client, monkeypatch, identities=[])
    token = _payload(preview)["confirmation_token"]

    first = client.post(
        "/api/v1/object-storage/management/feishu/sync/confirm/",
        {"confirmation_token": token, "idempotency_key": "sync-replay"},
        content_type="application/json",
    )
    replay = client.post(
        "/api/v1/object-storage/management/feishu/sync/confirm/",
        {"confirmation_token": token, "idempotency_key": "sync-replay-2"},
        content_type="application/json",
    )

    assert first.status_code == 200
    assert replay.status_code == 400
    assert _payload(replay)["error_code"] == "FEISHU_CONFIRMATION_INVALID"


def test_provider_failure_keeps_local_state_and_writes_failed_audit(
    client, feishu_config, platform_admin, feishu_identity_factory, monkeypatch
):
    from object_storage.feishu import FeishuProviderError
    from object_storage.models import AuditEvent

    existing = feishu_identity_factory(open_id="ou_existing", display_name="Stable")
    client.force_login(platform_admin)

    response = _preview(
        client,
        monkeypatch,
        error=FeishuProviderError("FEISHU_CONTACTS_PERMISSION_DENIED"),
    )

    existing.refresh_from_db()
    audit = AuditEvent.objects.get(action="feishu.identity.sync")
    assert response.status_code == 502
    assert _payload(response)["error_code"] == "FEISHU_CONTACTS_PERMISSION_DENIED"
    assert existing.display_name == "Stable"
    assert audit.result == "failed"
    assert audit.safe_metadata == {"error_code": "FEISHU_CONTACTS_PERMISSION_DENIED"}
    assert "email" not in audit.reason.lower()
