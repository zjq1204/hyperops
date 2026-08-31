from types import SimpleNamespace

import pytest

from object_storage.crypto import encrypt_secret

pytestmark = pytest.mark.django_db


def _payload(response):
    body = response.json()
    return body.get("data", body)


@pytest.fixture(autouse=True)
def stable_object_storage_secret(settings):
    settings.SECRET_KEY = "object-storage-employee-tests-stable-secret"


@pytest.fixture
def member_client(client, storage_membership_factory, storage_resource_pool_factory):
    membership = storage_membership_factory()
    storage_resource_pool_factory(tenant=membership.tenant, enabled=True)
    client.force_login(membership.user)
    return client, membership


@pytest.fixture
def superuser_client(client, django_user_model):
    user = django_user_model.objects.create_superuser(
        username="object-storage-root", password="secret123"
    )
    client.force_login(user)
    client.defaults["HTTP_IDEMPOTENCY_KEY"] = "employee-admin-test"
    return client


def _create_key(identity, number, *, local_state="active", cloud_state="active"):
    from object_storage.models import StorageAccessKey

    return StorageAccessKey.objects.create(
        tenant=identity.tenant,
        cloud_identity=identity,
        access_key_id_encrypted=encrypt_secret(f"LTAI-key-{number}"),
        secret_access_key_encrypted=encrypt_secret(f"secret-{number}"),
        access_key_fingerprint=f"fingerprint-{number}",
        access_key_last_four=f"{number:04d}",
        local_state=local_state,
        cloud_state=cloud_state,
    )


def test_employee_can_only_list_owned_buckets(
    member_client,
    storage_bucket_factory,
    storage_cloud_identity_factory,
    storage_membership_factory,
):
    client, membership = member_client
    mine_identity = storage_cloud_identity_factory(membership=membership)
    mine = storage_bucket_factory(cloud_identity=mine_identity)
    other = storage_membership_factory(tenant=membership.tenant)
    other_identity = storage_cloud_identity_factory(
        membership=other,
        resource_pool=mine_identity.resource_pool,
    )
    other_bucket = storage_bucket_factory(cloud_identity=other_identity)

    response = client.get("/api/v1/object-storage/workspace/buckets/")

    assert response.status_code == 200
    assert [row["id"] for row in _payload(response)] == [mine.id]
    assert other_bucket.id not in [row["id"] for row in _payload(response)]


def test_new_bucket_reuses_existing_key_after_all_old_buckets_are_released(
    member_client,
    storage_cloud_identity_factory,
    monkeypatch,
):
    from object_storage.models import StorageApplication, StorageResourcePool

    client, membership = member_client
    pool = StorageResourcePool.objects.get(tenant=membership.tenant, enabled=True)
    identity = storage_cloud_identity_factory(
        membership=membership,
        resource_pool=pool,
    )
    _create_key(identity, 1)
    queued = []
    monkeypatch.setattr(
        "object_storage.tasks.run_storage_application.delay", queued.append
    )

    response = client.post(
        "/api/v1/object-storage/workspace/applications/",
        {"project": "new", "environment": "test", "purpose": "data"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="add-after-release",
    )

    application = StorageApplication.objects.get(idempotency_key="add-after-release")
    assert response.status_code == 202
    assert application.action_type == StorageApplication.ActionType.ADD_BUCKET


def test_employee_cannot_read_another_members_credential(
    member_client, storage_cloud_identity_factory, storage_membership_factory
):
    client, membership = member_client
    other_member = storage_membership_factory(tenant=membership.tenant)
    other_identity = storage_cloud_identity_factory(membership=other_member)
    key = _create_key(other_identity, 1)

    response = client.get(f"/api/v1/object-storage/workspace/credentials/{key.id}/")

    assert response.status_code == 404
    assert "secret_access_key" not in _payload(response)


def test_suspended_member_cannot_apply_or_retrieve(
    member_client, storage_cloud_identity_factory
):
    client, membership = member_client
    membership.is_active = False
    membership.save(update_fields=("is_active",))
    identity = storage_cloud_identity_factory(membership=membership)
    key = _create_key(identity, 1)

    buckets = client.get("/api/v1/object-storage/workspace/buckets/")
    credentials = client.get(f"/api/v1/object-storage/workspace/credentials/{key.id}/")
    application = client.post(
        "/api/v1/object-storage/workspace/applications/",
        {
            "action_type": "add_bucket",
            "project": "app",
            "environment": "test",
            "purpose": "data",
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="suspended-application",
    )

    assert buckets.status_code == 403
    assert credentials.status_code == 403
    assert application.status_code == 403


def test_non_superuser_cannot_reveal_secret(
    member_client, storage_cloud_identity_factory
):
    client, membership = member_client
    identity = storage_cloud_identity_factory(membership=membership)
    key = _create_key(identity, 1)

    response = client.post(
        f"/api/v1/object-storage/management/access-keys/{key.id}/reveal/",
        {"reason": "support investigation"},
        content_type="application/json",
    )

    assert response.status_code == 403
    assert "secret_access_key" not in _payload(response)


def test_superuser_reveal_requires_reason_and_returns_one_key(
    superuser_client, storage_cloud_identity_factory
):
    identity = storage_cloud_identity_factory()
    key = _create_key(identity, 1)
    url = f"/api/v1/object-storage/management/access-keys/{key.id}/reveal/"

    missing_reason = superuser_client.post(url, {}, content_type="application/json")
    revealed = superuser_client.post(
        url,
        {"reason": "incident investigation"},
        content_type="application/json",
    )

    assert missing_reason.status_code == 400
    assert missing_reason["Cache-Control"] == "no-store"
    assert revealed.status_code == 200
    assert _payload(revealed)["access_key_id"] == "LTAI-key-1"
    assert _payload(revealed)["secret_access_key"] == "secret-1"
    assert revealed["Cache-Control"] == "no-store"


def test_rotation_with_two_active_keys_proposes_oldest_key(
    member_client, storage_cloud_identity_factory
):
    client, membership = member_client
    identity = storage_cloud_identity_factory(membership=membership)
    oldest = _create_key(identity, 1)
    newest = _create_key(identity, 2)

    response = client.get(
        "/api/v1/object-storage/workspace/credentials/rotation-preview/"
    )

    assert response.status_code == 200
    assert _payload(response)["candidate"]["id"] == oldest.id
    assert _payload(response)["candidate"]["last_four"] == oldest.access_key_last_four
    assert "secret_access_key" not in _payload(response)


def test_nonempty_bucket_release_is_rejected(
    member_client, storage_bucket_factory, storage_cloud_identity_factory, monkeypatch
):
    client, membership = member_client
    identity = storage_cloud_identity_factory(membership=membership)
    bucket = storage_bucket_factory(cloud_identity=identity)
    monkeypatch.setattr(
        "object_storage.views_employee.get_provider_for_pool",
        lambda pool: SimpleNamespace(
            inspect_bucket_emptiness=lambda selected: SimpleNamespace(
                is_empty=False,
                object_count=1,
                version_count=0,
                delete_marker_count=0,
                multipart_upload_count=0,
            )
        ),
    )

    response = client.post(
        f"/api/v1/object-storage/workspace/buckets/{bucket.id}/release/",
        {"reason": "cleanup"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="release-nonempty",
    )

    assert response.status_code == 409
    assert _payload(response)["error_code"] == "BUCKET_NOT_EMPTY"


def test_empty_bucket_release_creates_async_application(
    member_client,
    storage_bucket_factory,
    storage_cloud_identity_factory,
    monkeypatch,
):
    from object_storage.models import StorageApplication

    client, membership = member_client
    identity = storage_cloud_identity_factory(membership=membership)
    bucket = storage_bucket_factory(cloud_identity=identity)
    queued = []
    monkeypatch.setattr(
        "object_storage.views_employee.get_provider_for_pool",
        lambda pool: SimpleNamespace(
            inspect_bucket_emptiness=lambda selected: SimpleNamespace(is_empty=True)
        ),
    )
    monkeypatch.setattr(
        "object_storage.tasks.run_storage_application.delay", queued.append
    )

    response = client.post(
        f"/api/v1/object-storage/workspace/buckets/{bucket.id}/release/",
        {"bucket_name": bucket.name, "reason": "project complete"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="release-empty",
    )

    application = StorageApplication.objects.get(idempotency_key="release-empty")
    assert response.status_code == 202
    assert application.action_type == StorageApplication.ActionType.RELEASE_BUCKET
    assert application.request_fields["target_bucket_id"] == bucket.id
    assert queued == [application.id]


def test_confirmed_rotation_creates_async_application(
    member_client, storage_cloud_identity_factory, monkeypatch
):
    from object_storage.models import StorageApplication, StorageResourcePool

    client, membership = member_client
    pool = StorageResourcePool.objects.get(tenant=membership.tenant, enabled=True)
    identity = storage_cloud_identity_factory(
        membership=membership,
        resource_pool=pool,
    )
    oldest = _create_key(identity, 1)
    _create_key(identity, 2)
    queued = []
    monkeypatch.setattr(
        "object_storage.tasks.run_storage_application.delay", queued.append
    )

    response = client.post(
        "/api/v1/object-storage/workspace/credentials/rotation-preview/",
        {"candidate_access_key_id": oldest.id, "confirmed": True},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="rotate-two-keys",
    )
    duplicate = client.post(
        "/api/v1/object-storage/workspace/credentials/rotation-preview/",
        {"candidate_access_key_id": oldest.id, "confirmed": True},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="rotate-two-keys",
    )

    application = StorageApplication.objects.get(idempotency_key="rotate-two-keys")
    assert response.status_code == 202
    assert duplicate.status_code == 202
    assert application.action_type == StorageApplication.ActionType.ROTATE_CREDENTIAL
    assert application.request_fields["candidate_access_key_id"] == oldest.id
    assert queued == [application.id]


def test_superuser_suspends_and_reactivates_member_without_reenabling_key(
    superuser_client,
    storage_cloud_identity_factory,
    monkeypatch,
):
    from object_storage.models import StorageAccessKey, StorageApplication

    identity = storage_cloud_identity_factory()
    membership = identity.membership
    key = _create_key(
        identity,
        1,
        local_state=StorageAccessKey.LocalState.RETIRED,
        cloud_state=StorageAccessKey.CloudState.INACTIVE,
    )
    queued = []
    monkeypatch.setattr(
        "object_storage.tasks.run_storage_application.delay", queued.append
    )

    suspended = superuser_client.post(
        f"/api/v1/object-storage/management/members/{membership.id}/suspend/",
        {"reason": "employee departure"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="suspend-member",
    )
    membership.refresh_from_db()
    assert suspended.status_code == 202
    assert membership.is_active is False

    reactivated = superuser_client.post(
        f"/api/v1/object-storage/management/members/{membership.id}/reactivate/",
        {"reason": "employee returned"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="reactivate-member",
    )
    membership.refresh_from_db()
    key.refresh_from_db()

    assert reactivated.status_code == 202
    assert membership.is_active is True
    assert key.cloud_state == StorageAccessKey.CloudState.INACTIVE
    assert StorageApplication.objects.filter(applicant=membership).count() == 2
    assert len(queued) == 2

    duplicate_suspend = superuser_client.post(
        f"/api/v1/object-storage/management/members/{membership.id}/suspend/",
        {"reason": "employee departure"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="suspend-member",
    )
    membership.refresh_from_db()

    assert duplicate_suspend.status_code == 202
    assert membership.is_active is True
    assert len(queued) == 2


def test_state_change_without_idempotency_key_does_not_change_member(
    superuser_client, storage_cloud_identity_factory
):
    identity = storage_cloud_identity_factory()
    membership = identity.membership
    superuser_client.defaults.pop("HTTP_IDEMPOTENCY_KEY", None)

    response = superuser_client.post(
        f"/api/v1/object-storage/management/members/{membership.id}/suspend/",
        {"reason": "employee departure"},
        content_type="application/json",
    )

    membership.refresh_from_db()
    assert response.status_code == 400
    assert membership.is_active is True


def test_superuser_can_suspend_member_without_cloud_identity(
    superuser_client,
    storage_membership_factory,
    storage_resource_pool_factory,
    monkeypatch,
):
    membership = storage_membership_factory()
    storage_resource_pool_factory(tenant=membership.tenant, enabled=True)
    queued = []
    monkeypatch.setattr(
        "object_storage.tasks.run_storage_application.delay", queued.append
    )

    response = superuser_client.post(
        f"/api/v1/object-storage/management/members/{membership.id}/suspend/",
        {"reason": "employee departure"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="suspend-without-cloud-identity",
    )

    membership.refresh_from_db()
    assert response.status_code == 202
    assert membership.is_active is False
    assert len(queued) == 1
