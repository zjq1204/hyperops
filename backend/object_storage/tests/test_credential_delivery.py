from datetime import timedelta

import pytest
from django.utils import timezone

pytestmark = pytest.mark.django_db


def _payload(response):
    body = response.json()
    return body.get("data", body)


@pytest.fixture(autouse=True)
def stable_object_storage_secret(settings):
    settings.SECRET_KEY = "object-storage-delivery-tests-stable-secret"


@pytest.fixture
def member_client(client, storage_membership_factory, storage_resource_pool_factory):
    membership = storage_membership_factory()
    storage_resource_pool_factory(tenant=membership.tenant, enabled=True)
    client.force_login(membership.user)
    return client, membership


def test_delivery_ticket_is_single_use_and_no_store(
    member_client, storage_cloud_identity_factory
):
    from object_storage.crypto import encrypt_secret
    from object_storage.models import StorageAccessKey
    from object_storage.services.credentials import create_delivery_ticket

    client, membership = member_client
    identity = storage_cloud_identity_factory(membership=membership)
    key = StorageAccessKey.objects.create(
        tenant=membership.tenant,
        cloud_identity=identity,
        access_key_id_encrypted=encrypt_secret("LTAI-delivery-1234"),
        secret_access_key_encrypted=encrypt_secret("delivery-secret"),
        access_key_fingerprint="delivery-fingerprint",
        access_key_last_four="1234",
        local_state=StorageAccessKey.LocalState.DELIVERY_READY,
    )
    _ticket, raw_token = create_delivery_ticket(
        application=_application(membership, identity.resource_pool),
        access_key=key,
        membership=membership,
        tenant=membership.tenant,
    )

    first = client.post(
        "/api/v1/object-storage/workspace/credentials/deliver/",
        {"token": raw_token},
        content_type="application/json",
    )
    second = client.post(
        "/api/v1/object-storage/workspace/credentials/deliver/",
        {"token": raw_token},
        content_type="application/json",
    )

    assert first.status_code == 200
    assert first["Cache-Control"] == "no-store"
    assert second.status_code == 400
    assert _payload(second)["error_code"] == "DELIVERY_TOKEN_CONSUMED"


def test_delivery_ticket_uses_enterprise_expiry_range(
    member_client, storage_cloud_identity_factory
):
    from object_storage.models import StorageAccessKey
    from object_storage.services.credentials import create_delivery_ticket

    _client, membership = member_client
    identity = storage_cloud_identity_factory(membership=membership)
    key = StorageAccessKey.objects.create(
        tenant=membership.tenant,
        cloud_identity=identity,
        access_key_id_encrypted="id",
        secret_access_key_encrypted="secret",
        access_key_fingerprint="expiry-fingerprint",
        access_key_last_four="4321",
    )
    application = _application(membership, identity.resource_pool)
    before = timezone.now()
    ticket, _raw_token = create_delivery_ticket(
        application=application,
        access_key=key,
        membership=membership,
        tenant=membership.tenant,
    )

    assert (
        before + timedelta(seconds=membership.tenant.delivery_lifetime_seconds)
        <= ticket.expires_at
    )
    assert ticket.expires_at <= timezone.now() + timedelta(
        seconds=membership.tenant.delivery_lifetime_seconds
    )


def test_employee_fetches_ephemeral_delivery_token_for_owned_application(
    member_client,
    storage_cloud_identity_factory,
):
    from object_storage.models import StorageAccessKey
    from object_storage.services.credentials import create_delivery_ticket

    client, membership = member_client
    identity = storage_cloud_identity_factory(membership=membership)
    key = StorageAccessKey.objects.create(
        tenant=membership.tenant,
        cloud_identity=identity,
        access_key_id_encrypted="encrypted-id",
        secret_access_key_encrypted="encrypted-secret",
        access_key_fingerprint="handoff-fingerprint",
        access_key_last_four="9876",
    )
    application = _application(membership, identity.resource_pool)
    _ticket, raw_token = create_delivery_ticket(
        application=application,
        access_key=key,
        membership=membership,
        tenant=membership.tenant,
    )

    response = client.get(
        f"/api/v1/object-storage/workspace/applications/{application.id}/delivery-token/"
    )

    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    assert _payload(response)["token"] == raw_token
    assert raw_token not in application.delivery_ticket.token_digest


def test_missing_delivery_cache_reissues_token_and_digest(
    member_client, storage_cloud_identity_factory
):
    from django.core.cache import cache

    from object_storage.models import StorageAccessKey
    from object_storage.services.credentials import create_delivery_ticket

    client, membership = member_client
    identity = storage_cloud_identity_factory(membership=membership)
    key = StorageAccessKey.objects.create(
        tenant=membership.tenant,
        cloud_identity=identity,
        access_key_id_encrypted="encrypted-id",
        secret_access_key_encrypted="encrypted-secret",
        access_key_fingerprint="reissue-fingerprint",
        access_key_last_four="6789",
    )
    application = _application(membership, identity.resource_pool)
    ticket, original_token = create_delivery_ticket(
        application=application,
        access_key=key,
        membership=membership,
        tenant=membership.tenant,
    )
    original_digest = ticket.token_digest
    cache.clear()

    response = client.get(
        f"/api/v1/object-storage/workspace/applications/{application.id}/delivery-token/"
    )

    ticket.refresh_from_db()
    replacement = _payload(response)["token"]
    assert response.status_code == 200
    assert replacement != original_token
    assert ticket.token_digest != original_digest


def _application(membership, pool):
    from object_storage.models import StorageApplication

    return StorageApplication.objects.create(
        tenant=membership.tenant,
        applicant=membership,
        action_type=StorageApplication.ActionType.FIRST_BUCKET_AND_CREDENTIAL,
        idempotency_key=f"delivery-{membership.pk}-{pool.pk}-{timezone.now().timestamp()}",
        request_fields={"resource_pool_id": pool.pk},
    )
