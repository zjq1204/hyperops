from types import SimpleNamespace

import pytest
from django.utils import timezone

from object_storage.crypto import encrypt_secret

pytestmark = pytest.mark.django_db


def _payload(response):
    body = response.json()
    return body.get("data", body)


@pytest.fixture(autouse=True)
def stable_secret(settings):
    settings.SECRET_KEY = "employee-api-contract-stable-secret"


def test_employee_without_storage_membership_gets_not_configured_state(
    client, django_user_model
):
    user = django_user_model.objects.create_user(
        username="storage-unconfigured-user",
        password="secret123",
    )
    client.force_login(user)

    response = client.get("/api/v1/object-storage/workspace/overview/")

    assert response.status_code == 403
    assert _payload(response)["error_code"] == "OBJECT_STORAGE_NOT_CONFIGURED"


@pytest.fixture
def employee_context(
    client,
    user_factory,
    platform_object_storage_config,
    storage_resource_pool_factory,
):
    from object_storage.models import PlatformFeishuConfig, StorageResourcePool

    user = user_factory()
    PlatformFeishuConfig.objects.update_or_create(
        singleton_key="default",
        defaults={
            "enabled": True,
            "validation_status": PlatformFeishuConfig.ValidationStatus.VALID,
        },
    )
    platform_object_storage_config.pause_new_applications = False
    platform_object_storage_config.pause_key_operations = False
    platform_object_storage_config.save()
    pool = storage_resource_pool_factory(
        enabled=True,
        validation_status=StorageResourcePool.ValidationStatus.VALID,
    )
    client.force_login(user)
    return client, user, pool, platform_object_storage_config


def _key(identity, number=1):
    from object_storage.models import AccessKey

    return AccessKey.objects.create(
        cloud_identity=identity,
        access_key_id_encrypted=encrypt_secret(f"LTAI-action-{number}"),
        secret_access_key_encrypted=encrypt_secret(f"action-secret-{number}"),
        access_key_fingerprint=f"action-fingerprint-{number}",
        access_key_last_four=f"{number:04d}",
        local_state=AccessKey.LocalState.ACTIVE,
    )


def test_batch_create_is_idempotent_and_rejects_frontend_ownership(
    employee_context, monkeypatch
):
    client, user, _pool, _config = employee_context
    captured = []
    batch = SimpleNamespace(pk=17)

    def create_batch(**kwargs):
        captured.append(kwargs)
        return batch

    monkeypatch.setattr(
        "object_storage.views_employee.create_application_batch", create_batch
    )
    monkeypatch.setattr(
        "object_storage.views_employee.ApplicationBatchEmployeeSerializer",
        lambda value: SimpleNamespace(data={"id": value.pk, "status": "pending"}),
    )
    body = {
        "items": [
            {
                "business_name": "logs",
                "purpose": "audit logs",
                "environment": "test",
                "initial_suffix": "abcd1234",
                "rendered_bucket_name": "hyperops-test-logs-abcd1234",
            }
        ]
    }
    first = client.post(
        "/api/v1/object-storage/workspace/applications/",
        body,
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="batch-create-1",
    )
    forbidden_owner = client.post(
        "/api/v1/object-storage/workspace/applications/",
        {**body, "applicant_id": user.id + 1},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="batch-create-2",
    )

    assert first.status_code == 202
    assert captured[0]["user"] == user
    assert captured[0]["idempotency_key"] == "batch-create-1"
    assert forbidden_owner.status_code == 400


def test_application_item_retry_and_cancel_are_independent(
    employee_context, application_batch_factory, monkeypatch
):
    from object_storage.models import ApplicationItem

    client, user, _pool, _config = employee_context
    batch = application_batch_factory(applicant=user, item_count=2)
    failed, pending = batch.items.order_by("id")
    failed.status = ApplicationItem.Status.FAILED
    failed.error_code = "BUCKET_CREATE_FAILED"
    failed.save(update_fields=("status", "error_code", "updated_at"))
    queued = []
    monkeypatch.setattr(
        "object_storage.tasks.run_storage_application_batch.delay", queued.append
    )

    retried = client.post(
        f"/api/v1/object-storage/workspace/applications/{batch.id}/items/{failed.id}/retry/",
        {},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="retry-item-1",
    )
    cancelled = client.post(
        f"/api/v1/object-storage/workspace/applications/{batch.id}/items/{pending.id}/cancel/",
        {},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="cancel-item-1",
    )

    failed.refresh_from_db()
    pending.refresh_from_db()
    assert retried.status_code == 202
    assert cancelled.status_code == 200
    assert failed.status == ApplicationItem.Status.WAITING_RETRY
    assert pending.status == ApplicationItem.Status.CANCELLED
    assert queued == [batch.id]


def test_cross_user_item_action_returns_not_found(
    employee_context, application_batch_factory, user_factory
):
    client, _user, _pool, _config = employee_context
    batch = application_batch_factory(applicant=user_factory(), item_count=1)
    item = batch.items.get()
    item.status = "failed"
    item.save(update_fields=("status", "updated_at"))

    response = client.post(
        f"/api/v1/object-storage/workspace/applications/{batch.id}/items/{item.id}/retry/",
        {},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="cross-user-retry",
    )

    assert response.status_code == 404


@pytest.mark.parametrize("action", ["disable", "enable", "rotate", "revoke"])
def test_single_key_actions_are_owner_scoped_and_require_idempotency(
    employee_context, cloud_identity_factory, monkeypatch, action
):
    client, user, pool, _config = employee_context
    identity = cloud_identity_factory(user=user, resource_pool=pool, state="active")
    key = _key(identity)
    called = []

    def operation(**kwargs):
        called.append(kwargs)
        return key

    monkeypatch.setattr(
        f"object_storage.views_employee.{action}_access_key_action", operation
    )
    url = f"/api/v1/object-storage/workspace/credentials/{key.id}/{action}/"
    missing = client.post(url, {}, content_type="application/json")
    response = client.post(
        url,
        {},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=f"key-{action}-1",
    )

    assert missing.status_code == 400
    assert response.status_code == 200
    assert called[0]["actor"] == user
    assert _payload(response)["id"] == key.id
    assert "action-secret" not in response.content.decode()


def test_delivery_token_and_consume_are_no_store(
    employee_context,
    monkeypatch,
):
    from object_storage.models import ApiIdempotencyRecord, DeliveryTicket
    from object_storage.services import applications
    from object_storage.services.applications import create_application_batch
    from object_storage.services.naming import render_bucket_name
    from object_storage.tests.test_application_service import FakeProvider

    client, user, pool, config = employee_context
    suffix = "delivery"
    batch = create_application_batch(
        user=user,
        resource_pool=pool,
        idempotency_key="delivery-application",
        items=[
            {
                "business_name": "Delivery",
                "project": "platform",
                "environment": "test",
                "purpose": "credential delivery",
                "notes": "",
                "initial_suffix": suffix,
                "rendered_bucket_name": render_bucket_name(
                    template=config.naming_template,
                    prefix="hyperops",
                    user=user.get_username(),
                    business_name="Delivery",
                    project="platform",
                    environment="test",
                    purpose="credential delivery",
                    suffix=suffix,
                ),
            }
        ],
        enqueue=False,
    )
    monkeypatch.setattr(
        applications, "get_provider_for_pool", lambda _pool: FakeProvider()
    )
    applications.execute_application_batch(batch.pk, execution_key="delivery:0")
    batch.refresh_from_db()
    key = batch.issued_access_key
    ticket = DeliveryTicket.objects.get(application_batch=batch)

    raw_token_rejected = client.post(
        f"/api/v1/object-storage/workspace/credentials/{key.id}/deliver/",
        {"token": "client-supplied-token"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="client-token-rejected",
    )
    consumed = client.post(
        f"/api/v1/object-storage/workspace/credentials/{key.id}/deliver/",
        {},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="consume-token-1",
    )
    same_request = client.post(
        f"/api/v1/object-storage/workspace/credentials/{key.id}/deliver/",
        {},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="consume-token-1",
    )
    consumed_again = client.post(
        f"/api/v1/object-storage/workspace/credentials/{key.id}/deliver/",
        {},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="consume-token-2",
    )

    assert raw_token_rejected.status_code == 400
    assert _payload(raw_token_rejected)["error_code"] == (
        "DELIVERY_REQUEST_BODY_UNSUPPORTED"
    )
    assert consumed.status_code == 200
    assert consumed["Cache-Control"] == "no-store"
    assert _payload(consumed)["access_key_id"] == "LTAI-batch-key-1"
    assert _payload(consumed)["secret_access_key"] == "employee-secret"
    assert same_request.status_code == 409
    assert _payload(same_request)["error_code"] == ("IDEMPOTENCY_RESULT_NOT_REPLAYABLE")
    assert consumed_again.status_code in (400, 409)
    assert _payload(consumed_again)["error_code"] in {
        "DELIVERY_TOKEN_CONSUMED",
        "DELIVERY_TOKEN_UNAVAILABLE",
    }
    record = ApiIdempotencyRecord.objects.get(
        actor=user, idempotency_key="consume-token-1"
    )
    assert record.status == ApiIdempotencyRecord.Status.COMPLETED
    assert record.response_body is None
    assert "employee-secret" not in str(record.__dict__)
    ticket.refresh_from_db()
    assert ticket.status == DeliveryTicket.Status.CONSUMED
    assert ticket.attempt_count == 1


def test_delivery_rejects_cross_user_key_and_legacy_no_id_endpoint(
    employee_context, user_factory, cloud_identity_factory, access_key_factory
):
    client, user, pool, _config = employee_context
    other = user_factory()
    identity = cloud_identity_factory(user=other, resource_pool=pool)
    key = access_key_factory(cloud_identity=identity)

    response = client.post(
        "/api/v1/object-storage/workspace/credentials/deliver/",
        {},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="legacy-delivery-endpoint",
    )
    cross_user = client.post(
        f"/api/v1/object-storage/workspace/credentials/{key.id}/deliver/",
        {},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="cross-user-delivery",
    )

    assert response.status_code == 404
    assert cross_user.status_code == 404


def test_single_key_rotation_creates_one_time_delivery_batch(
    employee_context, cloud_identity_factory, monkeypatch
):
    from object_storage.models import AccessKey, ApplicationBatch, DeliveryTicket

    client, user, pool, _config = employee_context
    identity = cloud_identity_factory(user=user, resource_pool=pool, state="active")
    selected = _key(identity, 31)
    replacement = _key(identity, 32)
    replacement.local_state = AccessKey.LocalState.DELIVERY_READY
    replacement.save(update_fields=("local_state", "updated_at"))
    monkeypatch.setattr(
        "object_storage.views_employee.rotate_access_key_action",
        lambda **kwargs: replacement,
    )

    response = client.post(
        f"/api/v1/object-storage/workspace/credentials/{selected.id}/rotate/",
        {},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="rotate-delivery-1",
    )

    payload = _payload(response)
    batch = ApplicationBatch.objects.get(pk=payload["delivery_application_id"])
    ticket = DeliveryTicket.objects.get(application_batch=batch)
    assert response.status_code == 200
    assert batch.applicant == user
    assert batch.issued_access_key == replacement
    assert ticket.access_key == replacement
    assert "access_key_id" not in payload
    assert "secret_access_key" not in payload


def test_single_existing_key_rotation_does_not_select_retirement_candidate(
    employee_context, cloud_identity_factory, monkeypatch
):
    from object_storage import views_employee

    _client, user, pool, _config = employee_context
    identity = cloud_identity_factory(user=user, resource_pool=pool, state="active")
    selected = _key(identity, 41)
    captured = {}
    monkeypatch.setattr(views_employee, "_provider", lambda access_key: object())

    def rotate(**kwargs):
        captured.update(kwargs)
        return selected

    monkeypatch.setattr(views_employee, "rotate_access_key_for_actor", rotate)

    views_employee.rotate_access_key_action(access_key=selected, actor=user)

    assert captured["selected_access_key_id"] is None


def test_bucket_release_and_recover_are_owner_scoped(
    employee_context, cloud_identity_factory, bucket_factory, monkeypatch
):
    client, user, pool, _config = employee_context
    identity = cloud_identity_factory(user=user, resource_pool=pool, state="active")
    bucket = bucket_factory(
        cloud_identity=identity,
        state="active",
        pending_delete_at=timezone.now(),
    )
    calls = []

    def operation(**kwargs):
        calls.append(kwargs)
        return bucket

    monkeypatch.setattr("object_storage.views_employee.release_bucket", operation)
    monkeypatch.setattr("object_storage.views_employee.recover_bucket", operation)
    body = {"bucket_name": bucket.name, "confirmed": True, "reason": "cleanup"}

    released = client.post(
        f"/api/v1/object-storage/workspace/buckets/{bucket.id}/release/",
        body,
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="release-bucket-1",
    )
    recovered = client.post(
        f"/api/v1/object-storage/workspace/buckets/{bucket.id}/recover/",
        body,
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="recover-bucket-1",
    )

    assert released.status_code == 202
    assert recovered.status_code == 200
    assert all(call["actor"] == user for call in calls)


def test_paused_platform_returns_stable_domain_codes(employee_context):
    client, _user, _pool, config = employee_context
    config.pause_new_applications = True
    config.pause_key_operations = True
    config.save()

    application = client.post(
        "/api/v1/object-storage/workspace/applications/",
        {"items": []},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="paused-application",
    )

    assert application.status_code == 409
    assert _payload(application)["error_code"] == "NEW_APPLICATIONS_PAUSED"
