import hashlib
import logging
import secrets
import uuid
from datetime import timedelta
from types import SimpleNamespace

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from object_storage.crypto import decrypt_secret, encrypt_secret
from object_storage.models import (
    AccessKey,
    CloudIdentity,
    DeliveryTicket,
    PlatformObjectStorageConfig,
)
from object_storage.permissions import has_object_storage_admin_access
from object_storage.services.audit import record_audit_event

logger = logging.getLogger(__name__)

MIN_DELIVERY_LIFETIME_SECONDS = 600
MAX_DELIVERY_LIFETIME_SECONDS = 604800
CREDENTIAL_OPERATION_LEASE_SECONDS = 300
UNCERTAIN_MUTATION_ERROR = "CLOUD_MUTATION_OUTCOME_UNKNOWN"
MANUAL_RECONCILIATION_ERROR = "MANUAL_RECONCILIATION_REQUIRED"


class CredentialDeliveryError(RuntimeError):
    def __init__(self, error_code):
        self.error_code = error_code
        super().__init__(error_code)


class CredentialRotationError(RuntimeError):
    def __init__(self, error_code, *, manual_required=False):
        self.error_code = error_code
        self.manual_required = manual_required
        super().__init__(error_code)


def _key_actor_allowed(access_key, actor):
    return bool(
        actor
        and (
            actor.pk == access_key.cloud_identity.user_id
            or has_object_storage_admin_access(actor)
        )
    )


def _assert_key_actor(access_key, actor):
    if not _key_actor_allowed(access_key, actor):
        raise CredentialRotationError("ACCESS_KEY_OWNERSHIP_REQUIRED")


def _key_audit(*, actor, action, access_key, result="succeeded", reason=""):
    record_audit_event(
        actor=actor,
        action=action,
        target_type="AccessKey",
        target_id=access_key.pk,
        result=result,
        reason=reason,
        safe_metadata={"last_four": access_key.access_key_last_four},
    )


def _claim_key_operation(access_key_id, *, actor, operation_type):
    with transaction.atomic():
        selected = AccessKey.objects.select_related("cloud_identity").get(
            pk=access_key_id
        )
        identity = CloudIdentity.objects.select_for_update().get(
            pk=selected.cloud_identity_id
        )
        selected = (
            AccessKey.objects.select_for_update()
            .select_related("cloud_identity")
            .get(pk=access_key_id)
        )
        _assert_key_actor(selected, actor)
        if (
            selected.deleted_at is not None
            or selected.local_state == AccessKey.LocalState.RETIRED
        ):
            if operation_type == "revoke":
                return selected, selected.operation_generation, "", False
            raise CredentialRotationError("ACCESS_KEY_REVOKED")
        if (
            operation_type == "disable"
            and selected.local_state == AccessKey.LocalState.DISABLED
        ) or (
            operation_type == "enable"
            and selected.local_state == AccessKey.LocalState.ACTIVE
        ):
            return selected, selected.operation_generation, "", False
        if identity.credential_operation_error_code:
            if identity.credential_operation_error_code == UNCERTAIN_MUTATION_ERROR:
                raise CredentialRotationError(
                    MANUAL_RECONCILIATION_ERROR,
                    manual_required=True,
                )
            raise CredentialRotationError(
                identity.credential_operation_error_code,
                manual_required=True,
            )
        if identity.credential_operation_token:
            if not identity.credential_operation_lease_until or (
                identity.credential_operation_lease_until <= timezone.now()
            ):
                raise CredentialRotationError(
                    MANUAL_RECONCILIATION_ERROR,
                    manual_required=True,
                )
            if (
                identity.credential_operation_type == operation_type
                and identity.credential_operation_key_id == selected.pk
                and selected.operation_token == identity.credential_operation_token
            ):
                return (
                    selected,
                    identity.credential_operation_generation,
                    identity.credential_operation_token,
                    False,
                )
            raise CredentialRotationError("RESOURCE_OPERATION_IN_PROGRESS")
        now = timezone.now()
        identity.credential_operation_generation += 1
        identity.credential_operation_token = uuid.uuid4().hex
        identity.credential_operation_type = operation_type
        identity.credential_operation_key_id = selected.pk
        identity.credential_operation_acquired_at = now
        identity.credential_operation_lease_until = now + timedelta(
            seconds=CREDENTIAL_OPERATION_LEASE_SECONDS
        )
        identity.save(
            update_fields=(
                "credential_operation_generation",
                "credential_operation_token",
                "credential_operation_type",
                "credential_operation_key_id",
                "credential_operation_acquired_at",
                "credential_operation_lease_until",
                "updated_at",
            )
        )
        selected.operation_generation += 1
        selected.operation_token = identity.credential_operation_token
        selected.operation_type = operation_type
        selected.operation_acquired_at = now
        selected.operation_lease_until = now + timedelta(
            seconds=CREDENTIAL_OPERATION_LEASE_SECONDS
        )
        selected.operation_error_code = ""
        selected.save(
            update_fields=(
                "operation_generation",
                "operation_token",
                "operation_type",
                "operation_acquired_at",
                "operation_lease_until",
                "operation_error_code",
                "updated_at",
            )
        )
        return (
            selected,
            identity.credential_operation_generation,
            selected.operation_token,
            True,
        )


def _key_operation_matches(identity, access_key, generation, token, operation_type):
    return bool(
        identity.credential_operation_generation == generation
        and identity.credential_operation_token == token
        and identity.credential_operation_type == operation_type
        and identity.credential_operation_key_id == access_key.pk
        and access_key.operation_token == token
        and access_key.operation_type == operation_type
        and identity.credential_operation_error_code != UNCERTAIN_MUTATION_ERROR
        and identity.credential_operation_lease_until
        and identity.credential_operation_lease_until > timezone.now()
    )


def _clear_key_operation(access_key):
    access_key.operation_token = ""
    access_key.operation_type = ""


def _clear_key_claim(identity, access_key, *, error_code=""):
    _clear_key_operation(access_key)
    access_key.operation_acquired_at = None
    access_key.operation_lease_until = None
    access_key.operation_error_code = error_code
    _clear_credential_operation(identity, error_code=error_code)


def disable_access_key(*, access_key, actor, provider, reason=""):
    """Disable one key; this remains available while key operations are paused."""

    selected, generation, token, claimed = _claim_key_operation(
        access_key.pk, actor=actor, operation_type="disable"
    )
    if not claimed:
        return selected
    try:
        assert_credential_operation_claim(
            selected.cloud_identity_id, generation, token, "disable"
        )
        provider.deactivate_access_key(provider_access_key(selected))
    except Exception as error:
        _freeze_credential_operation(
            selected.cloud_identity_id, generation, token, "disable"
        )
        raise
    with transaction.atomic():
        identity = CloudIdentity.objects.select_for_update().get(
            pk=selected.cloud_identity_id
        )
        current = AccessKey.objects.select_for_update().get(pk=selected.pk)
        if not _key_operation_matches(identity, current, generation, token, "disable"):
            return current
        current.cloud_state = AccessKey.CloudState.INACTIVE
        current.local_state = AccessKey.LocalState.DISABLED
        current.deactivated_at = timezone.now()
        _clear_key_claim(identity, current)
        current.save(
            update_fields=(
                "cloud_state",
                "local_state",
                "deactivated_at",
                "operation_token",
                "operation_type",
                "operation_acquired_at",
                "operation_lease_until",
                "operation_error_code",
                "updated_at",
            )
        )
        identity.save(
            update_fields=(
                "credential_operation_token",
                "credential_operation_type",
                "credential_operation_key_id",
                "credential_operation_acquired_at",
                "credential_operation_lease_until",
                "credential_operation_error_code",
                "updated_at",
            )
        )
    _key_audit(
        actor=actor,
        action="storage.credential.disabled",
        access_key=current,
        reason=reason,
    )
    return current


def enable_access_key(*, access_key, actor, provider, reason=""):
    """Enable one key after the platform key-operation gate permits it."""

    with transaction.atomic():
        authorized = (
            AccessKey.objects.select_for_update()
            .select_related("cloud_identity")
            .get(pk=access_key.pk)
        )
        _assert_key_actor(authorized, actor)

    from object_storage.services.platform import ensure_key_operations_allowed

    ensure_key_operations_allowed()
    selected, generation, token, claimed = _claim_key_operation(
        access_key.pk, actor=actor, operation_type="enable"
    )
    if not claimed:
        return selected
    try:
        assert_credential_operation_claim(
            selected.cloud_identity_id, generation, token, "enable"
        )
        provider.activate_access_key(provider_access_key(selected))
    except Exception:
        _freeze_credential_operation(
            selected.cloud_identity_id, generation, token, "enable"
        )
        raise
    with transaction.atomic():
        identity = CloudIdentity.objects.select_for_update().get(
            pk=selected.cloud_identity_id
        )
        current = AccessKey.objects.select_for_update().get(pk=selected.pk)
        if not _key_operation_matches(identity, current, generation, token, "enable"):
            return current
        current.cloud_state = AccessKey.CloudState.ACTIVE
        current.local_state = AccessKey.LocalState.ACTIVE
        current.deactivated_at = None
        _clear_key_claim(identity, current)
        current.save(
            update_fields=(
                "cloud_state",
                "local_state",
                "deactivated_at",
                "operation_token",
                "operation_type",
                "operation_acquired_at",
                "operation_lease_until",
                "operation_error_code",
                "updated_at",
            )
        )
        identity.save(
            update_fields=(
                "credential_operation_token",
                "credential_operation_type",
                "credential_operation_key_id",
                "credential_operation_acquired_at",
                "credential_operation_lease_until",
                "credential_operation_error_code",
                "updated_at",
            )
        )
    _key_audit(
        actor=actor,
        action="storage.credential.enabled",
        access_key=current,
        reason=reason,
    )
    return current


def revoke_access_key(*, access_key, actor, provider, reason=""):
    """Revoke one key without changing any sibling key."""

    selected, generation, token, claimed = _claim_key_operation(
        access_key.pk, actor=actor, operation_type="revoke"
    )
    if not claimed:
        return selected
    try:
        assert_credential_operation_claim(
            selected.cloud_identity_id, generation, token, "revoke"
        )
        provider.delete_access_key(provider_access_key(selected))
    except Exception:
        _freeze_credential_operation(
            selected.cloud_identity_id, generation, token, "revoke"
        )
        raise
    with transaction.atomic():
        identity = CloudIdentity.objects.select_for_update().get(
            pk=selected.cloud_identity_id
        )
        current = AccessKey.objects.select_for_update().get(pk=selected.pk)
        if not _key_operation_matches(identity, current, generation, token, "revoke"):
            return current
        current.cloud_state = AccessKey.CloudState.DELETED
        current.local_state = AccessKey.LocalState.RETIRED
        current.deleted_at = timezone.now()
        _clear_key_claim(identity, current)
        current.save(
            update_fields=(
                "cloud_state",
                "local_state",
                "deleted_at",
                "operation_token",
                "operation_type",
                "operation_acquired_at",
                "operation_lease_until",
                "operation_error_code",
                "updated_at",
            )
        )
        identity.save(
            update_fields=(
                "credential_operation_token",
                "credential_operation_type",
                "credential_operation_key_id",
                "credential_operation_acquired_at",
                "credential_operation_lease_until",
                "credential_operation_error_code",
                "updated_at",
            )
        )
    _key_audit(
        actor=actor,
        action="storage.credential.revoked",
        access_key=current,
        reason=reason,
    )
    return current


def rotate_access_key_for_actor(
    *, identity, actor, provider, selected_access_key_id=None, reason=""
):
    if not actor or not (
        actor.pk == identity.user_id or has_object_storage_admin_access(actor)
    ):
        raise CredentialRotationError("ACCESS_KEY_OWNERSHIP_REQUIRED")
    result = rotate_access_key(
        identity=identity,
        provider=provider,
        selected_access_key_id=selected_access_key_id,
        actor=actor,
        reason=reason,
    )
    _key_audit(
        actor=actor,
        action="storage.credential.rotated",
        access_key=result,
        reason=reason,
    )
    return result


def create_access_key_for_actor(*, identity, actor, provider, reason=""):
    if not actor or not (
        actor.pk == identity.user_id or has_object_storage_admin_access(actor)
    ):
        raise CredentialRotationError("ACCESS_KEY_OWNERSHIP_REQUIRED")
    from object_storage.services.platform import ensure_key_operations_allowed

    ensure_key_operations_allowed()
    try:
        result = persist_new_access_key(identity=identity, provider=provider)
    except Exception as error:
        if isinstance(error, CredentialRotationError):
            raise
        raise CredentialRotationError("KEY_CREATION_FAILED") from error
    _key_audit(
        actor=actor,
        action="storage.credential.created",
        access_key=result,
        reason=reason,
    )
    return result


def fingerprint_access_key(access_key_id):
    return hashlib.sha256(str(access_key_id).encode("utf-8")).hexdigest()


def digest_delivery_token(raw_token):
    return hashlib.sha256(str(raw_token).encode("utf-8")).hexdigest()


def encrypt_issued_access_key(issued):
    access_key_id = str(issued.access_key_id)
    return {
        "access_key_id_encrypted": encrypt_secret(access_key_id),
        "secret_access_key_encrypted": encrypt_secret(str(issued.secret_access_key)),
        "access_key_fingerprint": fingerprint_access_key(access_key_id),
        "access_key_last_four": access_key_id[-4:],
    }


def _delivery_cache_key(ticket_id):
    return f"object-storage:delivery-token:v3:{ticket_id}"


def _delivery_lifetime(platform_config):
    lifetime = int(platform_config.delivery_lifetime_seconds)
    if not MIN_DELIVERY_LIFETIME_SECONDS <= lifetime <= (MAX_DELIVERY_LIFETIME_SECONDS):
        raise CredentialDeliveryError("DELIVERY_LIFETIME_INVALID")
    return lifetime


@transaction.atomic
def create_delivery_ticket(
    *,
    application_batch,
    access_key,
    user,
    platform_config=None,
):
    if application_batch.applicant_id != user.pk:
        raise CredentialDeliveryError("DELIVERY_OWNERSHIP_INVALID")
    if access_key.cloud_identity.user_id != user.pk:
        raise CredentialDeliveryError("DELIVERY_OWNERSHIP_INVALID")
    existing = (
        DeliveryTicket.objects.select_for_update()
        .filter(application_batch=application_batch)
        .first()
    )
    if existing is not None:
        raw_token = cache.get(_delivery_cache_key(existing.pk))
        if (
            existing.status == DeliveryTicket.Status.READY
            and raw_token
            and digest_delivery_token(raw_token) == existing.token_digest
        ):
            return existing, raw_token
        raise CredentialDeliveryError("DELIVERY_TICKET_ALREADY_EXISTS")

    config = platform_config or PlatformObjectStorageConfig.objects.get(
        singleton_key="default"
    )
    lifetime = _delivery_lifetime(config)
    raw_token = secrets.token_urlsafe(32)
    ticket = DeliveryTicket.objects.create(
        application_batch=application_batch,
        access_key=access_key,
        user=user,
        token_digest=digest_delivery_token(raw_token),
        expires_at=timezone.now() + timedelta(seconds=lifetime),
    )
    cache.set(_delivery_cache_key(ticket.pk), raw_token, timeout=lifetime)
    return ticket, raw_token


def _delivery_ticket_for_update(*, raw_token, user, application_batch):
    return (
        DeliveryTicket.objects.select_for_update()
        .select_related("access_key", "application_batch")
        .filter(
            token_digest=digest_delivery_token(raw_token),
            user=user,
            application_batch=application_batch,
        )
        .first()
    )


def consume_delivery_token(*, raw_token, user, application_batch):
    with transaction.atomic():
        ticket = _delivery_ticket_for_update(
            raw_token=raw_token,
            user=user,
            application_batch=application_batch,
        )
        if ticket is None:
            consumed = DeliveryTicket.objects.filter(
                token_digest=digest_delivery_token(raw_token),
                user=user,
                application_batch=application_batch,
                status=DeliveryTicket.Status.CONSUMED,
            ).exists()
            error_code = (
                "DELIVERY_TOKEN_CONSUMED" if consumed else "DELIVERY_TOKEN_INVALID"
            )
            raise CredentialDeliveryError(error_code)
        ticket.attempt_count += 1
        if ticket.status == DeliveryTicket.Status.CONSUMED:
            ticket.save(update_fields=("attempt_count",))
            raise CredentialDeliveryError("DELIVERY_TOKEN_CONSUMED")
        if ticket.status != DeliveryTicket.Status.READY:
            ticket.save(update_fields=("attempt_count",))
            raise CredentialDeliveryError("DELIVERY_TOKEN_UNAVAILABLE")
        if ticket.expires_at <= timezone.now():
            ticket.status = DeliveryTicket.Status.EXPIRED
            ticket.save(update_fields=("status", "attempt_count"))
            raise CredentialDeliveryError("DELIVERY_TOKEN_EXPIRED")

        access_key = ticket.access_key
        secret = {
            "access_key_id": decrypt_secret(access_key.access_key_id_encrypted),
            "secret_access_key": decrypt_secret(access_key.secret_access_key_encrypted),
        }
        ticket.status = DeliveryTicket.Status.CONSUMED
        ticket.consumed_at = timezone.now()
        ticket.save(update_fields=("status", "consumed_at", "attempt_count"))
        access_key.local_state = AccessKey.LocalState.ACTIVE
        access_key.save(update_fields=("local_state", "updated_at"))
        record_audit_event(
            actor=user,
            action="storage.credential.delivered",
            target_type="AccessKey",
            target_id=access_key.pk,
            result="succeeded",
            safe_metadata={
                "application_id": application_batch.pk,
                "last_four": access_key.access_key_last_four,
            },
        )
        cache_key = _delivery_cache_key(ticket.pk)
    try:
        cache.delete(cache_key)
    except Exception:
        logger.warning(
            "Object storage delivery cache deletion failed ticket_id=%s",
            ticket.pk,
        )
    return secret


def get_ephemeral_delivery_token(*, application_batch, user):
    with transaction.atomic():
        ticket = (
            DeliveryTicket.objects.select_for_update()
            .filter(application_batch=application_batch, user=user)
            .first()
        )
        if ticket is None or ticket.status != DeliveryTicket.Status.READY:
            raise CredentialDeliveryError("DELIVERY_TOKEN_UNAVAILABLE")
        now = timezone.now()
        if ticket.expires_at <= now:
            ticket.status = DeliveryTicket.Status.EXPIRED
            ticket.save(update_fields=("status",))
            raise CredentialDeliveryError("DELIVERY_TOKEN_EXPIRED")
        cache_key = _delivery_cache_key(ticket.pk)
        raw_token = cache.get(cache_key)
        if raw_token and digest_delivery_token(raw_token) == ticket.token_digest:
            return raw_token
        if ticket.token_rotated_at is not None:
            raise CredentialDeliveryError("DELIVERY_TOKEN_UNAVAILABLE")

        raw_token = secrets.token_urlsafe(32)
        ticket.token_digest = digest_delivery_token(raw_token)
        ticket.token_rotated_at = now
        ticket.save(update_fields=("token_digest", "token_rotated_at"))
        timeout = max(1, int((ticket.expires_at - now).total_seconds()))
        cache.set(cache_key, raw_token, timeout=timeout)
        record_audit_event(
            actor=user,
            action="storage.credential.delivery_token_rotated",
            target_type="DeliveryTicket",
            target_id=ticket.pk,
            result="succeeded",
            safe_metadata={"application_id": application_batch.pk},
        )
        return raw_token


def provider_access_key(access_key):
    return SimpleNamespace(
        cloud_identity=access_key.cloud_identity,
        access_key_id=decrypt_secret(access_key.access_key_id_encrypted),
    )


def persist_new_access_key(
    *,
    identity,
    provider,
    operation_token=None,
    operation_generation=None,
    operation_type="create",
    encryptor=encrypt_issued_access_key,
):
    claimed_identity, generation, token, owns_claim = _claim_credential_operation(
        identity.pk,
        operation_type=operation_type,
        owner_token=operation_token,
        owner_generation=operation_generation,
    )
    try:
        assert_credential_operation_claim(
            identity.pk, generation, token, operation_type
        )
        issued = provider.create_access_key(claimed_identity)
    except Exception:
        _freeze_credential_operation(identity.pk, generation, token, operation_type)
        raise
    try:
        encrypted = encryptor(issued)
        with transaction.atomic():
            locked_identity = CloudIdentity.objects.select_for_update().get(
                pk=identity.pk
            )
            if not _credential_operation_matches(
                locked_identity,
                generation,
                token,
                operation_type,
            ):
                raise CredentialRotationError(
                    MANUAL_RECONCILIATION_ERROR,
                    manual_required=True,
                )
            access_key = AccessKey.objects.create(
                cloud_identity=locked_identity,
                local_state=AccessKey.LocalState.DELIVERY_READY,
                operation_generation=1,
                operation_token=token,
                operation_type=operation_type,
                operation_acquired_at=locked_identity.credential_operation_acquired_at,
                operation_lease_until=locked_identity.credential_operation_lease_until,
                **encrypted,
            )
            locked_identity.credential_operation_key_id = access_key.pk
            locked_identity.save(
                update_fields=("credential_operation_key_id", "updated_at")
            )
    except Exception as persistence_error:
        if isinstance(persistence_error, CredentialRotationError):
            raise
        exact_key = SimpleNamespace(
            cloud_identity=claimed_identity,
            access_key_id=str(issued.access_key_id),
        )
        try:
            assert_credential_operation_claim(
                identity.pk, generation, token, operation_type
            )
            provider.delete_access_key(exact_key)
        except Exception as cleanup_error:
            _freeze_credential_operation(
                identity.pk,
                generation,
                token,
                operation_type,
            )
            raise CredentialRotationError(
                "KEY_COMPENSATION_FAILED",
                manual_required=True,
            ) from cleanup_error
        if owns_claim:
            _finish_credential_operation(identity.pk, generation, token, operation_type)
        raise CredentialRotationError(
            "KEY_LOCAL_PERSISTENCE_FAILED",
            manual_required=True,
        ) from persistence_error
    if owns_claim:
        _finish_credential_operation(identity.pk, generation, token, operation_type)
    return access_key


def _provider_key_items(result):
    return tuple(getattr(result, "items", result))


def _claim_credential_operation(
    identity_id,
    *,
    operation_type,
    key_id=None,
    owner_token=None,
    owner_generation=None,
):
    with transaction.atomic():
        identity = CloudIdentity.objects.select_for_update().get(pk=identity_id)
        if identity.state == CloudIdentity.State.SUSPENDED and operation_type in {
            "application_create",
            "create",
            "enable",
            "rotate",
        }:
            raise CredentialRotationError("IDENTITY_SUSPENDED")
        if identity.credential_operation_error_code:
            if identity.credential_operation_error_code == UNCERTAIN_MUTATION_ERROR:
                raise CredentialRotationError(
                    MANUAL_RECONCILIATION_ERROR,
                    manual_required=True,
                )
            raise CredentialRotationError(
                identity.credential_operation_error_code,
                manual_required=True,
            )
        if identity.credential_operation_token:
            if (
                owner_token
                and identity.credential_operation_token == owner_token
                and identity.credential_operation_lease_until
                and identity.credential_operation_lease_until > timezone.now()
                and (
                    owner_generation is None
                    or identity.credential_operation_generation == owner_generation
                )
                and identity.credential_operation_type == operation_type
            ):
                return (
                    identity,
                    identity.credential_operation_generation,
                    identity.credential_operation_token,
                    False,
                )
            if not identity.credential_operation_lease_until or (
                identity.credential_operation_lease_until <= timezone.now()
            ):
                raise CredentialRotationError(
                    MANUAL_RECONCILIATION_ERROR,
                    manual_required=True,
                )
            if owner_token:
                raise CredentialRotationError("CREDENTIAL_OPERATION_SUPERSEDED")
            raise CredentialRotationError("RESOURCE_OPERATION_IN_PROGRESS")
        if owner_token:
            raise CredentialRotationError("CREDENTIAL_OPERATION_SUPERSEDED")
        now = timezone.now()
        identity.credential_operation_generation += 1
        identity.credential_operation_token = uuid.uuid4().hex
        identity.credential_operation_type = operation_type
        identity.credential_operation_key_id = key_id
        identity.credential_operation_acquired_at = now
        identity.credential_operation_lease_until = now + timedelta(
            seconds=CREDENTIAL_OPERATION_LEASE_SECONDS
        )
        identity.save(
            update_fields=(
                "credential_operation_generation",
                "credential_operation_token",
                "credential_operation_type",
                "credential_operation_key_id",
                "credential_operation_acquired_at",
                "credential_operation_lease_until",
                "updated_at",
            )
        )
        return (
            identity,
            identity.credential_operation_generation,
            identity.credential_operation_token,
            True,
        )


def _credential_operation_matches(identity, generation, token, operation_type):
    return bool(
        identity.credential_operation_generation == generation
        and identity.credential_operation_token == token
        and identity.credential_operation_type == operation_type
        and identity.credential_operation_error_code != UNCERTAIN_MUTATION_ERROR
        and identity.credential_operation_lease_until
        and identity.credential_operation_lease_until > timezone.now()
    )


def assert_credential_operation_claim(identity_id, generation, token, operation_type):
    with transaction.atomic():
        identity = CloudIdentity.objects.select_for_update().get(pk=identity_id)
        if not _credential_operation_matches(
            identity, generation, token, operation_type
        ):
            raise CredentialRotationError(
                MANUAL_RECONCILIATION_ERROR,
                manual_required=True,
            )
        return identity


def delete_access_key_under_claim(
    *, access_key, provider, operation_generation, operation_token, operation_type
):
    identity_id = access_key.cloud_identity_id
    assert_credential_operation_claim(
        identity_id,
        operation_generation,
        operation_token,
        operation_type,
    )
    try:
        provider.delete_access_key(provider_access_key(access_key))
    except Exception:
        _freeze_credential_operation(
            identity_id,
            operation_generation,
            operation_token,
            operation_type,
        )
        raise
    with transaction.atomic():
        identity = CloudIdentity.objects.select_for_update().get(pk=identity_id)
        key = AccessKey.objects.select_for_update().get(pk=access_key.pk)
        if not _credential_operation_matches(
            identity,
            operation_generation,
            operation_token,
            operation_type,
        ):
            raise CredentialRotationError(
                MANUAL_RECONCILIATION_ERROR,
                manual_required=True,
            )
        key.cloud_state = AccessKey.CloudState.DELETED
        key.local_state = AccessKey.LocalState.RETIRED
        key.deleted_at = timezone.now()
        key.save(
            update_fields=(
                "cloud_state",
                "local_state",
                "deleted_at",
                "updated_at",
            )
        )
        return key


def _clear_credential_operation(identity, *, error_code=""):
    identity.credential_operation_token = ""
    identity.credential_operation_type = ""
    identity.credential_operation_key_id = None
    identity.credential_operation_acquired_at = None
    identity.credential_operation_lease_until = None
    identity.credential_operation_error_code = error_code


def _freeze_credential_operation(
    identity_id, generation, token, operation_type, *, now=None
):
    now = now or timezone.now()
    with transaction.atomic():
        identity = CloudIdentity.objects.select_for_update().get(pk=identity_id)
        if not (
            identity.credential_operation_generation == generation
            and identity.credential_operation_token == token
            and identity.credential_operation_type == operation_type
        ):
            return identity
        identity.state = CloudIdentity.State.ERROR
        identity.credential_operation_error_code = UNCERTAIN_MUTATION_ERROR
        identity.save(
            update_fields=(
                "state",
                "credential_operation_error_code",
                "updated_at",
            )
        )
        if identity.credential_operation_key_id:
            key = (
                AccessKey.objects.select_for_update()
                .filter(pk=identity.credential_operation_key_id, operation_token=token)
                .first()
            )
            if key is not None:
                key.cloud_state = AccessKey.CloudState.UNKNOWN
                key.local_state = AccessKey.LocalState.ERROR
                key.operation_error_code = UNCERTAIN_MUTATION_ERROR
                key.save(
                    update_fields=(
                        "cloud_state",
                        "local_state",
                        "operation_error_code",
                        "updated_at",
                    )
                )
        return identity


def _finish_credential_operation(
    identity_id, generation, token, operation_type, *, error_code=""
):
    with transaction.atomic():
        identity = CloudIdentity.objects.select_for_update().get(pk=identity_id)
        if not _credential_operation_matches(
            identity, generation, token, operation_type
        ):
            return identity
        key_id = identity.credential_operation_key_id
        if key_id:
            key = AccessKey.objects.select_for_update().filter(pk=key_id).first()
            if key and key.operation_token == token:
                _clear_key_operation(key)
                key.operation_acquired_at = None
                key.operation_lease_until = None
                key.operation_error_code = error_code
                key.save(
                    update_fields=(
                        "cloud_state",
                        "local_state",
                        "deleted_at",
                        "operation_token",
                        "operation_type",
                        "operation_acquired_at",
                        "operation_lease_until",
                        "operation_error_code",
                        "updated_at",
                    )
                )
        _clear_credential_operation(identity, error_code=error_code)
        identity.save(
            update_fields=(
                "credential_operation_token",
                "credential_operation_type",
                "credential_operation_key_id",
                "credential_operation_acquired_at",
                "credential_operation_lease_until",
                "credential_operation_error_code",
                "updated_at",
            )
        )
        return identity


def recover_expired_credential_operation(identity_id, *, provider, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        identity = CloudIdentity.objects.select_for_update().get(pk=identity_id)
        if not (
            identity.credential_operation_token
            and identity.credential_operation_lease_until
            and identity.credential_operation_lease_until <= now
        ):
            return identity
        generation = identity.credential_operation_generation
        token = identity.credential_operation_token
        operation_type = identity.credential_operation_type
    # The read is diagnostic only. A timed-out request may still complete after
    # this snapshot, so automatic recovery must retain the mutation claim.
    try:
        _provider_key_items(provider.list_access_keys(identity))
    except Exception:
        pass
    return _freeze_credential_operation(
        identity_id,
        generation,
        token,
        operation_type,
        now=now,
    )


def _assert_reconciliation_actor(identity, actor, reason):
    if not has_object_storage_admin_access(actor):
        raise CredentialRotationError("ADMIN_REQUIRED")
    if not str(reason or "").strip():
        raise CredentialRotationError("RECONCILIATION_REASON_REQUIRED")


def reconcile_credential_operation_uncertainty(*, identity, actor, provider, reason=""):
    """Read cloud keys and retain the frozen claim for manual resolution."""

    with transaction.atomic():
        locked = CloudIdentity.objects.select_for_update().get(pk=identity.pk)
        _assert_reconciliation_actor(locked, actor, reason)
        if not (
            locked.credential_operation_token
            and locked.credential_operation_error_code == UNCERTAIN_MUTATION_ERROR
        ):
            raise CredentialRotationError("CREDENTIAL_OPERATION_NOT_FROZEN")
        token = locked.credential_operation_token
        operation_type = locked.credential_operation_type
        local = {
            key.access_key_fingerprint: key.cloud_state
            for key in locked.access_keys.filter(
                deleted_at__isnull=True,
                cloud_state__in=AccessKey.PROVIDER_SLOT_CLOUD_STATES,
            )
        }
    cloud_items = _provider_key_items(provider.list_access_keys(locked))
    cloud = {
        str(item.fingerprint): str(getattr(item, "status", "") or "").lower()
        for item in cloud_items
    }
    observed = {
        "keys": [
            {
                "fingerprint": str(item.fingerprint),
                "last_four": str(getattr(item, "last_four", "") or ""),
                "status": str(getattr(item, "status", "") or "").lower(),
            }
            for item in sorted(cloud_items, key=lambda item: str(item.fingerprint))
        ]
    }
    with transaction.atomic():
        current = CloudIdentity.objects.select_for_update().get(pk=locked.pk)
        if not (
            current.credential_operation_token == token
            and current.credential_operation_error_code == UNCERTAIN_MUTATION_ERROR
        ):
            return current
        current.credential_observed_snapshot = observed
        current.save(
            update_fields=(
                "credential_observed_snapshot",
                "updated_at",
            )
        )
    record_audit_event(
        actor=actor,
        action="storage.credential.operation_reconciled",
        target_type="CloudIdentity",
        target_id=locked.pk,
        result="observed",
        reason=reason,
        safe_metadata={"user_id": locked.user_id},
    )
    return CloudIdentity.objects.get(pk=locked.pk)


def acknowledge_credential_operation_uncertainty(
    *,
    identity,
    actor,
    reason,
    identity_name,
    operation_type,
    operation_generation,
    operation_token,
    cloud_console_resolved,
    observation_summary,
    resolved_state=CloudIdentity.State.ERROR,
    resolved_key_state=None,
):
    """Clear a frozen claim after an administrator verifies it externally."""

    with transaction.atomic():
        locked = CloudIdentity.objects.select_for_update().get(pk=identity.pk)
        _assert_reconciliation_actor(locked, actor, reason)
        if not (
            locked.credential_operation_token
            and locked.credential_operation_error_code == UNCERTAIN_MUTATION_ERROR
            and locked.ram_user_name == identity_name
            and locked.credential_operation_type == operation_type
            and locked.credential_operation_generation == operation_generation
            and locked.credential_operation_token == operation_token
        ):
            raise CredentialRotationError("RESOURCE_OPERATION_CONFIRMATION_MISMATCH")
        if not cloud_console_resolved or not str(observation_summary or "").strip():
            raise CredentialRotationError("CLOUD_CONSOLE_RESOLUTION_REQUIRED")
        if resolved_state not in {
            CloudIdentity.State.ACTIVE,
            CloudIdentity.State.SUSPENDED,
            CloudIdentity.State.ERROR,
        }:
            raise CredentialRotationError("CREDENTIAL_RESOLUTION_STATE_INVALID")
        key_id = locked.credential_operation_key_id
        token = locked.credential_operation_token
        if key_id:
            key = AccessKey.objects.select_for_update().filter(pk=key_id).first()
            if key is not None and key.operation_token == token:
                if resolved_key_state not in {
                    AccessKey.CloudState.ACTIVE,
                    AccessKey.CloudState.INACTIVE,
                    AccessKey.CloudState.DELETED,
                }:
                    raise CredentialRotationError("CREDENTIAL_KEY_RESOLUTION_REQUIRED")
                key.cloud_state = resolved_key_state
                key.local_state = (
                    AccessKey.LocalState.RETIRED
                    if resolved_key_state == AccessKey.CloudState.DELETED
                    else (
                        AccessKey.LocalState.ACTIVE
                        if resolved_key_state == AccessKey.CloudState.ACTIVE
                        else AccessKey.LocalState.DISABLED
                    )
                )
                if resolved_key_state == AccessKey.CloudState.DELETED:
                    key.deleted_at = key.deleted_at or timezone.now()
                _clear_key_operation(key)
                key.operation_acquired_at = None
                key.operation_lease_until = None
                key.operation_error_code = ""
                key.save(
                    update_fields=(
                        "cloud_state",
                        "local_state",
                        "deleted_at",
                        "operation_token",
                        "operation_type",
                        "operation_acquired_at",
                        "operation_lease_until",
                        "operation_error_code",
                        "updated_at",
                    )
                )
        locked.state = resolved_state
        _clear_credential_operation(locked)
        locked.save(
            update_fields=(
                "state",
                "credential_operation_token",
                "credential_operation_type",
                "credential_operation_key_id",
                "credential_operation_acquired_at",
                "credential_operation_lease_until",
                "credential_operation_error_code",
                "updated_at",
            )
        )
    record_audit_event(
        actor=actor,
        action="storage.credential.operation_acknowledged",
        target_type="CloudIdentity",
        target_id=locked.pk,
        result="succeeded",
        reason=reason,
        safe_metadata={
            "user_id": locked.user_id,
            "status": resolved_state,
            "count": len(locked.credential_observed_snapshot.get("keys", [])),
        },
    )
    return CloudIdentity.objects.get(pk=locked.pk)


def _reconciled_local_keys(identity, cloud_keys):
    local_keys = list(
        identity.access_keys.select_for_update()
        .filter(
            cloud_state__in=AccessKey.PROVIDER_SLOT_CLOUD_STATES,
            local_state__in=AccessKey.PROVIDER_SLOT_LOCAL_STATES,
            deleted_at__isnull=True,
        )
        .order_by("created_at", "id")
    )
    local_fingerprints = {key.access_key_fingerprint for key in local_keys}
    cloud_fingerprints = {
        key.fingerprint
        for key in cloud_keys
        if str(getattr(key, "status", "")).lower() in {"active", "inactive"}
    }
    if cloud_fingerprints - local_fingerprints:
        raise CredentialRotationError(
            "CLOUD_KEY_RECOVERY_REQUIRED",
            manual_required=True,
        )
    if local_fingerprints - cloud_fingerprints:
        raise CredentialRotationError(
            "LOCAL_KEY_STATE_INCONSISTENT",
            manual_required=True,
        )
    return local_keys


def _rotation_candidate_from_keys(local_keys):
    inactive = [
        key for key in local_keys if key.cloud_state == AccessKey.CloudState.INACTIVE
    ]
    return inactive[0] if inactive else local_keys[0]


def rotate_access_key(
    *, identity, provider, selected_access_key_id=None, actor=None, reason=""
):
    if actor is not None:
        if actor.pk != identity.user_id and not has_object_storage_admin_access(actor):
            raise CredentialRotationError("ACCESS_KEY_OWNERSHIP_REQUIRED")
        from object_storage.services.platform import ensure_key_operations_allowed

        ensure_key_operations_allowed()
    claimed_identity, generation, token, _owns_claim = _claim_credential_operation(
        identity.pk,
        operation_type="rotate",
    )
    try:
        cloud_keys = _provider_key_items(provider.list_access_keys(claimed_identity))
        with transaction.atomic():
            locked_identity = CloudIdentity.objects.select_for_update().get(
                pk=identity.pk
            )
            if not _credential_operation_matches(
                locked_identity, generation, token, "rotate"
            ):
                raise CredentialRotationError("CREDENTIAL_OPERATION_SUPERSEDED")
            local_keys = _reconciled_local_keys(locked_identity, cloud_keys)
            if not local_keys:
                raise CredentialRotationError(
                    "ACCESS_KEY_REQUIRED",
                    manual_required=True,
                )
            if len(local_keys) > 2:
                raise CredentialRotationError(
                    "ACCESS_KEY_LIMIT_EXCEEDED",
                    manual_required=True,
                )
            if len(local_keys) == 2:
                if selected_access_key_id is None:
                    raise CredentialRotationError("ROTATION_SELECTION_REQUIRED")
                candidate = _rotation_candidate_from_keys(local_keys)
                if candidate.pk != selected_access_key_id:
                    raise CredentialRotationError("ROTATION_SELECTION_INVALID")
                selected = candidate
                if selected.operation_token:
                    raise CredentialRotationError("KEY_OPERATION_IN_PROGRESS")
                now = timezone.now()
                selected.operation_generation += 1
                selected.operation_token = token
                selected.operation_type = "rotate"
                selected.operation_acquired_at = now
                selected.operation_lease_until = now + timedelta(
                    seconds=CREDENTIAL_OPERATION_LEASE_SECONDS
                )
                selected.operation_error_code = ""
                selected.save(
                    update_fields=(
                        "operation_generation",
                        "operation_token",
                        "operation_type",
                        "operation_acquired_at",
                        "operation_lease_until",
                        "operation_error_code",
                        "updated_at",
                    )
                )
                locked_identity.credential_operation_key_id = selected.pk
                locked_identity.save(
                    update_fields=("credential_operation_key_id", "updated_at")
                )
                provider_key = provider_access_key(candidate)
            elif selected_access_key_id is not None:
                raise CredentialRotationError("ROTATION_SELECTION_INVALID")
    except Exception:
        _finish_credential_operation(identity.pk, generation, token, "rotate")
        raise

    if len(local_keys) == 2:
        try:
            assert_credential_operation_claim(identity.pk, generation, token, "rotate")
            provider.deactivate_access_key(provider_key)
        except Exception as error:
            _freeze_credential_operation(identity.pk, generation, token, "rotate")
            raise CredentialRotationError(
                "KEY_DEACTIVATE_FAILED", manual_required=True
            ) from error
        with transaction.atomic():
            locked_identity = CloudIdentity.objects.select_for_update().get(
                pk=identity.pk
            )
            selected = AccessKey.objects.select_for_update().get(pk=selected.pk)
            if not (
                _credential_operation_matches(
                    locked_identity, generation, token, "rotate"
                )
                and selected.operation_token == token
            ):
                raise CredentialRotationError("CREDENTIAL_OPERATION_SUPERSEDED")
            selected.cloud_state = AccessKey.CloudState.INACTIVE
            selected.local_state = AccessKey.LocalState.RETIRING
            selected.deactivated_at = timezone.now()
            selected.save(
                update_fields=(
                    "cloud_state",
                    "local_state",
                    "deactivated_at",
                    "updated_at",
                )
            )
        try:
            assert_credential_operation_claim(identity.pk, generation, token, "rotate")
            provider.delete_access_key(provider_key)
        except Exception as error:
            _freeze_credential_operation(identity.pk, generation, token, "rotate")
            raise CredentialRotationError(
                "KEY_DELETE_FAILED", manual_required=True
            ) from error
        with transaction.atomic():
            locked_identity = CloudIdentity.objects.select_for_update().get(
                pk=identity.pk
            )
            selected = AccessKey.objects.select_for_update().get(pk=selected.pk)
            if not (
                _credential_operation_matches(
                    locked_identity, generation, token, "rotate"
                )
                and selected.operation_token == token
            ):
                raise CredentialRotationError("CREDENTIAL_OPERATION_SUPERSEDED")
            selected.cloud_state = AccessKey.CloudState.DELETED
            selected.local_state = AccessKey.LocalState.RETIRED
            selected.deleted_at = timezone.now()
            _clear_key_operation(selected)
            selected.operation_acquired_at = None
            selected.operation_lease_until = None
            selected.save(
                update_fields=(
                    "cloud_state",
                    "local_state",
                    "deleted_at",
                    "operation_token",
                    "operation_type",
                    "operation_acquired_at",
                    "operation_lease_until",
                    "updated_at",
                )
            )
    try:
        replacement = persist_new_access_key(
            identity=identity,
            provider=provider,
            operation_token=token,
            operation_generation=generation,
            operation_type="rotate",
        )
    except Exception as error:
        current = CloudIdentity.objects.get(pk=identity.pk)
        if current.credential_operation_error_code != UNCERTAIN_MUTATION_ERROR:
            _finish_credential_operation(
                identity.pk,
                generation,
                token,
                "rotate",
                error_code="ROTATION_REPLACEMENT_FAILED",
            )
        if (
            isinstance(error, CredentialRotationError)
            and error.error_code == MANUAL_RECONCILIATION_ERROR
        ):
            raise
        raise CredentialRotationError(
            "ROTATION_REPLACEMENT_FAILED",
            manual_required=True,
        ) from error
    _finish_credential_operation(identity.pk, generation, token, "rotate")
    return replacement


def rotation_candidate(identity):
    if identity is None:
        return None
    keys = list(
        identity.access_keys.filter(
            cloud_state__in=(
                AccessKey.CloudState.ACTIVE,
                AccessKey.CloudState.INACTIVE,
            ),
            deleted_at__isnull=True,
        ).order_by("created_at", "id")
    )
    if len(keys) < 2:
        return None
    return _rotation_candidate_from_keys(keys)


def reveal_access_key(*, access_key, actor, reason, request_id="", ip_address=None):
    reason = str(reason or "").strip()
    if not reason:
        raise ValueError("REVEAL_REASON_REQUIRED")
    secret = {
        "access_key_id": decrypt_secret(access_key.access_key_id_encrypted),
        "secret_access_key": decrypt_secret(access_key.secret_access_key_encrypted),
    }
    record_audit_event(
        actor=actor,
        action="storage.credential.revealed",
        target_type="AccessKey",
        target_id=access_key.pk,
        result="succeeded",
        reason=reason,
        request_id=request_id,
        ip_address=ip_address,
        safe_metadata={"last_four": access_key.access_key_last_four},
    )
    return secret
