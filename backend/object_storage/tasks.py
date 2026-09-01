import logging

from celery import shared_task
from django.utils import timezone

from object_storage.models import ApplicationBatch
from object_storage.services.applications import (
    MAX_PROVIDER_RETRIES,
    execute_application_batch,
    is_retryable_provider_error,
    mark_claim_recovery_enqueue_failed,
    mark_batch_manual_required,
    recover_expired_application_claim,
)
from object_storage.services.provider_errors import ObjectStorageProviderError

logger = logging.getLogger(__name__)


def _batch_result(batch):
    return {
        "batch_id": batch.pk,
        "status": batch.status,
        "counts": {
            "item_count": int(batch.item_count),
            "pending_count": int(batch.pending_count),
            "success_count": int(batch.success_count),
            "failed_count": int(batch.failed_count),
        },
    }


def _run_storage_application_batch(task, batch_id):
    task_id = str(getattr(task.request, "id", "") or "")
    execution_key = (
        f"{task_id}:{getattr(task.request, 'retries', 0)}" if task_id else ""
    )
    try:
        return _batch_result(
            execute_application_batch(batch_id, execution_key=execution_key)
        )
    except ObjectStorageProviderError as error:
        retries = int(getattr(task.request, "retries", 0) or 0)
        if is_retryable_provider_error(error) and retries < MAX_PROVIDER_RETRIES:
            raise task.retry(exc=error, countdown=2 ** (retries + 1))
        batch = mark_batch_manual_required(
            batch_id,
            error,
            expected_claim_version=getattr(
                error,
                "application_claim_version",
                None,
            ),
        )
        return _batch_result(batch)


@shared_task(
    bind=True,
    name="object_storage.run_storage_application_batch",
    max_retries=MAX_PROVIDER_RETRIES,
)
def run_storage_application_batch(self, batch_id):
    return _run_storage_application_batch(self, batch_id)


@shared_task(name="object_storage.recover_expired_application_claims")
def recover_expired_application_claims():
    now = timezone.now()
    batch_ids = list(
        ApplicationBatch.objects.filter(
            status=ApplicationBatch.Status.RUNNING,
            run_lease_until__lt=now,
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    recovered_count = 0
    enqueued_count = 0
    failed_enqueue_count = 0
    failed_count = 0
    recovered_batches = []
    for batch_id in batch_ids:
        try:
            batch, recovery_generation = recover_expired_application_claim(
                batch_id, now=now
            )
        except Exception:
            failed_count += 1
            logger.exception(
                "Object storage claim recovery failed batch_id=%s",
                batch_id,
            )
            continue
        if (
            recovery_generation is not None
            and not batch.running_task_id
            and not batch.owner_token
        ):
            recovered_count += 1
            recovered_batches.append((batch_id, recovery_generation))
    for batch_id, recovery_generation in recovered_batches:
        try:
            run_storage_application_batch.delay(batch_id)
        except Exception:
            failed_enqueue_count += 1
            logger.exception(
                "Object storage recovered claim enqueue failed batch_id=%s",
                batch_id,
            )
            try:
                mark_claim_recovery_enqueue_failed(batch_id, recovery_generation)
            except Exception:
                logger.exception(
                    "Object storage recovered claim manual fallback failed "
                    "batch_id=%s",
                    batch_id,
                )
            continue
        enqueued_count += 1
    return {
        "candidate_count": len(batch_ids),
        "recovered_count": recovered_count,
        "enqueued_count": enqueued_count,
        "failed_enqueue_count": failed_enqueue_count,
        "failed_count": failed_count,
    }


@shared_task(name="object_storage.release_bucket")
def release_bucket_task(
    bucket_id, *, actor_id=None, reason="", action_generation, owner_token
):
    from django.contrib.auth import get_user_model

    from object_storage.services.lifecycle import _release_bucket_cloud

    actor = get_user_model().objects.get(pk=actor_id) if actor_id else None
    bucket = _release_bucket_cloud(
        bucket_id,
        action_generation=action_generation,
        owner_token=owner_token,
        actor=actor,
        reason=reason,
    )
    return {"bucket_id": bucket.pk, "state": bucket.state}


@shared_task(name="object_storage.recover_bucket")
def recover_bucket_task(bucket_id, *, actor_id=None, bucket_name="", confirmed=True):
    from django.contrib.auth import get_user_model

    from object_storage.models import Bucket
    from object_storage.services.lifecycle import recover_bucket

    bucket = Bucket.objects.get(pk=bucket_id)
    actor = get_user_model().objects.get(pk=actor_id) if actor_id else bucket.owner
    result = recover_bucket(
        bucket=bucket,
        actor=actor,
        bucket_name=bucket_name or bucket.name,
        confirmed=confirmed,
    )
    return {"bucket_id": result.pk, "state": result.state}


@shared_task(name="object_storage.delete_bucket")
def delete_bucket_task(bucket_id):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import delete_bucket

    bucket = Bucket.objects.get(pk=bucket_id)
    result = delete_bucket(bucket=bucket)
    return {"bucket_id": result.pk, "state": result.state}


@shared_task(name="object_storage.update_bucket_configuration")
def update_bucket_configuration_task(
    bucket_id,
    *,
    actor_id=None,
    reason="",
    configuration_generation,
    operation_token,
):
    from django.contrib.auth import get_user_model

    from object_storage.services.lifecycle import _apply_bucket_configuration

    actor = get_user_model().objects.get(pk=actor_id) if actor_id else None
    result = _apply_bucket_configuration(
        bucket_id,
        configuration_generation=configuration_generation,
        operation_token=operation_token,
        actor=actor,
        reason=reason,
    )
    return {"bucket_id": result.pk, "state": result.state}


@shared_task(name="object_storage.suspend_user_resources")
def suspend_user_resources_task(identity_id, *, actor_id=None, reason=""):
    from django.contrib.auth import get_user_model

    from object_storage.services.lifecycle import _disable_identity_keys

    actor = get_user_model().objects.get(pk=actor_id) if actor_id else None
    identity = _disable_identity_keys(identity_id, actor=actor, reason=reason)
    return {"identity_id": identity.pk, "state": identity.state}
