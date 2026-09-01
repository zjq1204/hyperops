import json
from io import StringIO

import pytest
from django.core.management.base import CommandError

from object_storage.crypto import (
    SecretConfigurationError,
    SecretDecryptionError,
    decrypt_secret,
    encrypt_secret,
    is_secret_envelope,
)


def test_encrypt_secret_round_trips_with_derived_object_storage_key(settings):
    settings.SECRET_KEY = "stable-test-root-secret"

    first = encrypt_secret("secret-value")
    second = encrypt_secret("secret-value")

    assert first.startswith("v1:aesgcm:")
    assert decrypt_secret(first) == "secret-value"
    assert first != second
    assert is_secret_envelope(first) is True


def test_tampered_ciphertext_is_rejected(settings):
    settings.SECRET_KEY = "stable-test-root-secret"
    envelope = encrypt_secret("secret-value")
    replacement = "A" if envelope[-1] != "A" else "B"

    with pytest.raises(SecretDecryptionError):
        decrypt_secret(f"{envelope[:-1]}{replacement}")


@pytest.mark.parametrize(
    "value",
    [
        "",
        "plaintext",
        "v2:aesgcm:bm9uY2U:Y2lwaGVydGV4dA",
        "v1:unknown:bm9uY2U:Y2lwaGVydGV4dA",
        "v1:aesgcm:not-base64!:Y2lwaGVydGV4dA",
    ],
)
def test_malformed_or_unsupported_envelopes_are_rejected(settings, value):
    settings.SECRET_KEY = "stable-test-root-secret"

    assert is_secret_envelope(value) is False
    with pytest.raises(SecretDecryptionError):
        decrypt_secret(value)


@pytest.mark.parametrize(
    "root_secret",
    [
        "",
        "django-insecure-$k0f0!qp@0k%1xa_)zy!+xvwpv)+&$q&!d69ma@l615bdc2ytd",
    ],
)
def test_default_or_empty_root_secret_is_rejected(settings, root_secret):
    settings.SECRET_KEY = root_secret

    with pytest.raises(SecretConfigurationError):
        encrypt_secret("secret-value")


class FakeQuerySet:
    def __init__(self, records):
        self.records = records

    def select_for_update(self):
        return self

    def only(self, *fields):
        return self

    def order_by(self, *fields):
        return self

    def iterator(self, chunk_size):
        return iter(self.records)


class FakeRecord:
    def __init__(self, pk, **fields):
        self.pk = pk
        self.saved_fields = []
        for name, value in fields.items():
            setattr(self, name, value)

    def save(self, *, update_fields):
        self.saved_fields.append(tuple(update_fields))


def test_reencrypt_command_rewraps_all_configured_secret_fields(
    db, settings, monkeypatch
):
    from object_storage.crypto import (
        _decrypt_secret_with_root,
        _encrypt_secret_with_root,
    )
    from object_storage.management.commands.reencrypt_object_storage_secrets import (
        Command,
    )

    old_root = "old-stable-root-secret"
    new_root = "new-stable-root-secret"
    app = FakeRecord(
        1,
        app_secret_encrypted=_encrypt_secret_with_root("feishu-secret", old_root),
    )
    pool = FakeRecord(
        2,
        management_access_key_encrypted=_encrypt_secret_with_root(
            "manager-ak", old_root
        ),
        management_secret_key_encrypted=_encrypt_secret_with_root(
            "manager-sk", old_root
        ),
    )

    class FakeAppModel:
        objects = FakeQuerySet([app])

    class FakePoolModel:
        objects = FakeQuerySet([pool])

    monkeypatch.setattr(
        Command,
        "get_secret_field_targets",
        lambda self: (
            (
                "object_storage.PlatformFeishuConfig",
                FakeAppModel,
                ("app_secret_encrypted",),
            ),
            (
                "object_storage.StorageResourcePool",
                FakePoolModel,
                (
                    "management_access_key_encrypted",
                    "management_secret_key_encrypted",
                ),
            ),
        ),
    )
    answers = iter([old_root, new_root])
    monkeypatch.setattr("getpass.getpass", lambda prompt: next(answers))
    output = StringIO()
    command = Command(stdout=output)

    command.handle(confirm=True, batch_size=100)

    summary = json.loads(output.getvalue())
    assert summary["updated_fields"] == 3
    assert summary["updated_rows"] == 2
    assert (
        _decrypt_secret_with_root(app.app_secret_encrypted, new_root) == "feishu-secret"
    )
    assert (
        _decrypt_secret_with_root(pool.management_access_key_encrypted, new_root)
        == "manager-ak"
    )
    assert (
        _decrypt_secret_with_root(pool.management_secret_key_encrypted, new_root)
        == "manager-sk"
    )
    assert app.saved_fields == [("app_secret_encrypted",)]
    assert pool.saved_fields == [
        ("management_access_key_encrypted", "management_secret_key_encrypted")
    ]


def test_reencrypt_command_does_not_write_when_an_old_envelope_is_invalid(
    db,
    monkeypatch,
):
    from object_storage.crypto import _encrypt_secret_with_root
    from object_storage.management.commands.reencrypt_object_storage_secrets import (
        Command,
    )

    old_root = "old-stable-root-secret"
    record = FakeRecord(
        1,
        first_encrypted=_encrypt_secret_with_root("valid", old_root),
        second_encrypted="invalid-envelope",
    )

    class FakeModel:
        objects = FakeQuerySet([record])

    monkeypatch.setattr(
        Command,
        "get_secret_field_targets",
        lambda self: (
            (
                "object_storage.FakeSecretModel",
                FakeModel,
                ("first_encrypted", "second_encrypted"),
            ),
        ),
    )
    answers = iter([old_root, "new-stable-root-secret"])
    monkeypatch.setattr("getpass.getpass", lambda prompt: next(answers))

    with pytest.raises(CommandError, match="re-encryption aborted"):
        Command(stdout=StringIO()).handle(confirm=True, batch_size=100)

    assert record.saved_fields == []


def test_reencrypt_command_requires_explicit_confirmation():
    from object_storage.management.commands.reencrypt_object_storage_secrets import (
        Command,
    )

    with pytest.raises(CommandError, match="--confirm"):
        Command(stdout=StringIO()).handle(confirm=False, batch_size=100)


def test_reencrypt_command_targets_platform_secret_models():
    from object_storage.management.commands.reencrypt_object_storage_secrets import (
        SECRET_FIELD_TARGETS,
    )

    assert SECRET_FIELD_TARGETS == (
        ("PlatformFeishuConfig", ("app_secret_encrypted",)),
        (
            "StorageResourcePool",
            (
                "management_access_key_encrypted",
                "management_secret_key_encrypted",
            ),
        ),
        (
            "AccessKey",
            ("access_key_id_encrypted", "secret_access_key_encrypted"),
        ),
    )
