import hashlib
import inspect
from pathlib import Path

import pytest
from django.urls import get_resolver

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
    from object_storage.models import ApiIdempotencyRecord

    client, admin = admin_client
    body = '{"default_bucket_quota":8}'
    ApiIdempotencyRecord.objects.create(
        actor=admin,
        scope="PUT:/api/v1/object-storage/management/settings/",
        idempotency_key="settings-in-progress",
        payload_digest=hashlib.sha256(body.encode()).hexdigest(),
        status=ApiIdempotencyRecord.Status.IN_PROGRESS,
    )

    response = client.put(
        "/api/v1/object-storage/management/settings/",
        body,
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="settings-in-progress",
    )

    assert response.status_code == 409
    assert response.json()["data"]["error_code"] == "IDEMPOTENCY_IN_PROGRESS"


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
