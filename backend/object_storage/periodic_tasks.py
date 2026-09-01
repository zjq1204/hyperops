import logging

from celery import shared_task
from django.db import transaction
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
    TASK_REGISTRY.add(
        "object-storage.operation-recovery",
        "object_storage.recover_expired_resource_operations",
        schedule="*/5 * * * *",
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


@shared_task(name="object_storage.recover_expired_resource_operations")
def recover_expired_resource_operations_task(*, now=None):
    from object_storage.models import AccessKey, Bucket, CloudIdentity
    from object_storage.providers.aliyun import build_aliyun_provider
    from object_storage.services.credentials import (
        recover_expired_credential_operation,
    )
    from object_storage.services.lifecycle import (
        recover_expired_bucket_action_claim,
        recover_expired_bucket_configuration_claim,
    )

    now = now or timezone.now()
    configuration_ids = list(
        Bucket.objects.filter(
            configuration_operation_token__gt="",
            configuration_operation_lease_until__lte=now,
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    action_ids = list(
        Bucket.objects.filter(
            action_owner_token__gt="",
            action_lease_until__lte=now,
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    identity_ids = list(
        CloudIdentity.objects.filter(
            credential_operation_token__gt="",
            credential_operation_lease_until__lte=now,
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    for bucket_id in configuration_ids:
        recover_expired_bucket_configuration_claim(bucket_id, now=now)
    for bucket_id in action_ids:
        recover_expired_bucket_action_claim(bucket_id, now=now)
    for identity_id in identity_ids:
        identity = CloudIdentity.objects.select_related("resource_pool").get(
            pk=identity_id
        )
        recover_expired_credential_operation(
            identity_id,
            provider=build_aliyun_provider(identity.resource_pool),
            now=now,
        )

    orphan_ids = list(
        AccessKey.objects.filter(
            operation_token__gt="",
            operation_lease_until__lte=now,
            cloud_identity__credential_operation_token="",
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    for key_id in orphan_ids:
        with transaction.atomic():
            key = AccessKey.objects.select_for_update().get(pk=key_id)
            if not (
                key.operation_token
                and key.operation_lease_until
                and key.operation_lease_until <= now
                and not key.cloud_identity.credential_operation_token
            ):
                continue
            key.cloud_state = AccessKey.CloudState.UNKNOWN
            key.local_state = AccessKey.LocalState.ERROR
            key.operation_token = ""
            key.operation_type = ""
            key.operation_acquired_at = None
            key.operation_lease_until = None
            key.operation_error_code = "CREDENTIAL_OPERATION_CLAIM_EXPIRED"
            key.save(
                update_fields=(
                    "cloud_state",
                    "local_state",
                    "operation_token",
                    "operation_type",
                    "operation_acquired_at",
                    "operation_lease_until",
                    "operation_error_code",
                    "updated_at",
                )
            )
    return {
        "bucket_configuration_count": len(configuration_ids),
        "bucket_action_count": len(action_ids),
        "credential_count": len(identity_ids),
        "orphan_key_count": len(orphan_ids),
    }
