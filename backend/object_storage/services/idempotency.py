from django.db import transaction

from object_storage.models import ApiIdempotencyRecord
from object_storage.permissions import has_object_storage_admin_access
from object_storage.services.audit import record_audit_event


def resolve_idempotency_outcome(
    *, record, actor, resolution, current_status=None, reason="", request_id=""
):
    """Resolve an unknown outcome with an explicit external-reconciliation decision."""
    if not has_object_storage_admin_access(actor):
        raise PermissionError("ADMIN_REQUIRED")
    if resolution not in {"delete", "complete"}:
        raise ValueError("IDEMPOTENCY_RESOLUTION_INVALID")
    if not str(reason or "").strip():
        raise ValueError("IDEMPOTENCY_RESOLUTION_REASON_REQUIRED")
    with transaction.atomic():
        locked = ApiIdempotencyRecord.objects.select_for_update().get(pk=record.pk)
        if current_status != locked.status or locked.status != (
            ApiIdempotencyRecord.Status.OUTCOME_UNKNOWN
        ):
            raise ValueError("IDEMPOTENCY_STATUS_CHANGED")
        record_id = locked.pk
        if resolution == "delete":
            result = "deleted"
            locked.delete()
        else:
            result = ApiIdempotencyRecord.Status.COMPLETED
            locked.status = result
            locked.owner_token = ""
            locked.lease_until = None
            locked.response_status = 409
            locked.response_body = None
            locked.save(
                update_fields=(
                    "status",
                    "owner_token",
                    "lease_until",
                    "response_status",
                    "response_body",
                    "updated_at",
                )
            )
        record_audit_event(
            actor=actor,
            action="storage.api.idempotency.resolve",
            target_type="ApiIdempotencyRecord",
            target_id=record_id,
            result="succeeded",
            reason=reason,
            request_id=request_id,
            safe_metadata={"status": result, "result": resolution},
        )
        return result


def delete_completed_idempotency_records(*, before):
    return ApiIdempotencyRecord.objects.filter(
        status=ApiIdempotencyRecord.Status.COMPLETED,
        created_at__lt=before,
    ).delete()[0]
