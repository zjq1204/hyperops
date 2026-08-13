"""Tests for monitoring credential encryption envelopes."""

import pytest
from cryptography.fernet import Fernet
from django.test import override_settings

from monitoring_stack.services.credential_crypto import (
    CredentialDecryptionError,
    CredentialEncryptionUnavailable,
    configured_key_ring,
    decrypt_secret,
    encrypt_secret,
    envelope_key_id,
)


FERNET_A = "a1xYkQ9g7TCNCwOu5hQG1WsNC8ftDRqMtPUmBrAIE08="
FERNET_B = "sNYzH_a36G32EU5GoWan_S8LSAl2trjQKVtt2tXE1yY="


@override_settings(
    MONITORING_CREDENTIAL_ENCRYPTION_KEYS=f"new:{FERNET_A},old:{FERNET_B}"
)
def test_envelope_uses_primary_key_and_round_trips_without_plaintext():
    envelope = encrypt_secret("private material")

    assert envelope.startswith("v1:new:")
    assert decrypt_secret(envelope) == "private material"
    assert envelope_key_id(envelope) == "new"
    assert "private material" not in envelope


@override_settings(
    MONITORING_CREDENTIAL_ENCRYPTION_KEYS=f"new:{FERNET_A},old:{FERNET_B}"
)
def test_configured_key_ring_preserves_declared_order():
    assert [key_id for key_id, _cipher in configured_key_ring()] == ["new", "old"]


@override_settings(
    MONITORING_CREDENTIAL_ENCRYPTION_KEYS="",
    SECRET_KEY="must-never-be-used-for-monitoring-credentials",
)
def test_missing_key_ring_never_falls_back_to_secret_key():
    with pytest.raises(CredentialEncryptionUnavailable):
        encrypt_secret("secret")


@pytest.mark.parametrize(
    "key_ring",
    [
        "missing-separator",
        f":{FERNET_A}",
        "key-id:",
        "key-id:not-a-fernet-key",
        f"primary:{FERNET_A},broken",
    ],
)
def test_malformed_key_ring_is_rejected(key_ring):
    with override_settings(MONITORING_CREDENTIAL_ENCRYPTION_KEYS=key_ring):
        with pytest.raises(CredentialEncryptionUnavailable):
            configured_key_ring()


@pytest.mark.parametrize(
    "key_ring",
    [
        f",primary:{FERNET_A}",
        f"primary:{FERNET_A},",
        f"primary:{FERNET_A},,old:{FERNET_B}",
        f"primary:{FERNET_A[:12]} {FERNET_A[12:]}",
        f"primary:{FERNET_A[:12]}!\n{FERNET_A[12:]}",
    ],
    ids=[
        "leading-comma",
        "trailing-comma",
        "doubled-comma",
        "space-in-key",
        "punctuation-and-newline-in-key",
    ],
)
def test_key_ring_rejects_noncanonical_syntax(key_ring):
    with override_settings(MONITORING_CREDENTIAL_ENCRYPTION_KEYS=key_ring):
        with pytest.raises(CredentialEncryptionUnavailable):
            configured_key_ring()


@override_settings(
    MONITORING_CREDENTIAL_ENCRYPTION_KEYS=f"duplicate:{FERNET_A},duplicate:{FERNET_B}"
)
def test_duplicate_key_ids_are_rejected():
    with pytest.raises(CredentialEncryptionUnavailable):
        configured_key_ring()


@override_settings(
    MONITORING_CREDENTIAL_ENCRYPTION_KEYS=f"new:{FERNET_A},old:{FERNET_B}"
)
def test_old_key_envelope_decrypts_when_new_primary_exists():
    token = Fernet(FERNET_B.encode()).encrypt(b"old secret").decode("ascii")

    assert decrypt_secret(f"v1:old:{token}") == "old secret"


@override_settings(MONITORING_CREDENTIAL_ENCRYPTION_KEYS=f"other:{FERNET_B}")
def test_unknown_envelope_key_is_unavailable():
    token = Fernet(FERNET_A.encode()).encrypt(b"secret").decode("ascii")

    with pytest.raises(CredentialDecryptionError) as error:
        decrypt_secret(f"v1:removed:{token}")

    assert error.value.code == "CREDENTIAL_ENCRYPTION_KEY_UNAVAILABLE"


@override_settings(MONITORING_CREDENTIAL_ENCRYPTION_KEYS=f"primary:{FERNET_A}")
def test_unsupported_envelope_version_has_stable_error():
    with pytest.raises(CredentialDecryptionError) as error:
        decrypt_secret("v2:primary:token")

    assert error.value.code == "CREDENTIAL_ENVELOPE_UNSUPPORTED"


@override_settings(MONITORING_CREDENTIAL_ENCRYPTION_KEYS=f"primary:{FERNET_A}")
def test_invalid_token_has_stable_error():
    with pytest.raises(CredentialDecryptionError) as error:
        decrypt_secret("v1:primary:not-a-fernet-token")

    assert error.value.code == "CREDENTIAL_DECRYPTION_FAILED"


@override_settings(MONITORING_CREDENTIAL_ENCRYPTION_KEYS=f"primary:{FERNET_A}")
def test_invalid_decrypted_utf8_has_stable_error():
    token = Fernet(FERNET_A.encode()).encrypt(b"\xff").decode("ascii")

    with pytest.raises(CredentialDecryptionError) as error:
        decrypt_secret(f"v1:primary:{token}")

    assert error.value.code == "CREDENTIAL_DECRYPTION_FAILED"
