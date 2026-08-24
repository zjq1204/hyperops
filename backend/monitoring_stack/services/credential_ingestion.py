"""Bounded OpenSSH ingestion for monitoring SSH credentials."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Max

from monitoring_stack.models import (
    MonitoringSshCredential,
    MonitoringSshCredentialVersion,
)
from monitoring_stack.services.credential_crypto import encrypt_secret


class PrivateKeyValidationError(Exception):
    def __init__(self, code, field="private_key"):
        super().__init__(code)
        self.code = code
        self.field = field


class DuplicateCredentialFingerprint(Exception):
    def __init__(self, credential_id):
        super().__init__("DUPLICATE_CREDENTIAL_FINGERPRINT")
        self.code = "DUPLICATE_CREDENTIAL_FINGERPRINT"
        self.credential_id = credential_id


@dataclass(frozen=True)
class ParsedPrivateKey:
    normalized_private_key: str
    passphrase: str
    has_passphrase: bool
    algorithm: str
    key_size: int | None
    curve: str
    public_key_fingerprint: str
    public_key_text: str


def normalize_private_key(value):
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PrivateKeyValidationError("PRIVATE_KEY_NOT_UTF8") from exc
    normalized = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.rstrip("\n") + "\n"
    if len(normalized.encode("utf-8")) > settings.MONITORING_CREDENTIAL_MAX_UPLOAD_BYTES:
        raise PrivateKeyValidationError("PRIVATE_KEY_TOO_LARGE")
    if not normalized.strip():
        raise PrivateKeyValidationError("PRIVATE_KEY_INVALID")
    return normalized


def _write_private(path: Path, value: str):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(value)


def _askpass_command(command, passphrase, root):
    script = root / "askpass"
    script.write_text(
        "#!/bin/sh\ncat /proc/self/fd/$CREDENTIAL_PASSPHRASE_FD\n",
        encoding="ascii",
    )
    script.chmod(0o700)
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, str(passphrase).encode("utf-8"))
    finally:
        os.close(write_fd)
    env = {
        **os.environ,
        "SSH_ASKPASS": str(script),
        "SSH_ASKPASS_REQUIRE": "force",
        "DISPLAY": "hyperops:0",
        "CREDENTIAL_PASSPHRASE_FD": str(read_fd),
    }
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
            pass_fds=(read_fd,),
            stdin=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise PrivateKeyValidationError("OPENSSH_UNAVAILABLE") from exc
    finally:
        os.close(read_fd)
        script.unlink(missing_ok=True)


def inspect_private_key(value, passphrase=""):
    normalized = normalize_private_key(value)
    supplied_passphrase = str(passphrase or "")
    if len(supplied_passphrase.encode("utf-8")) > 4096:
        raise PrivateKeyValidationError("PASSPHRASE_TOO_LARGE", "passphrase")
    with tempfile.TemporaryDirectory(prefix="hyperops-credential-ingest-") as tmp:
        root = Path(tmp)
        root.chmod(0o700)
        private_path = root / "private.key"
        public_path = root / "public.key"
        _write_private(private_path, normalized)
        base_command = ["ssh-keygen", "-y", "-P", "", "-f", str(private_path)]
        try:
            empty_result = subprocess.run(
                base_command, capture_output=True, text=True, timeout=15
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise PrivateKeyValidationError("OPENSSH_UNAVAILABLE") from exc

        if empty_result.returncode == 0:
            if supplied_passphrase:
                raise PrivateKeyValidationError(
                    "PASSPHRASE_NOT_REQUIRED", "passphrase"
                )
            public_key = empty_result.stdout.strip()
            protected = False
        else:
            if not supplied_passphrase:
                lowered = (empty_result.stderr or "").lower()
                code = (
                    "PASSPHRASE_REQUIRED"
                    if "passphrase" in lowered or "incorrect" in lowered
                    else "PRIVATE_KEY_INVALID"
                )
                field = "passphrase" if code == "PASSPHRASE_REQUIRED" else "private_key"
                raise PrivateKeyValidationError(code, field)
            result = _askpass_command(
                ["ssh-keygen", "-y", "-f", str(private_path)],
                supplied_passphrase,
                root,
            )
            if result.returncode != 0:
                raise PrivateKeyValidationError("PASSPHRASE_INVALID", "passphrase")
            public_key = result.stdout.strip()
            protected = True

        if not public_key or len(public_key.split()) < 2:
            raise PrivateKeyValidationError("PRIVATE_KEY_INVALID")
        public_key_text = public_key + "\n"
        public_path.write_text(public_key_text, encoding="utf-8")
        public_path.chmod(0o600)
        try:
            fingerprint = subprocess.run(
                ["ssh-keygen", "-lf", str(public_path), "-E", "sha256"],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise PrivateKeyValidationError("OPENSSH_UNAVAILABLE") from exc
        if fingerprint.returncode != 0:
            raise PrivateKeyValidationError("PRIVATE_KEY_INVALID")
        parts = fingerprint.stdout.strip().split()
        if len(parts) < 2:
            raise PrivateKeyValidationError("PRIVATE_KEY_INVALID")
        try:
            key_size = int(parts[0])
        except ValueError:
            key_size = None
        algorithm = public_key.split()[0]
        curve = ""
        curve_match = re.match(r"ecdsa-sha2-(.+)", algorithm)
        if curve_match:
            curve = curve_match.group(1)
        return ParsedPrivateKey(
            normalized_private_key=normalized,
            passphrase=supplied_passphrase if protected else "",
            has_passphrase=protected,
            algorithm=algorithm,
            key_size=key_size,
            curve=curve,
            public_key_fingerprint=parts[1],
            public_key_text=public_key_text,
        )


@transaction.atomic
def create_credential_version(
    *, credential, private_key, passphrase="", actor=None, allow_duplicate=False
):
    parsed = inspect_private_key(private_key, passphrase)
    duplicate = (
        MonitoringSshCredentialVersion.objects.filter(
            public_key_fingerprint=parsed.public_key_fingerprint,
            credential__status=MonitoringSshCredential.STATUS_ACTIVE,
        )
        .exclude(credential=credential)
        .select_related("credential")
        .first()
    )
    if duplicate and not allow_duplicate:
        raise DuplicateCredentialFingerprint(duplicate.credential_id)
    next_version = (
        credential.versions.aggregate(value=Max("version"))["value"] or 0
    ) + 1
    return MonitoringSshCredentialVersion.objects.create(
        credential=credential,
        version=next_version,
        private_key_encrypted=encrypt_secret(parsed.normalized_private_key),
        passphrase_encrypted=(
            encrypt_secret(parsed.passphrase) if parsed.has_passphrase else ""
        ),
        has_passphrase=parsed.has_passphrase,
        algorithm=parsed.algorithm,
        key_size=parsed.key_size,
        curve=parsed.curve,
        public_key_fingerprint=parsed.public_key_fingerprint,
        public_key_text=parsed.public_key_text,
        created_by=actor,
    )


@transaction.atomic
def create_password_credential_version(*, credential, password, actor=None):
    value = str(password or "")
    if not value:
        raise ValueError("PASSWORD_REQUIRED")
    if len(value) > 4096:
        raise ValueError("PASSWORD_TOO_LONG")
    next_version = (
        credential.versions.aggregate(value=Max("version"))["value"] or 0
    ) + 1
    return MonitoringSshCredentialVersion.objects.create(
        credential=credential,
        version=next_version,
        secret_encrypted=encrypt_secret(value),
        algorithm="password",
        created_by=actor,
    )
