import pytest

from object_storage.crypto import encrypt_secret

pytestmark = pytest.mark.django_db


def _payload(response):
    body = response.json()
    return body.get("data", body)


@pytest.fixture(autouse=True)
def stable_secret(settings):
    settings.SECRET_KEY = "employee-read-contract-stable-secret"


@pytest.fixture
def ready_platform(platform_object_storage_config, storage_resource_pool_factory):
    from object_storage.models import PlatformFeishuConfig, StorageResourcePool

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
    return storage_resource_pool_factory(
        enabled=True,
        validation_status=StorageResourcePool.ValidationStatus.VALID,
    )


def _key(identity, number):
    from object_storage.models import AccessKey

    return AccessKey.objects.create(
        cloud_identity=identity,
        access_key_id_encrypted=encrypt_secret(f"LTAI-employee-{number}"),
        secret_access_key_encrypted=encrypt_secret(f"employee-secret-{number}"),
        access_key_fingerprint=f"employee-fingerprint-{number}",
        access_key_last_four=f"{number:04d}",
        local_state=AccessKey.LocalState.ACTIVE,
    )


def test_employee_reads_are_owner_scoped_and_secret_free(
    client,
    ready_platform,
    user_factory,
    cloud_identity_factory,
    bucket_factory,
    application_batch_factory,
):
    user = user_factory()
    other = user_factory()
    own_identity = cloud_identity_factory(user=user, resource_pool=ready_platform)
    other_identity = cloud_identity_factory(user=other, resource_pool=ready_platform)
    own_bucket = bucket_factory(cloud_identity=own_identity)
    other_bucket = bucket_factory(cloud_identity=other_identity)
    own_key = _key(own_identity, 1)
    other_key = _key(other_identity, 2)
    own_batch = application_batch_factory(applicant=user, item_count=2)
    other_batch = application_batch_factory(applicant=other, item_count=1)
    client.force_login(user)

    overview = client.get("/api/v1/object-storage/workspace/overview/")
    buckets = client.get("/api/v1/object-storage/workspace/buckets/")
    credentials = client.get("/api/v1/object-storage/workspace/credentials/")
    applications = client.get("/api/v1/object-storage/workspace/applications/")

    assert overview.status_code == 200
    assert [row["id"] for row in _payload(overview)["buckets"]] == [own_bucket.id]
    assert [row["id"] for row in _payload(buckets)] == [own_bucket.id]
    assert [row["id"] for row in _payload(credentials)] == [own_key.id]
    assert [row["id"] for row in _payload(applications)] == [own_batch.id]
    serialized = " ".join(
        response.content.decode() for response in (overview, buckets, credentials)
    )
    assert "LTAI-employee" not in serialized
    assert "employee-secret" not in serialized
    assert "encrypted" not in serialized
    assert other_bucket.id not in [row["id"] for row in _payload(buckets)]
    assert other_key.id not in [row["id"] for row in _payload(credentials)]
    assert other_batch.id not in [row["id"] for row in _payload(applications)]


def test_employee_detail_endpoints_hide_cross_user_resources(
    client, ready_platform, user_factory, cloud_identity_factory, bucket_factory
):
    user = user_factory()
    other_identity = cloud_identity_factory(
        user=user_factory(), resource_pool=ready_platform
    )
    bucket = bucket_factory(cloud_identity=other_identity)
    key = _key(other_identity, 9)
    client.force_login(user)

    bucket_response = client.get(
        f"/api/v1/object-storage/workspace/buckets/{bucket.id}/"
    )
    key_response = client.get(f"/api/v1/object-storage/workspace/credentials/{key.id}/")

    assert bucket_response.status_code == 404
    assert key_response.status_code == 404
    assert "employee-secret-9" not in key_response.content.decode()


def test_employee_application_detail_exposes_partial_item_statuses_only_to_owner(
    client, ready_platform, user_factory, application_batch_factory
):
    from object_storage.models import (
        ApplicationAttempt,
        ApplicationBatch,
        ApplicationEvent,
        ApplicationItem,
    )

    user = user_factory()
    batch = application_batch_factory(
        applicant=user,
        item_count=2,
        status=ApplicationBatch.Status.PARTIALLY_SUCCEEDED,
        success_count=1,
        failed_count=1,
        pending_count=0,
    )
    first, second = batch.items.order_by("id")
    first.status = ApplicationItem.Status.SUCCEEDED
    first.save(update_fields=("status", "updated_at"))
    second.status = ApplicationItem.Status.FAILED
    second.error_code = "BUCKET_CREATE_FAILED"
    second.error_summary = "provider traceback must stay private"
    second.save(update_fields=("status", "error_code", "error_summary", "updated_at"))
    attempt = ApplicationAttempt.objects.create(
        application_item=second,
        attempt_number=1,
        status=ApplicationAttempt.Status.FAILED,
        provider_request_id="employee-must-not-see-provider-request",
        error_code="BUCKET_CREATE_FAILED",
    )
    ApplicationEvent.objects.create(
        application_item=second,
        attempt=attempt,
        stage="BUCKET_CREATING",
        result="failed",
        error_code="BUCKET_CREATE_FAILED",
        safe_metadata={"region": "cn-hangzhou"},
    )
    client.force_login(user)

    response = client.get(f"/api/v1/object-storage/workspace/applications/{batch.id}/")
    payload = _payload(response)

    assert response.status_code == 200
    assert payload["status"] == ApplicationBatch.Status.PARTIALLY_SUCCEEDED
    assert payload["counts"] == {"total": 2, "pending": 0, "succeeded": 1, "failed": 1}
    assert [item["status"] for item in payload["items"]] == [
        ApplicationItem.Status.SUCCEEDED,
        ApplicationItem.Status.FAILED,
    ]
    assert payload["items"][1]["error_code"] == "BUCKET_CREATE_FAILED"
    assert payload["items"][1]["attempts"][0]["attempt_number"] == 1
    assert payload["items"][1]["events"][0]["safe_metadata"] == {
        "region": "cn-hangzhou"
    }
    assert "provider_request_id" not in payload["items"][1]["attempts"][0]
    assert "traceback" not in response.content.decode().lower()


def test_tenant_scope_query_is_rejected(client, ready_platform, user_factory):
    user = user_factory()
    client.force_login(user)

    response = client.get("/api/v1/object-storage/workspace/buckets/?tenant_id=123")

    assert response.status_code == 400
    assert _payload(response)["error_code"] == "TENANT_SCOPE_UNSUPPORTED"


def test_unconfigured_and_suspended_states_have_stable_codes(
    client, user_factory, cloud_identity_factory, storage_resource_pool_factory
):
    from object_storage.models import CloudIdentity, PlatformFeishuConfig

    unconfigured = user_factory()
    client.force_login(unconfigured)
    missing = client.get("/api/v1/object-storage/workspace/overview/")

    PlatformFeishuConfig.objects.update_or_create(
        singleton_key="default",
        defaults={"enabled": True, "validation_status": "valid"},
    )
    pool = storage_resource_pool_factory(enabled=True, validation_status="valid")
    suspended = user_factory()
    cloud_identity_factory(
        user=suspended,
        resource_pool=pool,
        state=CloudIdentity.State.SUSPENDED,
    )
    client.force_login(suspended)
    blocked = client.get("/api/v1/object-storage/workspace/overview/")

    assert missing.status_code == 403
    assert _payload(missing)["error_code"] == "OBJECT_STORAGE_NOT_CONFIGURED"
    assert blocked.status_code == 403
    assert _payload(blocked)["error_code"] == "OBJECT_STORAGE_SUSPENDED"


def test_configured_platform_without_employee_feature_is_denied(
    client, ready_platform, user_factory
):
    user = user_factory()
    user.platform_roles.clear()
    client.force_login(user)

    response = client.get("/api/v1/object-storage/workspace/overview/")

    assert response.status_code == 403
