from django.db import transaction

from object_storage.models import ApiIdempotencyRecord
from object_storage.permissions import has_object_storage_admin_access


def resolve_idempotency_outcome(*, record, actor, resolution):
    """Allow an object-storage administrator to clear a frozen operation claim."""
    if not has_object_storage_admin_access(actor):
        raise PermissionError("ADMIN_REQUIRED")
    if resolution != "retry":
        raise ValueError("IDEMPOTENCY_RESOLUTION_INVALID")
    with transaction.atomic():
        locked = ApiIdempotencyRecord.objects.select_for_update().get(pk=record.pk)
        if locked.status != ApiIdempotencyRecord.Status.OUTCOME_UNKNOWN:
            raise ValueError("IDEMPOTENCY_OUTCOME_NOT_UNKNOWN")
        locked.delete()


def delete_completed_idempotency_records(*, before):
    return ApiIdempotencyRecord.objects.filter(
        status=ApiIdempotencyRecord.Status.COMPLETED,
        created_at__lt=before,
    ).delete()[0]
