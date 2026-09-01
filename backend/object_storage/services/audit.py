import re
from datetime import timedelta

from django.utils import timezone

from object_storage.models import AuditEvent

_SENSITIVE_METADATA_KEY = re.compile(
    r"(?:secret|ciphertext|cipher|encrypted|envelope|token|password|authorization|private[_-]?key)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"(?i)(?:\bauthorization\s*:|\bbearer\s+|\bbasic\s+)"),
    re.compile(r"(?i)-----BEGIN [^-]*PRIVATE KEY-----"),
    re.compile(r"(?i)\bv1:aesgcm:"),
    re.compile(r"(?i)\bLTAI[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"^[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}$"),
    re.compile(
        r"(?i)(?:^|[\s:_-])(secret|token|password|access[_-]?key|private[_-]?key)"
        r"(?:$|[\s:_-])"
    ),
)
_SENSITIVE_NORMALIZED_KEYS = frozenset(
    {
        "apikey",
        "auth",
        "authorizationheader",
        "credential",
        "credentials",
        "sk",
    }
)


def _is_sensitive_metadata_key(key):
    key = str(key)
    normalized = re.sub(r"[^a-z0-9]", "", key.casefold())
    return bool(_SENSITIVE_METADATA_KEY.search(key)) or (
        normalized in _SENSITIVE_NORMALIZED_KEYS
    )


def sanitize_audit_metadata(metadata):
    """Reject metadata that could persist credentials, envelopes, or tokens."""

    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise ValueError("safe audit metadata must be an object")

    def walk(value):
        if isinstance(value, dict):
            cleaned = {}
            for key, child in value.items():
                if _is_sensitive_metadata_key(key):
                    raise ValueError("sensitive audit metadata is not allowed")
                cleaned[str(key)] = walk(child)
            return cleaned
        if isinstance(value, (list, tuple)):
            return [walk(child) for child in value]
        if isinstance(value, str) and any(
            pattern.search(value) for pattern in _SENSITIVE_VALUE_PATTERNS
        ):
            raise ValueError("sensitive audit metadata is not allowed")
        return value

    return walk(metadata)


def record_audit_event(
    *,
    tenant=None,
    action,
    target_type,
    target_id,
    result,
    actor=None,
    application=None,
    reason="",
    ip_address=None,
    request_id="",
    safe_metadata=None,
):
    del tenant, application
    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        result=result,
        reason=reason,
        ip_address=ip_address,
        request_id=request_id,
        safe_metadata=sanitize_audit_metadata(safe_metadata),
    )


def delete_expired_audit_events(*, now=None, retention_days=None):
    if retention_days is None:
        from object_storage.services.platform import get_object_storage_config

        retention_days = get_object_storage_config().audit_retention_days
    if int(retention_days) < 1:
        raise ValueError("audit retention must be positive")
    now = now or timezone.now()
    cutoff = now - timedelta(days=int(retention_days))
    deleted_count, _ = AuditEvent.objects.filter(created_at__lt=cutoff).delete()
    return deleted_count, cutoff
