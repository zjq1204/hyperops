import hashlib
from types import SimpleNamespace

from django.db import IntegrityError, transaction
from django.utils import timezone

from object_storage.crypto import decrypt_secret
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
    cleaned = {
        "project": str(fields.get("project") or "").strip(),
        "environment": str(fields.get("environment") or "").strip().lower(),
        "purpose": str(fields.get("purpose") or "").strip(),
        "notes": str(fields.get("notes") or "").strip(),
    }
    for field_name in ("target_bucket_id", "candidate_access_key_id"):
        if fields.get(field_name) is not None:
            cleaned[field_name] = int(fields[field_name])
    if "confirmed" in fields:
        cleaned["confirmed"] = bool(fields["confirmed"])
    if fields.get("reason") is not None:
        cleaned["reason"] = str(fields["reason"]).strip()
    return cleaned


def create_application(
    *,
    membership,
    resource_pool,
    action_type,
    idempotency_key,
    request_fields,
    enqueue=True,
    actor=None,
):
    if resource_pool.tenant_id != membership.tenant_id:
        raise ValueError("RESOURCE_POOL_TENANT_MISMATCH")
    fields = _request_fields(request_fields)
    fields["actor_user_id"] = (actor or membership.user).pk
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
    created = False
    try:
        with transaction.atomic():
            application = StorageApplication.objects.create(
                tenant=membership.tenant,
                applicant=membership,
                action_type=action_type,
                idempotency_key=key,
                request_fields=fields,
            )
            created = True
            record_audit_event(
                tenant=membership.tenant,
                action="storage.application.created",
                target_type="StorageApplication",
                target_id=application.pk,
                result="accepted",
                actor=actor or membership.user,
                application=application,
                safe_metadata={"action_type": action_type},
            )
    except IntegrityError:
        application = StorageApplication.objects.get(
            tenant=membership.tenant,
            applicant=membership,
            idempotency_key=key,
        )
    if enqueue and created:
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


def _application_actor(application, membership):
    actor_id = application.request_fields.get("actor_user_id")
    if actor_id == membership.user_id:
        return membership.user
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(pk=actor_id).first() or membership.user


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
    record_audit_event(
        tenant=application.tenant,
        actor=_application_actor(application, application.applicant),
        application=application,
        action="storage.application.manual_required",
        target_type="StorageApplication",
        target_id=application.pk,
        result="manual_required",
        reason=application.request_fields.get("reason", ""),
        safe_metadata={"stage": stage, "error_code": error_code},
        request_id=request_id,
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
        record_audit_event(
            tenant=application.tenant,
            actor=_application_actor(application, application.applicant),
            application=application,
            action="storage.application.retry_pending",
            target_type="StorageApplication",
            target_id=application.pk,
            result="retry_pending",
            reason=application.request_fields.get("reason", ""),
            safe_metadata={"stage": stage, "error_code": error_code},
            request_id=request_id,
        )


def _provider_key(access_key):
    return SimpleNamespace(
        cloud_identity=access_key.cloud_identity,
        access_key_id=decrypt_secret(access_key.access_key_id_encrypted),
    )


def _complete_application(application, attempt, membership, status):
    application.status = status
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
        actor=_application_actor(application, membership),
        application=application,
        reason=application.request_fields.get("reason", ""),
        safe_metadata={"status": application.status},
    )
    return application


def _create_and_deliver_access_key(
    application, attempt, membership, identity, provider
):
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
        cleanup_key = SimpleNamespace(
            cloud_identity=identity,
            access_key_id=issued.access_key_id,
        )
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
    try:
        create_delivery_ticket(
            application=application,
            access_key=access_key,
            membership=membership,
            tenant=application.tenant,
        )
    except Exception as delivery_error:
        cleanup_key = _provider_key(access_key)
        try:
            provider.delete_access_key(cleanup_key)
        except Exception as cleanup_error:
            raise ObjectStorageProviderError(
                "KEY_COMPENSATION_FAILED"
            ) from cleanup_error
        application.target_access_key = None
        application.save(update_fields=("target_access_key", "updated_at"))
        access_key.delivery_tickets.all().delete()
        access_key.delete()
        raise delivery_error
    record_audit_event(
        tenant=application.tenant,
        actor=_application_actor(application, membership),
        application=application,
        action="storage.credential.issued",
        target_type="StorageAccessKey",
        target_id=access_key.pk,
        result="succeeded",
        safe_metadata={"last_four": access_key.access_key_last_four},
    )
    _event(application, attempt, "DELIVERY_CREATING", "succeeded")
    return access_key


def _execute_rotation(application, attempt, membership, identity, provider):
    keys = list(
        identity.access_keys.select_for_update()
        .filter(
            cloud_state__in=(
                StorageAccessKey.CloudState.ACTIVE,
                StorageAccessKey.CloudState.INACTIVE,
            )
        )
        .order_by("created_at", "id")
    )
    if not keys or len(keys) > 2:
        raise ObjectStorageProviderError("KEY_COUNT_INCONSISTENT")
    cloud_keys = provider.list_access_keys(identity)
    cloud_fingerprints = {key.fingerprint for key in cloud_keys}
    known_fingerprints = {key.access_key_fingerprint for key in keys}
    if cloud_fingerprints - known_fingerprints:
        raise ObjectStorageProviderError("CLOUD_KEY_RECOVERY_REQUIRED")
    if len(keys) == 2:
        candidate = next(
            (
                key
                for key in keys
                if key.cloud_state == StorageAccessKey.CloudState.INACTIVE
            ),
            keys[0],
        )
        requested_candidate_id = application.request_fields.get(
            "candidate_access_key_id"
        )
        if (
            not application.request_fields.get("confirmed")
            or requested_candidate_id != candidate.pk
        ):
            raise ObjectStorageProviderError("ROTATION_CONFIRMATION_REQUIRED")
        application.current_stage = "KEY_DELETING"
        if candidate.access_key_fingerprint in cloud_fingerprints:
            provider.delete_access_key(_provider_key(candidate))
        candidate.cloud_state = StorageAccessKey.CloudState.DELETED
        candidate.local_state = StorageAccessKey.LocalState.RETIRED
        candidate.deleted_at = timezone.now()
        candidate.save(
            update_fields=(
                "cloud_state",
                "local_state",
                "deleted_at",
                "updated_at",
            )
        )
        record_audit_event(
            tenant=application.tenant,
            actor=membership.user,
            application=application,
            action="storage.credential.deleted",
            target_type="StorageAccessKey",
            target_id=candidate.pk,
            result="succeeded",
            safe_metadata={"last_four": candidate.access_key_last_four},
        )
        _event(application, attempt, "KEY_DELETING", "succeeded")
    application.current_stage = "KEY_CREATING"
    _create_and_deliver_access_key(
        application,
        attempt,
        membership,
        identity,
        provider,
    )
    return _complete_application(
        application,
        attempt,
        membership,
        StorageApplication.Status.DELIVERY_READY,
    )


def _execute_release(application, attempt, membership, identity, provider):
    bucket_id = application.request_fields.get("target_bucket_id")
    bucket = (
        StorageBucket.objects.select_for_update()
        .filter(pk=bucket_id, owner=membership, cloud_identity=identity)
        .first()
    )
    if bucket is None:
        raise ObjectStorageProviderError("BUCKET_NOT_FOUND")
    application.target_bucket = bucket
    application.save(update_fields=("target_bucket", "updated_at"))
    if bucket.state == StorageBucket.State.RELEASED:
        return _complete_application(
            application,
            attempt,
            membership,
            StorageApplication.Status.SUCCEEDED,
        )
    application.current_stage = "BUCKET_RELEASING"
    if provider.find_owned_bucket(bucket):
        emptiness = provider.inspect_bucket_emptiness(bucket)
        if not emptiness.is_empty:
            raise ObjectStorageProviderError("BUCKET_NOT_EMPTY")
        bucket.state = StorageBucket.State.RELEASING
        bucket.save(update_fields=("state", "updated_at"))
        provider.delete_owned_bucket(bucket)
    bucket.state = StorageBucket.State.RELEASED
    bucket.save(update_fields=("state", "updated_at"))
    record_audit_event(
        tenant=application.tenant,
        actor=membership.user,
        application=application,
        action="storage.bucket.released",
        target_type="StorageBucket",
        target_id=bucket.pk,
        result="succeeded",
        safe_metadata={"bucket_name": bucket.name},
    )
    _event(application, attempt, "BUCKET_RELEASING", "succeeded")
    application.current_stage = "POLICY_APPLYING"
    provider.reconcile_object_policy(identity, _active_owned_buckets(identity))
    _event(application, attempt, "POLICY_APPLYING", "succeeded")
    return _complete_application(
        application,
        attempt,
        membership,
        StorageApplication.Status.SUCCEEDED,
    )


def _execute_suspend(application, attempt, membership, identity, provider):
    application.current_stage = "KEYS_DEACTIVATING"
    identities = StorageCloudIdentity.objects.select_for_update().filter(
        membership=membership
    )
    for selected_identity in identities:
        selected_provider = (
            provider
            if selected_identity.resource_pool_id == identity.resource_pool_id
            else get_provider_for_pool(selected_identity.resource_pool)
        )
        cloud_keys = {
            key.fingerprint: key
            for key in selected_provider.list_access_keys(selected_identity)
        }
        known_fingerprints = set(
            selected_identity.access_keys.values_list(
                "access_key_fingerprint", flat=True
            )
        )
        if set(cloud_keys) - known_fingerprints:
            raise ObjectStorageProviderError("CLOUD_KEY_RECOVERY_REQUIRED")
        local_keys = {
            key.access_key_fingerprint: key
            for key in selected_identity.access_keys.select_for_update().filter(
                cloud_state__in=(
                    StorageAccessKey.CloudState.ACTIVE,
                    StorageAccessKey.CloudState.INACTIVE,
                )
            )
        }
        for fingerprint, cloud_key in cloud_keys.items():
            access_key = local_keys[fingerprint]
            if cloud_key.status.lower() == "active":
                selected_provider.deactivate_access_key(_provider_key(access_key))
            access_key.cloud_state = StorageAccessKey.CloudState.INACTIVE
            access_key.local_state = StorageAccessKey.LocalState.RETIRED
            access_key.deactivated_at = timezone.now()
            access_key.save(
                update_fields=(
                    "cloud_state",
                    "local_state",
                    "deactivated_at",
                    "updated_at",
                )
            )
            record_audit_event(
                tenant=application.tenant,
                actor=_application_actor(application, membership),
                application=application,
                action="storage.credential.deactivated",
                target_type="StorageAccessKey",
                target_id=access_key.pk,
                result="succeeded",
                reason=application.request_fields.get("reason", ""),
                safe_metadata={"last_four": access_key.access_key_last_four},
            )
        selected_identity.state = StorageCloudIdentity.State.SUSPENDED
        selected_identity.save(update_fields=("state", "updated_at"))
    record_audit_event(
        tenant=application.tenant,
        actor=_application_actor(application, membership),
        application=application,
        action="storage.membership.suspended",
        target_type="StorageMembership",
        target_id=membership.pk,
        result="succeeded",
        reason=application.request_fields.get("reason", ""),
    )
    _event(application, attempt, "KEYS_DEACTIVATING", "succeeded")
    return _complete_application(
        application,
        attempt,
        membership,
        StorageApplication.Status.SUCCEEDED,
    )


def _execute_reactivate(application, attempt, membership, identity):
    StorageCloudIdentity.objects.filter(
        membership=membership,
        state=StorageCloudIdentity.State.SUSPENDED,
    ).update(state=StorageCloudIdentity.State.ACTIVE, updated_at=timezone.now())
    record_audit_event(
        tenant=application.tenant,
        actor=_application_actor(application, membership),
        application=application,
        action="storage.membership.reactivated",
        target_type="StorageMembership",
        target_id=membership.pk,
        result="succeeded",
        reason=application.request_fields.get("reason", ""),
    )
    return _complete_application(
        application,
        attempt,
        membership,
        StorageApplication.Status.SUCCEEDED,
    )


def _execute_application_locked(application_id, execution_key=""):
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
    if (
        execution_key
        and application.attempts.filter(celery_task_id=execution_key).exists()
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
    attempt = StorageApplicationAttempt.objects.create(
        tenant=application.tenant,
        application=application,
        attempt_number=application.attempts.count() + 1,
        celery_task_id=execution_key,
        status=StorageApplicationAttempt.Status.RUNNING,
    )
    application.status = StorageApplication.Status.RUNNING
    application.started_at = application.started_at or application.created_at
    application.save(update_fields=("status", "started_at", "updated_at"))
    try:
        if application.action_type in (
            StorageApplication.ActionType.SUSPEND_MEMBERSHIP,
            StorageApplication.ActionType.REACTIVATE_MEMBERSHIP,
        ):
            identity = (
                StorageCloudIdentity.objects.select_for_update()
                .filter(membership=membership, resource_pool=pool)
                .first()
            )
            if identity is None:
                action = (
                    "storage.membership.suspended"
                    if application.action_type
                    == StorageApplication.ActionType.SUSPEND_MEMBERSHIP
                    else "storage.membership.reactivated"
                )
                record_audit_event(
                    tenant=application.tenant,
                    actor=_application_actor(application, membership),
                    application=application,
                    action=action,
                    target_type="StorageMembership",
                    target_id=membership.pk,
                    result="succeeded",
                    reason=application.request_fields.get("reason", ""),
                )
                return _complete_application(
                    application,
                    attempt,
                    membership,
                    StorageApplication.Status.SUCCEEDED,
                )
            provider = get_provider_for_pool(pool)
        else:
            identity = _identity_for(application, membership, pool)
            provider = get_provider_for_pool(pool)
        if application.action_type == StorageApplication.ActionType.ROTATE_CREDENTIAL:
            return _execute_rotation(
                application, attempt, membership, identity, provider
            )
        if application.action_type == StorageApplication.ActionType.RELEASE_BUCKET:
            return _execute_release(
                application, attempt, membership, identity, provider
            )
        if application.action_type == StorageApplication.ActionType.SUSPEND_MEMBERSHIP:
            return _execute_suspend(
                application, attempt, membership, identity, provider
            )
        if (
            application.action_type
            == StorageApplication.ActionType.REACTIVATE_MEMBERSHIP
        ):
            return _execute_reactivate(application, attempt, membership, identity)
        supported_actions = {
            StorageApplication.ActionType.FIRST_BUCKET_AND_CREDENTIAL,
            StorageApplication.ActionType.ADD_BUCKET,
        }
        if application.action_type not in supported_actions:
            raise ObjectStorageProviderError("APPLICATION_ACTION_NOT_IMPLEMENTED")
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
        application.current_stage = "BUCKET_CREATING"
        bucket_exists = provider.find_owned_bucket(bucket)
        if not bucket_exists:
            try:
                provider.create_owned_bucket(bucket)
            except Exception as error:
                if is_retryable_provider_error(error):
                    if provider.find_owned_bucket(bucket):
                        bucket.state = StorageBucket.State.ACTIVE
                    else:
                        raise
                else:
                    raise
        bucket.state = StorageBucket.State.ACTIVE
        bucket.save(update_fields=("state", "updated_at"))
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
        application.current_stage = "POLICY_APPLYING"
        provider.reconcile_object_policy(identity, _active_owned_buckets(identity))
        _event(application, attempt, "POLICY_APPLYING", "succeeded")
        if _is_first_application(application):
            application.current_stage = "KEY_CREATING"
            cloud_keys = provider.list_access_keys(identity)
            known_fingerprints = set(
                identity.access_keys.values_list("access_key_fingerprint", flat=True)
            )
            if any(key.fingerprint not in known_fingerprints for key in cloud_keys):
                raise ObjectStorageProviderError("CLOUD_KEY_RECOVERY_REQUIRED")
            if application.target_access_key_id or known_fingerprints:
                raise ObjectStorageProviderError("LOCAL_KEY_STATE_INCONSISTENT")
            _create_and_deliver_access_key(
                application,
                attempt,
                membership,
                identity,
                provider,
            )
            application.status = StorageApplication.Status.DELIVERY_READY
        else:
            application.status = StorageApplication.Status.SUCCEEDED
        return _complete_application(
            application,
            attempt,
            membership,
            application.status,
        )
    except Exception as error:
        stage = application.current_stage or "APPLICATION_EXECUTION"
        if is_retryable_provider_error(error):
            setattr(error, "application_stage", stage)
            raise
        return _manual_failure(application, attempt, error, stage)


def execute_application(application_id, *, execution_key=""):
    retry_error = None
    try:
        with transaction.atomic():
            try:
                result = _execute_application_locked(
                    application_id,
                    execution_key=execution_key,
                )
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
