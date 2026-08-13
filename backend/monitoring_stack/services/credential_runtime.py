"""Task-scoped runtime material for encrypted database SSH credentials."""

from __future__ import annotations

import os
import logging
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from monitoring_stack.services.credential_crypto import (
    CredentialDecryptionError,
    CredentialEncryptionUnavailable,
    decrypt_secret,
)
from monitoring_stack.services.credential_ingestion import (
    PrivateKeyValidationError,
    inspect_private_key,
)

logger = logging.getLogger(__name__)


class CredentialRuntimeError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass
class MaterializedCredentialBundle:
    key_paths: dict[int, Path]
    process_env: dict[str, str]
    snapshots: list[dict]


def _private_write(path, value):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(value)


def _parse_agent_output(output):
    values = {}
    for key in ("SSH_AUTH_SOCK", "SSH_AGENT_PID"):
        match = re.search(rf"{key}=([^;\n]+)", output or "")
        if match:
            values[key] = match.group(1)
    return values


class DatabaseSshCredentialProvider:
    @contextmanager
    def materialize(self, versions):
        unique = {version.id: version for version in versions}
        decrypted = {}
        try:
            for version in unique.values():
                decrypted[version.id] = (
                    decrypt_secret(version.private_key_encrypted),
                    decrypt_secret(version.passphrase_encrypted)
                    if version.has_passphrase
                    else "",
                )
        except (CredentialDecryptionError, CredentialEncryptionUnavailable) as exc:
            raise CredentialRuntimeError("CREDENTIAL_UNAVAILABLE") from exc

        root = Path(tempfile.mkdtemp(prefix="hyperops-monitoring-credentials-"))
        root.chmod(0o700)
        key_paths = {}
        agent_env = {}
        askpass = root / "askpass"
        try:
            for version_id, (private_key, _passphrase) in decrypted.items():
                path = root / f"{version_id}.key"
                _private_write(path, private_key)
                key_paths[version_id] = path

            protected = [v for v in unique.values() if v.has_passphrase]
            if protected:
                try:
                    agent = subprocess.run(
                        ["ssh-agent", "-s"],
                        capture_output=True,
                        text=True,
                        timeout=settings.MONITORING_CREDENTIAL_AGENT_TIMEOUT_SECONDS,
                    )
                except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                    raise CredentialRuntimeError(
                        "CREDENTIAL_AGENT_START_FAILED"
                    ) from exc
                agent_env = _parse_agent_output(agent.stdout)
                if agent.returncode != 0 or len(agent_env) != 2:
                    raise CredentialRuntimeError("CREDENTIAL_AGENT_START_FAILED")
                askpass.write_text(
                    "#!/bin/sh\ncat /proc/self/fd/$CREDENTIAL_PASSPHRASE_FD\n",
                    encoding="ascii",
                )
                askpass.chmod(0o700)
                for version in protected:
                    read_fd, write_fd = os.pipe()
                    try:
                        os.write(write_fd, decrypted[version.id][1].encode("utf-8"))
                    finally:
                        os.close(write_fd)
                    env = {
                        **os.environ,
                        **agent_env,
                        "SSH_ASKPASS": str(askpass),
                        "SSH_ASKPASS_REQUIRE": "force",
                        "DISPLAY": "hyperops:0",
                        "CREDENTIAL_PASSPHRASE_FD": str(read_fd),
                    }
                    try:
                        loaded = subprocess.run(
                            ["ssh-add", str(key_paths[version.id])],
                            capture_output=True,
                            text=True,
                            timeout=settings.MONITORING_CREDENTIAL_AGENT_TIMEOUT_SECONDS,
                            env=env,
                            pass_fds=(read_fd,),
                            stdin=subprocess.DEVNULL,
                        )
                    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                        raise CredentialRuntimeError(
                            "CREDENTIAL_AGENT_LOAD_FAILED"
                        ) from exc
                    finally:
                        os.close(read_fd)
                    if loaded.returncode != 0:
                        raise CredentialRuntimeError("CREDENTIAL_AGENT_LOAD_FAILED")

            snapshots = [
                {
                    "credential_id": version.credential_id,
                    "version_id": version.id,
                    "public_key_fingerprint": version.public_key_fingerprint,
                }
                for version in unique.values()
            ]
            yield MaterializedCredentialBundle(key_paths, agent_env, snapshots)
        finally:
            if agent_env:
                try:
                    subprocess.run(
                        ["ssh-agent", "-k"],
                        capture_output=True,
                        text=True,
                        timeout=settings.MONITORING_CREDENTIAL_AGENT_TIMEOUT_SECONDS,
                        env={**os.environ, **agent_env},
                    )
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
            for path in key_paths.values():
                try:
                    size = path.stat().st_size
                    with path.open("r+b", buffering=0) as handle:
                        handle.write(b"\0" * size)
                except OSError:
                    pass
            shutil.rmtree(root, ignore_errors=True)


@contextmanager
def materialize_legacy_credential(credential):
    """Temporary staged compatibility for active, unmigrated legacy files.

    Remove this adapter after migration reports no active version gaps and no
    nonblank legacy_file_name values in production.
    """
    if credential.status == credential.STATUS_NEEDS_REUPLOAD:
        raise CredentialRuntimeError("CREDENTIAL_NEEDS_REUPLOAD")
    path = credential.storage_path
    if (
        credential.status != credential.STATUS_ACTIVE
        or credential.active_version_id
        or not path
        or not path.is_file()
    ):
        raise CredentialRuntimeError("CREDENTIAL_UNAVAILABLE")
    try:
        parsed = inspect_private_key(path.read_bytes())
    except (OSError, PrivateKeyValidationError) as exc:
        raise CredentialRuntimeError("CREDENTIAL_NEEDS_REUPLOAD") from exc
    logger.warning(
        "using staged legacy monitoring SSH credential id=%s", credential.id
    )
    from monitoring_stack.models import MonitoringCredentialAudit
    MonitoringCredentialAudit.objects.create(
        credential=credential,
        action="validate",
        status="legacy_compatibility",
        metadata={"public_key_fingerprint": parsed.public_key_fingerprint},
    )
    root = Path(tempfile.mkdtemp(prefix="hyperops-monitoring-legacy-credential-"))
    root.chmod(0o700)
    key_path = root / f"{credential.id}.key"
    try:
        _private_write(key_path, parsed.normalized_private_key)
        yield MaterializedCredentialBundle(
            key_paths={credential.id: key_path},
            process_env={},
            snapshots=[{
                "credential_id": credential.id,
                "version_id": None,
                "public_key_fingerprint": parsed.public_key_fingerprint,
            }],
        )
    finally:
        try:
            size = key_path.stat().st_size
            with key_path.open("r+b", buffering=0) as handle:
                handle.write(b"\0" * size)
        except OSError:
            pass
        shutil.rmtree(root, ignore_errors=True)
