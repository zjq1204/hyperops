import hashlib
import logging
import secrets
from datetime import timedelta
from types import SimpleNamespace

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from object_storage.crypto import decrypt_secret, encrypt_secret
from object_storage.models import AccessKey, DeliveryTicket, PlatformObjectStorageConfig
from object_storage.services.audit import record_audit_event

logger = logging.getLogger(__name__)

MIN_DELIVERY_LIFETIME_SECONDS = 600
MAX_DELIVERY_LIFETIME_SECONDS = 604800


class CredentialDeliveryError(RuntimeError):
    def __init__(self, error_code):
        self.error_code = error_code
        super().__init__(error_code)


class CredentialRotationError(RuntimeError):
    def __init__(self, error_code, *, manual_required=False):
        self.error_code = error_code
        self.manual_required = manual_required
        super().__init__(error_code)


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


def _reconciled_local_keys(identity, provider):
    local_keys = list(
        identity.access_keys.select_for_update()
        .filter(
            cloud_state__in=AccessKey.PROVIDER_SLOT_CLOUD_STATES,
            local_state__in=AccessKey.PROVIDER_SLOT_LOCAL_STATES,
            deleted_at__isnull=True,
        )
        .order_by("created_at", "id")
    )
    cloud_keys = _provider_key_items(provider.list_access_keys(identity))
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


def rotate_access_key(*, identity, provider, selected_access_key_id=None):
    with transaction.atomic():
        local_keys = _reconciled_local_keys(identity, provider)
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
            selected = next(
                (key for key in local_keys if key.pk == selected_access_key_id),
                None,
            )
            if selected is None:
                raise CredentialRotationError("ROTATION_SELECTION_INVALID")
            provider_key = provider_access_key(selected)
            provider.deactivate_access_key(provider_key)
            provider.delete_access_key(provider_key)
            selected.cloud_state = AccessKey.CloudState.DELETED
            selected.local_state = AccessKey.LocalState.RETIRED
            selected.deactivated_at = selected.deactivated_at or timezone.now()
            selected.deleted_at = timezone.now()
            selected.save(
                update_fields=(
                    "cloud_state",
                    "local_state",
                    "deactivated_at",
                    "deleted_at",
                    "updated_at",
                )
            )
        elif selected_access_key_id is not None:
            raise CredentialRotationError("ROTATION_SELECTION_INVALID")

    if len(local_keys) == 2:
        try:
            return persist_new_access_key(identity=identity, provider=provider)
        except Exception as error:
            raise CredentialRotationError(
                "ROTATION_REPLACEMENT_FAILED",
                manual_required=True,
            ) from error
    return persist_new_access_key(identity=identity, provider=provider)


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
    return next(
        (key for key in keys if key.cloud_state == AccessKey.CloudState.INACTIVE),
        keys[0],
    )


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
