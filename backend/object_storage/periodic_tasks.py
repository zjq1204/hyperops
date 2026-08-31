import logging

from celery import shared_task
from django.utils import timezone

from core.periodic_registry import TASK_REGISTRY
from object_storage.services.audit import delete_expired_audit_events

logger = logging.getLogger(__name__)


def register_periodic_tasks():
    TASK_REGISTRY.add(
        "object-storage.audit-cleanup",
        "object_storage.delete_expired_audit_events",
        schedule="0 3 * * *",
        queue="object_storage",
    )


@shared_task(name="object_storage.delete_expired_audit_events")
def delete_expired_audit_events_task():
    now = timezone.now()
    deleted_count, cutoff = delete_expired_audit_events(now=now)
    logger.info(
        "对象存储审计记录清理完成 | operation=cleanup_audit_events "
        "range_start=%s range_end=%s count=%s",
        cutoff.isoformat(),
        now.isoformat(),
        deleted_count,
    )
    return {"deleted_count": deleted_count}
