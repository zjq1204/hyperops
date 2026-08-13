"""Lifecycle, validation, and sanitized audit services for SSH credentials."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from monitoring_stack.models import (
    MonitoringCredentialAudit,
    MonitoringCredentialValidation,
    MonitoringHost,
    MonitoringSshCredential,
    MonitoringSshCredentialVersion,
)
from monitoring_stack.services.credential_crypto import decrypt_secret
from monitoring_stack.services.credential_runtime import (
    CredentialRuntimeError,
    DatabaseSshCredentialProvider,
)
from monitoring_stack.services.ssh_verification import (
    connection_fingerprint,
    unverified_verification_defaults,
)


AUDIT_METADATA_KEYS = {
    "error_code", "latency_ms", "old_version_id", "new_version_id",
    "validation_total", "validation_passed", "validation_failed",
    "public_key_fingerprint", "algorithm", "key_size", "curve",
}


class CredentialLifecycleError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class CredentialActivationError(CredentialLifecycleError):
    pass


class CredentialReferenceConflict(CredentialLifecycleError):
    def __init__(self, hosts):
        super().__init__("CREDENTIAL_IN_USE")
        self.hosts = hosts


def request_context_from_request(request):
    return {
        "source_ip": request.META.get("REMOTE_ADDR") or None,
        "request_id": request.headers.get("X-Request-ID", "")[:128],
    }


def record_credential_audit(
    *, action, status, credential=None, version=None, actor=None,
    affected_host_ids=None, metadata=None, request_context=None,
):
    context = request_context or {}
    sanitized = {
        key: value for key, value in (metadata or {}).items()
        if key in AUDIT_METADATA_KEYS
    }
    return MonitoringCredentialAudit.objects.create(
        credential=credential,
        version=version,
        action=action,
        status=status,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        source_ip=context.get("source_ip") or None,
        request_id=str(context.get("request_id") or "")[:128],
        affected_host_ids=list(affected_host_ids or []),
        metadata=sanitized,
    )


def assert_credential_assignable(credential):
    if credential.status == MonitoringSshCredential.STATUS_NEEDS_REUPLOAD:
        raise CredentialLifecycleError("CREDENTIAL_NEEDS_REUPLOAD")
    version = credential.active_version
    if credential.status != MonitoringSshCredential.STATUS_ACTIVE or not version:
        raise CredentialLifecycleError("CREDENTIAL_UNAVAILABLE")
    if version.validation_status != MonitoringSshCredentialVersion.VALIDATION_VALID:
        raise CredentialLifecycleError("CREDENTIAL_NOT_VALIDATED")
    try:
        decrypt_secret(version.private_key_encrypted)
        if version.has_passphrase:
            decrypt_secret(version.passphrase_encrypted)
    except Exception as exc:
        raise CredentialLifecycleError("CREDENTIAL_UNAVAILABLE") from exc
    return version


def _host_fingerprint(host, version):
    return connection_fingerprint(
        address=host.address,
        ssh_user=host.ssh_user,
        ssh_port=host.ssh_port,
        ssh_auth_type=MonitoringHost.SSH_AUTH_KEY,
        ssh_credential_id=version.credential_id,
        ssh_credential_version_id=version.id,
        ssh_public_key_fingerprint=version.public_key_fingerprint,
    )


def validate_version_on_hosts(
    *, version, hosts, actor=None, request_context=None, connection_checker=None
):
    from monitoring_stack.services.core import check_monitoring_ssh_connection

    checker = connection_checker or check_monitoring_ssh_connection
    hosts = list(hosts)
    results = []
    with DatabaseSshCredentialProvider().materialize([version]) as bundle:
        for host in hosts:
            fingerprint = _host_fingerprint(host, version)
            try:
                result = checker(
                    address=host.address,
                    ssh_user=host.ssh_user or "root",
                    ssh_port=host.ssh_port or 22,
                    key_path=bundle.key_paths[version.id],
                    process_env=bundle.process_env,
                    key_prevalidated=True,
                )
                status, error_code = "success", ""
                latency = result.get("latency_ms")
            except Exception as exc:
                status = "failed"
                error_code = getattr(exc, "code", "SSH_COMMAND_FAILED")
                latency = None
            results.append(MonitoringCredentialValidation.objects.create(
                version=version, host=host if getattr(host, "pk", None) else None,
                connection_fingerprint=fingerprint, status=status,
                error_code=error_code, latency_ms=latency,
                checked_by=actor if getattr(actor, "is_authenticated", False) else None,
            ))
    failures = [item for item in results if item.status != "success"]
    version.validation_status = (
        version.VALIDATION_INVALID if failures else version.VALIDATION_VALID
    )
    version.validation_error_code = failures[0].error_code if failures else ""
    version.save(update_fields=["validation_status", "validation_error_code"])
    record_credential_audit(
        action="validate", status="failed" if failures else "success",
        credential=version.credential, version=version, actor=actor,
        affected_host_ids=[host.id for host in hosts if getattr(host, "id", None)],
        metadata={"validation_total": len(results), "validation_passed": len(results) - len(failures), "validation_failed": len(failures)},
        request_context=request_context,
    )
    return results


def activate_version(*, credential_id, version_id, actor=None, request_context=None):
    required_hosts = list(MonitoringHost.objects.filter(
        ssh_key_credential_id=credential_id, enabled=True
    ))
    version = MonitoringSshCredentialVersion.objects.get(
        pk=version_id, credential_id=credential_id
    )
    if version.validation_status != version.VALIDATION_VALID:
        raise CredentialActivationError("CREDENTIAL_VALIDATION_INCOMPLETE")
    for host in required_hosts:
        latest = version.validations.filter(host=host).order_by("-checked_at", "-id").first()
        if not latest or latest.status != MonitoringCredentialValidation.STATUS_SUCCESS:
            raise CredentialActivationError("CREDENTIAL_VALIDATION_INCOMPLETE")
    try:
        decrypt_secret(version.private_key_encrypted)
        if version.has_passphrase:
            decrypt_secret(version.passphrase_encrypted)
    except Exception as exc:
        raise CredentialActivationError("CREDENTIAL_UNAVAILABLE") from exc

    with transaction.atomic():
        credential = MonitoringSshCredential.objects.select_for_update().get(pk=credential_id)
        if credential.status == credential.STATUS_ARCHIVED:
            raise CredentialActivationError("CREDENTIAL_ARCHIVED")
        target = MonitoringSshCredentialVersion.objects.select_for_update().get(pk=version_id, credential=credential)
        old = credential.active_version
        now = timezone.now()
        if old and old.id != target.id:
            old.retired_at = now
            old.save(update_fields=["retired_at"])
        target.activated_at = target.activated_at or now
        target.retired_at = None
        target.save(update_fields=["activated_at", "retired_at"])
        credential.active_version = target
        credential.status = credential.STATUS_ACTIVE
        credential.updated_by = actor if getattr(actor, "is_authenticated", False) else None
        credential.save(update_fields=["active_version", "status", "updated_by", "updated_at"])
        defaults = unverified_verification_defaults()
        MonitoringHost.objects.filter(ssh_key_credential=credential).update(**defaults)
        record_credential_audit(
            action="activate_version", status="success", credential=credential,
            version=target, actor=actor,
            affected_host_ids=[host.id for host in required_hosts],
            metadata={"old_version_id": getattr(old, "id", None), "new_version_id": target.id},
            request_context=request_context,
        )
    return credential


def _referenced_hosts(credential):
    return [{"id": host.id, "name": host.hostname} for host in credential.hosts.order_by("id")]


def archive_credential(*, credential_id, actor=None, request_context=None):
    with transaction.atomic():
        credential = MonitoringSshCredential.objects.select_for_update().get(pk=credential_id)
        hosts = _referenced_hosts(credential)
        if hosts:
            raise CredentialReferenceConflict(hosts)
        credential.status = credential.STATUS_ARCHIVED
        credential.archived_at = timezone.now()
        credential.updated_by = actor if getattr(actor, "is_authenticated", False) else None
        credential.save(update_fields=["status", "archived_at", "updated_by", "updated_at"])
        record_credential_audit(action="archive", status="success", credential=credential, actor=actor, request_context=request_context)
    return credential


def delete_credential(*, credential_id, actor=None, request_context=None):
    with transaction.atomic():
        credential = MonitoringSshCredential.objects.select_for_update().get(pk=credential_id)
        hosts = _referenced_hosts(credential)
        if hosts:
            raise CredentialReferenceConflict(hosts)
        if credential.status != credential.STATUS_ARCHIVED:
            raise CredentialLifecycleError("CREDENTIAL_ARCHIVE_REQUIRED")
        cutoff = timezone.now() - timedelta(days=settings.MONITORING_CREDENTIAL_SECRET_RETENTION_DAYS)
        if not credential.archived_at or credential.archived_at > cutoff:
            raise CredentialLifecycleError("CREDENTIAL_RETENTION_ACTIVE")
        record_credential_audit(action="delete", status="success", credential=credential, actor=actor, request_context=request_context)
        credential.delete()
