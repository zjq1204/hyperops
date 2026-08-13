"""Encryption envelopes for monitoring SSH credential secrets."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class CredentialEncryptionUnavailable(Exception):
    """Raised when the configured credential key ring cannot be used."""


class CredentialDecryptionError(Exception):
    """Raised when a credential envelope cannot be decrypted safely."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def configured_key_ring() -> list[tuple[str, Fernet]]:
    """Return the configured key ring in primary-first order."""
    raw = str(
        getattr(settings, "MONITORING_CREDENTIAL_ENCRYPTION_KEYS", "") or ""
    )
    entries: list[tuple[str, Fernet]] = []
    key_ids: set[str] = set()

    for item in (part.strip() for part in raw.split(",")):
        if not item:
            continue
        key_id, separator, encoded_key = item.partition(":")
        key_id = key_id.strip()
        encoded_key = encoded_key.strip()
        if not separator or not key_id or not encoded_key:
            raise CredentialEncryptionUnavailable(
                "invalid credential encryption key ring"
            )
        if key_id in key_ids:
            raise CredentialEncryptionUnavailable(
                "duplicate credential encryption key id"
            )
        try:
            cipher = Fernet(encoded_key.encode("ascii"))
        except (TypeError, ValueError, UnicodeEncodeError) as exc:
            raise CredentialEncryptionUnavailable(
                "invalid credential encryption key"
            ) from exc
        key_ids.add(key_id)
        entries.append((key_id, cipher))

    if not entries:
        raise CredentialEncryptionUnavailable(
            "credential encryption key ring is not configured"
        )
    return entries


def encrypt_secret(value: str) -> str:
    """Encrypt with the primary configured key into a versioned envelope."""
    key_id, cipher = configured_key_ring()[0]
    token = cipher.encrypt(str(value).encode("utf-8")).decode("ascii")
    return f"v1:{key_id}:{token}"


def decrypt_secret(envelope: str) -> str:
    """Decrypt with the envelope key ID or raise a stable domain error."""
    version, key_id, token = _parse_envelope(envelope)
    if version != "v1":
        raise CredentialDecryptionError("CREDENTIAL_ENVELOPE_UNSUPPORTED")

    cipher = dict(configured_key_ring()).get(key_id)
    if cipher is None:
        raise CredentialDecryptionError("CREDENTIAL_ENCRYPTION_KEY_UNAVAILABLE")

    try:
        return cipher.decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError) as exc:
        raise CredentialDecryptionError("CREDENTIAL_DECRYPTION_FAILED") from exc


def envelope_key_id(envelope: str) -> str:
    """Return the key ID without decrypting the envelope."""
    version, key_id, _token = _parse_envelope(envelope)
    if version != "v1":
        raise CredentialDecryptionError("CREDENTIAL_ENVELOPE_UNSUPPORTED")
    return key_id


def _parse_envelope(envelope: str) -> tuple[str, str, str]:
    try:
        version, key_id, token = str(envelope or "").split(":", 2)
    except ValueError as exc:
        raise CredentialDecryptionError("CREDENTIAL_ENVELOPE_UNSUPPORTED") from exc
    if not version or not key_id or not token:
        raise CredentialDecryptionError("CREDENTIAL_ENVELOPE_UNSUPPORTED")
    return version, key_id, token
