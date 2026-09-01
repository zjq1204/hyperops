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
        "ou_existing": "updates",
        "ou_deactivated": "new_remote",
    }
    assert existing.user.feishu_identity.open_id == "ou_existing"


def test_preview_classifies_every_identity_once(
    feishu_config, platform_admin, client, feishu_identity_factory, monkeypatch
):
    unchanged = feishu_identity_factory(
        open_id="ou_unchanged",
        union_id="union-ou_unchanged",
        display_name="User ou_unchanged",
        profile_snapshot={"email": "ou_unchanged@example.com"},
        department_snapshot=["department-1"],
    )
    updated = feishu_identity_factory(open_id="ou_updated", display_name="Old")
    account_disabled = feishu_identity_factory(open_id="ou_disabled")
    deleted = feishu_identity_factory(open_id="ou_deleted")
    outside_scope = feishu_identity_factory(open_id="ou_outside")
    client.force_login(platform_admin)

    response = _preview(
        client,
        monkeypatch,
        identities=[
            _identity("ou_unchanged"),
            _identity("ou_updated", display_name="New"),
            _identity(
                "ou_disabled",
                is_active=False,
                is_eligible=False,
                status_reason="account_disabled",
            ),
            _identity(
                "ou_deleted",
                is_active=False,
                is_eligible=False,
                status_reason="deleted",
            ),
            _identity("ou_new"),
        ],
    )

    payload = _payload(response)
    assert response.status_code == 200
    assert payload["counts"] == {
        "creates": 1,
        "updates": 1,
        "account_disabled": 1,
        "deleted": 1,
        "outside_scope": 1,
        "unchanged": 1,
    }
    assert {row["category"] for row in payload["items"]} == {
        "new_remote",
        "updates",
        "account_disabled",
        "deleted",
        "outside_scope",
        "unchanged",
    }
    assert unchanged.display_name == "User ou_unchanged"
    assert updated.display_name == "Old"
    assert outside_scope.is_active is True


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

    identities = client.list_department_users(app_config=object(), department_id="0")

    assert [identity.open_id for identity in identities] == [
        "ou_first",
        "ou_second",
    ]
    assert identities[1].status_reason == "account_disabled"
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


def test_contacts_client_recurses_departments_and_deduplicates_users(monkeypatch):
    from object_storage.feishu import FeishuClient

    client = FeishuClient()
    monkeypatch.setattr(client, "_tenant_token", lambda _config: "tenant-token")
    calls = []

    def request_json(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if "/departments/0/children" in url:
            return {
                "data": {
                    "items": [{"open_department_id": "dep-a"}],
                    "has_more": False,
                }
            }
        if "/departments/dep-a/children" in url:
            return {
                "data": {
                    "items": [{"open_department_id": "dep-b"}],
                    "has_more": False,
                }
            }
        if "/departments/dep-b/children" in url:
            return {"data": {"items": [], "has_more": False}}
        department_id = kwargs["params"]["department_id"]
        if department_id == "0":
            items = [{"open_id": "ou_root", "name": "Root"}]
        elif department_id == "dep-a":
            items = [{"open_id": "ou_nested", "name": "Nested"}]
        else:
            items = [
                {"open_id": "ou_nested", "name": "Nested"},
                {"open_id": "ou_deep", "name": "Deep"},
            ]
        return {"data": {"items": items, "has_more": False}}

    monkeypatch.setattr(client, "_request_json", request_json)

    identities = client.list_visible_users(app_config=object())

    assert {identity.open_id for identity in identities} == {
        "ou_root",
        "ou_nested",
        "ou_deep",
    }
    assert len(identities) == 3
    assert [
        kwargs["params"]["department_id"]
        for _, url, kwargs in calls
        if "find_by_department" in url
    ] == [
        "0",
        "dep-a",
        "dep-b",
    ]


def test_contacts_department_failure_prevents_a_partial_snapshot(
    client, feishu_config, platform_admin, feishu_identity_factory, monkeypatch
):
    from object_storage import views_feishu_admin
    from object_storage.feishu import FeishuProviderError

    existing = feishu_identity_factory(open_id="ou_existing", display_name="Stable")
    client.force_login(platform_admin)
    monkeypatch.setattr(
        views_feishu_admin,
        "get_feishu_client",
        lambda: FakeFeishuSyncClient(
            error=FeishuProviderError("FEISHU_CONTACTS_DEPARTMENT_UNAVAILABLE")
        ),
    )

    response = client.post(
        "/api/v1/object-storage/management/feishu/sync/preview/",
        {},
        content_type="application/json",
    )

    existing.refresh_from_db()
    assert response.status_code == 502
    assert _payload(response)["error_code"] == "FEISHU_CONTACTS_DEPARTMENT_UNAVAILABLE"
    assert existing.display_name == "Stable"
    assert existing.is_active is True


def test_nested_department_user_is_not_marked_outside_scope(
    client, feishu_config, platform_admin, feishu_identity_factory, monkeypatch
):
    existing = feishu_identity_factory(open_id="ou_nested", display_name="Old")
    client.force_login(platform_admin)

    response = _preview(
        client,
        monkeypatch,
        identities=[_identity("ou_nested", display_name="Nested Updated")],
    )

    item = next(
        row for row in _payload(response)["items"] if row["open_id"] == "ou_nested"
    )
    assert item["category"] == "updates"
    assert item["category"] != "outside_scope"
    existing.refresh_from_db()
    assert existing.display_name == "Old"


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
    assert _payload(replay)["error_code"] == "TOKEN_ALREADY_CONSUMED"


def test_consumed_token_is_still_rejected_after_31_seconds(
    client, feishu_config, platform_admin, monkeypatch
):
    from django.core.cache.backends import base

    client.force_login(platform_admin)
    preview = _preview(client, monkeypatch, identities=[])
    token = _payload(preview)["confirmation_token"]
    first = client.post(
        "/api/v1/object-storage/management/feishu/sync/confirm/",
        {"confirmation_token": token, "idempotency_key": "first-key"},
        content_type="application/json",
    )
    current_time = base.time.time()
    monkeypatch.setattr(base.time, "time", lambda: current_time + 31)

    replay = client.post(
        "/api/v1/object-storage/management/feishu/sync/confirm/",
        {"confirmation_token": token, "idempotency_key": "second-key"},
        content_type="application/json",
    )

    assert first.status_code == 200
    assert replay.status_code == 400
    assert _payload(replay)["error_code"] == "TOKEN_ALREADY_CONSUMED"


def test_unconsumed_token_is_expired_after_confirmation_ttl(
    client, feishu_config, platform_admin, monkeypatch
):
    from django.core.cache.backends import base

    from object_storage.services.feishu_sync import CONFIRMATION_TTL_SECONDS

    client.force_login(platform_admin)
    preview = _preview(client, monkeypatch, identities=[])
    token = _payload(preview)["confirmation_token"]
    current_time = base.time.time()
    monkeypatch.setattr(
        base.time,
        "time",
        lambda: current_time + CONFIRMATION_TTL_SECONDS + 1,
    )

    response = client.post(
        "/api/v1/object-storage/management/feishu/sync/confirm/",
        {"confirmation_token": token, "idempotency_key": "expired-token"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert _payload(response)["error_code"] == "FEISHU_CONFIRMATION_EXPIRED"


def test_new_remote_confirm_does_not_create_local_users(
    client, feishu_config, platform_admin, django_user_model, monkeypatch
):
    client.force_login(platform_admin)
    preview = _preview(client, monkeypatch, identities=[_identity("ou_new")])
    token = _payload(preview)["confirmation_token"]
    before = django_user_model.objects.count()

    response = client.post(
        "/api/v1/object-storage/management/feishu/sync/confirm/",
        {"confirmation_token": token, "idempotency_key": "new-only"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert django_user_model.objects.count() == before
    assert _payload(response)["skipped_new_remote"] == 1


def test_same_idempotency_key_rejects_a_different_preview_snapshot(
    client, feishu_config, platform_admin, monkeypatch
):
    client.force_login(platform_admin)
    first = _preview(client, monkeypatch, identities=[_identity("ou_first")])
    second = _preview(client, monkeypatch, identities=[_identity("ou_second")])

    first_response = client.post(
        "/api/v1/object-storage/management/feishu/sync/confirm/",
        {
            "confirmation_token": _payload(first)["confirmation_token"],
            "idempotency_key": "same-key",
        },
        content_type="application/json",
    )
    second_response = client.post(
        "/api/v1/object-storage/management/feishu/sync/confirm/",
        {
            "confirmation_token": _payload(second)["confirmation_token"],
            "idempotency_key": "same-key",
        },
        content_type="application/json",
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 400
    assert _payload(second_response)["error_code"] == "IDEMPOTENCY_KEY_REUSED"


def test_same_idempotency_key_and_snapshot_returns_the_original_result(
    client, feishu_config, platform_admin, monkeypatch
):
    client.force_login(platform_admin)
    preview = _preview(client, monkeypatch, identities=[_identity("ou_same")])
    token = _payload(preview)["confirmation_token"]
    body = {"confirmation_token": token, "idempotency_key": "same-snapshot"}

    first = client.post(
        "/api/v1/object-storage/management/feishu/sync/confirm/",
        body,
        content_type="application/json",
    )
    replay = client.post(
        "/api/v1/object-storage/management/feishu/sync/confirm/",
        body,
        content_type="application/json",
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert _payload(replay) == _payload(first)


def test_sync_endpoints_reject_tenant_body_and_query_parameters(
    client, feishu_config, platform_admin, monkeypatch
):
    client.force_login(platform_admin)
    monkeypatch.setattr(
        "object_storage.views_feishu_admin.get_feishu_client",
        lambda: FakeFeishuSyncClient([]),
    )

    preview_body = client.post(
        "/api/v1/object-storage/management/feishu/sync/preview/",
        {"tenant_code": "legacy"},
        content_type="application/json",
    )
    preview_query = client.post(
        "/api/v1/object-storage/management/feishu/sync/preview/?tenant_id=1",
        {},
        content_type="application/json",
    )
    confirm_query = client.post(
        "/api/v1/object-storage/management/feishu/sync/confirm/?tenant=legacy",
        {"confirmation_token": "invalid", "idempotency_key": "tenant-check"},
        content_type="application/json",
    )

    for response in (preview_body, preview_query, confirm_query):
        assert response.status_code == 400
        assert _payload(response)["error_code"] == "TENANT_SCOPE_UNSUPPORTED"


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
