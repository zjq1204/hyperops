import base64
import binascii
import os
import re

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

_VERSION = "v1"
_ALGORITHM = "aesgcm"
_AAD = b"v1:aesgcm"
_HKDF_CONTEXT = b"hyperops/object-storage/v1"
_ENVELOPE_PATTERN = re.compile(
    r"^v1:aesgcm:(?P<nonce>[A-Za-z0-9_-]{16}):" r"(?P<ciphertext>[A-Za-z0-9_-]{22,})$"
)


class SecretCryptoError(Exception):
    """Base error for object-storage secret protection."""


class SecretConfigurationError(SecretCryptoError):
    """Raised when root-secret material is unsafe or unusable."""


class SecretDecryptionError(SecretCryptoError):
    """Raised when an encrypted secret cannot be authenticated."""


def _encode_base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_base64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        decoded = base64.b64decode(f"{value}{padding}", altchars=b"-_", validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SecretDecryptionError("Secret envelope is malformed") from exc
    if _encode_base64url(decoded) != value:
        raise SecretDecryptionError("Secret envelope is malformed")
    return decoded


def _validate_root_secret(root_secret: str) -> bytes:
    insecure_roots = set(getattr(settings, "OBJECT_STORAGE_INSECURE_ROOT_SECRETS", ()))
    if (
        not isinstance(root_secret, str)
        or not root_secret
        or root_secret in insecure_roots
    ):
        raise SecretConfigurationError(
            "Object storage requires a non-default stable Django SECRET_KEY"
        )
    return root_secret.encode("utf-8")


def _derive_key(root_secret: str) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=_HKDF_CONTEXT,
    ).derive(_validate_root_secret(root_secret))


def _parse_envelope(envelope: str) -> tuple[bytes, bytes]:
    if not isinstance(envelope, str):
        raise SecretDecryptionError("Secret envelope is malformed")
    match = _ENVELOPE_PATTERN.fullmatch(envelope)
    if match is None:
        raise SecretDecryptionError("Secret envelope is malformed or unsupported")
    nonce = _decode_base64url(match.group("nonce"))
    ciphertext = _decode_base64url(match.group("ciphertext"))
    if len(nonce) != 12 or len(ciphertext) < 16:
        raise SecretDecryptionError("Secret envelope is malformed")
    return nonce, ciphertext


def _encrypt_secret_with_root(value: str, root_secret: str) -> str:
    if not isinstance(value, str):
        raise TypeError("Secret value must be a string")
    nonce = os.urandom(12)
    ciphertext = AESGCM(_derive_key(root_secret)).encrypt(
        nonce, value.encode("utf-8"), _AAD
    )
    return ":".join(
        (
            _VERSION,
            _ALGORITHM,
            _encode_base64url(nonce),
            _encode_base64url(ciphertext),
        )
    )


def _decrypt_secret_with_root(envelope: str, root_secret: str) -> str:
    nonce, ciphertext = _parse_envelope(envelope)
    try:
        plaintext = AESGCM(_derive_key(root_secret)).decrypt(nonce, ciphertext, _AAD)
        return plaintext.decode("utf-8")
    except (InvalidTag, UnicodeDecodeError) as exc:
        raise SecretDecryptionError("Secret envelope authentication failed") from exc


def encrypt_secret(value: str) -> str:
    """Return a versioned authenticated ciphertext envelope."""

    try:
        root_secret = settings.SECRET_KEY
    except ImproperlyConfigured as exc:
        raise SecretConfigurationError(
            "Object storage requires a non-empty Django SECRET_KEY"
        ) from exc
    return _encrypt_secret_with_root(value, root_secret)


def decrypt_secret(envelope: str) -> str:
    """Return plaintext from a supported authenticated envelope."""

    try:
        root_secret = settings.SECRET_KEY
    except ImproperlyConfigured as exc:
        raise SecretConfigurationError(
            "Object storage requires a non-empty Django SECRET_KEY"
        ) from exc
    return _decrypt_secret_with_root(envelope, root_secret)


def is_secret_envelope(value: str) -> bool:
    """Return whether a value has the supported canonical envelope grammar."""

    try:
        _parse_envelope(value)
    except SecretDecryptionError:
        return False
    return True
