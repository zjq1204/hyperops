import hashlib
import json
import uuid
from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from object_storage.models import (
    AccessKey,
    ApplicationBatch,
    ApplicationAttempt,
    ApplicationEvent,
    ApplicationItem,
    Bucket,
    CloudIdentity,
    DeliveryTicket,
    PlatformObjectStorageConfig,
)
from object_storage.providers.aliyun import build_aliyun_provider
from object_storage.providers.base import BucketConfiguration
from object_storage.services.audit import record_audit_event
from object_storage.services.credentials import (
    CredentialDeliveryError,
    CredentialRotationError,
    create_delivery_ticket,
    encrypt_issued_access_key,
    fingerprint_access_key,
    persist_new_access_key,
    provider_access_key,
)
from object_storage.services.naming import (
    BucketNameCandidate,
    BucketNamingError,
    create_bucket_with_unique_name,
    render_bucket_name,
)
from object_storage.services.policy import BucketQuotaExceeded, reserve_bucket_capacity
from object_storage.services.platform import (
    default_bucket_configuration_snapshot,
    ensure_key_operations_allowed,
)
from object_storage.services.provider_errors import (
    ObjectStorageProviderError,
    is_temporary_provider_error,
)

MAX_PROVIDER_RETRIES = 3
RUN_LEASE_SECONDS = 300
RESOURCE_STATES_WITH_UNRESOLVED_CLOUD_RESOURCE = (
    Bucket.State.REQUESTED,
    Bucket.State.CREATING,
    Bucket.State.WAITING_RETRY,
    Bucket.State.ACTIVE,
    Bucket.State.RELEASING,
    Bucket.State.PENDING_DELETION,
    Bucket.State.DELETION_BLOCKED,
)


class ApplicationServiceError(RuntimeError):
    def __init__(self, error_code):
        self.error_code = error_code
        super().__init__(error_code)


class StaleApplicationClaim(ApplicationServiceError):
    def __init__(self):
        super().__init__("STALE_APPLICATION_CLAIM")


def _lock_application_claim(batch_id, owner_token, *, item_ids=()):
    batch = ApplicationBatch.objects.select_for_update().get(pk=batch_id)
    if not (
        owner_token
        and batch.status == ApplicationBatch.Status.RUNNING
        and batch.running_task_id
        and batch.owner_token == owner_token
    ):
        raise StaleApplicationClaim()

    expected_item_ids = set(item_ids)
    if not expected_item_ids:
        return batch, {}
    items = {
        item.pk: item
        for item in ApplicationItem.objects.select_for_update().filter(
            batch_id=batch_id,
            pk__in=expected_item_ids,
        )
    }
    if set(items) != expected_item_ids or any(
        item.status != ApplicationItem.Status.CREATING for item in items.values()
    ):
        raise StaleApplicationClaim()
    return batch, items


def _assert_application_claim(batch_id, owner_token, *, item_ids=()):
    with transaction.atomic():
        _lock_application_claim(batch_id, owner_token, item_ids=item_ids)


def _call_provider_with_claim(
    batch_id,
    owner_token,
    callback,
    *,
    item_ids=(),
):
    _assert_application_claim(batch_id, owner_token, item_ids=item_ids)
    try:
        result = callback()
    except Exception:
        _assert_application_claim(batch_id, owner_token, item_ids=item_ids)
        raise
    _assert_application_claim(batch_id, owner_token, item_ids=item_ids)
    return result


def get_provider_for_pool(resource_pool):
    return build_aliyun_provider(resource_pool)


def is_retryable_provider_error(error):
    return is_temporary_provider_error(error)


def _required_text(item, field_name):
    value = str(item.get(field_name) or "").strip()
    if not value:
        raise ApplicationServiceError(f"{field_name.upper()}_REQUIRED")
    return value


def _optional_text(item, field_name):
    return str(item.get(field_name) or "").strip()


def _normalize_item(*, item, user, config):
    if not isinstance(item, dict):
        raise ApplicationServiceError("APPLICATION_ITEM_INVALID")
    normalized = {
        "business_name": _required_text(item, "business_name"),
        "purpose": _required_text(item, "purpose"),
        "project": _optional_text(item, "project"),
        "environment": str(item.get("environment") or Bucket.Environment.DEVELOPMENT)
        .strip()
        .lower(),
        "notes": _optional_text(item, "notes"),
        "initial_suffix": str(item.get("initial_suffix") or "").strip(),
        "rendered_bucket_name": str(item.get("rendered_bucket_name") or "").strip(),
    }
    if normalized["environment"] not in Bucket.Environment.values:
        raise ApplicationServiceError("ENVIRONMENT_INVALID")
    try:
        expected_name = render_bucket_name(
            template=config.naming_template,
            prefix="hyperops",
            user=user.get_username(),
            business_name=normalized["business_name"],
            project=normalized["project"],
            environment=normalized["environment"],
            purpose=normalized["purpose"],
            suffix=normalized["initial_suffix"],
        )
    except BucketNamingError as error:
        raise ApplicationServiceError(str(error)) from error
    if normalized["rendered_bucket_name"] != expected_name:
        raise ApplicationServiceError("PREVIEW_BUCKET_NAME_MISMATCH")
    return normalized


def _canonical_payload(*, resource_pool, config, items):
    payload = {
        "resource_pool_id": resource_pool.pk,
        "naming_template_version": config.naming_template_version,
        "items": items,
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _ram_user_name(user):
    digest = hashlib.sha256(
        f"{user.pk}:{user.get_username()}".encode("utf-8")
    ).hexdigest()[:20]
    return f"hyperops-{user.pk}-{digest}"[:128]


def _existing_batch(user, idempotency_key, payload_digest):
    batch = ApplicationBatch.objects.filter(
        applicant=user,
        idempotency_key=idempotency_key,
    ).first()
    if batch is None:
        return None
    if batch.payload_digest != payload_digest:
        raise ApplicationServiceError("IDEMPOTENCY_KEY_REUSED")
    return batch


def _local_identity(user, resource_pool):
    identity, created = CloudIdentity.objects.get_or_create(
        user=user,
        defaults={
            "resource_pool": resource_pool,
            "ram_user_name": _ram_user_name(user),
            "state": CloudIdentity.State.PROVISIONING,
        },
    )
    if identity.resource_pool_id != resource_pool.pk:
        raise ApplicationServiceError("CLOUD_IDENTITY_RESOURCE_POOL_MISMATCH")
    return identity, created


def _create_reserved_batch(
    *,
    user,
    resource_pool,
    config,
    idempotency_key,
    payload_digest,
    items,
):
    existing = _existing_batch(user, idempotency_key, payload_digest)
    if existing is not None:
        return existing, False

    identity, identity_created = _local_identity(user, resource_pool)
    batch = ApplicationBatch.objects.create(
        applicant=user,
        idempotency_key=idempotency_key,
        payload_digest=payload_digest,
        item_count=len(items),
        pending_count=len(items),
        cloud_identity=identity,
        identity_created_by_batch=identity_created,
    )
    for fields in items:
        item = ApplicationItem.objects.create(batch=batch, **fields)
        bucket = Bucket.objects.create(
            owner=user,
            resource_pool=resource_pool,
            cloud_identity=identity,
            business_name=fields["business_name"],
            name=fields["rendered_bucket_name"],
            project=fields["project"],
            environment=fields["environment"],
            purpose=fields["purpose"],
            notes=fields["notes"],
            region=resource_pool.region,
            template_version=config.naming_template_version,
            config_snapshot={
                "naming_template": config.naming_template,
                "naming_template_version": config.naming_template_version,
                "bucket_configuration": default_bucket_configuration_snapshot(config),
            },
            desired_config_snapshot=default_bucket_configuration_snapshot(config),
            config_state=Bucket.ConfigurationState.PENDING,
            cloud_marker=f"hyperops:bucket:item:{item.pk}",
            state=Bucket.State.REQUESTED,
        )
        item.bucket = bucket
        item.save(update_fields=("bucket", "updated_at"))
    record_audit_event(
        actor=user,
        action="storage.application_batch.created",
        target_type="ApplicationBatch",
        target_id=batch.pk,
        result="accepted",
        safe_metadata={
            "application_id": batch.pk,
            "total_count": len(items),
        },
    )
    return batch, True


def create_application_batch(
    *,
    user,
    resource_pool,
    idempotency_key,
    items,
    enqueue=True,
):
    key = str(idempotency_key or "").strip()
    if not key:
        raise ApplicationServiceError("IDEMPOTENCY_KEY_REQUIRED")
    if len(key) > 128:
        raise ApplicationServiceError("IDEMPOTENCY_KEY_INVALID")
    if not isinstance(items, (list, tuple)) or not items:
        raise ApplicationServiceError("APPLICATION_ITEMS_REQUIRED")
    config = PlatformObjectStorageConfig.objects.get(singleton_key="default")
    normalized_items = [
        _normalize_item(item=item, user=user, config=config) for item in items
    ]
    names = [item["rendered_bucket_name"] for item in normalized_items]
    if len(names) != len(set(names)):
        raise ApplicationServiceError("DUPLICATE_BUCKET_NAME")
    payload_digest = _canonical_payload(
        resource_pool=resource_pool,
        config=config,
        items=normalized_items,
    )
    existing = _existing_batch(user, key, payload_digest)
    if existing is not None:
        return existing

    def reserve(locked_user, _capacity):
        return _create_reserved_batch(
            user=locked_user,
            resource_pool=resource_pool,
            config=config,
            idempotency_key=key,
            payload_digest=payload_digest,
            items=normalized_items,
        )

    try:
        batch, created = reserve_bucket_capacity(
            user,
            requested_count=len(normalized_items),
            reserve_callback=reserve,
            platform_config=config,
        )
    except (BucketQuotaExceeded, IntegrityError):
        existing = _existing_batch(user, key, payload_digest)
        if existing is not None:
            return existing
        raise
    if enqueue and created:
        from object_storage.tasks import run_storage_application_batch

        run_storage_application_batch.delay(batch.pk)
    return batch


def _error_code(error, default="APPLICATION_EXECUTION_FAILED"):
    return str(getattr(error, "error_code", default) or default)


def _request_id(error):
    return str(getattr(error, "request_id", "") or "")


def _event(item, attempt, stage, result, *, error_code="", request_id=""):
    metadata = {}
    if request_id:
        metadata["provider_request_id"] = request_id
    return ApplicationEvent.objects.create(
        application_item=item,
        attempt=attempt,
        stage=stage,
        result=result,
        error_code=error_code,
        safe_metadata=metadata,
    )


def _attempt_for(item, execution_key):
    with transaction.atomic():
        locked_item = ApplicationItem.objects.select_for_update().get(pk=item.pk)
        if execution_key:
            existing = locked_item.attempts.filter(task_id=execution_key).first()
            if existing is not None:
                return existing, False
        last_attempt = locked_item.attempts.order_by("-attempt_number").first()
        attempt = ApplicationAttempt.objects.create(
            application_item=locked_item,
            attempt_number=(last_attempt.attempt_number + 1 if last_attempt else 1),
            task_id=execution_key,
        )
        return attempt, True


def _claim_item(item_id, execution_key, owner_token):
    batch_id = ApplicationItem.objects.only("batch_id").get(pk=item_id).batch_id
    with transaction.atomic():
        _lock_application_claim(batch_id, owner_token)
        item = ApplicationItem.objects.select_for_update().get(pk=item_id)
        if item.status not in {
            ApplicationItem.Status.PENDING,
            ApplicationItem.Status.WAITING_RETRY,
        }:
            return None
        if execution_key and item.attempts.filter(task_id=execution_key).exists():
            return None
        last_attempt = item.attempts.order_by("-attempt_number").first()
        item.status = ApplicationItem.Status.CREATING
        item.current_stage = "BUCKET_CREATING"
        item.error_code = ""
        item.error_summary = ""
        item.save(
            update_fields=(
                "status",
                "current_stage",
                "error_code",
                "error_summary",
                "updated_at",
            )
        )
        attempt = ApplicationAttempt.objects.create(
            application_item=item,
            attempt_number=(last_attempt.attempt_number + 1 if last_attempt else 1),
            task_id=execution_key,
        )
        _event(item, attempt, "BUCKET_CREATING", "started")
        return item, attempt


def _finish_attempt(
    attempt,
    status,
    *,
    error_code="",
    provider_request_id="",
):
    attempt.status = status
    attempt.error_code = error_code
    attempt.provider_request_id = provider_request_id
    attempt.finished_at = timezone.now()
    attempt.save(
        update_fields=(
            "status",
            "error_code",
            "provider_request_id",
            "finished_at",
        )
    )


def _set_item_failure_locked(item, attempt, error, *, manual=False):
    code = _error_code(error)
    request_id = _request_id(error)
    status = (
        ApplicationItem.Status.MANUAL_REQUIRED
        if manual
        else ApplicationItem.Status.FAILED
    )
    item.status = status
    item.error_code = code
    item.error_summary = code
    item.save(
        update_fields=(
            "status",
            "error_code",
            "error_summary",
            "updated_at",
        )
    )
    _finish_attempt(
        attempt,
        ApplicationAttempt.Status.FAILED,
        error_code=code,
        provider_request_id=request_id,
    )
    _event(
        item,
        attempt,
        item.current_stage or "APPLICATION_EXECUTION",
        "failed",
        error_code=code,
        request_id=request_id,
    )


def _set_item_failure(item, attempt, error, *, owner_token, manual=False):
    with transaction.atomic():
        _batch, items = _lock_application_claim(
            item.batch_id,
            owner_token,
            item_ids=(item.pk,),
        )
        locked_attempt = ApplicationAttempt.objects.select_for_update().get(
            pk=attempt.pk
        )
        _set_item_failure_locked(
            items[item.pk],
            locked_attempt,
            error,
            manual=manual,
        )


def _set_item_waiting_locked(item, attempt, error, stage):
    code = _error_code(error)
    request_id = _request_id(error)
    item.status = ApplicationItem.Status.WAITING_RETRY
    item.current_stage = stage
    item.retry_count += 1
    item.error_code = code
    item.error_summary = code
    item.save(
        update_fields=(
            "status",
            "current_stage",
            "retry_count",
            "error_code",
            "error_summary",
            "updated_at",
        )
    )
    _finish_attempt(
        attempt,
        ApplicationAttempt.Status.FAILED,
        error_code=code,
        provider_request_id=request_id,
    )
    _event(
        item,
        attempt,
        stage,
        "waiting_retry",
        error_code=code,
        request_id=request_id,
    )


def _set_item_waiting(item, attempt, error, stage, *, owner_token):
    with transaction.atomic():
        _batch, items = _lock_application_claim(
            item.batch_id,
            owner_token,
            item_ids=(item.pk,),
        )
        locked_attempt = ApplicationAttempt.objects.select_for_update().get(
            pk=attempt.pk
        )
        _set_item_waiting_locked(
            items[item.pk],
            locked_attempt,
            error,
            stage,
        )


def _refresh_batch_status_locked(batch):
    statuses = list(batch.items.values_list("status", flat=True))
    pending_states = {
        ApplicationItem.Status.PENDING,
        ApplicationItem.Status.CREATING,
        ApplicationItem.Status.WAITING_RETRY,
    }
    failed_states = {
        ApplicationItem.Status.FAILED,
        ApplicationItem.Status.CANCELLED,
        ApplicationItem.Status.MANUAL_REQUIRED,
        ApplicationItem.Status.DELETE_BLOCKED,
    }
    pending = sum(status in pending_states for status in statuses)
    succeeded = statuses.count(ApplicationItem.Status.SUCCEEDED)
    failed = sum(status in failed_states for status in statuses)
    if ApplicationItem.Status.MANUAL_REQUIRED in statuses:
        status = ApplicationBatch.Status.MANUAL_REQUIRED
    elif pending:
        status = (
            ApplicationBatch.Status.RUNNING
            if batch.started_at is not None
            else ApplicationBatch.Status.PENDING
        )
    elif succeeded == len(statuses) and statuses:
        status = ApplicationBatch.Status.SUCCEEDED
    elif succeeded:
        status = ApplicationBatch.Status.PARTIALLY_SUCCEEDED
    elif statuses and all(
        item_status == ApplicationItem.Status.CANCELLED for item_status in statuses
    ):
        status = ApplicationBatch.Status.CANCELLED
    else:
        status = ApplicationBatch.Status.FAILED
    batch.item_count = len(statuses)
    batch.pending_count = pending
    batch.success_count = succeeded
    batch.failed_count = failed
    batch.status = status
    if not pending:
        batch.finished_at = batch.finished_at or timezone.now()
        batch.current_stage = ""
    batch.save(
        update_fields=(
            "item_count",
            "pending_count",
            "success_count",
            "failed_count",
            "status",
            "finished_at",
            "current_stage",
            "updated_at",
        )
    )
    return batch


def refresh_batch_status(batch, *, owner_token=None):
    if owner_token is None:
        return _refresh_batch_status_locked(batch)
    with transaction.atomic():
        locked_batch, _items = _lock_application_claim(batch.pk, owner_token)
        return _refresh_batch_status_locked(locked_batch)


def _mark_batch_items(batch, error, *, waiting, stage, owner_token=None):
    with transaction.atomic():
        if owner_token is None:
            locked_batch = ApplicationBatch.objects.select_for_update().get(pk=batch.pk)
        else:
            locked_batch, _locked_items = _lock_application_claim(
                batch.pk,
                owner_token,
            )
        items = list(
            locked_batch.items.select_for_update()
            .filter(
                status__in=(
                    ApplicationItem.Status.PENDING,
                    ApplicationItem.Status.CREATING,
                    ApplicationItem.Status.WAITING_RETRY,
                )
            )
            .order_by("id")
        )
        for item in items:
            last_attempt = item.attempts.order_by("-attempt_number").first()
            attempt = ApplicationAttempt.objects.create(
                application_item=item,
                attempt_number=(last_attempt.attempt_number + 1 if last_attempt else 1),
            )
            item.current_stage = stage
            if waiting:
                _set_item_waiting_locked(item, attempt, error, stage)
            else:
                _set_item_failure_locked(item, attempt, error, manual=True)
        locked_batch.current_stage = stage
        locked_batch.error_code = _error_code(error)
        locked_batch.error_summary = _error_code(error)
        locked_batch.save(
            update_fields=(
                "current_stage",
                "error_code",
                "error_summary",
                "updated_at",
            )
        )
        return _refresh_batch_status_locked(locked_batch)


def _principal(batch, identity, provider, owner_token):
    principal = _call_provider_with_claim(
        batch.pk,
        owner_token,
        lambda: provider.find_or_create_personal_principal(identity),
    )
    with transaction.atomic():
        locked_batch, _items = _lock_application_claim(batch.pk, owner_token)
        locked_identity = CloudIdentity.objects.select_for_update().get(pk=identity.pk)
        expected_marker = f"hyperops:identity:{locked_identity.pk}"
        if (
            str(getattr(principal, "marker", "")) != expected_marker
            or str(getattr(principal, "user_name", "")) != locked_identity.ram_user_name
        ):
            raise ObjectStorageProviderError("PRINCIPAL_OWNERSHIP_CONFLICT")
        locked_identity.ram_user_id = str(getattr(principal, "user_id", ""))
        locked_identity.ram_user_name = str(principal.user_name)
        locked_identity.state = CloudIdentity.State.ACTIVE
        locked_identity.last_synced_at = timezone.now()
        locked_identity.save(
            update_fields=(
                "ram_user_id",
                "ram_user_name",
                "state",
                "last_synced_at",
                "updated_at",
            )
        )
        if bool(getattr(principal, "created", False)):
            locked_batch.principal_created_by_batch = True
            locked_batch.save(
                update_fields=("principal_created_by_batch", "updated_at")
            )
    identity.ram_user_id = locked_identity.ram_user_id
    identity.ram_user_name = locked_identity.ram_user_name
    identity.state = locked_identity.state
    identity.last_synced_at = locked_identity.last_synced_at
    batch.principal_created_by_batch = locked_batch.principal_created_by_batch


def _provider_items(result):
    return tuple(getattr(result, "items", result))


def _mark_stale_key_cleanup_uncertain(batch_id, issued):
    error_code = "STALE_CLAIM_KEY_CLEANUP_UNCERTAIN"
    access_key_id = str(issued.access_key_id)
    with transaction.atomic():
        batch = (
            ApplicationBatch.objects.select_for_update()
            .select_related("applicant")
            .get(pk=batch_id)
        )
        items = list(
            batch.items.select_for_update().filter(
                status__in=(
                    ApplicationItem.Status.PENDING,
                    ApplicationItem.Status.CREATING,
                    ApplicationItem.Status.WAITING_RETRY,
                )
            )
        )
        for item in items:
            item.status = ApplicationItem.Status.MANUAL_REQUIRED
            item.current_stage = "KEY_RECONCILING"
            item.error_code = error_code
            item.error_summary = error_code
            item.save(
                update_fields=(
                    "status",
                    "current_stage",
                    "error_code",
                    "error_summary",
                    "updated_at",
                )
            )
        batch.status = ApplicationBatch.Status.MANUAL_REQUIRED
        batch.pending_count = 0
        batch.failed_count = batch.items.filter(
            status__in=(
                ApplicationItem.Status.FAILED,
                ApplicationItem.Status.CANCELLED,
                ApplicationItem.Status.MANUAL_REQUIRED,
                ApplicationItem.Status.DELETE_BLOCKED,
            )
        ).count()
        batch.running_task_id = ""
        batch.owner_token = ""
        batch.run_lease_until = None
        batch.current_stage = "KEY_RECONCILING"
        batch.error_code = error_code
        batch.error_summary = error_code
        batch.finished_at = batch.finished_at or timezone.now()
        batch.save(
            update_fields=(
                "status",
                "pending_count",
                "failed_count",
                "running_task_id",
                "owner_token",
                "run_lease_until",
                "current_stage",
                "error_code",
                "error_summary",
                "finished_at",
                "updated_at",
            )
        )
        record_audit_event(
            actor=batch.applicant,
            action="storage.application.stale_claim_key_cleanup_uncertain",
            target_type="ApplicationBatch",
            target_id=batch.pk,
            result="manual_required",
            safe_metadata={
                "application_id": batch.pk,
                "error_code": error_code,
                "fingerprint": fingerprint_access_key(access_key_id),
                "last_four": access_key_id[-4:],
            },
        )
    return batch


def _cleanup_stale_created_key(batch, identity, provider, issued):
    access_key_id = str(issued.access_key_id)
    exact_key = SimpleNamespace(
        cloud_identity=identity,
        access_key_id=access_key_id,
    )
    try:
        provider.delete_access_key(exact_key)
        remaining_fingerprints = {
            key.fingerprint
            for key in _provider_items(provider.list_access_keys(identity))
        }
        if fingerprint_access_key(access_key_id) in remaining_fingerprints:
            raise RuntimeError("stale access key still present after cleanup")
    except Exception:
        _mark_stale_key_cleanup_uncertain(batch.pk, issued)


def _valid_local_key(batch, identity, provider, owner_token):
    cloud_keys = _provider_items(
        _call_provider_with_claim(
            batch.pk,
            owner_token,
            lambda: provider.list_access_keys(identity),
        )
    )
    cloud_fingerprints = {
        key.fingerprint
        for key in cloud_keys
        if str(getattr(key, "status", "")).lower() in {"active", "inactive"}
    }
    local_keys = list(
        identity.access_keys.filter(
            cloud_state__in=AccessKey.PROVIDER_SLOT_CLOUD_STATES,
            local_state__in=AccessKey.PROVIDER_SLOT_LOCAL_STATES,
            deleted_at__isnull=True,
        ).order_by("created_at", "id")
    )
    local_fingerprints = {key.access_key_fingerprint for key in local_keys}
    if cloud_fingerprints != local_fingerprints:
        raise CredentialRotationError(
            "CLOUD_KEY_RECOVERY_REQUIRED",
            manual_required=True,
        )
    return local_keys[0] if local_keys else None


def _persist_batch_access_key(batch, identity, provider, owner_token):
    _assert_application_claim(batch.pk, owner_token)
    ensure_key_operations_allowed()
    _assert_application_claim(batch.pk, owner_token)
    issued = provider.create_access_key(identity)
    try:
        _assert_application_claim(batch.pk, owner_token)
        encrypted_key = encrypt_issued_access_key(issued)
        with transaction.atomic():
            locked_batch, _items = _lock_application_claim(batch.pk, owner_token)
            locked_identity = CloudIdentity.objects.select_for_update().get(
                pk=identity.pk
            )
            access_key = AccessKey.objects.create(
                cloud_identity=locked_identity,
                local_state=AccessKey.LocalState.DELIVERY_READY,
                **encrypted_key,
            )
            locked_batch.issued_access_key = access_key
            locked_batch.key_created_by_batch = True
            locked_batch.save(
                update_fields=(
                    "issued_access_key",
                    "key_created_by_batch",
                    "updated_at",
                )
            )
            record_audit_event(
                actor=locked_batch.applicant,
                action="storage.credential.issued",
                target_type="AccessKey",
                target_id=access_key.pk,
                result="succeeded",
                safe_metadata={
                    "application_id": locked_batch.pk,
                    "last_four": access_key.access_key_last_four,
                },
            )
    except StaleApplicationClaim:
        _cleanup_stale_created_key(batch, identity, provider, issued)
        raise
    except Exception as persistence_error:
        try:
            _assert_application_claim(batch.pk, owner_token)
        except StaleApplicationClaim:
            _cleanup_stale_created_key(batch, identity, provider, issued)
            raise
        exact_key = SimpleNamespace(
            cloud_identity=identity,
            access_key_id=str(issued.access_key_id),
        )
        try:
            _call_provider_with_claim(
                batch.pk,
                owner_token,
                lambda: provider.delete_access_key(exact_key),
            )
        except StaleApplicationClaim:
            raise
        except Exception as cleanup_error:
            raise CredentialRotationError(
                "KEY_COMPENSATION_FAILED",
                manual_required=True,
            ) from cleanup_error
        raise CredentialRotationError(
            "KEY_LOCAL_PERSISTENCE_FAILED",
            manual_required=True,
        ) from persistence_error
    batch.issued_access_key = access_key
    batch.key_created_by_batch = True
    return access_key


def _ensure_access_key(batch, identity, provider, owner_token):
    valid_key = _valid_local_key(batch, identity, provider, owner_token)
    if valid_key is not None:
        with transaction.atomic():
            locked_batch, _items = _lock_application_claim(batch.pk, owner_token)
            if (
                locked_batch.issued_access_key_id != valid_key.pk
                or locked_batch.key_created_by_batch
            ):
                locked_batch.issued_access_key = valid_key
                locked_batch.key_created_by_batch = False
                locked_batch.save(
                    update_fields=(
                        "issued_access_key",
                        "key_created_by_batch",
                        "updated_at",
                    )
                )
        batch.issued_access_key = valid_key
        batch.key_created_by_batch = False
        return valid_key
    return _persist_batch_access_key(batch, identity, provider, owner_token)


def _owned(ownership):
    if isinstance(ownership, bool):
        return ownership, ownership
    return bool(ownership.exists), bool(ownership.owned)


def _bucket_render_values(item, bucket):
    snapshot = bucket.config_snapshot
    return {
        "template": snapshot["naming_template"],
        "prefix": "hyperops",
        "user": bucket.owner.get_username(),
        "business_name": item.business_name,
        "project": item.project,
        "environment": item.environment,
        "purpose": item.purpose,
    }


def _desired_bucket_configuration(bucket):
    try:
        return BucketConfiguration.from_snapshot(bucket.desired_config_snapshot)
    except (AttributeError, TypeError, ValueError) as error:
        raise ObjectStorageProviderError("BUCKET_CONFIGURATION_INVALID") from error


def _applied_bucket_configuration(bucket):
    if not bucket.applied_config_snapshot:
        return None
    try:
        return BucketConfiguration.from_snapshot(bucket.applied_config_snapshot)
    except (AttributeError, TypeError, ValueError) as error:
        raise ObjectStorageProviderError(
            "BUCKET_APPLIED_CONFIGURATION_INVALID"
        ) from error


def _reconcile_existing_bucket_configuration(
    item,
    bucket,
    provider,
    configuration,
    owner_token,
):
    return _call_provider_with_claim(
        item.batch_id,
        owner_token,
        lambda: provider.update_bucket_configuration(
            bucket,
            configuration,
            previous_configuration=_applied_bucket_configuration(bucket),
            allow_public_read=False,
        ),
        item_ids=(item.pk,),
    )


def _ensure_bucket(item, provider, owner_token):
    with transaction.atomic():
        _batch, items = _lock_application_claim(
            item.batch_id,
            owner_token,
            item_ids=(item.pk,),
        )
        locked_item = items[item.pk]
        bucket = (
            Bucket.objects.select_for_update()
            .select_related("owner")
            .get(pk=locked_item.bucket_id)
        )
        active = bucket.state == Bucket.State.ACTIVE
        applied = bucket.applied_config_snapshot == bucket.desired_config_snapshot
        if not active and bucket.state not in {
            Bucket.State.REQUESTED,
            Bucket.State.CREATING,
            Bucket.State.WAITING_RETRY,
        }:
            raise ObjectStorageProviderError("BUCKET_STATE_INCONSISTENT")
        if not active:
            bucket.state = Bucket.State.CREATING
            bucket.save(update_fields=("state", "updated_at"))

    if active:
        exists, owned = _owned(
            _call_provider_with_claim(
                item.batch_id,
                owner_token,
                lambda: provider.find_owned_bucket(bucket),
                item_ids=(item.pk,),
            )
        )
        if not exists or not owned:
            raise ObjectStorageProviderError("BUCKET_OWNERSHIP_CONFLICT")
        if applied:
            return bucket

    configuration = _desired_bucket_configuration(bucket)

    if active:
        _reconcile_existing_bucket_configuration(
            item,
            bucket,
            provider,
            configuration,
            owner_token,
        )
        with transaction.atomic():
            _lock_application_claim(
                item.batch_id,
                owner_token,
                item_ids=(item.pk,),
            )
            bucket = Bucket.objects.select_for_update().get(pk=bucket.pk)
            bucket.applied_config_snapshot = bucket.desired_config_snapshot
            bucket.config_state = Bucket.ConfigurationState.APPLIED
            bucket.config_error_code = ""
            bucket.config_error_summary = ""
            bucket.last_synced_at = timezone.now()
            bucket.save(
                update_fields=(
                    "applied_config_snapshot",
                    "config_state",
                    "config_error_code",
                    "config_error_summary",
                    "last_synced_at",
                    "updated_at",
                )
            )
        return bucket

    initial = BucketNameCandidate(
        name=item.rendered_bucket_name,
        suffix=item.initial_suffix,
    )

    def create(candidate):
        with transaction.atomic():
            _batch, _items = _lock_application_claim(
                item.batch_id,
                owner_token,
                item_ids=(item.pk,),
            )
            locked_bucket = Bucket.objects.select_for_update().get(pk=bucket.pk)
            if locked_bucket.name != candidate.name:
                locked_bucket.name = candidate.name
                locked_bucket.save(update_fields=("name", "updated_at"))
            bucket.name = locked_bucket.name
        ownership = _call_provider_with_claim(
            item.batch_id,
            owner_token,
            lambda: provider.find_owned_bucket(bucket),
            item_ids=(item.pk,),
        )
        exists, owned = _owned(ownership)
        if exists and owned:
            return SimpleNamespace(created=False, request_id="")
        if exists:
            raise ObjectStorageProviderError("BUCKET_NAME_CONFLICT")
        return _call_provider_with_claim(
            item.batch_id,
            owner_token,
            lambda: provider.create_owned_bucket(bucket, configuration),
            item_ids=(item.pk,),
        )

    try:
        mutation = create_bucket_with_unique_name(
            create_callback=create,
            initial_candidate=initial,
            **_bucket_render_values(item, bucket),
        )
        if not getattr(mutation, "created", False):
            _reconcile_existing_bucket_configuration(
                item,
                bucket,
                provider,
                configuration,
                owner_token,
            )
    except StaleApplicationClaim:
        raise
    except Exception as error:
        temporary = is_retryable_provider_error(error)
        exists = owned = False
        try:
            exists, owned = _owned(
                _call_provider_with_claim(
                    item.batch_id,
                    owner_token,
                    lambda: provider.find_owned_bucket(bucket),
                    item_ids=(item.pk,),
                )
            )
        except StaleApplicationClaim:
            raise
        except Exception:
            pass
        with transaction.atomic():
            _lock_application_claim(
                item.batch_id,
                owner_token,
                item_ids=(item.pk,),
            )
            locked_bucket = Bucket.objects.select_for_update().get(pk=bucket.pk)
            recoverable_configuration = exists and owned
            rollback_failed = (
                _error_code(error) == "BUCKET_CONFIGURATION_ROLLBACK_FAILED"
            )
            locked_bucket.state = (
                Bucket.State.WAITING_RETRY
                if temporary or recoverable_configuration
                else Bucket.State.FAILED
            )
            update_fields = ["state", "updated_at"]
            if recoverable_configuration:
                locked_bucket.config_error_code = _error_code(
                    error, "BUCKET_CONFIGURATION_UPDATE_FAILED"
                )
                locked_bucket.config_error_summary = locked_bucket.config_error_code
                locked_bucket.config_state = (
                    Bucket.ConfigurationState.UNKNOWN
                    if rollback_failed
                    else Bucket.ConfigurationState.RETRYABLE_ERROR
                )
                update_fields.extend(
                    ("config_error_code", "config_error_summary", "config_state")
                )
            locked_bucket.save(update_fields=tuple(update_fields))
        if recoverable_configuration and not temporary and not rollback_failed:
            raise ObjectStorageProviderError(
                "BUCKET_CONFIGURATION_UPDATE_FAILED",
                retryable=True,
                request_id=_request_id(error),
            ) from error
        raise
    with transaction.atomic():
        _lock_application_claim(
            item.batch_id,
            owner_token,
            item_ids=(item.pk,),
        )
        bucket = Bucket.objects.select_for_update().get(pk=bucket.pk)
        bucket.state = Bucket.State.ACTIVE
        bucket.applied_config_snapshot = bucket.desired_config_snapshot
        bucket.config_state = Bucket.ConfigurationState.APPLIED
        bucket.config_error_code = ""
        bucket.config_error_summary = ""
        bucket.last_synced_at = timezone.now()
        bucket.save(
            update_fields=(
                "state",
                "applied_config_snapshot",
                "config_state",
                "config_error_code",
                "config_error_summary",
                "last_synced_at",
                "updated_at",
            )
        )
    return bucket


def _process_items(batch, provider, execution_key, owner_token):
    retry_errors = []
    policy_candidates = []
    item_ids = list(
        batch.items.filter(
            status__in=(
                ApplicationItem.Status.PENDING,
                ApplicationItem.Status.WAITING_RETRY,
            )
        )
        .order_by("id")
        .values_list("id", flat=True)
    )
    for item_id in item_ids:
        claimed = _claim_item(item_id, execution_key, owner_token)
        if claimed is None:
            continue
        item, attempt = claimed
        try:
            _ensure_bucket(item, provider, owner_token)
        except StaleApplicationClaim:
            raise
        except Exception as error:
            if is_retryable_provider_error(error):
                _set_item_waiting(
                    item,
                    attempt,
                    error,
                    "BUCKET_CREATING",
                    owner_token=owner_token,
                )
                retry_errors.append(error)
            else:
                _set_item_failure(
                    item,
                    attempt,
                    error,
                    owner_token=owner_token,
                    manual=(
                        _error_code(error) == "BUCKET_CONFIGURATION_ROLLBACK_FAILED"
                    ),
                )
            continue
        policy_candidates.append((item, attempt))
    return policy_candidates, retry_errors


def _active_owned_buckets(batch, identity, provider, owner_token, item_ids):
    _assert_application_claim(batch.pk, owner_token, item_ids=item_ids)
    buckets = list(
        Bucket.objects.filter(
            owner=batch.applicant,
            cloud_identity=identity,
            state=Bucket.State.ACTIVE,
        ).order_by("name")
    )
    for bucket in buckets:
        exists, owned = _owned(
            _call_provider_with_claim(
                batch.pk,
                owner_token,
                lambda bucket=bucket: provider.find_owned_bucket(bucket),
                item_ids=item_ids,
            )
        )
        if not exists or not owned:
            raise ObjectStorageProviderError("BUCKET_OWNERSHIP_CONFLICT")
    return buckets


def _apply_policy(batch, identity, provider, candidates, owner_token):
    if not candidates:
        return None
    item_ids = tuple(item.pk for item, _attempt in candidates)
    try:
        buckets = _active_owned_buckets(
            batch,
            identity,
            provider,
            owner_token,
            item_ids,
        )
        _call_provider_with_claim(
            batch.pk,
            owner_token,
            lambda: provider.reconcile_object_policy(identity, buckets),
            item_ids=item_ids,
        )
    except StaleApplicationClaim:
        raise
    except Exception as error:
        temporary = is_retryable_provider_error(error)
        for item, attempt in candidates:
            if temporary:
                _set_item_waiting(
                    item,
                    attempt,
                    error,
                    "POLICY_APPLYING",
                    owner_token=owner_token,
                )
            else:
                _set_item_failure(
                    item,
                    attempt,
                    error,
                    owner_token=owner_token,
                    manual=True,
                )
        return error
    with transaction.atomic():
        _locked_batch, locked_items = _lock_application_claim(
            batch.pk,
            owner_token,
            item_ids=item_ids,
        )
        attempts = {
            attempt.pk: attempt
            for attempt in ApplicationAttempt.objects.select_for_update().filter(
                pk__in=(attempt.pk for _item, attempt in candidates)
            )
        }
        for item, attempt in candidates:
            locked_item = locked_items[item.pk]
            locked_attempt = attempts[attempt.pk]
            locked_item.status = ApplicationItem.Status.SUCCEEDED
            locked_item.current_stage = ""
            locked_item.error_code = ""
            locked_item.error_summary = ""
            locked_item.save(
                update_fields=(
                    "status",
                    "current_stage",
                    "error_code",
                    "error_summary",
                    "updated_at",
                )
            )
            _finish_attempt(locked_attempt, ApplicationAttempt.Status.SUCCEEDED)
            _event(
                locked_item,
                locked_attempt,
                "POLICY_APPLYING",
                "succeeded",
            )
    return None


def _ensure_delivery(batch, owner_token):
    with transaction.atomic():
        locked_batch, _items = _lock_application_claim(batch.pk, owner_token)
        locked_batch = ApplicationBatch.objects.select_related(
            "applicant",
            "issued_access_key",
            "issued_access_key__cloud_identity",
        ).get(pk=locked_batch.pk)
        if (
            locked_batch.issued_access_key_id is None
            or not locked_batch.items.filter(
                status=ApplicationItem.Status.SUCCEEDED
            ).exists()
        ):
            return
        if DeliveryTicket.objects.filter(application_batch=locked_batch).exists():
            return
        create_delivery_ticket(
            application_batch=locked_batch,
            access_key=locked_batch.issued_access_key,
            user=locked_batch.applicant,
        )


def _batch_is_terminal(batch):
    if batch.status in {
        ApplicationBatch.Status.SUCCEEDED,
        ApplicationBatch.Status.CANCELLED,
        ApplicationBatch.Status.FAILED,
        ApplicationBatch.Status.MANUAL_REQUIRED,
    }:
        return True
    if batch.status == ApplicationBatch.Status.PARTIALLY_SUCCEEDED:
        return not batch.items.filter(
            status__in=(
                ApplicationItem.Status.PENDING,
                ApplicationItem.Status.CREATING,
                ApplicationItem.Status.WAITING_RETRY,
            )
        ).exists()
    return False


def _claim_batch(batch_id, execution_key):
    with transaction.atomic():
        batch = ApplicationBatch.objects.select_for_update().get(pk=batch_id)
        get_user_model().objects.select_for_update().get(pk=batch.applicant_id)
        now = timezone.now()
        if _batch_is_terminal(batch):
            return batch, False, ""
        if execution_key:
            processable_ids = batch.items.filter(
                status__in=(
                    ApplicationItem.Status.PENDING,
                    ApplicationItem.Status.WAITING_RETRY,
                )
            ).values_list("pk", flat=True)
            if (
                processable_ids
                and not ApplicationItem.objects.filter(
                    pk__in=processable_ids,
                )
                .exclude(attempts__task_id=execution_key)
                .exists()
            ):
                return batch, False, ""
        # Fail closed after lease expiry. Automatic takeover could overlap a
        # slow worker that is still inside a provider call.
        if batch.status == ApplicationBatch.Status.RUNNING and batch.running_task_id:
            return batch, False, ""
        if batch.cloud_identity_id:
            CloudIdentity.objects.select_for_update().get(pk=batch.cloud_identity_id)
            if (
                ApplicationBatch.objects.filter(
                    cloud_identity_id=batch.cloud_identity_id,
                    status=ApplicationBatch.Status.RUNNING,
                    run_lease_until__gt=now,
                )
                .exclude(pk=batch.pk)
                .exists()
            ):
                return batch, False, ""
        for item in batch.items.select_for_update().filter(
            status=ApplicationItem.Status.CREATING
        ):
            item.status = ApplicationItem.Status.WAITING_RETRY
            item.save(update_fields=("status", "updated_at"))
        owner = execution_key or f"direct:{batch.pk}:{now.timestamp()}"
        owner_token = uuid.uuid4().hex
        claim_version = batch.claim_version + 1
        batch.status = ApplicationBatch.Status.RUNNING
        batch.started_at = batch.started_at or now
        batch.running_task_id = owner
        batch.owner_token = owner_token
        batch.claim_version = claim_version
        batch.run_lease_until = now + timedelta(seconds=RUN_LEASE_SECONDS)
        batch.current_stage = batch.current_stage or "PRINCIPAL_BINDING"
        batch.save(
            update_fields=(
                "status",
                "started_at",
                "running_task_id",
                "owner_token",
                "claim_version",
                "run_lease_until",
                "current_stage",
                "updated_at",
            )
        )
        return batch, True, owner_token


def _release_batch_lease(batch_id, owner_token):
    return ApplicationBatch.objects.filter(
        pk=batch_id,
        owner_token=owner_token,
    ).update(running_task_id="", owner_token="", run_lease_until=None)


def recover_expired_application_claim(batch, *, now=None, provider=None):
    batch_id = getattr(batch, "pk", batch)
    now = now or timezone.now()
    with transaction.atomic():
        locked_batch = ApplicationBatch.objects.select_for_update().get(pk=batch_id)
        get_user_model().objects.select_for_update().get(pk=locked_batch.applicant_id)
        if locked_batch.cloud_identity_id:
            identity = (
                CloudIdentity.objects.select_for_update()
                .select_related("resource_pool")
                .get(pk=locked_batch.cloud_identity_id)
            )
        else:
            identity = (
                CloudIdentity.objects.select_for_update()
                .select_related("resource_pool")
                .filter(user_id=locked_batch.applicant_id)
                .first()
            )
        if not (
            locked_batch.status == ApplicationBatch.Status.RUNNING
            and locked_batch.running_task_id
            and locked_batch.run_lease_until
            and locked_batch.run_lease_until < now
        ):
            return locked_batch, None
        recovery_items = list(
            locked_batch.items.select_for_update()
            .filter(
                status__in=(
                    ApplicationItem.Status.PENDING,
                    ApplicationItem.Status.CREATING,
                )
            )
            .values("pk", "bucket_id")
        )
        recovery_generation = locked_batch.claim_version + 1
        recovery_token = f"recovery:{uuid.uuid4().hex}"
        locked_batch.claim_version = recovery_generation
        locked_batch.running_task_id = "claim-recovery"
        locked_batch.owner_token = recovery_token
        locked_batch.run_lease_until = now + timedelta(seconds=RUN_LEASE_SECONDS)
        locked_batch.save(
            update_fields=(
                "claim_version",
                "running_task_id",
                "owner_token",
                "run_lease_until",
                "updated_at",
            )
        )
        resource_pool = identity.resource_pool if identity is not None else None

    selected_provider = provider
    if recovery_items and selected_provider is None and resource_pool is not None:
        selected_provider = get_provider_for_pool(resource_pool)
    recovery_results = {}
    for snapshot in recovery_items:
        cloud_uncertain = False
        if snapshot["bucket_id"] and selected_provider is not None:
            bucket = Bucket.objects.get(pk=snapshot["bucket_id"])
            try:
                cloud_exists, owned = _owned(
                    selected_provider.find_owned_bucket(bucket)
                )
                cloud_uncertain = cloud_exists and not owned
            except Exception:
                cloud_uncertain = True
        recovery_results[snapshot["pk"]] = cloud_uncertain

    with transaction.atomic():
        locked_batch = ApplicationBatch.objects.select_for_update().get(pk=batch_id)
        if not (
            locked_batch.claim_version == recovery_generation
            and locked_batch.owner_token == recovery_token
            and locked_batch.running_task_id == "claim-recovery"
        ):
            return locked_batch, None
        locked_items = {
            item.pk: item
            for item in locked_batch.items.select_for_update().filter(
                pk__in=recovery_results
            )
        }
        for item_id, cloud_uncertain in recovery_results.items():
            item = locked_items[item_id]
            attempt = item.attempts.order_by("-attempt_number").first()
            if item.bucket_id and not cloud_uncertain:
                locked_bucket = Bucket.objects.select_for_update().get(
                    pk=item.bucket_id
                )
                locked_bucket.state = Bucket.State.WAITING_RETRY
                locked_bucket.save(update_fields=("state", "updated_at"))
            item.current_stage = "CLAIM_RECOVERY"
            item.error_code = (
                "CLAIM_EXPIRED_CLOUD_STATE_UNKNOWN"
                if cloud_uncertain
                else "CLAIM_EXPIRED"
            )
            item.error_summary = item.error_code
            item.status = (
                ApplicationItem.Status.MANUAL_REQUIRED
                if cloud_uncertain
                else ApplicationItem.Status.WAITING_RETRY
            )
            item.retry_count += 1
            item.save(
                update_fields=(
                    "status",
                    "current_stage",
                    "retry_count",
                    "error_code",
                    "error_summary",
                    "updated_at",
                )
            )
            if attempt is not None:
                _finish_attempt(
                    attempt,
                    ApplicationAttempt.Status.FAILED,
                    error_code=item.error_code,
                )
            _event(
                item,
                attempt,
                "CLAIM_RECOVERY",
                "manual_required" if cloud_uncertain else "recovered",
                error_code=item.error_code,
            )
        locked_batch.running_task_id = ""
        locked_batch.owner_token = ""
        locked_batch.run_lease_until = None
        locked_batch.current_stage = "CLAIM_RECOVERY"
        locked_batch.error_code = "CLAIM_EXPIRED"
        locked_batch.error_summary = "Expired application claim recovered"
        locked_batch.save(
            update_fields=(
                "running_task_id",
                "owner_token",
                "run_lease_until",
                "current_stage",
                "error_code",
                "error_summary",
                "updated_at",
            )
        )
        result = refresh_batch_status(locked_batch)
        if result.status not in {
            ApplicationBatch.Status.RUNNING,
            ApplicationBatch.Status.MANUAL_REQUIRED,
        }:
            result.status = ApplicationBatch.Status.MANUAL_REQUIRED
            result.current_stage = "CLAIM_RECOVERY"
            result.error_code = "CLAIM_EXPIRED_TERMINAL_STATE_UNKNOWN"
            result.error_summary = result.error_code
            result.save(
                update_fields=(
                    "status",
                    "current_stage",
                    "error_code",
                    "error_summary",
                    "updated_at",
                )
            )
        record_audit_event(
            actor=locked_batch.applicant,
            action="storage.application.claim_recovered",
            target_type="ApplicationBatch",
            target_id=locked_batch.pk,
            result=(
                "manual_required"
                if result.status == ApplicationBatch.Status.MANUAL_REQUIRED
                else "recovered"
            ),
            safe_metadata={
                "application_id": locked_batch.pk,
                "status": result.status,
            },
        )
        return result, recovery_generation


def mark_claim_recovery_enqueue_failed(batch_id, recovery_generation):
    error_code = "CLAIM_RECOVERY_ENQUEUE_FAILED"
    with transaction.atomic():
        batch = (
            ApplicationBatch.objects.select_for_update()
            .select_related("applicant")
            .get(pk=batch_id)
        )
        if not (
            batch.status == ApplicationBatch.Status.RUNNING
            and not batch.running_task_id
            and not batch.owner_token
            and batch.claim_version == recovery_generation
        ):
            return batch
        items = list(
            batch.items.select_for_update().filter(
                status__in=(
                    ApplicationItem.Status.PENDING,
                    ApplicationItem.Status.CREATING,
                    ApplicationItem.Status.WAITING_RETRY,
                )
            )
        )
        for item in items:
            item.status = ApplicationItem.Status.MANUAL_REQUIRED
            item.current_stage = "CLAIM_RECOVERY"
            item.error_code = error_code
            item.error_summary = error_code
            item.save(
                update_fields=(
                    "status",
                    "current_stage",
                    "error_code",
                    "error_summary",
                    "updated_at",
                )
            )
        batch.status = ApplicationBatch.Status.MANUAL_REQUIRED
        batch.pending_count = 0
        batch.failed_count = batch.items.filter(
            status__in=(
                ApplicationItem.Status.FAILED,
                ApplicationItem.Status.CANCELLED,
                ApplicationItem.Status.MANUAL_REQUIRED,
                ApplicationItem.Status.DELETE_BLOCKED,
            )
        ).count()
        batch.running_task_id = ""
        batch.owner_token = ""
        batch.run_lease_until = None
        batch.current_stage = "CLAIM_RECOVERY"
        batch.error_code = error_code
        batch.error_summary = error_code
        batch.finished_at = batch.finished_at or timezone.now()
        batch.save(
            update_fields=(
                "status",
                "pending_count",
                "failed_count",
                "running_task_id",
                "owner_token",
                "run_lease_until",
                "current_stage",
                "error_code",
                "error_summary",
                "finished_at",
                "updated_at",
            )
        )
        record_audit_event(
            actor=batch.applicant,
            action="storage.application.claim_recovery_enqueue_failed",
            target_type="ApplicationBatch",
            target_id=batch.pk,
            result="manual_required",
            safe_metadata={
                "application_id": batch.pk,
                "error_code": error_code,
            },
        )
        return batch


def execute_application_batch(batch_id, *, execution_key=""):
    batch, claimed, owner_token = _claim_batch(batch_id, execution_key)
    if not claimed:
        return batch
    try:
        try:
            batch = ApplicationBatch.objects.select_related(
                "applicant",
                "issued_access_key",
                "cloud_identity",
                "cloud_identity__resource_pool",
            ).get(pk=batch_id)
            identity = batch.cloud_identity or CloudIdentity.objects.select_related(
                "resource_pool"
            ).get(user=batch.applicant)
            provider = get_provider_for_pool(identity.resource_pool)
            _principal(batch, identity, provider, owner_token)
            with transaction.atomic():
                locked_batch, _items = _lock_application_claim(
                    batch.pk,
                    owner_token,
                )
                locked_batch.current_stage = "KEY_RECONCILING"
                locked_batch.save(update_fields=("current_stage", "updated_at"))
            batch.current_stage = "KEY_RECONCILING"
            _ensure_access_key(batch, identity, provider, owner_token)
        except StaleApplicationClaim:
            raise
        except Exception as error:
            temporary = is_retryable_provider_error(error)
            batch = _mark_batch_items(
                batch,
                error,
                waiting=temporary,
                stage=batch.current_stage,
                owner_token=owner_token,
            )
            if temporary:
                error.application_claim_version = batch.claim_version
                raise error
            return batch

        candidates, retry_errors = _process_items(
            batch,
            provider,
            execution_key,
            owner_token,
        )
        policy_error = _apply_policy(
            batch,
            identity,
            provider,
            candidates,
            owner_token,
        )
        if policy_error is not None and is_retryable_provider_error(policy_error):
            retry_errors.append(policy_error)
        try:
            _ensure_delivery(batch, owner_token)
        except StaleApplicationClaim:
            raise
        except CredentialDeliveryError as error:
            with transaction.atomic():
                locked_batch, _items = _lock_application_claim(
                    batch.pk,
                    owner_token,
                )
                _refresh_batch_status_locked(locked_batch)
                locked_batch.status = ApplicationBatch.Status.MANUAL_REQUIRED
                locked_batch.current_stage = "DELIVERY_CREATING"
                locked_batch.error_code = error.error_code
                locked_batch.error_summary = error.error_code
                locked_batch.save(
                    update_fields=(
                        "status",
                        "current_stage",
                        "error_code",
                        "error_summary",
                        "updated_at",
                    )
                )
                batch = locked_batch
            return batch
        batch = refresh_batch_status(batch, owner_token=owner_token)
        batch.refresh_from_db()
        if retry_errors:
            retry_errors[0].application_claim_version = batch.claim_version
            raise retry_errors[0]
        return batch
    finally:
        if _release_batch_lease(batch_id, owner_token):
            batch.running_task_id = ""
            batch.owner_token = ""
            batch.run_lease_until = None


def execute_application(application_id, *, execution_key=""):
    return execute_application_batch(application_id, execution_key=execution_key)


def retry_application_bucket_configuration(bucket_id, *, enqueue=True, actor=None):
    """Reset one recoverable Bucket configuration item for the fixed retry path."""

    with transaction.atomic():
        bucket = Bucket.objects.select_for_update().get(pk=bucket_id)
        if bucket.config_state == Bucket.ConfigurationState.UNKNOWN:
            raise ApplicationServiceError("BUCKET_CONFIGURATION_STATE_UNKNOWN")
        if not (
            bucket.state == Bucket.State.WAITING_RETRY
            and bucket.config_state == Bucket.ConfigurationState.RETRYABLE_ERROR
        ):
            raise ApplicationServiceError("BUCKET_CONFIGURATION_RETRY_NOT_ALLOWED")
        item = (
            ApplicationItem.objects.select_for_update()
            .filter(bucket=bucket)
            .order_by("pk")
            .first()
        )
        if item is None or item.status not in {
            ApplicationItem.Status.WAITING_RETRY,
            ApplicationItem.Status.FAILED,
            ApplicationItem.Status.MANUAL_REQUIRED,
        }:
            raise ApplicationServiceError("BUCKET_CONFIGURATION_RETRY_NOT_ALLOWED")
        batch = ApplicationBatch.objects.select_for_update().get(pk=item.batch_id)
        if batch.running_task_id or batch.owner_token:
            raise ApplicationServiceError("APPLICATION_IN_PROGRESS")

        item.status = ApplicationItem.Status.WAITING_RETRY
        item.current_stage = "BUCKET_CREATING"
        item.error_code = ""
        item.error_summary = ""
        item.save(
            update_fields=(
                "status",
                "current_stage",
                "error_code",
                "error_summary",
                "updated_at",
            )
        )
        batch.status = ApplicationBatch.Status.PENDING
        batch.current_stage = "BUCKET_CREATING"
        batch.error_code = ""
        batch.error_summary = ""
        batch.finished_at = None
        batch.save(
            update_fields=(
                "status",
                "current_stage",
                "error_code",
                "error_summary",
                "finished_at",
                "updated_at",
            )
        )
        record_audit_event(
            actor=actor or batch.applicant,
            action="storage.bucket.configuration_retry_requested",
            target_type="Bucket",
            target_id=bucket.pk,
            result="accepted",
            safe_metadata={
                "application_id": batch.pk,
                "item_id": item.pk,
                "bucket_id": bucket.pk,
            },
        )
    if enqueue:
        from object_storage.tasks import run_storage_application_batch

        run_storage_application_batch.delay(batch.pk)
    return batch


def mark_batch_manual_required(batch_id, error, *, expected_claim_version):
    with transaction.atomic():
        batch = ApplicationBatch.objects.select_for_update().get(pk=batch_id)
        if not (
            expected_claim_version is not None
            and batch.claim_version == expected_claim_version
            and not batch.running_task_id
            and not batch.owner_token
        ):
            return batch
        _mark_batch_items(
            batch,
            error,
            waiting=False,
            stage=batch.current_stage or "APPLICATION_EXECUTION",
        )
        return batch


def _cancel_manual(batch, item, error):
    item.status = ApplicationItem.Status.MANUAL_REQUIRED
    item.current_stage = "CANCEL_CLEANUP"
    item.error_code = _error_code(error, "CANCEL_CLOUD_STATE_UNKNOWN")
    item.error_summary = item.error_code
    item.save(
        update_fields=(
            "status",
            "current_stage",
            "error_code",
            "error_summary",
            "updated_at",
        )
    )
    record_audit_event(
        actor=batch.applicant,
        action="storage.application.cancel_manual_required",
        target_type="ApplicationItem",
        target_id=item.pk,
        result="manual_required",
        safe_metadata={
            "application_id": batch.pk,
            "item_id": item.pk,
            "error_code": item.error_code,
        },
    )


def _cancel_cloud_states(batch, provider):
    manual = {}
    clear = []
    items = list(batch.items.select_related("bucket").order_by("id"))
    for item in items:
        if item.status in {
            ApplicationItem.Status.SUCCEEDED,
            ApplicationItem.Status.CANCELLED,
        }:
            continue
        if item.bucket_id is None:
            clear.append(item.pk)
            continue
        try:
            exists, owned = _owned(provider.find_owned_bucket(item.bucket))
        except Exception as error:
            manual[item.pk] = error
            continue
        if exists:
            manual[item.pk] = ObjectStorageProviderError(
                "CANCEL_CLOUD_BUCKET_PRESENT" if owned else "BUCKET_OWNERSHIP_CONFLICT"
            )
        else:
            clear.append(item.pk)
    return clear, manual


def _can_delete_principal(batch, identity):
    if not batch.identity_created_by_batch or not batch.principal_created_by_batch:
        return False
    current_bucket_ids = set(
        batch.items.exclude(bucket_id=None).values_list("bucket_id", flat=True)
    )
    if (
        Bucket.objects.filter(
            owner=batch.applicant,
            resource_pool=identity.resource_pool,
            state__in=RESOURCE_STATES_WITH_UNRESOLVED_CLOUD_RESOURCE,
        )
        .exclude(pk__in=current_bucket_ids)
        .exists()
    ):
        return False
    if (
        Bucket.objects.filter(
            cloud_identity=identity,
            state__in=RESOURCE_STATES_WITH_UNRESOLVED_CLOUD_RESOURCE,
        )
        .exclude(pk__in=current_bucket_ids)
        .exists()
    ):
        return False
    if (
        AccessKey.objects.filter(
            cloud_identity=identity,
            cloud_state__in=(
                AccessKey.CloudState.ACTIVE,
                AccessKey.CloudState.INACTIVE,
                AccessKey.CloudState.UNKNOWN,
            ),
            deleted_at__isnull=True,
        )
        .exclude(pk=batch.issued_access_key_id)
        .exists()
    ):
        return False
    return True


def _mark_cancel_cleanup_manual_locked(batch, error):
    item = (
        batch.items.select_for_update()
        .exclude(status=ApplicationItem.Status.SUCCEEDED)
        .order_by("id")
        .first()
    )
    if item is not None:
        _cancel_manual(batch, item, error)
    batch.error_code = _error_code(error, "CANCEL_CLEANUP_FAILED")
    batch.error_summary = batch.error_code
    batch.save(update_fields=("error_code", "error_summary", "updated_at"))
    return refresh_batch_status(batch)


def cancel_application_batch(batch_id):
    with transaction.atomic():
        batch = (
            ApplicationBatch.objects.select_for_update()
            .select_related("applicant")
            .get(pk=batch_id)
        )
        get_user_model().objects.select_for_update().get(pk=batch.applicant_id)
        if batch.status == ApplicationBatch.Status.RUNNING and batch.running_task_id:
            raise ApplicationServiceError("CANCEL_IN_PROGRESS")
        identity_id = batch.cloud_identity_id
        if identity_id is None:
            identity_id = (
                CloudIdentity.objects.filter(user=batch.applicant)
                .values_list("pk", flat=True)
                .first()
            )
        if identity_id is None:
            for item in batch.items.select_for_update().exclude(
                status=ApplicationItem.Status.SUCCEEDED
            ):
                item.status = ApplicationItem.Status.CANCELLED
                item.save(update_fields=("status", "updated_at"))
            return refresh_batch_status(batch)
        identity = (
            CloudIdentity.objects.select_for_update()
            .select_related("resource_pool")
            .get(pk=identity_id)
        )
        cancel_generation = batch.claim_version + 1
        cancel_token = f"cancel:{uuid.uuid4().hex}"
        batch.claim_version = cancel_generation
        batch.running_task_id = "application-cancel"
        batch.owner_token = cancel_token
        batch.run_lease_until = timezone.now() + timedelta(seconds=RUN_LEASE_SECONDS)
        batch.save(
            update_fields=(
                "claim_version",
                "running_task_id",
                "owner_token",
                "run_lease_until",
                "updated_at",
            )
        )
        resource_pool = identity.resource_pool

    provider = get_provider_for_pool(resource_pool)
    clear_ids, manual_errors = _cancel_cloud_states(batch, provider)

    with transaction.atomic():
        batch = ApplicationBatch.objects.select_for_update().get(pk=batch_id)
        if not (
            batch.claim_version == cancel_generation
            and batch.owner_token == cancel_token
            and batch.running_task_id == "application-cancel"
        ):
            return batch
        identity = CloudIdentity.objects.select_for_update().get(pk=identity_id)
        items = list(
            batch.items.select_for_update().select_related("bucket").order_by("id")
        )
        locked_buckets = {
            selected.pk: selected
            for selected in Bucket.objects.select_for_update().filter(
                pk__in=[item.bucket_id for item in items if item.bucket_id]
            )
        }
        for item in items:
            if item.status == ApplicationItem.Status.SUCCEEDED:
                continue
            manual_error = manual_errors.get(item.pk)
            if manual_error is not None:
                _cancel_manual(batch, item, manual_error)
                continue
            if item.pk in clear_ids:
                item.status = ApplicationItem.Status.CANCELLED
                item.current_stage = ""
                item.save(update_fields=("status", "current_stage", "updated_at"))
                locked_bucket = locked_buckets.get(item.bucket_id)
                if locked_bucket and locked_bucket.state != Bucket.State.CANCELLED:
                    locked_bucket.state = Bucket.State.CANCELLED
                    locked_bucket.save(update_fields=("state", "updated_at"))
        if manual_errors:
            batch.error_code = "CANCEL_CLOUD_STATE_UNKNOWN"
            batch.error_summary = "Cancellation requires manual cleanup"
        batch = refresh_batch_status(batch)
        cleanup_key = None
        delete_principal = False
        if (
            not batch.success_count
            and batch.status != ApplicationBatch.Status.MANUAL_REQUIRED
        ):
            if batch.key_created_by_batch and batch.issued_access_key_id:
                cleanup_key = AccessKey.objects.get(pk=batch.issued_access_key_id)
            delete_principal = _can_delete_principal(batch, identity)
        if cleanup_key is not None or delete_principal:
            batch.status = ApplicationBatch.Status.RUNNING
            batch.current_stage = "CANCEL_CLEANUP"
            batch.save(update_fields=("status", "current_stage", "updated_at"))

    cleanup_error = None
    if cleanup_key is not None:
        try:
            cloud_fingerprints = {
                item.fingerprint
                for item in _provider_items(provider.list_access_keys(identity))
            }
            if cleanup_key.access_key_fingerprint in cloud_fingerprints:
                provider.delete_access_key(provider_access_key(cleanup_key))
        except Exception as error:
            cleanup_error = error
    principal_deleted = False
    if cleanup_error is None and delete_principal:
        try:
            provider.delete_personal_principal(identity)
            principal_deleted = True
        except Exception as error:
            cleanup_error = error

    with transaction.atomic():
        batch = ApplicationBatch.objects.select_for_update().get(pk=batch_id)
        if not (
            batch.claim_version == cancel_generation
            and batch.owner_token == cancel_token
            and batch.running_task_id == "application-cancel"
        ):
            return batch
        identity = CloudIdentity.objects.select_for_update().get(pk=identity_id)
        if cleanup_error is not None:
            result = _mark_cancel_cleanup_manual_locked(batch, cleanup_error)
        else:
            if cleanup_key is not None:
                batch.issued_access_key = None
                batch.key_created_by_batch = False
                batch.save(
                    update_fields=(
                        "issued_access_key",
                        "key_created_by_batch",
                        "updated_at",
                    )
                )
                AccessKey.objects.filter(pk=cleanup_key.pk).delete()
            if principal_deleted:
                identity.state = CloudIdentity.State.ERROR
                identity.save(update_fields=("state", "updated_at"))
            result = refresh_batch_status(batch)
        batch.running_task_id = ""
        batch.owner_token = ""
        batch.run_lease_until = None
        batch.save(
            update_fields=(
                "running_task_id",
                "owner_token",
                "run_lease_until",
                "updated_at",
            )
        )
        result.refresh_from_db()
        return result
