import pytest

from object_storage.models import (
    StorageAccessKey,
    StorageApplication,
    StorageApplicationAttempt,
    StorageApplicationEvent,
)
from object_storage.tests.test_employee_api import _create_key

pytestmark = pytest.mark.django_db


def _payload(response):
    body = response.json()
    return body.get("data", body)


@pytest.fixture(autouse=True)
def stable_object_storage_secret(settings):
    settings.SECRET_KEY = "object-storage-employee-read-tests-stable-secret"


@pytest.fixture
def member_client(client, storage_membership_factory, storage_resource_pool_factory):
    membership = storage_membership_factory()
    storage_resource_pool_factory(tenant=membership.tenant, enabled=True)
    client.force_login(membership.user)
    return client, membership


def test_employee_overview_returns_owned_resources_and_quota(
    member_client, storage_cloud_identity_factory, storage_bucket_factory
):
    client, membership = member_client
    identity = storage_cloud_identity_factory(membership=membership)
    bucket = storage_bucket_factory(cloud_identity=identity)
    key = _create_key(identity, 1)

    response = client.get("/api/v1/object-storage/workspace/overview/")

    payload = _payload(response)
    assert response.status_code == 200
    assert payload["quota"] == {
        "used": 1,
        "limit": membership.tenant.default_bucket_quota,
    }
    assert payload["cloud_identity"]["ram_user_name"] == identity.ram_user_name
    assert payload["buckets"][0]["id"] == bucket.id
    assert payload["credentials"][0]["id"] == key.id
    assert "access_key_id_encrypted" not in str(payload)
    assert "secret_access_key" not in str(payload)


def test_employee_application_list_and_detail_are_owner_scoped(
    member_client, storage_membership_factory, storage_resource_pool_factory
):
    client, membership = member_client
    other = storage_membership_factory(tenant=membership.tenant)
    pool = storage_resource_pool_factory(tenant=membership.tenant)
    own = StorageApplication.objects.create(
        tenant=membership.tenant,
        applicant=membership,
        action_type=StorageApplication.ActionType.ADD_BUCKET,
        idempotency_key="own-read",
        request_fields={"project": "safe-project", "environment": "test"},
        status=StorageApplication.Status.FAILED,
        error_code="PROVIDER_TIMEOUT",
        error_summary="The provider did not respond in time.",
    )
    other_application = StorageApplication.objects.create(
        tenant=other.tenant,
        applicant=other,
        action_type=StorageApplication.ActionType.ADD_BUCKET,
        idempotency_key="other-read",
        request_fields={"project": "other-project", "resource_pool_id": pool.id},
    )
    attempt = StorageApplicationAttempt.objects.create(
        tenant=membership.tenant,
        application=own,
        attempt_number=1,
        status=StorageApplicationAttempt.Status.FAILED,
        error_code="PROVIDER_TIMEOUT",
        provider_request_id="safe-request-id",
    )
    StorageApplicationEvent.objects.create(
        tenant=membership.tenant,
        application=own,
        attempt=attempt,
        stage="BUCKET_CREATING",
        result="failed",
        error_code="PROVIDER_TIMEOUT",
        safe_metadata={"region": "cn-hangzhou"},
    )

    response = client.get("/api/v1/object-storage/workspace/applications/")
    payload = _payload(response)

    assert response.status_code == 200
    assert [row["id"] for row in payload] == [own.id]
    assert other_application.id not in [row["id"] for row in payload]
    assert "request_fields" not in str(payload)

    detail = client.get(f"/api/v1/object-storage/workspace/applications/{own.id}/")
    detail_payload = _payload(detail)

    assert detail.status_code == 200
    assert detail_payload["attempts"][0]["error_code"] == "PROVIDER_TIMEOUT"
    assert "provider_request_id" not in detail_payload["attempts"][0]
    assert detail_payload["events"][0]["safe_metadata"] == {"region": "cn-hangzhou"}

    forbidden = client.get(
        f"/api/v1/object-storage/workspace/applications/{other_application.id}/"
    )
    assert forbidden.status_code == 404


def test_employee_overview_does_not_return_retired_key_as_active(
    member_client, storage_cloud_identity_factory
):
    client, membership = member_client
    identity = storage_cloud_identity_factory(membership=membership)
    _create_key(
        identity,
        1,
        local_state=StorageAccessKey.LocalState.RETIRED,
        cloud_state=StorageAccessKey.CloudState.INACTIVE,
    )

    response = client.get("/api/v1/object-storage/workspace/overview/")

    payload = _payload(response)
    assert response.status_code == 200
    assert (
        payload["credentials"][0]["local_state"] == StorageAccessKey.LocalState.RETIRED
    )


def test_employee_can_retry_owned_failed_application_once(
    member_client,
    storage_membership_factory,
    monkeypatch,
):
    client, membership = member_client
    other = storage_membership_factory(tenant=membership.tenant)
    application = StorageApplication.objects.create(
        tenant=membership.tenant,
        applicant=membership,
        action_type=StorageApplication.ActionType.ADD_BUCKET,
        idempotency_key="employee-retry-source",
        status=StorageApplication.Status.FAILED,
        error_code="PROVIDER_TIMEOUT",
    )
    other_application = StorageApplication.objects.create(
        tenant=other.tenant,
        applicant=other,
        action_type=StorageApplication.ActionType.ADD_BUCKET,
        idempotency_key="other-retry-source",
        status=StorageApplication.Status.FAILED,
    )
    queued = []
    monkeypatch.setattr(
        "object_storage.tasks.run_storage_application.delay", queued.append
    )
    url = f"/api/v1/object-storage/workspace/applications/{application.id}/retry/"

    response = client.post(
        url,
        {},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="employee-retry-request",
    )
    duplicate = client.post(
        url,
        {},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="employee-retry-request",
    )
    forbidden = client.post(
        f"/api/v1/object-storage/workspace/applications/{other_application.id}/retry/",
        {},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="employee-other-retry",
    )

    application.refresh_from_db()
    assert response.status_code == 202
    assert duplicate.status_code == 202
    assert forbidden.status_code == 404
    assert application.status == StorageApplication.Status.PENDING
    assert application.error_code == ""
    assert queued == [application.id]


def test_employee_retry_enqueue_failure_returns_to_manual_required(
    member_client,
    monkeypatch,
):
    client, membership = member_client
    application = StorageApplication.objects.create(
        tenant=membership.tenant,
        applicant=membership,
        action_type=StorageApplication.ActionType.ADD_BUCKET,
        idempotency_key="employee-retry-broker-source",
        status=StorageApplication.Status.FAILED,
    )
    monkeypatch.setattr(
        "object_storage.tasks.run_storage_application.delay",
        lambda application_id: (_ for _ in ()).throw(ConnectionError("broker down")),
    )

    response = client.post(
        f"/api/v1/object-storage/workspace/applications/{application.id}/retry/",
        {},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="employee-retry-broker-request",
    )

    application.refresh_from_db()
    assert response.status_code == 503
    assert application.status == StorageApplication.Status.MANUAL_REQUIRED
    assert application.error_code == "TASK_ENQUEUE_FAILED"
    assert application.tenant.audit_events.filter(
        application=application,
        action="storage.application.employee_retry_enqueue_failed",
        request_id="employee-retry-broker-request",
    ).exists()
