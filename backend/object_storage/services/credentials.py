import hashlib
import secrets
from datetime import timedelta

from django.utils import timezone

from object_storage.crypto import encrypt_secret
from object_storage.models import StorageAccessKey, StorageDeliveryTicket


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
    return ticket, raw_token


def digest_delivery_token(raw_token):
    return hashlib.sha256(str(raw_token).encode("utf-8")).hexdigest()


def access_key_from_issued(*, issued, identity, tenant, local_state):
    encrypted = encrypt_issued_access_key(issued)
    return StorageAccessKey.objects.create(
        tenant=tenant,
        cloud_identity=identity,
        local_state=local_state,
        **encrypted,
    )
