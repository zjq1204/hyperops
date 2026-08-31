from datetime import timedelta

from django.utils import timezone

from object_storage.models import StorageAuditEvent


def record_audit_event(
    *,
    tenant,
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
    return StorageAuditEvent.objects.create(
        tenant=tenant,
        actor=actor,
        application=application,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        result=result,
        reason=reason,
        ip_address=ip_address,
        request_id=request_id,
        safe_metadata=safe_metadata or {},
    )


def delete_expired_audit_events(*, now=None, retention_days=30):
    now = now or timezone.now()
    cutoff = now - timedelta(days=retention_days)
    deleted_count, _ = StorageAuditEvent.objects.filter(created_at__lt=cutoff).delete()
    return deleted_count, cutoff
