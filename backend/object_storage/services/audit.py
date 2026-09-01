from datetime import timedelta

from django.utils import timezone

from object_storage.models import AuditEvent

SAFE_METADATA_KEYS = frozenset(
    {
        "provider",
        "changed_fields",
        "last_four",
        "fingerprint",
        "request_id",
        "provider_request_id",
        "action_type",
        "stage",
        "error_code",
        "status",
        "result",
        "bucket_name",
        "region",
        "count",
        "total_count",
        "success_count",
        "failed_count",
        "user_id",
        "bucket_id",
        "application_id",
        "item_id",
    }
)
SAFE_METADATA_LIST_KEYS = frozenset({"changed_fields"})


def _is_controlled_string(value):
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 64
        and value[0].isalpha()
        and all(character.isalnum() or character == "_" for character in value)
    )


def sanitize_audit_metadata(metadata):
    """Allow only documented, non-secret audit fields and JSON-safe values."""

    if metadata is None:
        return {}
    if not isinstance(metadata, dict):
        raise ValueError("safe audit metadata must be an object")
    cleaned = {}
    for key, value in metadata.items():
        if key not in SAFE_METADATA_KEYS:
            raise ValueError("sensitive audit metadata is not allowed")
        if key in SAFE_METADATA_LIST_KEYS:
            if not isinstance(value, list) or not all(
                _is_controlled_string(item) for item in value
            ):
                raise ValueError("sensitive audit metadata is not allowed")
            cleaned[key] = list(value)
        elif isinstance(value, (dict, list, tuple)):
            raise ValueError("sensitive audit metadata is not allowed")
        elif not isinstance(value, (str, int, float, bool, type(None))):
            raise ValueError("sensitive audit metadata is not allowed")
        else:
            cleaned[key] = value
    return cleaned


def record_audit_event(
    *,
    action,
    target_type,
    target_id,
    result,
    actor=None,
    reason="",
    ip_address=None,
    request_id="",
    safe_metadata=None,
):
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
