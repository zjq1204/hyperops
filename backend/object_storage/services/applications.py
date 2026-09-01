import hashlib
import json
from types import SimpleNamespace

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
from object_storage.services.audit import record_audit_event
from object_storage.services.credentials import (
    CredentialDeliveryError,
    CredentialRotationError,
    create_delivery_ticket,
    encrypt_issued_access_key,
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
from object_storage.services.provider_errors import (
    ObjectStorageProviderError,
    is_temporary_provider_error,
)

MAX_PROVIDER_RETRIES = 3


class ApplicationServiceError(RuntimeError):
    def __init__(self, error_code):
        self.error_code = error_code
        super().__init__(error_code)


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
    identity, _created = CloudIdentity.objects.get_or_create(
        user=user,
        defaults={
            "resource_pool": resource_pool,
            "ram_user_name": _ram_user_name(user),
            "state": CloudIdentity.State.PROVISIONING,
        },
    )
    if identity.resource_pool_id != resource_pool.pk:
        raise ApplicationServiceError("CLOUD_IDENTITY_RESOURCE_POOL_MISMATCH")
    return identity


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

    identity = _local_identity(user, resource_pool)
    batch = ApplicationBatch.objects.create(
        applicant=user,
        idempotency_key=idempotency_key,
        payload_digest=payload_digest,
        item_count=len(items),
        pending_count=len(items),
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
            },
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
    if execution_key:
        existing = item.attempts.filter(task_id=execution_key).first()
        if existing is not None:
            return existing, False
    attempt = ApplicationAttempt.objects.create(
        application_item=item,
        attempt_number=item.attempts.count() + 1,
        task_id=execution_key,
    )
    return attempt, True


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


def _set_item_failure(item, attempt, error, *, manual=False):
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


def _set_item_waiting(item, attempt, error, stage):
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


def refresh_batch_status(batch):
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


def _mark_batch_items(batch, error, *, waiting, stage):
    items = list(
        batch.items.filter(
            status__in=(
                ApplicationItem.Status.PENDING,
                ApplicationItem.Status.CREATING,
                ApplicationItem.Status.WAITING_RETRY,
            )
        ).order_by("id")
    )
    for item in items:
        attempt, created = _attempt_for(item, "")
        if not created:
            continue
        item.current_stage = stage
        if waiting:
            _set_item_waiting(item, attempt, error, stage)
        else:
            _set_item_failure(item, attempt, error, manual=True)
    batch.current_stage = stage
    batch.error_code = _error_code(error)
    batch.error_summary = _error_code(error)
    batch.save(
        update_fields=(
            "current_stage",
            "error_code",
            "error_summary",
            "updated_at",
        )
    )
    return refresh_batch_status(batch)


def _principal(identity, provider):
    principal = provider.find_or_create_personal_principal(identity)
    expected_marker = f"hyperops:identity:{identity.pk}"
    if (
        str(getattr(principal, "marker", "")) != expected_marker
        or str(getattr(principal, "user_name", "")) != identity.ram_user_name
    ):
        raise ObjectStorageProviderError("PRINCIPAL_OWNERSHIP_CONFLICT")
    identity.ram_user_id = str(getattr(principal, "user_id", ""))
    identity.ram_user_name = str(principal.user_name)
    identity.state = CloudIdentity.State.ACTIVE
    identity.last_synced_at = timezone.now()
    identity.save(
        update_fields=(
            "ram_user_id",
            "ram_user_name",
            "state",
            "last_synced_at",
            "updated_at",
        )
    )


def _provider_items(result):
    return tuple(getattr(result, "items", result))


def _valid_local_key(identity, provider):
    cloud_keys = _provider_items(provider.list_access_keys(identity))
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


def _persist_batch_access_key(identity, provider):
    issued = provider.create_access_key(identity)
    try:
        return AccessKey.objects.create(
            cloud_identity=identity,
            local_state=AccessKey.LocalState.DELIVERY_READY,
            **encrypt_issued_access_key(issued),
        )
    except Exception as persistence_error:
        exact_key = SimpleNamespace(
            cloud_identity=identity,
            access_key_id=str(issued.access_key_id),
        )
        try:
            provider.delete_access_key(exact_key)
        except Exception as cleanup_error:
            raise CredentialRotationError(
                "KEY_COMPENSATION_FAILED",
                manual_required=True,
            ) from cleanup_error
        raise CredentialRotationError(
            "KEY_LOCAL_PERSISTENCE_FAILED",
            manual_required=True,
        ) from persistence_error


def _ensure_access_key(batch, identity, provider):
    valid_key = _valid_local_key(identity, provider)
    if valid_key is not None:
        return valid_key
    access_key = _persist_batch_access_key(identity, provider)
    batch.issued_access_key = access_key
    batch.save(update_fields=("issued_access_key", "updated_at"))
    record_audit_event(
        actor=batch.applicant,
        action="storage.credential.issued",
        target_type="AccessKey",
        target_id=access_key.pk,
        result="succeeded",
        safe_metadata={
            "application_id": batch.pk,
            "last_four": access_key.access_key_last_four,
        },
    )
    return access_key


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


def _ensure_bucket(item, provider):
    bucket = Bucket.objects.select_related("owner").get(pk=item.bucket_id)
    if bucket.state == Bucket.State.ACTIVE:
        exists, owned = _owned(provider.find_owned_bucket(bucket))
        if not exists or not owned:
            raise ObjectStorageProviderError("BUCKET_OWNERSHIP_CONFLICT")
        return bucket
    if bucket.state not in {
        Bucket.State.REQUESTED,
        Bucket.State.CREATING,
        Bucket.State.WAITING_RETRY,
    }:
        raise ObjectStorageProviderError("BUCKET_STATE_INCONSISTENT")

    initial = BucketNameCandidate(
        name=item.rendered_bucket_name,
        suffix=item.initial_suffix,
    )

    def create(candidate):
        if bucket.name != candidate.name:
            bucket.name = candidate.name
            bucket.save(update_fields=("name", "updated_at"))
        ownership = provider.find_owned_bucket(bucket)
        exists, owned = _owned(ownership)
        if exists and owned:
            return SimpleNamespace(created=False, request_id="")
        if exists:
            raise ObjectStorageProviderError("BUCKET_NAME_CONFLICT")
        return provider.create_owned_bucket(bucket)

    bucket.state = Bucket.State.CREATING
    bucket.save(update_fields=("state", "updated_at"))
    try:
        create_bucket_with_unique_name(
            create_callback=create,
            initial_candidate=initial,
            **_bucket_render_values(item, bucket),
        )
    except Exception as error:
        if is_retryable_provider_error(error):
            exists, owned = _owned(provider.find_owned_bucket(bucket))
            if not (exists and owned):
                bucket.state = Bucket.State.WAITING_RETRY
                bucket.save(update_fields=("state", "updated_at"))
                raise
        else:
            bucket.state = Bucket.State.FAILED
            bucket.save(update_fields=("state", "updated_at"))
            raise
    bucket.state = Bucket.State.ACTIVE
    bucket.last_synced_at = timezone.now()
    bucket.save(update_fields=("state", "last_synced_at", "updated_at"))
    return bucket


def _process_items(batch, provider, execution_key):
    retry_errors = []
    policy_candidates = []
    items = list(
        batch.items.select_related("bucket", "bucket__owner")
        .filter(
            status__in=(
                ApplicationItem.Status.PENDING,
                ApplicationItem.Status.WAITING_RETRY,
            )
        )
        .order_by("id")
    )
    for item in items:
        attempt, created = _attempt_for(item, execution_key)
        if not created:
            continue
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
        _event(item, attempt, "BUCKET_CREATING", "started")
        try:
            _ensure_bucket(item, provider)
        except Exception as error:
            if is_retryable_provider_error(error):
                _set_item_waiting(item, attempt, error, "BUCKET_CREATING")
                retry_errors.append(error)
            else:
                _set_item_failure(item, attempt, error)
            continue
        policy_candidates.append((item, attempt))
    return policy_candidates, retry_errors


def _active_owned_buckets(batch, identity, provider):
    buckets = list(
        Bucket.objects.filter(
            owner=batch.applicant,
            cloud_identity=identity,
            state=Bucket.State.ACTIVE,
        ).order_by("name")
    )
    for bucket in buckets:
        exists, owned = _owned(provider.find_owned_bucket(bucket))
        if not exists or not owned:
            raise ObjectStorageProviderError("BUCKET_OWNERSHIP_CONFLICT")
    return buckets


def _apply_policy(batch, identity, provider, candidates):
    if not candidates:
        return None
    try:
        buckets = _active_owned_buckets(batch, identity, provider)
        provider.reconcile_object_policy(identity, buckets)
    except Exception as error:
        temporary = is_retryable_provider_error(error)
        for item, attempt in candidates:
            if temporary:
                _set_item_waiting(item, attempt, error, "POLICY_APPLYING")
            else:
                _set_item_failure(item, attempt, error, manual=True)
        return error
    for item, attempt in candidates:
        item.status = ApplicationItem.Status.SUCCEEDED
        item.current_stage = ""
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
        _finish_attempt(attempt, ApplicationAttempt.Status.SUCCEEDED)
        _event(item, attempt, "POLICY_APPLYING", "succeeded")
    return None


def _ensure_delivery(batch):
    if batch.issued_access_key_id is None or batch.success_count < 1:
        return
    if DeliveryTicket.objects.filter(application_batch=batch).exists():
        return
    create_delivery_ticket(
        application_batch=batch,
        access_key=batch.issued_access_key,
        user=batch.applicant,
    )


def execute_application_batch(batch_id, *, execution_key=""):
    batch = (
        ApplicationBatch.objects.select_related("applicant", "issued_access_key")
        .prefetch_related("items")
        .get(pk=batch_id)
    )
    if batch.status in {
        ApplicationBatch.Status.SUCCEEDED,
        ApplicationBatch.Status.PARTIALLY_SUCCEEDED,
        ApplicationBatch.Status.CANCELLED,
        ApplicationBatch.Status.FAILED,
        ApplicationBatch.Status.MANUAL_REQUIRED,
    }:
        return batch
    batch.status = ApplicationBatch.Status.RUNNING
    batch.started_at = batch.started_at or timezone.now()
    batch.current_stage = "PRINCIPAL_BINDING"
    batch.save(update_fields=("status", "started_at", "current_stage", "updated_at"))
    identity = CloudIdentity.objects.select_related("resource_pool").get(
        user=batch.applicant
    )
    provider = get_provider_for_pool(identity.resource_pool)
    try:
        _principal(identity, provider)
        batch.current_stage = "KEY_RECONCILING"
        batch.save(update_fields=("current_stage", "updated_at"))
        _ensure_access_key(batch, identity, provider)
    except Exception as error:
        temporary = is_retryable_provider_error(error)
        _mark_batch_items(
            batch,
            error,
            waiting=temporary,
            stage=batch.current_stage,
        )
        if temporary:
            raise error
        return batch

    candidates, retry_errors = _process_items(batch, provider, execution_key)
    policy_error = _apply_policy(batch, identity, provider, candidates)
    if policy_error is not None and is_retryable_provider_error(policy_error):
        retry_errors.append(policy_error)
    refresh_batch_status(batch)
    try:
        _ensure_delivery(batch)
    except CredentialDeliveryError as error:
        batch.status = ApplicationBatch.Status.MANUAL_REQUIRED
        batch.current_stage = "DELIVERY_CREATING"
        batch.error_code = error.error_code
        batch.error_summary = error.error_code
        batch.save(
            update_fields=(
                "status",
                "current_stage",
                "error_code",
                "error_summary",
                "updated_at",
            )
        )
        return batch
    batch.refresh_from_db()
    if retry_errors:
        raise retry_errors[0]
    return batch


def mark_batch_manual_required(batch_id, error):
    batch = ApplicationBatch.objects.get(pk=batch_id)
    _mark_batch_items(
        batch,
        error,
        waiting=False,
        stage=batch.current_stage or "APPLICATION_EXECUTION",
    )
    return batch


def cancel_application_batch(batch_id):
    with transaction.atomic():
        batch = (
            ApplicationBatch.objects.select_for_update()
            .select_related("applicant", "issued_access_key")
            .get(pk=batch_id)
        )
        for item in batch.items.select_for_update().exclude(
            status=ApplicationItem.Status.SUCCEEDED
        ):
            item.status = ApplicationItem.Status.CANCELLED
            item.current_stage = ""
            item.save(update_fields=("status", "current_stage", "updated_at"))
            if item.bucket_id and item.bucket.state != Bucket.State.ACTIVE:
                item.bucket.state = Bucket.State.CANCELLED
                item.bucket.save(update_fields=("state", "updated_at"))
        refresh_batch_status(batch)
        if batch.success_count:
            return batch

    identity = CloudIdentity.objects.select_related("resource_pool").get(
        user=batch.applicant
    )
    provider = get_provider_for_pool(identity.resource_pool)
    for bucket in Bucket.objects.filter(
        application_items__batch=batch,
    ):
        exists, _owned_by_platform = _owned(provider.find_owned_bucket(bucket))
        if exists:
            return mark_batch_manual_required(
                batch.pk,
                ObjectStorageProviderError("CANCEL_CLOUD_BUCKET_PRESENT"),
            )
    if batch.issued_access_key_id is not None:
        consumed = DeliveryTicket.objects.filter(
            application_batch=batch,
            status=DeliveryTicket.Status.CONSUMED,
        ).exists()
        if not consumed:
            cloud_fingerprints = {
                key.fingerprint
                for key in _provider_items(provider.list_access_keys(identity))
            }
            key = batch.issued_access_key
            if key.access_key_fingerprint in cloud_fingerprints:
                provider.delete_access_key(provider_access_key(key))
            batch.issued_access_key = None
            batch.save(update_fields=("issued_access_key", "updated_at"))
            key.delete()
    provider.delete_personal_principal(identity)
    batch.refresh_from_db()
    return batch
