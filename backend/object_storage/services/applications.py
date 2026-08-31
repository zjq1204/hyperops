import hashlib
from django.db import IntegrityError, transaction
from django.utils import timezone

from object_storage.models import (
    StorageAccessKey,
    StorageApplication,
    StorageApplicationAttempt,
    StorageApplicationEvent,
    StorageBucket,
    StorageCloudIdentity,
    StorageMembership,
)
from object_storage.providers.aliyun import build_aliyun_provider
from object_storage.services.audit import record_audit_event
from object_storage.services.credentials import (
    create_delivery_ticket,
    encrypt_issued_access_key,
)
from object_storage.services.naming import render_bucket_name
from object_storage.services.policy import enforce_bucket_quota
from object_storage.services.provider_errors import ObjectStorageProviderError

MAX_PROVIDER_RETRIES = 3


def get_provider_for_pool(resource_pool):
    return build_aliyun_provider(resource_pool)


def is_retryable_provider_error(error):
    return bool(getattr(error, "retryable", False))


def _ram_user_name(membership):
    digest = hashlib.sha256(
        f"{membership.tenant.code}:{membership.feishu_open_id}".encode("utf-8")
    ).hexdigest()[:20]
    return f"hyperops-{membership.tenant.code}-{digest}"[:128]


def _request_fields(fields):
    return {
        "project": str(fields.get("project") or "").strip(),
        "environment": str(fields.get("environment") or "").strip().lower(),
        "purpose": str(fields.get("purpose") or "").strip(),
        "notes": str(fields.get("notes") or "").strip(),
    }


def create_application(
    *,
    membership,
    resource_pool,
    action_type,
    idempotency_key,
    request_fields,
    enqueue=True,
):
    fields = _request_fields(request_fields)
    key = str(idempotency_key or "").strip()
    if not key:
        raise ValueError("IDEMPOTENCY_KEY_REQUIRED")
    existing = StorageApplication.objects.filter(
        tenant=membership.tenant,
        applicant=membership,
        idempotency_key=key,
    ).first()
    if existing:
        return existing
    fields["resource_pool_id"] = resource_pool.pk
    try:
        with transaction.atomic():
            application = StorageApplication.objects.create(
                tenant=membership.tenant,
                applicant=membership,
                action_type=action_type,
                idempotency_key=key,
                request_fields=fields,
            )
            record_audit_event(
                tenant=membership.tenant,
                action="storage.application.created",
                target_type="StorageApplication",
                target_id=application.pk,
                result="accepted",
                actor=membership.user,
                application=application,
                safe_metadata={"action_type": action_type},
            )
    except IntegrityError:
        application = StorageApplication.objects.get(
            tenant=membership.tenant,
            applicant=membership,
            idempotency_key=key,
        )
    if enqueue:
        from object_storage.tasks import run_storage_application

        run_storage_application.delay(application.pk)
    return application


def _event(application, attempt, stage, result, *, error_code="", metadata=None):
    return StorageApplicationEvent.objects.create(
        tenant=application.tenant,
        application=application,
        attempt=attempt,
        stage=stage,
        result=result,
        error_code=error_code,
        safe_metadata=metadata or {},
    )


def _error_details(error):
    if isinstance(error, ObjectStorageProviderError):
        return error.error_code, error.request_id
    return str(getattr(error, "error_code", "APPLICATION_EXECUTION_FAILED")), str(
        getattr(error, "request_id", "") or ""
    )


def _identity_for(application, membership, pool):
    identity, _created = StorageCloudIdentity.objects.select_for_update().get_or_create(
        tenant=application.tenant,
        membership=membership,
        resource_pool=pool,
        defaults={
            "ram_user_name": _ram_user_name(membership),
            "state": StorageCloudIdentity.State.PROVISIONING,
        },
    )
    return identity


def _create_local_bucket(application, identity):
    fields = application.request_fields
    name = render_bucket_name(
        tenant=application.tenant,
        membership=identity.membership,
        project=fields["project"],
        environment=fields["environment"],
        purpose=fields["purpose"],
    )
    return StorageBucket.objects.create(
        tenant=application.tenant,
        resource_pool=identity.resource_pool,
        owner=identity.membership,
        cloud_identity=identity,
        name=name,
        project=fields["project"],
        environment=fields["environment"],
        purpose=fields["purpose"],
        notes=fields["notes"],
        region=identity.resource_pool.region,
        template_version=application.tenant.naming_template_version,
        cloud_marker=f"hyperops:bucket:application:{application.pk}",
        state=StorageBucket.State.CREATING,
    )


def _active_owned_buckets(identity):
    return StorageBucket.objects.filter(
        owner=identity.membership,
        cloud_identity=identity,
        state=StorageBucket.State.ACTIVE,
    )


def _is_first_application(application):
    return (
        application.action_type
        == StorageApplication.ActionType.FIRST_BUCKET_AND_CREDENTIAL
    )


def _manual_failure(application, attempt, error, stage):
    error_code, request_id = _error_details(error)
    attempt.status = StorageApplicationAttempt.Status.FAILED
    attempt.error_code = error_code
    attempt.provider_request_id = request_id
    attempt.finished_at = timezone.now()
    attempt.save(
        update_fields=("status", "error_code", "provider_request_id", "finished_at")
    )
    _event(application, attempt, stage, "failed", error_code=error_code)
    application.status = StorageApplication.Status.MANUAL_REQUIRED
    application.error_code = error_code
    application.error_summary = "需要人工处理"
    application.current_stage = stage
    application.finished_at = timezone.now()
    application.save(
        update_fields=(
            "status",
            "error_code",
            "error_summary",
            "current_stage",
            "finished_at",
            "updated_at",
        )
    )
    return application


def _persist_retryable_failure(application_id, error, stage):
    error_code, request_id = _error_details(error)
    with transaction.atomic():
        application = StorageApplication.objects.select_for_update().get(
            pk=application_id
        )
        attempt = (
            application.attempts.select_for_update().order_by("-attempt_number").first()
        )
        if attempt is None:
            return
        attempt.status = StorageApplicationAttempt.Status.FAILED
        attempt.error_code = error_code
        attempt.provider_request_id = request_id
        attempt.finished_at = timezone.now()
        attempt.save(
            update_fields=("status", "error_code", "provider_request_id", "finished_at")
        )
        application.status = StorageApplication.Status.RUNNING
        application.current_stage = stage
        application.error_code = error_code
        application.error_summary = "临时故障，等待自动重试"
        application.save(
            update_fields=(
                "status",
                "current_stage",
                "error_code",
                "error_summary",
                "updated_at",
            )
        )
        _event(application, attempt, stage, "failed", error_code=error_code)


def _execute_application_locked(application_id):
    application = (
        StorageApplication.objects.select_for_update()
        .select_related("tenant", "applicant")
        .get(pk=application_id)
    )
    if application.status in (
        StorageApplication.Status.SUCCEEDED,
        StorageApplication.Status.DELIVERY_READY,
    ):
        return application
    membership = (
        StorageMembership.objects.select_for_update()
        .select_related("tenant")
        .get(pk=application.applicant_id)
    )
    pool_id = application.request_fields.get("resource_pool_id")
    from object_storage.models import StorageResourcePool

    pool = StorageResourcePool.objects.select_for_update().get(pk=pool_id)
    provider = get_provider_for_pool(pool)
    attempt = StorageApplicationAttempt.objects.create(
        tenant=application.tenant,
        application=application,
        attempt_number=application.attempts.count() + 1,
        status=StorageApplicationAttempt.Status.RUNNING,
    )
    application.status = StorageApplication.Status.RUNNING
    application.started_at = application.started_at or application.created_at
    application.save(update_fields=("status", "started_at", "updated_at"))
    identity = _identity_for(application, membership, pool)
    try:
        application.current_stage = "IDENTITY_CHECKING"
        _event(application, attempt, "IDENTITY_CHECKING", "succeeded")
        enforce_bucket_quota(membership)
        _event(application, attempt, "QUOTA_CHECKING", "succeeded")
        application.current_stage = "BUCKET_CREATING"
        _event(application, attempt, "BUCKET_CREATING", "started")
        bucket = application.target_bucket
        if bucket is None:
            bucket = _create_local_bucket(application, identity)
        elif bucket.state in (StorageBucket.State.ACTIVE, StorageBucket.State.CREATING):
            bucket = StorageBucket.objects.select_for_update().get(pk=bucket.pk)
        else:
            raise ObjectStorageProviderError("BUCKET_STATE_INCONSISTENT")
        application.target_bucket = bucket
        application.save(update_fields=("target_bucket", "current_stage", "updated_at"))
        application.current_stage = "PRINCIPAL_BINDING"
        if (
            identity.state != StorageCloudIdentity.State.ACTIVE
            or not identity.ram_user_id
        ):
            principal = provider.find_or_create_personal_principal(identity)
            identity.ram_user_id = principal.user_id
            identity.ram_user_name = principal.user_name
            identity.state = StorageCloudIdentity.State.ACTIVE
            identity.save(
                update_fields=("ram_user_id", "ram_user_name", "state", "updated_at")
            )
        _event(application, attempt, "PRINCIPAL_BINDING", "succeeded")
        application.current_stage = "BUCKET_CREATING"
        try:
            provider.create_owned_bucket(bucket)
        except Exception as error:
            if is_retryable_provider_error(error) and hasattr(
                provider, "find_owned_bucket"
            ):
                if provider.find_owned_bucket(bucket):
                    bucket.state = StorageBucket.State.ACTIVE
                else:
                    raise
            else:
                raise
        bucket.state = StorageBucket.State.ACTIVE
        bucket.save(update_fields=("state", "updated_at"))
        # BUCKET_CREATING is recorded once before the principal call so the
        # technical event stream reflects the declared workflow order.
        application.current_stage = "POLICY_APPLYING"
        provider.reconcile_object_policy(identity, _active_owned_buckets(identity))
        _event(application, attempt, "POLICY_APPLYING", "succeeded")
        if _is_first_application(application):
            application.current_stage = "KEY_CREATING"
            issued = provider.create_access_key(identity)
            try:
                encrypted = encrypt_issued_access_key(issued)
                access_key = StorageAccessKey.objects.create(
                    tenant=application.tenant,
                    cloud_identity=identity,
                    local_state=StorageAccessKey.LocalState.DELIVERY_READY,
                    **encrypted,
                )
            except Exception as encryption_error:
                cleanup_key = type("NewCloudKey", (), {})()
                cleanup_key.cloud_identity = identity
                cleanup_key.access_key_id = issued.access_key_id
                try:
                    provider.delete_access_key(cleanup_key)
                except Exception as cleanup_error:
                    raise ObjectStorageProviderError(
                        "KEY_COMPENSATION_FAILED"
                    ) from cleanup_error
                raise encryption_error
            application.target_access_key = access_key
            application.save(update_fields=("target_access_key", "updated_at"))
            _event(application, attempt, "KEY_CREATING", "succeeded")
            _event(application, attempt, "SECRET_ENCRYPTING", "succeeded")
            application.current_stage = "DELIVERY_CREATING"
            create_delivery_ticket(
                application=application,
                access_key=access_key,
                membership=membership,
                tenant=application.tenant,
            )
            _event(application, attempt, "DELIVERY_CREATING", "succeeded")
            application.status = StorageApplication.Status.DELIVERY_READY
        else:
            application.status = StorageApplication.Status.SUCCEEDED
        application.current_stage = ""
        application.finished_at = timezone.now()
        attempt.status = StorageApplicationAttempt.Status.SUCCEEDED
        attempt.finished_at = timezone.now()
        attempt.save(update_fields=("status", "finished_at"))
        application.save(
            update_fields=("status", "current_stage", "finished_at", "updated_at")
        )
        record_audit_event(
            tenant=application.tenant,
            action="storage.application.completed",
            target_type="StorageApplication",
            target_id=application.pk,
            result="succeeded",
            actor=membership.user,
            application=application,
            safe_metadata={"status": application.status},
        )
        return application
    except Exception as error:
        stage = application.current_stage or "APPLICATION_EXECUTION"
        if is_retryable_provider_error(error):
            setattr(error, "application_stage", stage)
            raise
        return _manual_failure(application, attempt, error, stage)


def execute_application(application_id):
    retry_error = None
    try:
        with transaction.atomic():
            try:
                result = _execute_application_locked(application_id)
            except Exception as error:
                if not is_retryable_provider_error(error):
                    raise
                _persist_retryable_failure(
                    application_id,
                    error,
                    getattr(error, "application_stage", "APPLICATION_EXECUTION"),
                )
                retry_error = error
    except Exception as error:
        raise
    if retry_error is not None:
        raise retry_error
    return result


def mark_application_manual_required(application_id, error):
    error_code, request_id = _error_details(error)
    with transaction.atomic():
        application = StorageApplication.objects.select_for_update().get(
            pk=application_id
        )
        attempt = (
            application.attempts.select_for_update().order_by("-attempt_number").first()
        )
        if attempt is None:
            return application
        return _manual_failure(
            application,
            attempt,
            ObjectStorageProviderError(error_code, request_id=request_id),
            application.current_stage or "APPLICATION_EXECUTION",
        )
