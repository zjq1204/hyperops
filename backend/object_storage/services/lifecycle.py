"""Bucket and object-storage user lifecycle actions.

Database state changes are kept separate from provider calls so every cloud
mutation can be retried by a Celery task without repeating an unsafe action.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from object_storage.models import AccessKey, Bucket, CloudIdentity
from object_storage.permissions import has_object_storage_admin_access
from object_storage.providers.base import BucketConfiguration
from object_storage.services.audit import record_audit_event
from object_storage.services.policy import BucketQuotaExceeded, check_bucket_capacity
from object_storage.services.provider_errors import ObjectStorageProviderError

RETENTION_DAYS = 7


class LifecycleError(RuntimeError):
    def __init__(self, error_code):
        self.error_code = error_code
        super().__init__(error_code)


class BucketConfigurationError(LifecycleError):
    pass


def _is_admin(actor):
    return has_object_storage_admin_access(actor)


def _provider(bucket):
    from object_storage.providers.aliyun import build_aliyun_provider

    return build_aliyun_provider(bucket.resource_pool)


def _assert_actor(bucket, actor, *, allow_background=False):
    if allow_background and actor is None:
        return
    if actor is None or (
        not _is_admin(actor) and bucket.owner_id != getattr(actor, "pk", None)
    ):
        raise LifecycleError("BUCKET_OWNERSHIP_REQUIRED")


def _assert_confirmation(bucket, bucket_name, confirmed):
    if not confirmed:
        raise LifecycleError("BUCKET_NAME_CONFIRMATION_REQUIRED")
    if str(bucket_name or "").strip() != bucket.name:
        raise LifecycleError("BUCKET_NAME_CONFIRMATION_MISMATCH")


def _error_code(error, default):
    return str(getattr(error, "error_code", "") or default)


def _confirmed_empty(inspection):
    if not getattr(inspection, "is_empty", False):
        return False
    return not any(
        int(getattr(inspection, field, 0) or 0)
        for field in (
            "object_count",
            "version_count",
            "delete_marker_count",
            "multipart_upload_count",
        )
    )


def _set_deletion_error(bucket, error_code, *, state=Bucket.State.DELETION_BLOCKED):
    bucket.state = state
    bucket.deletion_error_code = error_code
    bucket.deletion_error_summary = error_code
    bucket.save(
        update_fields=(
            "state",
            "deletion_error_code",
            "deletion_error_summary",
            "updated_at",
        )
    )


def _active_buckets(identity, *, exclude_id=None):
    query = Bucket.objects.filter(
        owner_id=identity.user_id,
        cloud_identity=identity,
        state=Bucket.State.ACTIVE,
    )
    if exclude_id is not None:
        query = query.exclude(pk=exclude_id)
    return list(query.order_by("name"))


def _reconcile_policy(bucket, provider):
    return provider.reconcile_object_policy(
        bucket.cloud_identity,
        _active_buckets(bucket.cloud_identity, exclude_id=bucket.pk),
    )


def release_bucket(
    *,
    bucket,
    actor,
    bucket_name,
    confirmed,
    provider=None,
    enqueue=True,
    reason="",
):
    """Request a seven-day release after a provider emptiness check."""

    _assert_actor(bucket, actor)
    _assert_confirmation(bucket, bucket_name, confirmed)
    with transaction.atomic():
        locked = (
            Bucket.objects.select_for_update()
            .select_related("owner", "cloud_identity", "resource_pool")
            .get(pk=bucket.pk)
        )
        if locked.state in (Bucket.State.PENDING_DELETION, Bucket.State.RELEASED):
            return locked
        if locked.state == Bucket.State.RELEASING:
            pass
        elif locked.state not in (Bucket.State.ACTIVE, Bucket.State.DELETION_BLOCKED):
            raise LifecycleError("BUCKET_RELEASE_NOT_ALLOWED")
        else:
            locked.state = Bucket.State.RELEASING
            locked.deletion_error_code = ""
            locked.deletion_error_summary = ""
            locked.save(
                update_fields=(
                    "state",
                    "deletion_error_code",
                    "deletion_error_summary",
                    "updated_at",
                )
            )
    if enqueue:
        from object_storage.tasks import release_bucket_task

        release_bucket_task.delay(
            locked.pk,
            actor_id=getattr(actor, "pk", None),
            reason=reason,
        )
        return locked
    return _release_bucket_cloud(
        locked.pk, provider=provider, actor=actor, reason=reason
    )


def _release_bucket_cloud(bucket_id, *, provider=None, actor=None, reason=""):
    bucket = Bucket.objects.select_related(
        "owner", "cloud_identity", "resource_pool"
    ).get(pk=bucket_id)
    if bucket.state in (Bucket.State.PENDING_DELETION, Bucket.State.RELEASED):
        return bucket
    provider = provider or _provider(bucket)
    try:
        inspection = provider.inspect_bucket_emptiness(bucket)
    except Exception as error:
        with transaction.atomic():
            locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
            _set_deletion_error(locked, _error_code(error, "BUCKET_EMPTY_CHECK_FAILED"))
        raise
    if not _confirmed_empty(inspection):
        with transaction.atomic():
            locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
            locked.state = Bucket.State.ACTIVE
            locked.deletion_error_code = "BUCKET_NOT_EMPTY"
            locked.deletion_error_summary = "BUCKET_NOT_EMPTY"
            locked.save(
                update_fields=(
                    "state",
                    "deletion_error_code",
                    "deletion_error_summary",
                    "updated_at",
                )
            )
        raise LifecycleError("BUCKET_NOT_EMPTY")

    try:
        _reconcile_policy(bucket, provider)
    except Exception as error:
        with transaction.atomic():
            locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
            _set_deletion_error(
                locked, _error_code(error, "POLICY_RECONCILIATION_FAILED")
            )
        raise
    pending_delete_at = timezone.now() + timedelta(days=RETENTION_DAYS)
    with transaction.atomic():
        locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
        locked.state = Bucket.State.PENDING_DELETION
        locked.pending_delete_at = pending_delete_at
        locked.deletion_error_code = ""
        locked.deletion_error_summary = ""
        locked.save(
            update_fields=(
                "state",
                "pending_delete_at",
                "deletion_error_code",
                "deletion_error_summary",
                "updated_at",
            )
        )
    record_audit_event(
        actor=actor,
        action="storage.bucket.release",
        target_type="Bucket",
        target_id=bucket.pk,
        result="succeeded",
        reason=reason,
        safe_metadata={"bucket_name": bucket.name},
    )
    return Bucket.objects.get(pk=bucket.pk)


def recover_bucket(*, bucket, actor, bucket_name, confirmed, provider=None, reason=""):
    _assert_actor(bucket, actor)
    _assert_confirmation(bucket, bucket_name, confirmed)
    with transaction.atomic():
        locked = (
            Bucket.objects.select_for_update()
            .select_related("cloud_identity", "resource_pool")
            .get(pk=bucket.pk)
        )
        if locked.state != Bucket.State.PENDING_DELETION:
            raise LifecycleError("BUCKET_RECOVERY_NOT_ALLOWED")
        if not locked.pending_delete_at or locked.pending_delete_at <= timezone.now():
            raise LifecycleError("BUCKET_RECOVERY_WINDOW_EXPIRED")
        user = get_user_model().objects.select_for_update().get(pk=locked.owner_id)
        try:
            check_bucket_capacity(user)
        except BucketQuotaExceeded as error:
            raise LifecycleError("BUCKET_QUOTA_EXCEEDED") from error
        locked.state = Bucket.State.ACTIVE
        locked.pending_delete_at = None
        locked.deletion_error_code = ""
        locked.deletion_error_summary = ""
        locked.save(
            update_fields=(
                "state",
                "pending_delete_at",
                "deletion_error_code",
                "deletion_error_summary",
                "updated_at",
            )
        )
    provider = provider or _provider(locked)
    try:
        buckets = _active_buckets(locked.cloud_identity)
        if all(candidate.pk != locked.pk for candidate in buckets):
            buckets.append(locked)
        provider.reconcile_object_policy(
            locked.cloud_identity,
            sorted(buckets, key=lambda candidate: candidate.name),
        )
    except Exception:
        with transaction.atomic():
            current = Bucket.objects.select_for_update().get(pk=locked.pk)
            current.state = Bucket.State.PENDING_DELETION
            current.pending_delete_at = timezone.now() + timedelta(days=RETENTION_DAYS)
            current.deletion_error_code = "POLICY_RECONCILIATION_FAILED"
            current.deletion_error_summary = "POLICY_RECONCILIATION_FAILED"
            current.save(
                update_fields=(
                    "state",
                    "pending_delete_at",
                    "deletion_error_code",
                    "deletion_error_summary",
                    "updated_at",
                )
            )
        raise
    record_audit_event(
        actor=actor,
        action="storage.bucket.recover",
        target_type="Bucket",
        target_id=locked.pk,
        result="succeeded",
        reason=reason,
        safe_metadata={"bucket_name": locked.name},
    )
    return Bucket.objects.get(pk=locked.pk)


def retry_delete_bucket(
    *, bucket, actor, bucket_name, confirmed, provider=None, reason=""
):
    _assert_actor(bucket, actor)
    _assert_confirmation(bucket, bucket_name, confirmed)
    with transaction.atomic():
        locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
        if locked.state == Bucket.State.RELEASED:
            return locked
        if locked.state != Bucket.State.DELETION_BLOCKED:
            raise LifecycleError("BUCKET_DELETE_RETRY_NOT_ALLOWED")
        locked.state = Bucket.State.RELEASING
        locked.save(update_fields=("state", "updated_at"))
    return _delete_bucket_cloud(
        locked.pk, provider=provider, actor=actor, reason=reason
    )


def delete_bucket(
    *,
    bucket,
    provider=None,
    actor=None,
    reason="",
    bucket_name=None,
    confirmed=False,
    immediate=False,
):
    """Delete an expired bucket, or perform an explicitly confirmed admin delete."""

    bucket = Bucket.objects.get(pk=bucket.pk)
    if bucket.state == Bucket.State.RELEASED:
        return bucket

    if immediate:
        if not _is_admin(actor):
            raise LifecycleError("ADMIN_REQUIRED")
        if not str(reason or "").strip():
            raise LifecycleError("DELETE_REASON_REQUIRED")
        _assert_confirmation(bucket, bucket_name, confirmed)
        with transaction.atomic():
            locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
            if locked.state == Bucket.State.RELEASED:
                return locked
            locked.state = Bucket.State.RELEASING
            locked.save(update_fields=("state", "updated_at"))
        return _delete_bucket_cloud(
            locked.pk, provider=provider, actor=actor, reason=reason
        )
    if bucket.state != Bucket.State.PENDING_DELETION:
        raise LifecycleError("BUCKET_EXPIRY_NOT_REACHED")
    if not bucket.pending_delete_at or bucket.pending_delete_at > timezone.now():
        raise LifecycleError("BUCKET_EXPIRY_NOT_REACHED")
    return _delete_bucket_cloud(
        bucket.pk, provider=provider, actor=actor, reason=reason
    )


def _delete_bucket_cloud(bucket_id, *, provider=None, actor=None, reason=""):
    bucket = Bucket.objects.select_related(
        "owner", "cloud_identity", "resource_pool"
    ).get(pk=bucket_id)
    if bucket.state == Bucket.State.RELEASED:
        return bucket
    provider = provider or _provider(bucket)
    try:
        ownership = provider.find_owned_bucket(bucket)
        if not ownership.exists:
            result = None
        elif not ownership.owned:
            raise LifecycleError("BUCKET_OWNERSHIP_CONFLICT")
        else:
            inspection = provider.inspect_bucket_emptiness(bucket)
            if not _confirmed_empty(inspection):
                raise LifecycleError("BUCKET_NOT_EMPTY")
            result = provider.delete_owned_bucket(bucket)
    except Exception as error:
        with transaction.atomic():
            locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
            _set_deletion_error(locked, _error_code(error, "BUCKET_DELETE_FAILED"))
        return Bucket.objects.get(pk=bucket.pk)
    with transaction.atomic():
        locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
        locked.state = Bucket.State.RELEASED
        locked.pending_delete_at = None
        locked.deletion_error_code = ""
        locked.deletion_error_summary = ""
        locked.save(
            update_fields=(
                "state",
                "pending_delete_at",
                "deletion_error_code",
                "deletion_error_summary",
                "updated_at",
            )
        )
    record_audit_event(
        actor=actor,
        action="storage.bucket.delete",
        target_type="Bucket",
        target_id=bucket.pk,
        result="succeeded",
        reason=reason,
        safe_metadata={"bucket_name": bucket.name},
    )
    return Bucket.objects.get(pk=bucket.pk)


def _configuration_from_desired(desired):
    try:
        return BucketConfiguration.from_snapshot(desired)
    except (AttributeError, TypeError, ValueError) as error:
        raise BucketConfigurationError(str(error)) from error


def _configuration_from_applied(applied):
    if not applied:
        return None
    return _configuration_from_desired(applied)


def update_bucket_configuration(
    *,
    bucket,
    actor,
    desired,
    provider=None,
    enqueue=True,
    reason="",
    bucket_name=None,
    confirmed=False,
):
    if not _is_admin(actor):
        raise BucketConfigurationError("ADMIN_REQUIRED")
    if desired.get("acl") == "public_read":
        if not str(reason or "").strip():
            raise BucketConfigurationError("CONFIG_REASON_REQUIRED")
        _assert_confirmation(bucket, bucket_name, confirmed)
    configuration = _configuration_from_desired(desired)
    snapshot = configuration.as_snapshot()
    with transaction.atomic():
        locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
        locked.desired_config_snapshot = snapshot
        locked.config_state = Bucket.ConfigurationState.PENDING
        locked.config_error_code = ""
        locked.config_error_summary = ""
        locked.save(
            update_fields=(
                "desired_config_snapshot",
                "config_state",
                "config_error_code",
                "config_error_summary",
                "updated_at",
            )
        )
    if enqueue:
        from object_storage.tasks import update_bucket_configuration_task

        update_bucket_configuration_task.delay(
            bucket.pk,
            actor_id=getattr(actor, "pk", None),
            reason=reason,
        )
        return locked
    return _apply_bucket_configuration(
        bucket.pk, provider=provider, actor=actor, reason=reason
    )


def _apply_bucket_configuration(bucket_id, *, provider=None, actor=None, reason=""):
    bucket = Bucket.objects.select_related("resource_pool").get(pk=bucket_id)
    desired = bucket.desired_config_snapshot
    configuration = _configuration_from_desired(desired)
    previous_configuration = _configuration_from_applied(bucket.applied_config_snapshot)
    provider = provider or _provider(bucket)
    try:
        provider.update_bucket_configuration(
            bucket,
            configuration,
            previous_configuration=previous_configuration,
            allow_public_read=(configuration.acl == "public_read" and _is_admin(actor)),
        )
    except Exception as error:
        error_code = str(
            getattr(error, "error_code", "") or "BUCKET_CONFIGURATION_UPDATE_FAILED"
        )
        with transaction.atomic():
            locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
            locked.config_error_code = error_code
            locked.config_error_summary = str(error)[:255]
            locked.config_state = (
                Bucket.ConfigurationState.UNKNOWN
                if error_code == "BUCKET_CONFIGURATION_ROLLBACK_FAILED"
                else Bucket.ConfigurationState.RETRYABLE_ERROR
            )
            locked.save(
                update_fields=(
                    "config_error_code",
                    "config_error_summary",
                    "config_state",
                    "updated_at",
                )
            )
        raise BucketConfigurationError(error_code) from error
    with transaction.atomic():
        locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
        locked.applied_config_snapshot = desired
        locked.config_state = Bucket.ConfigurationState.APPLIED
        locked.config_error_code = ""
        locked.config_error_summary = ""
        locked.save(
            update_fields=(
                "applied_config_snapshot",
                "config_state",
                "config_error_code",
                "config_error_summary",
                "updated_at",
            )
        )
    record_audit_event(
        actor=actor,
        action="storage.bucket.configuration.updated",
        target_type="Bucket",
        target_id=bucket.pk,
        result="succeeded",
        reason=reason,
        safe_metadata={"bucket_name": bucket.name},
    )
    return Bucket.objects.get(pk=bucket.pk)


def retry_bucket_configuration(
    *,
    bucket,
    actor,
    provider=None,
    enqueue=True,
    reason="",
    bucket_name=None,
    confirmed=False,
):
    if not _is_admin(actor):
        raise BucketConfigurationError("ADMIN_REQUIRED")
    desired = bucket.desired_config_snapshot
    return update_bucket_configuration(
        bucket=bucket,
        actor=actor,
        desired=desired,
        provider=provider,
        enqueue=enqueue,
        reason=reason,
        bucket_name=bucket_name or bucket.name,
        confirmed=confirmed,
    )


def suspend_user_resources(*, user, actor, provider=None, enqueue=True, reason=""):
    if not _is_admin(actor):
        raise LifecycleError("ADMIN_REQUIRED")
    identity = CloudIdentity.objects.get(user=user)
    identity.state = CloudIdentity.State.SUSPENDED
    identity.save(update_fields=("state", "updated_at"))
    if enqueue:
        from object_storage.tasks import suspend_user_resources_task

        suspend_user_resources_task.delay(
            identity.pk,
            actor_id=getattr(actor, "pk", None),
            reason=reason,
        )
        return identity
    return _disable_identity_keys(
        identity.pk, provider=provider, actor=actor, reason=reason
    )


def reactivate_user_resources(*, user, actor, reason=""):
    if not _is_admin(actor):
        raise LifecycleError("ADMIN_REQUIRED")
    identity = CloudIdentity.objects.get(user=user)
    identity.state = CloudIdentity.State.ACTIVE
    identity.save(update_fields=("state", "updated_at"))
    record_audit_event(
        actor=actor,
        action="storage.user.reactivated",
        target_type="CloudIdentity",
        target_id=identity.pk,
        result="succeeded",
        reason=reason,
        safe_metadata={"user_id": identity.user_id},
    )
    return identity


def _disable_identity_keys(identity_id, *, provider=None, actor=None, reason=""):
    identity = CloudIdentity.objects.get(pk=identity_id)
    if provider is None:
        from object_storage.providers.aliyun import build_aliyun_provider

        provider = build_aliyun_provider(identity.resource_pool)
    for key in identity.access_keys.filter(
        local_state__in=(
            AccessKey.LocalState.ISSUING,
            AccessKey.LocalState.DELIVERY_READY,
            AccessKey.LocalState.ACTIVE,
        ),
        deleted_at__isnull=True,
    ).order_by("pk"):
        from object_storage.services.credentials import provider_access_key

        provider.deactivate_access_key(provider_access_key(key))
        key.cloud_state = AccessKey.CloudState.INACTIVE
        key.local_state = AccessKey.LocalState.DISABLED
        key.deactivated_at = timezone.now()
        key.save(
            update_fields=(
                "cloud_state",
                "local_state",
                "deactivated_at",
                "updated_at",
            )
        )
    record_audit_event(
        actor=actor,
        action="storage.user.suspended",
        target_type="CloudIdentity",
        target_id=identity.pk,
        result="succeeded",
        reason=reason,
        safe_metadata={"user_id": identity.user_id},
    )
    return identity
