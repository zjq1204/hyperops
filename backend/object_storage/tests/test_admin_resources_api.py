import pytest
from django.utils import timezone

from object_storage.crypto import encrypt_secret

pytestmark = pytest.mark.django_db


def _payload(response):
    body = response.json()
    return body.get("data", body)


def _rows(response):
    payload = _payload(response)
    return payload.get("results", payload) if isinstance(payload, dict) else payload


@pytest.fixture(autouse=True)
def stable_object_storage_secret(settings):
    settings.SECRET_KEY = "object-storage-admin-resources-stable-secret"


@pytest.fixture
def superuser_client(client, django_user_model):
    user = django_user_model.objects.create_superuser(
        username="object-storage-admin", password="secret123"
    )
    client.force_login(user)
    return client, user


def _create_key(identity, number=1):
    from object_storage.models import StorageAccessKey

    return StorageAccessKey.objects.create(
        tenant=identity.tenant,
        cloud_identity=identity,
        access_key_id_encrypted=encrypt_secret(f"LTAI-admin-{number}"),
        secret_access_key_encrypted=encrypt_secret(f"admin-secret-{number}"),
        access_key_fingerprint=f"admin-fingerprint-{number}",
        access_key_last_four=f"{number:04d}",
        local_state=StorageAccessKey.LocalState.ACTIVE,
    )


def test_only_superuser_can_list_all_tenants(
    client, django_user_model, storage_tenant_factory
):
    storage_tenant_factory()
    user = django_user_model.objects.create_user(username="ordinary-resource-admin")
    client.force_login(user)

    response = client.get("/api/v1/object-storage/management/tenants/")

    assert response.status_code == 403


def test_admin_configuration_mutation_requires_idempotency_key(superuser_client):
    client, _admin = superuser_client

    response = client.post(
        "/api/v1/object-storage/management/tenants/",
        {
            "code": "missing-idempotency",
            "name": "Missing Idempotency",
            "delivery_lifetime_seconds": 86400,
        },
        content_type="application/json",
    )

    assert response.status_code == 400


def test_admin_can_suspend_member_without_deleting_bucket_data(
    superuser_client,
    storage_cloud_identity_factory,
    storage_bucket_factory,
    monkeypatch,
):
    client, _admin = superuser_client
    identity = storage_cloud_identity_factory()
    membership = identity.membership
    bucket = storage_bucket_factory(cloud_identity=identity)
    queued = []
    monkeypatch.setattr(
        "object_storage.tasks.run_storage_application.delay", queued.append
    )

    response = client.post(
        f"/api/v1/object-storage/management/members/{membership.id}/suspend/",
        {"reason": "employee departure"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="admin-suspend-member",
    )

    membership.refresh_from_db()
    bucket.refresh_from_db()
    assert response.status_code == 202
    assert membership.is_active is False
    assert bucket.pk is not None
    assert queued


def test_admin_can_retry_manual_required_application(
    superuser_client,
    storage_membership_factory,
    storage_resource_pool_factory,
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    from object_storage.models import StorageApplication, StorageApplicationAttempt

    client, _admin = superuser_client
    membership = storage_membership_factory()
    pool = storage_resource_pool_factory(tenant=membership.tenant, enabled=True)
    application = StorageApplication.objects.create(
        tenant=membership.tenant,
        applicant=membership,
        action_type=StorageApplication.ActionType.ADD_BUCKET,
        idempotency_key="failed-application",
        request_fields={"resource_pool_id": pool.pk},
        status=StorageApplication.Status.MANUAL_REQUIRED,
        current_stage="POLICY_APPLYING",
        error_code="PROVIDER_PERMISSION_DENIED",
        finished_at=timezone.now(),
    )
    StorageApplicationAttempt.objects.create(
        tenant=membership.tenant,
        application=application,
        attempt_number=1,
        status=StorageApplicationAttempt.Status.FAILED,
        error_code="PROVIDER_PERMISSION_DENIED",
    )
    queued = []
    monkeypatch.setattr(
        "object_storage.tasks.run_storage_application.delay", queued.append
    )
    url = f"/api/v1/object-storage/management/applications/{application.id}/retry/"

    with django_capture_on_commit_callbacks(execute=True):
        first = client.post(
            url,
            {"reason": "credentials fixed"},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="retry-manual-1",
        )
    duplicate = client.post(
        url,
        {"reason": "credentials fixed"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="retry-manual-1",
    )

    application.refresh_from_db()
    assert first.status_code == 202
    assert duplicate.status_code == 202
    assert application.status == StorageApplication.Status.PENDING
    assert application.error_code == ""
    assert queued == [application.id]


def test_admin_secret_reveal_audits_reason_and_safe_key_metadata(
    superuser_client, storage_cloud_identity_factory
):
    client, admin = superuser_client
    identity = storage_cloud_identity_factory()
    key = _create_key(identity)

    response = client.post(
        f"/api/v1/object-storage/management/access-keys/{key.id}/reveal/",
        {"reason": "incident investigation"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="reveal-key-1",
    )

    event = key.tenant.audit_events.get(action="storage.credential.revealed")
    assert response.status_code == 200
    assert event.actor == admin
    assert event.reason == "incident investigation"
    assert event.safe_metadata == {"last_four": key.access_key_last_four}
    assert "secret" not in str(event.safe_metadata).lower()


def test_admin_secret_reveal_requires_idempotency_and_rejects_replay(
    superuser_client, storage_cloud_identity_factory
):
    client, _admin = superuser_client
    identity = storage_cloud_identity_factory()
    key = _create_key(identity)
    url = f"/api/v1/object-storage/management/access-keys/{key.id}/reveal/"
    payload = {"reason": "incident investigation"}

    missing = client.post(url, payload, content_type="application/json")
    first = client.post(
        url,
        payload,
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="reveal-key-1",
    )
    replay = client.post(
        url,
        payload,
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="reveal-key-1",
    )

    assert missing.status_code == 400
    assert first.status_code == 200
    assert replay.status_code == 409
    assert (
        key.tenant.audit_events.filter(action="storage.credential.revealed").count()
        == 1
    )


def test_admin_retry_broker_failure_restores_manual_required(
    superuser_client,
    storage_membership_factory,
    storage_resource_pool_factory,
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    from object_storage.models import StorageApplication, StorageApplicationAttempt

    client, _admin = superuser_client
    membership = storage_membership_factory()
    pool = storage_resource_pool_factory(tenant=membership.tenant, enabled=True)
    application = StorageApplication.objects.create(
        tenant=membership.tenant,
        applicant=membership,
        action_type=StorageApplication.ActionType.ADD_BUCKET,
        idempotency_key="broker-failure-application",
        request_fields={"resource_pool_id": pool.pk},
        status=StorageApplication.Status.MANUAL_REQUIRED,
        error_code="PROVIDER_PERMISSION_DENIED",
    )
    StorageApplicationAttempt.objects.create(
        tenant=membership.tenant,
        application=application,
        attempt_number=1,
        status=StorageApplicationAttempt.Status.FAILED,
    )
    monkeypatch.setattr(
        "object_storage.tasks.run_storage_application.delay",
        lambda application_id: (_ for _ in ()).throw(ConnectionError("broker down")),
    )

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            f"/api/v1/object-storage/management/applications/{application.id}/retry/",
            {"reason": "credentials fixed"},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="retry-broker-failure",
        )

    application.refresh_from_db()
    assert response.status_code == 503
    assert application.status == StorageApplication.Status.MANUAL_REQUIRED
    assert application.error_code == "TASK_ENQUEUE_FAILED"


def test_admin_responses_never_include_ciphertext(
    superuser_client,
    storage_cloud_identity_factory,
    storage_bucket_factory,
):
    client, _admin = superuser_client
    identity = storage_cloud_identity_factory()
    bucket = storage_bucket_factory(cloud_identity=identity)
    key = _create_key(identity)

    responses = [
        client.get("/api/v1/object-storage/management/members/"),
        client.get("/api/v1/object-storage/management/cloud-identities/"),
        client.get("/api/v1/object-storage/management/buckets/"),
        client.get("/api/v1/object-storage/management/access-keys/"),
    ]

    assert all(response.status_code == 200 for response in responses)
    serialized = " ".join(response.content.decode("utf-8") for response in responses)
    assert key.access_key_id_encrypted not in serialized
    assert key.secret_access_key_encrypted not in serialized
    assert bucket.name in serialized


def test_admin_application_detail_contains_only_safe_attempts_and_events(
    superuser_client, storage_membership_factory, storage_resource_pool_factory
):
    from object_storage.models import (
        StorageApplication,
        StorageApplicationAttempt,
        StorageApplicationEvent,
    )

    client, _admin = superuser_client
    membership = storage_membership_factory()
    pool = storage_resource_pool_factory(tenant=membership.tenant)
    application = StorageApplication.objects.create(
        tenant=membership.tenant,
        applicant=membership,
        action_type=StorageApplication.ActionType.ADD_BUCKET,
        idempotency_key="admin-detail",
        request_fields={"resource_pool_id": pool.pk, "notes": "safe note"},
    )
    attempt = StorageApplicationAttempt.objects.create(
        tenant=membership.tenant,
        application=application,
        attempt_number=1,
        status=StorageApplicationAttempt.Status.FAILED,
        error_code="PROVIDER_TIMEOUT",
        provider_request_id="safe-provider-request",
    )
    StorageApplicationEvent.objects.create(
        tenant=membership.tenant,
        application=application,
        attempt=attempt,
        stage="BUCKET_CREATING",
        result="failed",
        error_code="PROVIDER_TIMEOUT",
    )

    response = client.get(
        f"/api/v1/object-storage/management/applications/{application.id}/"
    )

    payload = _rows(response)
    assert response.status_code == 200
    assert payload["attempts"][0]["provider_request_id"] == "safe-provider-request"
    assert payload["events"][0]["stage"] == "BUCKET_CREATING"
    assert "request_fields" not in payload


def test_admin_audit_search_filters_tenant_and_recent_window(
    superuser_client, storage_tenant_factory
):
    from object_storage.models import StorageAuditEvent

    client, _admin = superuser_client
    tenant = storage_tenant_factory()
    other = storage_tenant_factory()
    StorageAuditEvent.objects.create(
        tenant=tenant,
        action="storage.test.target",
        target_type="StorageBucket",
        target_id="1",
        result="succeeded",
    )
    StorageAuditEvent.objects.create(
        tenant=other,
        action="storage.test.other",
        target_type="StorageBucket",
        target_id="2",
        result="succeeded",
    )

    response = client.get(
        f"/api/v1/object-storage/management/audit-events/?tenant_id={tenant.id}"
    )

    payload = _rows(response)
    assert response.status_code == 200
    assert [row["action"] for row in payload] == ["storage.test.target"]
