import logging

from celery import shared_task
from django.utils import timezone

from core.periodic_registry import TASK_REGISTRY
from object_storage.services.audit import delete_expired_audit_events

logger = logging.getLogger(__name__)


def register_periodic_tasks():
    TASK_REGISTRY.add(
        "object-storage.claim-recovery",
        "object_storage.recover_expired_application_claims",
        schedule="*/5 * * * *",
        queue="object_storage",
    )
    TASK_REGISTRY.add(
        "object-storage.audit-cleanup",
        "object_storage.delete_expired_audit_events",
        schedule="0 3 * * *",
        queue="object_storage",
    )
    TASK_REGISTRY.add(
        "object-storage.bucket-deletion",
        "object_storage.delete_expired_buckets",
        schedule="15 3 * * *",
        queue="object_storage",
    )


@shared_task(name="object_storage.delete_expired_audit_events")
def delete_expired_audit_events_task():
    now = timezone.now()
    deleted_count, cutoff = delete_expired_audit_events(now=now)
    logger.info(
        "object_storage.audit_cleanup completed | operation=cleanup_audit_events "
        "range_start=%s range_end=%s deleted_count=%s",
        cutoff.isoformat(),
        now.isoformat(),
        deleted_count,
    )
    return {"deleted_count": deleted_count}


@shared_task(name="object_storage.delete_expired_buckets")
def delete_expired_buckets_task():
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import delete_bucket

    now = timezone.now()
    bucket_ids = list(
        Bucket.objects.filter(
            state=Bucket.State.PENDING_DELETION,
            pending_delete_at__lte=now,
        ).values_list("pk", flat=True)
    )
    deleted_count = 0
    blocked_count = 0
    for bucket_id in bucket_ids:
        bucket = Bucket.objects.get(pk=bucket_id)
        result = delete_bucket(bucket=bucket)
        if result.state == Bucket.State.RELEASED:
            deleted_count += 1
        else:
            blocked_count += 1
    return {
        "candidate_count": len(bucket_ids),
        "deleted_count": deleted_count,
        "blocked_count": blocked_count,
    }
