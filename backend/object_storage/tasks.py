from celery import shared_task

from object_storage.services.applications import (
    MAX_PROVIDER_RETRIES,
    execute_application_batch,
    mark_batch_manual_required,
    is_retryable_provider_error,
)
from object_storage.services.provider_errors import ObjectStorageProviderError


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
        batch = mark_batch_manual_required(batch_id, error)
        return _batch_result(batch)


@shared_task(
    bind=True,
    name="object_storage.run_storage_application_batch",
    max_retries=MAX_PROVIDER_RETRIES,
)
def run_storage_application_batch(self, batch_id):
    return _run_storage_application_batch(self, batch_id)
