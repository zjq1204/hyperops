from types import SimpleNamespace

import pytest
from django.core.cache import cache

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def stable_object_storage_secret(settings):
    settings.SECRET_KEY = "object-storage-delivery-tests-stable-secret"


def _encrypted_key(identity, *, access_key_id="LTAI-delivery-1234", state=None):
    from object_storage.models import AccessKey
    from object_storage.services.credentials import encrypt_issued_access_key

    return AccessKey.objects.create(
        cloud_identity=identity,
        local_state=state or AccessKey.LocalState.DELIVERY_READY,
        **encrypt_issued_access_key(
            SimpleNamespace(
                access_key_id=access_key_id,
                secret_access_key="delivery-secret",
            )
        ),
    )


def test_delivery_ticket_is_owned_single_use_and_returns_full_secret_once(
    application_batch_factory, cloud_identity_factory, user_factory
):
    from object_storage.models import AccessKey, DeliveryTicket
    from object_storage.services.credentials import (
        CredentialDeliveryError,
        consume_delivery_token,
        create_delivery_ticket,
    )

    identity = cloud_identity_factory()
    batch = application_batch_factory(applicant=identity.user)
    key = _encrypted_key(identity)
    ticket, raw_token = create_delivery_ticket(
        application_batch=batch,
        access_key=key,
        user=identity.user,
    )

    assert raw_token not in ticket.token_digest
    with pytest.raises(CredentialDeliveryError, match="DELIVERY_TOKEN_INVALID"):
        consume_delivery_token(
            raw_token=raw_token,
            user=user_factory(),
            application_batch=batch,
        )
    with pytest.raises(CredentialDeliveryError, match="DELIVERY_TOKEN_INVALID"):
        consume_delivery_token(
            raw_token=raw_token,
            user=identity.user,
            application_batch=application_batch_factory(applicant=identity.user),
        )

    secret = consume_delivery_token(
        raw_token=raw_token,
        user=identity.user,
        application_batch=batch,
    )

    assert secret == {
        "access_key_id": "LTAI-delivery-1234",
        "secret_access_key": "delivery-secret",
    }
    ticket.refresh_from_db()
    key.refresh_from_db()
    assert ticket.status == DeliveryTicket.Status.CONSUMED
    assert ticket.consumed_at is not None
    assert key.local_state == AccessKey.LocalState.ACTIVE
    with pytest.raises(CredentialDeliveryError, match="DELIVERY_TOKEN_CONSUMED"):
        consume_delivery_token(
            raw_token=raw_token,
            user=identity.user,
            application_batch=batch,
        )


@pytest.mark.parametrize("lifetime", [599, 604801])
def test_delivery_ticket_rejects_lifetime_outside_enterprise_range(
    lifetime,
    application_batch_factory,
    cloud_identity_factory,
    platform_object_storage_config,
):
    from object_storage.services.credentials import (
        CredentialDeliveryError,
        create_delivery_ticket,
    )

    identity = cloud_identity_factory()
    batch = application_batch_factory(applicant=identity.user)
    key = _encrypted_key(identity)
    platform_object_storage_config.delivery_lifetime_seconds = lifetime

    with pytest.raises(CredentialDeliveryError, match="DELIVERY_LIFETIME_INVALID"):
        create_delivery_ticket(
            application_batch=batch,
            access_key=key,
            user=identity.user,
            platform_config=platform_object_storage_config,
        )


def test_missing_cache_rotates_delivery_token_only_once_and_audits(
    application_batch_factory, cloud_identity_factory
):
    from object_storage.models import AuditEvent
    from object_storage.services.credentials import (
        CredentialDeliveryError,
        create_delivery_ticket,
        get_ephemeral_delivery_token,
    )

    identity = cloud_identity_factory()
    batch = application_batch_factory(applicant=identity.user)
    key = _encrypted_key(identity)
    ticket, original = create_delivery_ticket(
        application_batch=batch,
        access_key=key,
        user=identity.user,
    )
    original_digest = ticket.token_digest
    cache.clear()

    replacement = get_ephemeral_delivery_token(
        application_batch=batch,
        user=identity.user,
    )

    ticket.refresh_from_db()
    assert replacement != original
    assert ticket.token_digest != original_digest
    assert ticket.token_rotated_at is not None
    assert AuditEvent.objects.filter(
        action="storage.credential.delivery_token_rotated",
        target_id=str(ticket.pk),
    ).exists()
    cache.clear()
    with pytest.raises(CredentialDeliveryError, match="DELIVERY_TOKEN_UNAVAILABLE"):
        get_ephemeral_delivery_token(
            application_batch=batch,
            user=identity.user,
        )


def test_consumed_ticket_never_reissues_after_cache_loss(
    application_batch_factory, cloud_identity_factory
):
    from object_storage.services.credentials import (
        CredentialDeliveryError,
        consume_delivery_token,
        create_delivery_ticket,
        get_ephemeral_delivery_token,
    )

    identity = cloud_identity_factory()
    batch = application_batch_factory(applicant=identity.user)
    key = _encrypted_key(identity)
    _ticket, token = create_delivery_ticket(
        application_batch=batch,
        access_key=key,
        user=identity.user,
    )
    consume_delivery_token(
        raw_token=token,
        user=identity.user,
        application_batch=batch,
    )
    cache.clear()

    with pytest.raises(CredentialDeliveryError, match="DELIVERY_TOKEN_UNAVAILABLE"):
        get_ephemeral_delivery_token(
            application_batch=batch,
            user=identity.user,
        )


class RotationProvider:
    def __init__(self, keys):
        from object_storage.services.credentials import fingerprint_access_key

        self.cloud_keys = {
            key.pk: SimpleNamespace(
                access_key_id=f"LTAI-existing-{key.pk}",
                fingerprint=key.access_key_fingerprint,
                status=key.cloud_state,
            )
            for key in keys
        }
        self.calls = []
        self.fail_create = False
        self.fail_deactivate = False
        self.fail_delete = False
        self.fail_activate = False
        self.fingerprint_access_key = fingerprint_access_key

    def list_access_keys(self, _identity):
        return SimpleNamespace(items=tuple(self.cloud_keys.values()))

    def deactivate_access_key(self, key):
        if self.fail_deactivate:
            raise RuntimeError("deactivate failed")
        self.calls.append(("deactivate", key.access_key_id))

    def activate_access_key(self, key):
        if self.fail_activate:
            raise RuntimeError("activate failed")
        self.calls.append(("activate", key.access_key_id))

    def delete_access_key(self, key):
        if self.fail_delete:
            raise RuntimeError("delete failed")
        self.calls.append(("delete", key.access_key_id))

    def create_access_key(self, _identity):
        self.calls.append(("create",))
        if self.fail_create:
            raise RuntimeError("provider create failed")
        return SimpleNamespace(
            access_key_id="LTAI-rotation-new",
            secret_access_key="rotation-secret",
        )


def test_rotation_with_one_key_creates_second_without_deleting(
    cloud_identity_factory,
):
    from object_storage.models import AccessKey
    from object_storage.services.credentials import rotate_access_key

    identity = cloud_identity_factory()
    first = _encrypted_key(
        identity,
        access_key_id="LTAI-existing-one",
        state=AccessKey.LocalState.ACTIVE,
    )
    provider = RotationProvider([first])
    provider.cloud_keys[first.pk].access_key_id = "LTAI-existing-one"

    replacement = rotate_access_key(identity=identity, provider=provider)

    assert replacement.access_key_last_four == "-new"
    assert identity.access_keys.count() == 2
    assert provider.calls == [("create",)]


def test_rotation_with_two_keys_requires_explicit_selected_key(
    cloud_identity_factory,
):
    from object_storage.models import AccessKey
    from object_storage.services.credentials import (
        CredentialRotationError,
        rotate_access_key,
    )

    identity = cloud_identity_factory()
    first = _encrypted_key(
        identity,
        access_key_id="LTAI-existing-one",
        state=AccessKey.LocalState.ACTIVE,
    )
    second = _encrypted_key(
        identity,
        access_key_id="LTAI-existing-two",
        state=AccessKey.LocalState.ACTIVE,
    )
    provider = RotationProvider([first, second])

    with pytest.raises(CredentialRotationError, match="ROTATION_SELECTION_REQUIRED"):
        rotate_access_key(identity=identity, provider=provider)

    assert provider.calls == []


def test_rotation_rejects_selected_key_with_inflight_operation_claim(
    cloud_identity_factory,
):
    from object_storage.models import AccessKey
    from object_storage.services.credentials import (
        CredentialRotationError,
        rotate_access_key,
    )

    identity = cloud_identity_factory()
    selected = _encrypted_key(
        identity,
        access_key_id="LTAI-existing-one",
        state=AccessKey.LocalState.ACTIVE,
    )
    remaining = _encrypted_key(
        identity,
        access_key_id="LTAI-existing-two",
        state=AccessKey.LocalState.ACTIVE,
    )
    selected.operation_generation = 1
    selected.operation_token = "inflight-disable"
    selected.operation_type = "disable"
    selected.save(
        update_fields=(
            "operation_generation",
            "operation_token",
            "operation_type",
            "updated_at",
        )
    )
    provider = RotationProvider([selected, remaining])

    with pytest.raises(CredentialRotationError, match="KEY_OPERATION_IN_PROGRESS"):
        rotate_access_key(
            identity=identity,
            provider=provider,
            selected_access_key_id=selected.pk,
        )

    assert provider.calls == []


def test_rotation_delete_then_create_failure_preserves_other_key_and_is_manual(
    cloud_identity_factory,
):
    from object_storage.models import AccessKey
    from object_storage.services.credentials import (
        CredentialRotationError,
        rotate_access_key,
    )

    identity = cloud_identity_factory()
    selected = _encrypted_key(
        identity,
        access_key_id="LTAI-existing-one",
        state=AccessKey.LocalState.ACTIVE,
    )
    remaining = _encrypted_key(
        identity,
        access_key_id="LTAI-existing-two",
        state=AccessKey.LocalState.ACTIVE,
    )
    provider = RotationProvider([selected, remaining])
    provider.cloud_keys[selected.pk].access_key_id = "LTAI-existing-one"
    provider.cloud_keys[remaining.pk].access_key_id = "LTAI-existing-two"
    provider.fail_create = True

    with pytest.raises(
        CredentialRotationError, match="ROTATION_REPLACEMENT_FAILED"
    ) as captured:
        rotate_access_key(
            identity=identity,
            provider=provider,
            selected_access_key_id=selected.pk,
        )

    selected.refresh_from_db()
    remaining.refresh_from_db()
    assert captured.value.manual_required is True
    assert selected.cloud_state == AccessKey.CloudState.DELETED
    assert remaining.cloud_state == AccessKey.CloudState.ACTIVE
    assert provider.calls == [
        ("deactivate", "LTAI-existing-one"),
        ("delete", "LTAI-existing-one"),
        ("create",),
    ]


def test_rotation_delete_failure_reactivates_and_preserves_local_active(
    cloud_identity_factory,
):
    from object_storage.models import AccessKey
    from object_storage.services.credentials import (
        CredentialRotationError,
        rotate_access_key,
    )

    identity = cloud_identity_factory()
    selected = _encrypted_key(
        identity,
        access_key_id="LTAI-existing-one",
        state=AccessKey.LocalState.ACTIVE,
    )
    remaining = _encrypted_key(
        identity,
        access_key_id="LTAI-existing-two",
        state=AccessKey.LocalState.ACTIVE,
    )
    provider = RotationProvider([selected, remaining])
    provider.cloud_keys[selected.pk].access_key_id = "LTAI-existing-one"
    provider.cloud_keys[remaining.pk].access_key_id = "LTAI-existing-two"
    provider.fail_delete = True

    with pytest.raises(RuntimeError, match="delete failed"):
        rotate_access_key(
            identity=identity,
            provider=provider,
            selected_access_key_id=selected.pk,
        )

    selected.refresh_from_db()
    assert selected.cloud_state == AccessKey.CloudState.ACTIVE
    assert selected.local_state == AccessKey.LocalState.ACTIVE
    assert provider.calls == [
        ("deactivate", "LTAI-existing-one"),
        ("activate", "LTAI-existing-one"),
    ]


def test_rotation_reactivation_failure_marks_key_manual_without_claiming_active(
    cloud_identity_factory,
):
    from object_storage.models import AccessKey, AuditEvent
    from object_storage.services.credentials import (
        CredentialRotationError,
        rotate_access_key,
    )

    identity = cloud_identity_factory()
    selected = _encrypted_key(
        identity,
        access_key_id="LTAI-existing-one",
        state=AccessKey.LocalState.ACTIVE,
    )
    remaining = _encrypted_key(
        identity,
        access_key_id="LTAI-existing-two",
        state=AccessKey.LocalState.ACTIVE,
    )
    provider = RotationProvider([selected, remaining])
    provider.cloud_keys[selected.pk].access_key_id = "LTAI-existing-one"
    provider.cloud_keys[remaining.pk].access_key_id = "LTAI-existing-two"
    provider.fail_delete = True
    provider.fail_activate = True

    with pytest.raises(CredentialRotationError, match="KEY_DELETE_FAILED") as error:
        rotate_access_key(
            identity=identity,
            provider=provider,
            selected_access_key_id=selected.pk,
        )

    selected.refresh_from_db()
    assert error.value.manual_required is True
    assert selected.cloud_state == AccessKey.CloudState.UNKNOWN
    assert selected.local_state == AccessKey.LocalState.ERROR
    assert AuditEvent.objects.filter(
        action="storage.credential.rotation_manual_required",
        target_id=str(selected.pk),
    ).exists()


def test_rotation_rejects_newer_active_key_when_two_active_keys_exist(
    cloud_identity_factory,
):
    from object_storage.models import AccessKey
    from object_storage.services.credentials import (
        CredentialRotationError,
        rotate_access_key,
    )

    identity = cloud_identity_factory()
    first = _encrypted_key(identity, access_key_id="LTAI-existing-one")
    second = _encrypted_key(identity, access_key_id="LTAI-existing-two")
    provider = RotationProvider([first, second])
    provider.cloud_keys[first.pk].access_key_id = "LTAI-existing-one"
    provider.cloud_keys[second.pk].access_key_id = "LTAI-existing-two"

    with pytest.raises(CredentialRotationError, match="ROTATION_SELECTION_INVALID"):
        rotate_access_key(
            identity=identity,
            provider=provider,
            selected_access_key_id=second.pk,
        )

    assert provider.calls == []
