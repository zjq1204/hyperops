import pytest

from object_storage.crypto import encrypt_secret

pytestmark = pytest.mark.django_db


def _payload(response):
    body = response.json()
    return body.get("data", body)


@pytest.fixture(autouse=True)
def stable_object_storage_secret(settings):
    settings.SECRET_KEY = "object-storage-security-regression-secret"


@pytest.fixture
def member_client(client, user_factory, storage_resource_pool_factory):
    user = user_factory()
    storage_resource_pool_factory(enabled=True)
    client.force_login(user)
    return client, user


@pytest.fixture
def superuser_client(client, django_user_model):
    admin = django_user_model.objects.create_superuser(
        username="object-storage-security-admin",
        password="secret123",
    )
    client.force_login(admin)
    return client, admin


def _create_key(identity, number):
    from object_storage.models import AccessKey

    return AccessKey.objects.create(
        cloud_identity=identity,
        access_key_id_encrypted=encrypt_secret(f"LTAI-security-{number}"),
        secret_access_key_encrypted=encrypt_secret(f"security-secret-{number}"),
        access_key_fingerprint=f"security-fingerprint-{number}",
        access_key_last_four=f"{number:04d}",
    )


def test_employee_object_storage_views_are_owner_scoped(
    member_client,
    cloud_identity_factory,
    bucket_factory,
    user_factory,
):
    client, user = member_client
    own_identity = cloud_identity_factory(user=user)
    own_bucket = bucket_factory(cloud_identity=own_identity)
    own_key = _create_key(own_identity, 1)

    other_identity = cloud_identity_factory(
        user=user_factory(),
        resource_pool=own_identity.resource_pool,
    )
    other_bucket = bucket_factory(cloud_identity=other_identity)
    other_key = _create_key(other_identity, 2)

    overview = client.get("/api/v1/object-storage/workspace/overview/")
    buckets = client.get("/api/v1/object-storage/workspace/buckets/")
    own_credential = client.get(
        f"/api/v1/object-storage/workspace/credentials/{own_key.id}/"
    )
    other_credential = client.get(
        f"/api/v1/object-storage/workspace/credentials/{other_key.id}/"
    )

    assert overview.status_code == 200
    assert [row["id"] for row in _payload(overview)["buckets"]] == [own_bucket.id]
    assert [row["id"] for row in _payload(overview)["credentials"]] == [own_key.id]
    assert "secret_access_key" not in str(_payload(overview))
    assert buckets.status_code == 200
    assert [row["id"] for row in _payload(buckets)] == [own_bucket.id]
    assert own_credential.status_code == 200
    assert _payload(own_credential)["id"] == own_key.id
    assert "secret_access_key" not in str(_payload(own_credential))
    assert other_bucket.id not in [row["id"] for row in _payload(buckets)]
    assert other_credential.status_code == 404


def test_encrypted_credentials_and_audit_metadata_do_not_store_plaintext(
    superuser_client, cloud_identity_factory
):
    from object_storage.models import AuditEvent

    client, admin = superuser_client
    identity = cloud_identity_factory()
    key = _create_key(identity, 7)
    access_key = "LTAI-security-7"
    secret_key = "security-secret-7"

    response = client.get("/api/v1/object-storage/management/access-keys/")
    audit = AuditEvent.objects.create(
        actor=admin,
        action="storage.security.regression",
        target_type="AccessKey",
        target_id=key.id,
        result="succeeded",
        safe_metadata={"last_four": key.access_key_last_four},
    )

    key.refresh_from_db()
    assert response.status_code == 200
    assert access_key not in key.access_key_id_encrypted
    assert secret_key not in key.secret_access_key_encrypted
    assert access_key not in response.content.decode()
    assert secret_key not in response.content.decode()
    assert access_key not in str(audit.safe_metadata)
    assert secret_key not in str(audit.safe_metadata)
