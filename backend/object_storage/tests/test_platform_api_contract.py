import hashlib
import inspect
from pathlib import Path

import pytest
from django.urls import get_resolver
from django.utils import timezone

from object_storage.crypto import encrypt_secret

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def stable_secret(settings):
    settings.SECRET_KEY = "platform-api-contract-stable-secret"


@pytest.fixture
def admin_client(client, django_user_model):
    user = django_user_model.objects.create_superuser(
        username="platform-contract-admin", password="secret123"
    )
    client.force_login(user)
    return client, user


def test_runtime_api_modules_do_not_import_removed_enterprise_models():
    runtime_root = Path(__file__).parents[1]
    forbidden = (
        "StorageTenant",
        "StorageMembership",
        "FeishuAppConfig",
        "StorageApplication",
        "tenant_id",
        "services.tenant",
        "compatibility",
    )
    for path in runtime_root.rglob("*.py"):
        if "migrations" in path.parts or "tests" in path.parts:
            continue
        source = path.read_text()
        if path.name == "views_auth.py":
            source = source.replace('"tenant_id"', "")
        assert not any(name in source for name in forbidden), path
    assert not (runtime_root / "services" / "tenant.py").exists()


def test_audit_writer_has_no_removed_scope_arguments():
    from inspect import signature

    from object_storage.services.audit import record_audit_event

    assert "tenant" not in signature(record_audit_event).parameters
    assert "application" not in signature(record_audit_event).parameters


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


def test_non_sensitive_write_replays_exact_response_and_rejects_payload_reuse(
    admin_client,
):
    client, _admin = admin_client
    first = client.put(
        "/api/v1/object-storage/management/settings/",
        {"default_bucket_quota": 8},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="settings-idempotency-1",
    )
    replay = client.put(
        "/api/v1/object-storage/management/settings/",
        {"default_bucket_quota": 8},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="settings-idempotency-1",
    )
    reused = client.put(
        "/api/v1/object-storage/management/settings/",
        {"default_bucket_quota": 9},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="settings-idempotency-1",
    )

    assert first.status_code == 200
    assert replay.status_code == first.status_code
    assert replay.json() == first.json()
    assert reused.status_code == 409
    assert reused.json()["data"]["error_code"] == "IDEMPOTENCY_KEY_REUSED"


def test_idempotency_in_progress_fails_closed(admin_client, settings, monkeypatch):
    from datetime import timedelta

    from object_storage.models import ApiIdempotencyRecord

    client, admin = admin_client
    body = '{"default_bucket_quota":8}'
    ApiIdempotencyRecord.objects.create(
        actor=admin,
        scope="PUT:/api/v1/object-storage/management/settings/",
        idempotency_key="settings-in-progress",
        payload_digest=hashlib.sha256(body.encode()).hexdigest(),
        status=ApiIdempotencyRecord.Status.IN_PROGRESS,
        owner_token="active-owner",
        lease_until=timezone.now() + timedelta(minutes=5),
    )

    response = client.put(
        "/api/v1/object-storage/management/settings/",
        body,
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="settings-in-progress",
    )

    assert response.status_code == 409
    assert response.json()["data"]["error_code"] == "IDEMPOTENCY_IN_PROGRESS"


def test_expired_pure_database_idempotency_claim_can_be_reacquired(admin_client):
    from datetime import timedelta

    from object_storage.models import ApiIdempotencyRecord

    client, admin = admin_client
    body = '{"default_bucket_quota":8}'
    record = ApiIdempotencyRecord.objects.create(
        actor=admin,
        scope="PUT:/api/v1/object-storage/management/settings/",
        idempotency_key="settings-expired-lease",
        payload_digest=hashlib.sha256(body.encode()).hexdigest(),
        status=ApiIdempotencyRecord.Status.IN_PROGRESS,
        owner_token="expired-owner",
        lease_until=timezone.now() - timedelta(seconds=1),
        attempt_count=1,
    )

    response = client.put(
        "/api/v1/object-storage/management/settings/",
        body,
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="settings-expired-lease",
    )

    record.refresh_from_db()
    assert response.status_code == 200
    assert record.status == ApiIdempotencyRecord.Status.COMPLETED
    assert record.attempt_count == 2
    assert record.owner_token == ""
    assert record.lease_until is None


def test_expired_idempotency_lease_is_reclaimed_while_row_lock_is_held(monkeypatch):
    from contextlib import contextmanager
    from datetime import timedelta
    from types import SimpleNamespace
    from unittest.mock import Mock

    from object_storage.models import ApiIdempotencyRecord
    from object_storage.permissions import RequireIdempotencyKeyMixin

    lock_state = {"held": False}

    @contextmanager
    def atomic():
        lock_state["held"] = True
        try:
            yield
        finally:
            lock_state["held"] = False

    record = SimpleNamespace(
        payload_digest="digest",
        status=ApiIdempotencyRecord.Status.IN_PROGRESS,
        lease_until=timezone.now() - timedelta(seconds=1),
        owner_token="expired-owner",
        attempt_count=1,
    )

    def save(*, update_fields):
        assert lock_state["held"] is True
        assert set(update_fields) == {"owner_token", "lease_until", "attempt_count"}

    record.save = save
    queryset = Mock()
    queryset.filter.return_value.first.return_value = record
    monkeypatch.setattr(
        "object_storage.permissions.transaction.atomic",
        atomic,
    )
    monkeypatch.setattr(
        ApiIdempotencyRecord.objects,
        "select_for_update",
        lambda: queryset,
    )

    view = RequireIdempotencyKeyMixin()
    view.idempotency_reclaimable = True
    request = SimpleNamespace(
        user=SimpleNamespace(pk=1),
        method="PUT",
        path="/api/v1/object-storage/management/settings/",
        idempotency_key="expired-lease-lock",
    )

    claimed = view._lookup_or_create_idempotency(request, "digest")

    assert claimed is record
    assert record.attempt_count == 2
    assert record.owner_token != "expired-owner"


def test_expired_sensitive_idempotency_claim_fails_as_outcome_unknown(
    admin_client, cloud_identity_factory, access_key_factory, monkeypatch
):
    from datetime import timedelta

    from object_storage.models import ApiIdempotencyRecord

    client, admin = admin_client
    key = access_key_factory(cloud_identity=cloud_identity_factory())
    body = '{"reason":"incident investigation"}'
    url = f"/api/v1/object-storage/management/access-keys/{key.id}/reveal/"
    record = ApiIdempotencyRecord.objects.create(
        actor=admin,
        scope=f"POST:{url}",
        idempotency_key="sensitive-expired-lease",
        payload_digest=hashlib.sha256(body.encode()).hexdigest(),
        status=ApiIdempotencyRecord.Status.IN_PROGRESS,
        owner_token="expired-sensitive-owner",
        lease_until=timezone.now() - timedelta(seconds=1),
        attempt_count=1,
    )
    calls = []
    monkeypatch.setattr(
        "object_storage.views_admin.reveal_access_key",
        lambda **kwargs: calls.append(kwargs),
    )

    response = client.post(
        url,
        body,
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="sensitive-expired-lease",
    )

    record.refresh_from_db()
    assert response.status_code == 409
    assert response.json()["data"]["error_code"] == "IDEMPOTENCY_OUTCOME_UNKNOWN"
    assert calls == []
    assert record.status == ApiIdempotencyRecord.Status.OUTCOME_UNKNOWN
    assert record.response_body is None


def test_admin_can_resolve_unknown_idempotency_record_for_reconciliation(
    admin_client,
):
    from datetime import timedelta

    from object_storage.models import ApiIdempotencyRecord
    from object_storage.services.idempotency import resolve_idempotency_outcome

    _client, admin = admin_client
    record = ApiIdempotencyRecord.objects.create(
        actor=admin,
        scope="POST:/api/v1/object-storage/unknown/",
        idempotency_key="admin-resolution",
        payload_digest="0" * 64,
        status=ApiIdempotencyRecord.Status.OUTCOME_UNKNOWN,
        lease_until=timezone.now() - timedelta(seconds=1),
    )

    resolve_idempotency_outcome(
        record=record,
        actor=admin,
        resolution="delete",
        current_status=ApiIdempotencyRecord.Status.OUTCOME_UNKNOWN,
        reason="external operation reconciled",
    )

    assert not ApiIdempotencyRecord.objects.filter(pk=record.pk).exists()


def test_uncertainty_views_are_sensitive_idempotency_endpoints():
    from object_storage.permissions import RequireIdempotencyKeyMixin
    from object_storage.urls import urlpatterns
    from object_storage.views_admin import NoStoreResponseMixin

    uncertainty_views = {
        "management_credential_uncertainty_observe",
        "management_credential_uncertainty_acknowledge",
        "management_bucket_uncertainty_observe",
        "management_bucket_uncertainty_acknowledge",
        "management_bucket_configuration_uncertainty_observe",
        "management_bucket_configuration_uncertainty_acknowledge",
    }
    for pattern in urlpatterns:
        if pattern.name not in uncertainty_views:
            continue
        view_class = pattern.callback.view_class
        assert issubclass(view_class, RequireIdempotencyKeyMixin)
        assert issubclass(view_class, NoStoreResponseMixin)
        assert view_class.idempotency_sensitive is True


def test_admin_views_that_serialize_operation_tokens_are_no_store():
    from object_storage.views_admin import (
        BucketAdminDetailView,
        CloudIdentityAdminDetailView,
        NoStoreResponseMixin,
    )

    assert issubclass(BucketAdminDetailView, NoStoreResponseMixin)
    assert issubclass(CloudIdentityAdminDetailView, NoStoreResponseMixin)


def test_sensitive_idempotency_never_persists_response_body(
    admin_client, cloud_identity_factory, access_key_factory, monkeypatch
):
    from object_storage.models import ApiIdempotencyRecord

    client, admin = admin_client
    key = access_key_factory(cloud_identity=cloud_identity_factory())
    key.access_key_id_encrypted = encrypt_secret("LTAI-contract-reveal")
    key.secret_access_key_encrypted = encrypt_secret("contract-reveal-secret")
    key.save(update_fields=("access_key_id_encrypted", "secret_access_key_encrypted"))
    calls = []

    def reveal(**kwargs):
        calls.append(kwargs)
        return {
            "access_key_id": "LTAI-contract-reveal",
            "secret_access_key": "contract-reveal-secret",
        }

    monkeypatch.setattr("object_storage.views_admin.reveal_access_key", reveal)
    url = f"/api/v1/object-storage/management/access-keys/{key.id}/reveal/"
    response = client.post(
        url,
        {"reason": "incident investigation"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="sensitive-reveal-1",
    )
    replay = client.post(
        url,
        {"reason": "incident investigation"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="sensitive-reveal-1",
    )
    reused = client.post(
        url,
        {"reason": "different investigation"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="sensitive-reveal-1",
    )

    assert response.status_code == 200
    assert replay.status_code == 409
    assert replay.json()["data"]["error_code"] == ("IDEMPOTENCY_RESULT_NOT_REPLAYABLE")
    assert reused.status_code == 409
    assert reused.json()["data"]["error_code"] == "IDEMPOTENCY_KEY_REUSED"
    assert len(calls) == 1
    record = ApiIdempotencyRecord.objects.get(
        actor=admin, idempotency_key="sensitive-reveal-1"
    )
    assert record.status == ApiIdempotencyRecord.Status.COMPLETED
    assert record.response_body is None
    assert "contract-reveal-secret" not in str(record.__dict__)


def test_sensitive_idempotency_in_progress_fails_closed(
    admin_client, cloud_identity_factory, access_key_factory, monkeypatch
):
    from datetime import timedelta

    from object_storage.models import ApiIdempotencyRecord

    client, admin = admin_client
    key = access_key_factory(cloud_identity=cloud_identity_factory())
    body = '{"reason":"incident investigation"}'
    url = f"/api/v1/object-storage/management/access-keys/{key.id}/reveal/"
    ApiIdempotencyRecord.objects.create(
        actor=admin,
        scope=f"POST:{url}",
        idempotency_key="sensitive-in-progress",
        payload_digest=hashlib.sha256(body.encode()).hexdigest(),
        owner_token="active-sensitive-owner",
        lease_until=timezone.now() + timedelta(minutes=5),
    )
    calls = []
    monkeypatch.setattr(
        "object_storage.views_admin.reveal_access_key",
        lambda **kwargs: calls.append(kwargs),
    )

    response = client.post(
        url,
        body,
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="sensitive-in-progress",
    )

    assert response.status_code == 409
    assert response.json()["data"]["error_code"] == "IDEMPOTENCY_IN_PROGRESS"
    assert response["Cache-Control"] == "no-store"
    assert calls == []


def test_safe_idempotency_does_not_cache_a_5xx_and_retries_same_key(
    admin_client, monkeypatch
):
    from object_storage.models import ApiIdempotencyRecord
    from object_storage.services import platform

    client, admin = admin_client
    original = platform.validate_and_save_platform_config
    calls = []

    def fail_once(**kwargs):
        calls.append("failed")
        raise RuntimeError("temporary failure")

    monkeypatch.setattr(
        "object_storage.views_admin.validate_and_save_platform_config", fail_once
    )
    url = "/api/v1/object-storage/management/settings/"
    body = '{"default_bucket_quota":8}'
    first = client.put(
        url,
        body,
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="safe-5xx-retry",
    )
    record = ApiIdempotencyRecord.objects.get(
        actor=admin, idempotency_key="safe-5xx-retry"
    )
    assert first.status_code == 500
    assert record.status == ApiIdempotencyRecord.Status.IN_PROGRESS
    assert record.lease_until is None
    assert record.response_body is None

    monkeypatch.setattr(
        "object_storage.views_admin.validate_and_save_platform_config", original
    )
    second = client.put(
        url,
        body,
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="safe-5xx-retry",
    )

    record.refresh_from_db()
    assert second.status_code == 200
    assert calls == ["failed"]
    assert record.status == ApiIdempotencyRecord.Status.COMPLETED


def test_unsafe_idempotency_marks_a_5xx_as_outcome_unknown(admin_client, monkeypatch):
    from object_storage.models import ApiIdempotencyRecord

    client, admin = admin_client
    monkeypatch.setattr(
        "object_storage.serializers_admin.PlatformFeishuConfigAdminSerializer.save",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("temporary")),
    )
    url = "/api/v1/object-storage/management/feishu-settings/"
    response = client.patch(
        url,
        {"app_id": "cli-temporary"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="unsafe-5xx-outcome",
    )

    record = ApiIdempotencyRecord.objects.get(
        actor=admin, idempotency_key="unsafe-5xx-outcome"
    )
    assert response.status_code == 500
    assert record.status == ApiIdempotencyRecord.Status.OUTCOME_UNKNOWN


def test_sensitive_idempotency_marks_a_5xx_as_outcome_unknown(
    admin_client, cloud_identity_factory, access_key_factory, monkeypatch
):
    from object_storage.models import ApiIdempotencyRecord

    client, admin = admin_client
    key = access_key_factory(cloud_identity=cloud_identity_factory())
    monkeypatch.setattr(
        "object_storage.views_admin.reveal_access_key",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("provider timeout")),
    )
    url = f"/api/v1/object-storage/management/access-keys/{key.id}/reveal/"
    response = client.post(
        url,
        {"reason": "incident investigation"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="sensitive-5xx-outcome",
    )

    record = ApiIdempotencyRecord.objects.get(
        actor=admin, idempotency_key="sensitive-5xx-outcome"
    )
    assert response.status_code == 500
    assert record.status == ApiIdempotencyRecord.Status.OUTCOME_UNKNOWN
    assert record.response_body is None


def test_idempotency_recovery_api_lists_details_and_requires_admin_reason(
    admin_client, django_user_model
):
    from object_storage.models import ApiIdempotencyRecord

    client, admin = admin_client
    record = ApiIdempotencyRecord.objects.create(
        actor=admin,
        scope="POST:/api/v1/object-storage/provider/",
        idempotency_key="recovery-api-record",
        payload_digest="a" * 64,
        status=ApiIdempotencyRecord.Status.OUTCOME_UNKNOWN,
    )
    listed = client.get(
        "/api/v1/object-storage/management/idempotency-records/?status=outcome_unknown"
    )
    detail = client.get(
        f"/api/v1/object-storage/management/idempotency-records/{record.id}/"
    )
    missing_reason = client.post(
        f"/api/v1/object-storage/management/idempotency-records/{record.id}/resolve/",
        {"current_status": "outcome_unknown", "resolution": "delete"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="recovery-missing-reason",
    )
    ordinary = django_user_model.objects.create_user(username="not-storage-admin")
    client.force_login(ordinary)
    denied = client.get(
        "/api/v1/object-storage/management/idempotency-records/?status=outcome_unknown"
    )

    assert listed.status_code == 200
    assert listed.json()["data"]["results"][0]["id"] == record.id
    assert detail.status_code == 200
    assert detail.json()["data"]["status"] == "outcome_unknown"
    assert missing_reason.status_code == 400
    assert denied.status_code == 403


def test_idempotency_recovery_api_uses_status_cas_and_explicit_resolution(admin_client):
    from object_storage.models import ApiIdempotencyRecord, AuditEvent

    client, admin = admin_client
    record = ApiIdempotencyRecord.objects.create(
        actor=admin,
        scope="POST:/api/v1/object-storage/provider/",
        idempotency_key="recovery-api-delete",
        payload_digest="b" * 64,
        status=ApiIdempotencyRecord.Status.OUTCOME_UNKNOWN,
    )
    stale = client.post(
        f"/api/v1/object-storage/management/idempotency-records/{record.id}/resolve/",
        {
            "reason": "provider and database reconciled",
            "current_status": "completed",
            "resolution": "delete",
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="recovery-stale-status",
    )
    deleted = client.post(
        f"/api/v1/object-storage/management/idempotency-records/{record.id}/resolve/",
        {
            "reason": "provider and database reconciled",
            "current_status": "outcome_unknown",
            "resolution": "delete",
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="recovery-delete-record",
    )

    assert stale.status_code == 409
    assert stale.json()["data"]["error_code"] == "IDEMPOTENCY_STATUS_CHANGED"
    assert deleted.status_code == 204
    assert not ApiIdempotencyRecord.objects.filter(pk=record.pk).exists()
    assert AuditEvent.objects.filter(
        action="storage.api.idempotency.resolve",
        target_id=str(record.id),
        result="succeeded",
    ).exists()


def test_idempotency_recovery_api_can_mark_outcome_completed(admin_client):
    from object_storage.models import ApiIdempotencyRecord

    client, admin = admin_client
    record = ApiIdempotencyRecord.objects.create(
        actor=admin,
        scope="POST:/api/v1/object-storage/provider/",
        idempotency_key="recovery-api-complete",
        payload_digest="c" * 64,
        status=ApiIdempotencyRecord.Status.OUTCOME_UNKNOWN,
    )
    response = client.post(
        f"/api/v1/object-storage/management/idempotency-records/{record.id}/resolve/",
        {
            "reason": "external operation confirmed complete",
            "current_status": "outcome_unknown",
            "resolution": "complete",
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="recovery-complete-record",
    )

    record.refresh_from_db()
    assert response.status_code == 200
    assert record.status == ApiIdempotencyRecord.Status.COMPLETED
    assert record.response_body is None
