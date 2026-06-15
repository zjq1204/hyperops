"""Encryption helpers for LDAP secrets stored in the database."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _build_fernet_key(raw_key: str) -> bytes:
    normalized = (raw_key or "").strip()
    if not normalized:
        raise ImproperlyConfigured(
            "LDAP_CONFIG_ENCRYPTION_KEY is required for LDAP secret storage."
        )
    return base64.urlsafe_b64encode(hashlib.sha256(normalized.encode()).digest())


def _get_encryption_key() -> str:
    return (
        getattr(settings, "LDAP_CONFIG_ENCRYPTION_KEY", "")
        or getattr(settings, "SECRET_KEY", "")
    )


def _get_fernet() -> Fernet:
    return Fernet(_build_fernet_key(_get_encryption_key()))


def encrypt_secret(value: str) -> str:
    """Encrypt a secret value for storage."""
    if not value:
        return ""
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    """Decrypt a previously encrypted secret value."""
    if not value:
        return ""
    return _get_fernet().decrypt(value.encode()).decode()
