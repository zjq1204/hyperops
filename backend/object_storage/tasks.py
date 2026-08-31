import logging

from celery import shared_task

from object_storage.services.applications import (
    MAX_PROVIDER_RETRIES,
    execute_application,
    is_retryable_provider_error,
    mark_application_manual_required,
)
from object_storage.services.provider_errors import ObjectStorageProviderError

logger = logging.getLogger(__name__)


def _application_result(application):
    return {
        "application_id": application.pk,
        "status": application.status,
    }


def _run_storage_application(task, application_id):
    try:
        return _application_result(execute_application(application_id))
    except ObjectStorageProviderError as error:
        retries = getattr(task.request, "retries", 0)
        if is_retryable_provider_error(error) and retries < MAX_PROVIDER_RETRIES:
            raise task.retry(exc=error, countdown=2 ** (retries + 1))
        if not is_retryable_provider_error(error):
            application = mark_application_manual_required(application_id, error)
            return _application_result(application)
        application = mark_application_manual_required(application_id, error)
        return _application_result(application)


@shared_task(
    bind=True,
    name="object_storage.run_storage_application",
    max_retries=MAX_PROVIDER_RETRIES,
)
def run_storage_application(self, application_id):
    return _run_storage_application(self, application_id)
