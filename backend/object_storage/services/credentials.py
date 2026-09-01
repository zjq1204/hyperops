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
            raise CredentialRotationError(
                identity.credential_operation_error_code,
                manual_required=True,
            )
        if identity.credential_operation_token:
            if (
                identity.credential_operation_lease_until
                and identity.credential_operation_lease_until <= timezone.now()
            ):
                raise CredentialRotationError(
                    "CREDENTIAL_OPERATION_CLAIM_EXPIRED",
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
        provider.deactivate_access_key(provider_access_key(selected))
    except Exception:
        with transaction.atomic():
            identity = CloudIdentity.objects.select_for_update().get(
                pk=selected.cloud_identity_id
            )
            current = AccessKey.objects.select_for_update().get(pk=selected.pk)
            if _key_operation_matches(identity, current, generation, token, "disable"):
                _clear_key_claim(identity, current)
                current.save(
                    update_fields=(
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
        provider.activate_access_key(provider_access_key(selected))
    except Exception:
        with transaction.atomic():
            identity = CloudIdentity.objects.select_for_update().get(
                pk=selected.cloud_identity_id
            )
            current = AccessKey.objects.select_for_update().get(pk=selected.pk)
            if _key_operation_matches(identity, current, generation, token, "enable"):
                _clear_key_claim(identity, current)
                current.save(
                    update_fields=(
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
        provider.delete_access_key(provider_access_key(selected))
    except Exception:
        with transaction.atomic():
            identity = CloudIdentity.objects.select_for_update().get(
                pk=selected.cloud_identity_id
            )
            current = AccessKey.objects.select_for_update().get(pk=selected.pk)
            if _key_operation_matches(identity, current, generation, token, "revoke"):
                _clear_key_claim(identity, current)
                current.save(
                    update_fields=(
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


def persist_new_access_key(*, identity, provider):
    issued = provider.create_access_key(identity)
    try:
        encrypted = encrypt_issued_access_key(issued)
        return AccessKey.objects.create(
            cloud_identity=identity,
            local_state=AccessKey.LocalState.DELIVERY_READY,
            **encrypted,
        )
    except Exception as persistence_error:
        exact_key = SimpleNamespace(
            cloud_identity=identity,
            access_key_id=str(issued.access_key_id),
        )
        try:
            provider.delete_access_key(exact_key)
        except Exception as cleanup_error:
            raise CredentialRotationError(
                "KEY_COMPENSATION_FAILED",
                manual_required=True,
            ) from cleanup_error
        raise CredentialRotationError(
            "KEY_LOCAL_PERSISTENCE_FAILED",
            manual_required=True,
        ) from persistence_error


def _provider_key_items(result):
    return tuple(getattr(result, "items", result))


def _claim_credential_operation(identity_id, *, operation_type, key_id=None):
    with transaction.atomic():
        identity = CloudIdentity.objects.select_for_update().get(pk=identity_id)
        if identity.credential_operation_error_code:
            raise CredentialRotationError(
                identity.credential_operation_error_code,
                manual_required=True,
            )
        if identity.credential_operation_token:
            if (
                identity.credential_operation_lease_until
                and identity.credential_operation_lease_until <= timezone.now()
            ):
                raise CredentialRotationError(
                    "CREDENTIAL_OPERATION_CLAIM_EXPIRED",
                    manual_required=True,
                )
            raise CredentialRotationError("RESOURCE_OPERATION_IN_PROGRESS")
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
        )


def _credential_operation_matches(identity, generation, token, operation_type):
    return bool(
        identity.credential_operation_generation == generation
        and identity.credential_operation_token == token
        and identity.credential_operation_type == operation_type
    )


def _clear_credential_operation(identity, *, error_code=""):
    identity.credential_operation_token = ""
    identity.credential_operation_type = ""
    identity.credential_operation_key_id = None
    identity.credential_operation_acquired_at = None
    identity.credential_operation_lease_until = None
    identity.credential_operation_error_code = error_code


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
        key_id = identity.credential_operation_key_id
    cloud_statuses = {}
    reconciliation_failed = False
    try:
        for item in _provider_key_items(provider.list_access_keys(identity)):
            cloud_statuses[str(item.fingerprint)] = str(
                getattr(item, "status", "") or ""
            ).lower()
    except Exception:
        reconciliation_failed = True
    with transaction.atomic():
        locked_identity = CloudIdentity.objects.select_for_update().get(pk=identity_id)
        if not (
            _credential_operation_matches(
                locked_identity,
                generation,
                token,
                operation_type,
            )
            and locked_identity.credential_operation_lease_until
            and locked_identity.credential_operation_lease_until <= now
        ):
            return locked_identity
        key = (
            AccessKey.objects.select_for_update().filter(pk=key_id).first()
            if key_id
            else None
        )
        resolved = False
        if key is not None and not reconciliation_failed:
            cloud_status = cloud_statuses.get(key.access_key_fingerprint)
            if operation_type == "disable" and cloud_status == "inactive":
                key.cloud_state = AccessKey.CloudState.INACTIVE
                key.local_state = AccessKey.LocalState.DISABLED
                key.deactivated_at = key.deactivated_at or now
                resolved = True
            elif operation_type == "enable" and cloud_status == "active":
                key.cloud_state = AccessKey.CloudState.ACTIVE
                key.local_state = AccessKey.LocalState.ACTIVE
                key.deactivated_at = None
                resolved = True
            elif operation_type == "revoke" and cloud_status is None:
                key.cloud_state = AccessKey.CloudState.DELETED
                key.local_state = AccessKey.LocalState.RETIRED
                key.deleted_at = key.deleted_at or now
                resolved = True
        error_code = "" if resolved else "CREDENTIAL_OPERATION_CLAIM_EXPIRED"
        if key is not None:
            if not resolved:
                key.cloud_state = AccessKey.CloudState.UNKNOWN
                key.local_state = AccessKey.LocalState.ERROR
            _clear_key_operation(key)
            key.operation_acquired_at = None
            key.operation_lease_until = None
            key.operation_error_code = error_code
            key.save(
                update_fields=(
                    "cloud_state",
                    "local_state",
                    "deactivated_at",
                    "deleted_at",
                    "operation_token",
                    "operation_type",
                    "operation_acquired_at",
                    "operation_lease_until",
                    "operation_error_code",
                    "updated_at",
                )
            )
        _clear_credential_operation(locked_identity, error_code=error_code)
        locked_identity.save(
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
        return locked_identity


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


def _compensate_rotation_failure(
    *,
    identity,
    selected,
    provider,
    provider_key,
    error_code,
    original_error,
    generation,
    token,
):
    try:
        provider.activate_access_key(provider_key)
    except Exception as reactivation_error:
        with transaction.atomic():
            locked_identity = CloudIdentity.objects.select_for_update().get(
                pk=identity.pk
            )
            locked_key = AccessKey.objects.select_for_update().get(pk=selected.pk)
            if (
                _credential_operation_matches(
                    locked_identity, generation, token, "rotate"
                )
                and locked_key.operation_token == token
            ):
                locked_key.cloud_state = AccessKey.CloudState.UNKNOWN
                locked_key.local_state = AccessKey.LocalState.ERROR
                _clear_key_operation(locked_key)
                locked_key.operation_acquired_at = None
                locked_key.operation_lease_until = None
                locked_key.operation_error_code = error_code
                locked_key.save(
                    update_fields=(
                        "cloud_state",
                        "local_state",
                        "operation_token",
                        "operation_type",
                        "operation_acquired_at",
                        "operation_lease_until",
                        "operation_error_code",
                        "updated_at",
                    )
                )
                _clear_credential_operation(
                    locked_identity,
                    error_code=error_code,
                )
                locked_identity.save(
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
        record_audit_event(
            actor=identity.user,
            action="storage.credential.rotation_manual_required",
            target_type="AccessKey",
            target_id=selected.pk,
            result="manual_required",
            safe_metadata={
                "error_code": error_code,
                "last_four": selected.access_key_last_four,
            },
        )
        raise CredentialRotationError(
            error_code,
            manual_required=True,
        ) from reactivation_error
    with transaction.atomic():
        locked_identity = CloudIdentity.objects.select_for_update().get(pk=identity.pk)
        locked_key = AccessKey.objects.select_for_update().get(pk=selected.pk)
        if (
            _credential_operation_matches(locked_identity, generation, token, "rotate")
            and locked_key.operation_token == token
        ):
            locked_key.cloud_state = AccessKey.CloudState.ACTIVE
            locked_key.local_state = AccessKey.LocalState.ACTIVE
            locked_key.deactivated_at = None
            _clear_key_operation(locked_key)
            locked_key.operation_acquired_at = None
            locked_key.operation_lease_until = None
            locked_key.save(
                update_fields=(
                    "cloud_state",
                    "local_state",
                    "deactivated_at",
                    "operation_token",
                    "operation_type",
                    "operation_acquired_at",
                    "operation_lease_until",
                    "updated_at",
                )
            )
            _clear_credential_operation(locked_identity)
            locked_identity.save(
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
    raise original_error


def rotate_access_key(
    *, identity, provider, selected_access_key_id=None, actor=None, reason=""
):
    if actor is not None:
        if actor.pk != identity.user_id and not has_object_storage_admin_access(actor):
            raise CredentialRotationError("ACCESS_KEY_OWNERSHIP_REQUIRED")
        from object_storage.services.platform import ensure_key_operations_allowed

        ensure_key_operations_allowed()
    claimed_identity, generation, token = _claim_credential_operation(
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
            provider.deactivate_access_key(provider_key)
        except Exception as error:
            _compensate_rotation_failure(
                identity=identity,
                selected=selected,
                provider=provider,
                provider_key=provider_key,
                error_code="KEY_DEACTIVATE_FAILED",
                original_error=error,
                generation=generation,
                token=token,
            )
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
            provider.delete_access_key(provider_key)
        except Exception as error:
            _compensate_rotation_failure(
                identity=identity,
                selected=selected,
                provider=provider,
                provider_key=provider_key,
                error_code="KEY_DELETE_FAILED",
                original_error=error,
                generation=generation,
                token=token,
            )
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
        replacement = persist_new_access_key(identity=identity, provider=provider)
    except Exception as error:
        _finish_credential_operation(
            identity.pk,
            generation,
            token,
            "rotate",
            error_code="ROTATION_REPLACEMENT_FAILED",
        )
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
