import stat

import pytest

from django.contrib.auth import get_user_model

from monitoring_stack.models import MonitoringSshCredential, MonitoringSshCredentialVersion
from monitoring_stack.services.credential_crypto import encrypt_secret
from monitoring_stack.services.credential_runtime import DatabaseSshCredentialProvider


@pytest.mark.django_db
def test_materialized_key_is_private_and_removed():
    user = get_user_model().objects.create_user(username="runtime-user")
    credential = MonitoringSshCredential.objects.create(name="runtime", created_by=user)
    version = MonitoringSshCredentialVersion.objects.create(
        credential=credential, version=1,
        private_key_encrypted=encrypt_secret("private\n"),
        algorithm="ssh-ed25519", public_key_fingerprint="SHA256:test",
        public_key_text="ssh-ed25519 AAAA\n", created_by=user,
    )
    with DatabaseSshCredentialProvider().materialize([version]) as bundle:
        path = bundle.key_paths[version.id]
        root = path.parent
        assert stat.S_IMODE(root.stat().st_mode) == 0o700
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert set(bundle.snapshots[0]) == {"credential_id", "version_id", "public_key_fingerprint"}
    assert not root.exists()


@pytest.mark.django_db
def test_materialized_password_is_memory_only():
    user = get_user_model().objects.create_user(username="password-runtime-user")
    credential = MonitoringSshCredential.objects.create(
        name="password-runtime",
        credential_type="password",
        created_by=user,
    )
    version = MonitoringSshCredentialVersion.objects.create(
        credential=credential,
        version=1,
        secret_encrypted=encrypt_secret("runtime-password"),
        algorithm="password",
        validation_status=MonitoringSshCredentialVersion.VALIDATION_VALID,
        created_by=user,
    )

    with DatabaseSshCredentialProvider().materialize([version]) as bundle:
        assert bundle.passwords == {version.id: "runtime-password"}
        assert bundle.key_paths == {}
        assert list(bundle.snapshots) == [
            {
                "credential_id": credential.id,
                "version_id": version.id,
                "credential_type": "password",
            }
        ]
