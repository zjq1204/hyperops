import pytest

from monitoring_stack.services.credential_ingestion import (
    PrivateKeyValidationError,
    inspect_private_key,
    normalize_private_key,
)
from monitoring_stack.tests.ssh_key_fixtures import generate_private_key


def test_normalize_private_key_converts_crlf_and_adds_final_newline():
    assert normalize_private_key("line1\r\nline2\r") == "line1\nline2\n"


def test_openssh_ingestion_derives_metadata(tmp_path):
    parsed = inspect_private_key(generate_private_key(tmp_path).replace("\n", "\r\n"))
    assert parsed.algorithm == "ssh-ed25519"
    assert parsed.public_key_fingerprint.startswith("SHA256:")


def test_unnecessary_passphrase_is_field_error(tmp_path):
    with pytest.raises(PrivateKeyValidationError) as error:
        inspect_private_key(generate_private_key(tmp_path), "unused")
    assert (error.value.code, error.value.field) == ("PASSPHRASE_NOT_REQUIRED", "passphrase")
