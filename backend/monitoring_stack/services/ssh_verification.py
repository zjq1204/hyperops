import json

from django.core import signing
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.dateparse import parse_datetime

from monitoring_stack.models import MonitoringHost


RECEIPT_SALT = "monitoring-stack.ssh-verification.v1"
RECEIPT_MAX_AGE_SECONDS = 600


class SshVerificationReceiptError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def connection_fingerprint(
    *,
    address,
    ssh_user,
    ssh_port,
    ssh_auth_type,
    password="",
    ssh_key_id=None,
    ssh_key_name="",
):
    if ssh_auth_type == MonitoringHost.SSH_AUTH_PASSWORD:
        secret_identity = salted_hmac(
            RECEIPT_SALT,
            str(password or ""),
            algorithm="sha256",
        ).hexdigest()
    else:
        secret_identity = str(ssh_key_id or ssh_key_name or "")
    normalized = {
        "address": str(address or "").strip().lower(),
        "ssh_user": str(ssh_user or "root").strip(),
        "ssh_port": int(ssh_port or 22),
        "ssh_auth_type": str(ssh_auth_type or "").strip(),
        "secret_identity": secret_identity,
    }
    return salted_hmac(
        RECEIPT_SALT,
        json.dumps(normalized, sort_keys=True, separators=(",", ":")),
        algorithm="sha256",
    ).hexdigest()


def connection_fingerprint_for_host(host):
    return connection_fingerprint(
        address=host.address,
        ssh_user=host.ssh_user,
        ssh_port=host.ssh_port,
        ssh_auth_type=host.ssh_auth_type,
        password=host.ssh_password,
        ssh_key_id=host.ssh_key_credential_id,
        ssh_key_name=host.ssh_key,
    )


def issue_verification_receipt(
    *, user_id, host_id, fingerprint, checked_at, latency_ms
):
    return signing.dumps(
        {
            "version": 1,
            "user_id": int(user_id),
            "host_id": int(host_id) if host_id else None,
            "fingerprint": fingerprint,
            "checked_at": checked_at.isoformat(),
            "latency_ms": int(latency_ms),
        },
        salt=RECEIPT_SALT,
        compress=True,
    )


def load_verification_receipt(
    receipt, *, user_id, host_id, expected_fingerprint
):
    try:
        payload = signing.loads(
            receipt,
            salt=RECEIPT_SALT,
            max_age=RECEIPT_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired as exc:
        raise SshVerificationReceiptError("SSH_VERIFICATION_EXPIRED") from exc
    except signing.BadSignature as exc:
        raise SshVerificationReceiptError("SSH_VERIFICATION_MISMATCH") from exc

    expected_host_id = int(host_id) if host_id else None
    if (
        payload.get("version") != 1
        or payload.get("user_id") != int(user_id)
        or payload.get("host_id") != expected_host_id
        or payload.get("fingerprint") != expected_fingerprint
    ):
        raise SshVerificationReceiptError("SSH_VERIFICATION_MISMATCH")
    checked_at = parse_datetime(str(payload.get("checked_at") or ""))
    if checked_at is None:
        raise SshVerificationReceiptError("SSH_VERIFICATION_MISMATCH")
    if timezone.is_naive(checked_at):
        checked_at = timezone.make_aware(checked_at)
    return {
        "fingerprint": payload["fingerprint"],
        "checked_at": checked_at,
        "latency_ms": max(1, int(payload.get("latency_ms") or 1)),
    }


def failed_verification_defaults(*, fingerprint, error_code, checked_at=None):
    return {
        "ssh_verification_status": MonitoringHost.SSH_VERIFICATION_FAILED,
        "ssh_verification_checked_at": checked_at or timezone.now(),
        "ssh_verification_latency_ms": None,
        "ssh_verification_error_code": error_code,
        "ssh_verification_signature": fingerprint,
    }


def verified_verification_defaults(payload):
    return {
        "ssh_verification_status": MonitoringHost.SSH_VERIFICATION_VERIFIED,
        "ssh_verification_checked_at": payload["checked_at"],
        "ssh_verification_latency_ms": payload["latency_ms"],
        "ssh_verification_error_code": "",
        "ssh_verification_signature": payload["fingerprint"],
    }


def unverified_verification_defaults():
    return {
        "ssh_verification_status": MonitoringHost.SSH_VERIFICATION_UNVERIFIED,
        "ssh_verification_checked_at": None,
        "ssh_verification_latency_ms": None,
        "ssh_verification_error_code": "",
        "ssh_verification_signature": "",
    }
