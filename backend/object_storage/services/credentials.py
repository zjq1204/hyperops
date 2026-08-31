import hashlib
import logging
import secrets
from datetime import timedelta

from django.db import transaction
from django.core.cache import cache
from django.utils import timezone

from object_storage.crypto import decrypt_secret, encrypt_secret
from object_storage.models import StorageAccessKey, StorageDeliveryTicket
from object_storage.services.audit import record_audit_event

logger = logging.getLogger(__name__)


class CredentialDeliveryError(RuntimeError):
    def __init__(self, error_code):
        self.error_code = error_code
        super().__init__(error_code)


def _delivery_cache_key(application_id):
    return f"object-storage:delivery-token:{application_id}"


def fingerprint_access_key(access_key_id):
    return hashlib.sha256(str(access_key_id).encode("utf-8")).hexdigest()


def encrypt_issued_access_key(issued):
    """Encrypt both values before a provider-issued secret leaves the service."""
    access_key_id = str(issued.access_key_id)
    secret_access_key = str(issued.secret_access_key)
    return {
        "access_key_id_encrypted": encrypt_secret(access_key_id),
        "secret_access_key_encrypted": encrypt_secret(secret_access_key),
        "access_key_fingerprint": fingerprint_access_key(access_key_id),
        "access_key_last_four": access_key_id[-4:],
    }


def create_delivery_ticket(*, application, access_key, membership, tenant):
    raw_token = secrets.token_urlsafe(32)
    ticket = StorageDeliveryTicket.objects.create(
        tenant=tenant,
        application=application,
        access_key=access_key,
        membership=membership,
        token_digest=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        expires_at=timezone.now() + timedelta(seconds=tenant.delivery_lifetime_seconds),
    )
    cache.set(
        _delivery_cache_key(application.pk),
        encrypt_secret(raw_token),
        timeout=tenant.delivery_lifetime_seconds,
    )
    return ticket, raw_token


def digest_delivery_token(raw_token):
    return hashlib.sha256(str(raw_token).encode("utf-8")).hexdigest()


def consume_delivery_token(*, raw_token, membership):
    token_digest = digest_delivery_token(raw_token)
    with transaction.atomic():
        ticket = (
            StorageDeliveryTicket.objects.select_for_update()
            .select_related("access_key", "application")
            .filter(token_digest=token_digest, membership=membership)
            .first()
        )
        if ticket is None:
            raise CredentialDeliveryError("DELIVERY_TOKEN_INVALID")
        ticket.attempt_count += 1
        if ticket.status == StorageDeliveryTicket.Status.CONSUMED:
            ticket.save(update_fields=("attempt_count",))
            raise CredentialDeliveryError("DELIVERY_TOKEN_CONSUMED")
        if ticket.status != StorageDeliveryTicket.Status.READY:
            ticket.save(update_fields=("attempt_count",))
            raise CredentialDeliveryError("DELIVERY_TOKEN_UNAVAILABLE")
        if ticket.expires_at <= timezone.now():
            ticket.status = StorageDeliveryTicket.Status.EXPIRED
            ticket.save(update_fields=("status", "attempt_count"))
            raise CredentialDeliveryError("DELIVERY_TOKEN_EXPIRED")
        secret = {
            "access_key_id": decrypt_secret(ticket.access_key.access_key_id_encrypted),
            "secret_access_key": decrypt_secret(
                ticket.access_key.secret_access_key_encrypted
            ),
        }
        ticket.status = StorageDeliveryTicket.Status.CONSUMED
        ticket.consumed_at = timezone.now()
        ticket.save(update_fields=("status", "consumed_at", "attempt_count"))
        access_key = ticket.access_key
        access_key.local_state = StorageAccessKey.LocalState.ACTIVE
        access_key.save(update_fields=("local_state", "updated_at"))
        record_audit_event(
            tenant=membership.tenant,
            actor=membership.user,
            application=ticket.application,
            action="storage.credential.delivered",
            target_type="StorageAccessKey",
            target_id=access_key.pk,
            result="succeeded",
            safe_metadata={"last_four": access_key.access_key_last_four},
        )
        application_id = ticket.application_id
    try:
        cache.delete(_delivery_cache_key(application_id))
    except Exception:
        logger.warning(
            "对象存储领取缓存清理失败 | operation=delete_delivery_token "
            "application_id=%s",
            application_id,
        )
    return secret


def get_ephemeral_delivery_token(*, application, membership):
    cache_key = _delivery_cache_key(application.pk)
    cached_token = cache.get(cache_key)
    if cached_token:
        return decrypt_secret(cached_token)
    with transaction.atomic():
        ticket = (
            StorageDeliveryTicket.objects.select_for_update()
            .filter(application=application, membership=membership)
            .first()
        )
        if ticket is None or ticket.status != StorageDeliveryTicket.Status.READY:
            raise CredentialDeliveryError("DELIVERY_TOKEN_UNAVAILABLE")
        if ticket.expires_at <= timezone.now():
            raise CredentialDeliveryError("DELIVERY_TOKEN_EXPIRED")
        raw_token = secrets.token_urlsafe(32)
        ticket.token_digest = digest_delivery_token(raw_token)
        ticket.save(update_fields=("token_digest",))
        cache.set(
            cache_key,
            encrypt_secret(raw_token),
            timeout=max(1, int((ticket.expires_at - timezone.now()).total_seconds())),
        )
    return raw_token


def reveal_access_key(*, access_key, actor, reason, request_id="", ip_address=None):
    reason = str(reason or "").strip()
    if not reason:
        raise ValueError("REVEAL_REASON_REQUIRED")
    secret = {
        "access_key_id": decrypt_secret(access_key.access_key_id_encrypted),
        "secret_access_key": decrypt_secret(access_key.secret_access_key_encrypted),
    }
    record_audit_event(
        tenant=access_key.tenant,
        actor=actor,
        action="storage.credential.revealed",
        target_type="StorageAccessKey",
        target_id=access_key.pk,
        result="succeeded",
        reason=reason,
        request_id=request_id,
        ip_address=ip_address,
        safe_metadata={"last_four": access_key.access_key_last_four},
    )
    return secret


def rotation_candidate(identity):
    keys = list(
        StorageAccessKey.objects.filter(
            cloud_identity=identity,
            cloud_state__in=(
                StorageAccessKey.CloudState.ACTIVE,
                StorageAccessKey.CloudState.INACTIVE,
            ),
        ).order_by("created_at", "id")
    )
    if len(keys) < 2:
        return None
    return next(
        (
            key
            for key in keys
            if key.cloud_state == StorageAccessKey.CloudState.INACTIVE
        ),
        keys[0],
    )


def access_key_from_issued(*, issued, identity, tenant, local_state):
    encrypted = encrypt_issued_access_key(issued)
    return StorageAccessKey.objects.create(
        tenant=tenant,
        cloud_identity=identity,
        local_state=local_state,
        **encrypted,
    )
