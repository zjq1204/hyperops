"""Bucket and object-storage user lifecycle actions.

Database state changes are kept separate from provider calls so every cloud
mutation can be retried by a Celery task without repeating an unsafe action.
"""

from datetime import timedelta
import uuid

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
OPERATION_LEASE_SECONDS = 300
UNCERTAIN_MUTATION_ERROR = "CLOUD_MUTATION_OUTCOME_UNKNOWN"
MANUAL_RECONCILIATION_ERROR = "MANUAL_RECONCILIATION_REQUIRED"


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


def recover_expired_bucket_configuration_claim(bucket_id, *, provider=None, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        bucket = (
            Bucket.objects.select_for_update()
            .select_related("resource_pool")
            .get(pk=bucket_id)
        )
        if not (
            bucket.configuration_operation_token
            and bucket.configuration_operation_lease_until
            and bucket.configuration_operation_lease_until <= now
        ):
            return bucket
        token = bucket.configuration_operation_token
        claim_generation = bucket.configuration_claim_generation
    selected_provider = provider or _provider(bucket)
    observed = {}
    try:
        result = selected_provider.get_bucket_configuration(bucket)
        observed = (
            result.as_snapshot() if hasattr(result, "as_snapshot") else dict(result)
        )
    except Exception:
        pass
    with transaction.atomic():
        locked = Bucket.objects.select_for_update().get(pk=bucket_id)
        if not (
            locked.configuration_operation_token == token
            and locked.configuration_claim_generation == claim_generation
            and locked.configuration_operation_lease_until
            and locked.configuration_operation_lease_until <= now
        ):
            return locked
        locked.config_state = Bucket.ConfigurationState.UNKNOWN
        locked.config_error_code = UNCERTAIN_MUTATION_ERROR
        locked.config_error_summary = locked.config_error_code
        locked.configuration_observed_snapshot = observed
        locked.save(
            update_fields=(
                "config_state",
                "config_error_code",
                "config_error_summary",
                "configuration_observed_snapshot",
                "updated_at",
            )
        )
        return locked


def recover_expired_bucket_action_claim(bucket_id, *, provider=None, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        bucket = (
            Bucket.objects.select_for_update()
            .select_related("resource_pool")
            .get(pk=bucket_id)
        )
        if not (
            bucket.action_owner_token
            and bucket.action_lease_until
            and bucket.action_lease_until <= now
        ):
            return bucket
        token = bucket.action_owner_token
        generation = bucket.action_generation
        action_type = bucket.action_type
    selected_provider = provider or _provider(bucket)
    exists = owned = ownership_known = False
    inspection_observed = {}
    try:
        ownership = selected_provider.find_owned_bucket(bucket)
        if isinstance(ownership, bool):
            exists = owned = ownership
        else:
            exists = bool(ownership.exists)
            owned = bool(ownership.owned)
        ownership_known = True
        if exists and owned:
            inspection = selected_provider.inspect_bucket_emptiness(bucket)
            inspection_observed = {
                field: int(getattr(inspection, field, 0) or 0)
                for field in (
                    "object_count",
                    "version_count",
                    "delete_marker_count",
                    "multipart_upload_count",
                )
            }
    except Exception:
        pass
    with transaction.atomic():
        locked = Bucket.objects.select_for_update().get(pk=bucket_id)
        if not (
            _action_claim_owned(locked, generation, token, action_type)
            and locked.action_lease_until
            and locked.action_lease_until <= now
        ):
            return locked
        locked.state = Bucket.State.DELETION_BLOCKED
        locked.deletion_error_code = UNCERTAIN_MUTATION_ERROR
        locked.deletion_error_summary = locked.deletion_error_code
        locked.action_observed_snapshot = {
            "exists": exists,
            "owned": owned,
            "ownership_known": ownership_known,
            **inspection_observed,
        }
        locked.save(
            update_fields=(
                "state",
                "pending_delete_at",
                "deletion_error_code",
                "deletion_error_summary",
                "action_observed_snapshot",
                "action_owner_token",
                "action_type",
                "action_acquired_at",
                "action_lease_until",
                "updated_at",
            )
        )
        return locked


def _assert_manual_reconciliation_actor(actor, reason):
    if not _is_admin(actor):
        raise LifecycleError("ADMIN_REQUIRED")
    if not str(reason or "").strip():
        raise LifecycleError("RECONCILIATION_REASON_REQUIRED")


def reconcile_bucket_configuration_uncertainty(
    *, bucket, actor, provider=None, reason=""
):
    """Read cloud configuration and retain the frozen operation claim."""

    _assert_manual_reconciliation_actor(actor, reason)
    with transaction.atomic():
        locked = (
            Bucket.objects.select_for_update()
            .select_related("resource_pool")
            .get(pk=bucket.pk)
        )
        if not (
            locked.configuration_operation_token
            and locked.config_state == Bucket.ConfigurationState.UNKNOWN
            and locked.config_error_code == UNCERTAIN_MUTATION_ERROR
        ):
            raise BucketConfigurationError("BUCKET_CONFIGURATION_NOT_FROZEN")
        token = locked.configuration_operation_token
        desired = dict(locked.desired_config_snapshot)
        applied = dict(locked.applied_config_snapshot)
    selected_provider = provider or _provider(locked)
    observed_result = selected_provider.get_bucket_configuration(locked)
    observed = (
        observed_result.as_snapshot()
        if hasattr(observed_result, "as_snapshot")
        else dict(observed_result)
    )
    with transaction.atomic():
        current = Bucket.objects.select_for_update().get(pk=locked.pk)
        if not (
            current.configuration_operation_token == token
            and current.config_error_code == UNCERTAIN_MUTATION_ERROR
        ):
            return current
        current.configuration_observed_snapshot = observed
        current.save(
            update_fields=(
                "configuration_observed_snapshot",
                "updated_at",
            )
        )
    record_audit_event(
        actor=actor,
        action="storage.bucket.configuration.reconciled",
        target_type="Bucket",
        target_id=locked.pk,
        result="observed",
        reason=reason,
        safe_metadata={"bucket_name": locked.name},
    )
    return Bucket.objects.get(pk=locked.pk)


def acknowledge_bucket_configuration_uncertainty(
    *,
    bucket,
    actor,
    reason,
    bucket_name,
    operation_type,
    operation_generation,
    operation_token,
    resolution,
):
    """Resolve a frozen configuration after external administrator verification."""

    _assert_manual_reconciliation_actor(actor, reason)
    _assert_confirmation(bucket, bucket_name, True)
    if operation_type != "configuration":
        raise BucketConfigurationError("RESOURCE_OPERATION_CONFIRMATION_MISMATCH")
    if resolution not in {"desired", "applied", "unknown"}:
        raise BucketConfigurationError("BUCKET_CONFIGURATION_RESOLUTION_INVALID")
    with transaction.atomic():
        locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
        if not (
            locked.configuration_operation_token
            and locked.config_error_code == UNCERTAIN_MUTATION_ERROR
            and locked.configuration_generation == operation_generation
            and locked.configuration_operation_token == operation_token
        ):
            raise BucketConfigurationError("RESOURCE_OPERATION_CONFIRMATION_MISMATCH")
        if resolution == "unknown":
            raise BucketConfigurationError("MANUAL_RECONCILIATION_REQUIRED")
        snapshot = (
            _configuration_from_desired(locked.desired_config_snapshot).as_snapshot()
            if resolution == "desired"
            else (
                _configuration_from_applied(
                    locked.applied_config_snapshot
                ).as_snapshot()
                if locked.applied_config_snapshot
                else None
            )
        )
        if snapshot is None:
            raise BucketConfigurationError("BUCKET_CONFIGURATION_RESOLUTION_INVALID")
        locked.applied_config_snapshot = snapshot
        locked.config_state = (
            Bucket.ConfigurationState.APPLIED
            if resolution == "desired"
            else Bucket.ConfigurationState.RETRYABLE_ERROR
        )
        locked.config_error_code = ""
        locked.config_error_summary = ""
        locked.configuration_operation_token = ""
        locked.configuration_operation_acquired_at = None
        locked.configuration_operation_lease_until = None
        locked.save(
            update_fields=(
                "applied_config_snapshot",
                "config_state",
                "config_error_code",
                "config_error_summary",
                "configuration_operation_token",
                "configuration_operation_acquired_at",
                "configuration_operation_lease_until",
                "updated_at",
            )
        )
    record_audit_event(
        actor=actor,
        action="storage.bucket.configuration.acknowledged",
        target_type="Bucket",
        target_id=locked.pk,
        result="succeeded",
        reason=reason,
        safe_metadata={"bucket_name": locked.name, "status": resolution},
    )
    return Bucket.objects.get(pk=locked.pk)


def reconcile_bucket_action_uncertainty(*, bucket, actor, provider=None, reason=""):
    """Read ownership/emptiness and retain the frozen action claim."""

    _assert_manual_reconciliation_actor(actor, reason)
    with transaction.atomic():
        locked = (
            Bucket.objects.select_for_update()
            .select_related("resource_pool")
            .get(pk=bucket.pk)
        )
        if not (
            locked.action_owner_token
            and locked.deletion_error_code == UNCERTAIN_MUTATION_ERROR
        ):
            raise LifecycleError("BUCKET_ACTION_NOT_FROZEN")
        token = locked.action_owner_token
    selected_provider = provider or _provider(locked)
    ownership = selected_provider.find_owned_bucket(locked)
    exists = bool(ownership if isinstance(ownership, bool) else ownership.exists)
    observed = {
        "exists": exists,
        "owned": bool(ownership if isinstance(ownership, bool) else ownership.owned),
    }
    if exists:
        owned = observed["owned"]
        if owned:
            inspection = selected_provider.inspect_bucket_emptiness(locked)
            observed.update(
                {
                    field: int(getattr(inspection, field, 0) or 0)
                    for field in (
                        "object_count",
                        "version_count",
                        "delete_marker_count",
                        "multipart_upload_count",
                    )
                }
            )
    with transaction.atomic():
        current = Bucket.objects.select_for_update().get(pk=locked.pk)
        if not (
            current.action_owner_token == token
            and current.deletion_error_code == UNCERTAIN_MUTATION_ERROR
        ):
            return current
        current.action_observed_snapshot = observed
        current.save(
            update_fields=(
                "action_observed_snapshot",
                "updated_at",
            )
        )
    record_audit_event(
        actor=actor,
        action="storage.bucket.action.reconciled",
        target_type="Bucket",
        target_id=locked.pk,
        result="observed",
        reason=reason,
        safe_metadata={"bucket_name": locked.name, "status": "observed"},
    )
    return Bucket.objects.get(pk=locked.pk)


def acknowledge_bucket_action_uncertainty(
    *,
    bucket,
    actor,
    reason,
    bucket_name,
    operation_type,
    operation_generation,
    operation_token,
    resolved_state,
):
    """Resolve a frozen lifecycle action after external cloud verification."""

    _assert_manual_reconciliation_actor(actor, reason)
    _assert_confirmation(bucket, bucket_name, True)
    if resolved_state not in {
        Bucket.State.ACTIVE,
        Bucket.State.PENDING_DELETION,
        Bucket.State.DELETION_BLOCKED,
        Bucket.State.RELEASED,
    }:
        raise LifecycleError("BUCKET_ACTION_RESOLUTION_INVALID")
    with transaction.atomic():
        locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
        if not (
            locked.action_owner_token
            and locked.deletion_error_code == UNCERTAIN_MUTATION_ERROR
            and locked.action_type == operation_type
            and locked.action_generation == operation_generation
            and locked.action_owner_token == operation_token
        ):
            raise LifecycleError("RESOURCE_OPERATION_CONFIRMATION_MISMATCH")
        locked.state = resolved_state
        if resolved_state == Bucket.State.RELEASED:
            locked.pending_delete_at = None
        locked.deletion_error_code = ""
        locked.deletion_error_summary = ""
        _clear_action_claim(locked)
        locked.save(
            update_fields=(
                "state",
                "pending_delete_at",
                "deletion_error_code",
                "deletion_error_summary",
                "action_owner_token",
                "action_type",
                "action_acquired_at",
                "action_lease_until",
                "updated_at",
            )
        )
    record_audit_event(
        actor=actor,
        action="storage.bucket.action.acknowledged",
        target_type="Bucket",
        target_id=locked.pk,
        result="succeeded",
        reason=reason,
        safe_metadata={"bucket_name": locked.name, "status": resolved_state},
    )
    return Bucket.objects.get(pk=locked.pk)


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


def _action_claim_owned(bucket, generation, owner_token, action_type):
    return bool(
        bucket.action_generation == generation
        and bucket.action_owner_token == owner_token
        and bucket.action_type == action_type
    )


def _action_matches(bucket, generation, owner_token, action_type):
    return bool(
        _action_claim_owned(bucket, generation, owner_token, action_type)
        and bucket.deletion_error_code != UNCERTAIN_MUTATION_ERROR
        and bucket.action_lease_until
        and bucket.action_lease_until > timezone.now()
    )


def _claim_bucket_action(
    bucket_id,
    *,
    action_type,
    allowed_states,
    transition_state=None,
    error_code,
):
    with transaction.atomic():
        locked = (
            Bucket.objects.select_for_update()
            .select_related("owner", "cloud_identity", "resource_pool")
            .get(pk=bucket_id)
        )
        if locked.deletion_error_code == UNCERTAIN_MUTATION_ERROR:
            raise LifecycleError(MANUAL_RECONCILIATION_ERROR)
        if locked.action_owner_token:
            if not locked.action_lease_until or (
                locked.action_lease_until <= timezone.now()
            ):
                raise LifecycleError(MANUAL_RECONCILIATION_ERROR)
            if locked.action_type == action_type:
                return (
                    locked,
                    locked.action_generation,
                    locked.action_owner_token,
                    False,
                )
            raise LifecycleError("RESOURCE_OPERATION_IN_PROGRESS")
        if locked.state not in allowed_states:
            raise LifecycleError(error_code)
        now = timezone.now()
        locked.action_generation += 1
        locked.action_owner_token = uuid.uuid4().hex
        locked.action_type = action_type
        locked.action_acquired_at = now
        locked.action_lease_until = now + timedelta(seconds=OPERATION_LEASE_SECONDS)
        update_fields = [
            "action_generation",
            "action_owner_token",
            "action_type",
            "action_acquired_at",
            "action_lease_until",
            "updated_at",
        ]
        if transition_state is not None:
            locked.state = transition_state
            update_fields.append("state")
        locked.save(update_fields=tuple(update_fields))
        return (
            locked,
            locked.action_generation,
            locked.action_owner_token,
            True,
        )


def _clear_action_claim(bucket):
    bucket.action_owner_token = ""
    bucket.action_type = ""
    bucket.action_acquired_at = None
    bucket.action_lease_until = None


def _freeze_bucket_action_failure(
    bucket_id, *, action_generation, owner_token, action_type
):
    """Record an unknown cloud mutation while retaining its action claim."""

    with transaction.atomic():
        locked = Bucket.objects.select_for_update().get(pk=bucket_id)
        if not _action_claim_owned(locked, action_generation, owner_token, action_type):
            return locked
        locked.state = Bucket.State.DELETION_BLOCKED
        locked.deletion_error_code = UNCERTAIN_MUTATION_ERROR
        locked.deletion_error_summary = UNCERTAIN_MUTATION_ERROR
        locked.save(
            update_fields=(
                "state",
                "deletion_error_code",
                "deletion_error_summary",
                "updated_at",
            )
        )
        return locked


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
    current = Bucket.objects.get(pk=bucket.pk)
    if current.state in (Bucket.State.PENDING_DELETION, Bucket.State.RELEASED):
        return current
    locked, generation, owner_token, claimed = _claim_bucket_action(
        bucket.pk,
        action_type="release",
        allowed_states=(Bucket.State.ACTIVE, Bucket.State.DELETION_BLOCKED),
        transition_state=Bucket.State.RELEASING,
        error_code="BUCKET_RELEASE_NOT_ALLOWED",
    )
    if not claimed:
        return locked
    if enqueue:
        from object_storage.tasks import release_bucket_task

        release_bucket_task.delay(
            locked.pk,
            actor_id=getattr(actor, "pk", None),
            reason=reason,
            action_generation=generation,
            owner_token=owner_token,
        )
        return locked
    return _release_bucket_cloud(
        locked.pk,
        action_generation=generation,
        owner_token=owner_token,
        provider=provider,
        actor=actor,
        reason=reason,
    )


def _release_bucket_cloud(
    bucket_id,
    *,
    action_generation,
    owner_token,
    provider=None,
    actor=None,
    reason="",
):
    bucket = Bucket.objects.select_related(
        "owner", "cloud_identity", "resource_pool"
    ).get(pk=bucket_id)
    if not _action_matches(bucket, action_generation, owner_token, "release"):
        return bucket
    if bucket.action_lease_until and bucket.action_lease_until <= timezone.now():
        return recover_expired_bucket_action_claim(
            bucket_id, provider=provider or _provider(bucket)
        )
    with transaction.atomic():
        locked = Bucket.objects.select_for_update().get(pk=bucket_id)
        if not _action_matches(locked, action_generation, owner_token, "release"):
            return locked
        owner_token = uuid.uuid4().hex
        locked.action_owner_token = owner_token
        locked.action_lease_until = timezone.now() + timedelta(
            seconds=OPERATION_LEASE_SECONDS
        )
        locked.save(
            update_fields=(
                "action_owner_token",
                "action_lease_until",
                "updated_at",
            )
        )
    bucket.action_owner_token = owner_token
    provider = provider or _provider(bucket)
    try:
        inspection = provider.inspect_bucket_emptiness(bucket)
    except Exception as error:
        with transaction.atomic():
            locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
            if not _action_matches(locked, action_generation, owner_token, "release"):
                raise
            _set_deletion_error(locked, _error_code(error, "BUCKET_EMPTY_CHECK_FAILED"))
            _clear_action_claim(locked)
            locked.save(
                update_fields=(
                    "action_owner_token",
                    "action_type",
                    "action_acquired_at",
                    "action_lease_until",
                    "updated_at",
                )
            )
        raise
    if not _confirmed_empty(inspection):
        with transaction.atomic():
            locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
            if not _action_matches(locked, action_generation, owner_token, "release"):
                raise LifecycleError("BUCKET_NOT_EMPTY")
            locked.state = Bucket.State.ACTIVE
            locked.deletion_error_code = "BUCKET_NOT_EMPTY"
            locked.deletion_error_summary = "BUCKET_NOT_EMPTY"
            _clear_action_claim(locked)
            locked.save(
                update_fields=(
                    "state",
                    "deletion_error_code",
                    "deletion_error_summary",
                    "action_owner_token",
                    "action_type",
                    "action_acquired_at",
                    "action_lease_until",
                    "updated_at",
                )
            )
        raise LifecycleError("BUCKET_NOT_EMPTY")

    current = Bucket.objects.get(pk=bucket.pk)
    if not _action_matches(current, action_generation, owner_token, "release"):
        return current

    try:
        _reconcile_policy(bucket, provider)
    except Exception:
        _freeze_bucket_action_failure(
            bucket.pk,
            action_generation=action_generation,
            owner_token=owner_token,
            action_type="release",
        )
        raise
    pending_delete_at = timezone.now() + timedelta(days=RETENTION_DAYS)
    with transaction.atomic():
        locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
        if not _action_matches(locked, action_generation, owner_token, "release"):
            return locked
        locked.state = Bucket.State.PENDING_DELETION
        locked.pending_delete_at = pending_delete_at
        locked.deletion_error_code = ""
        locked.deletion_error_summary = ""
        _clear_action_claim(locked)
        locked.save(
            update_fields=(
                "state",
                "pending_delete_at",
                "deletion_error_code",
                "deletion_error_summary",
                "action_owner_token",
                "action_type",
                "action_acquired_at",
                "action_lease_until",
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
        locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
        if locked.deletion_error_code == UNCERTAIN_MUTATION_ERROR:
            raise LifecycleError(MANUAL_RECONCILIATION_ERROR)
        if locked.action_owner_token:
            if not locked.action_lease_until or (
                locked.action_lease_until <= timezone.now()
            ):
                raise LifecycleError(MANUAL_RECONCILIATION_ERROR)
            if locked.action_type == "recover":
                return locked
            raise LifecycleError("RESOURCE_OPERATION_IN_PROGRESS")
        if locked.state != Bucket.State.PENDING_DELETION:
            raise LifecycleError("BUCKET_RECOVERY_NOT_ALLOWED")
        if not locked.pending_delete_at or locked.pending_delete_at <= timezone.now():
            raise LifecycleError("BUCKET_RECOVERY_WINDOW_EXPIRED")
        user = get_user_model().objects.select_for_update().get(pk=locked.owner_id)
        try:
            check_bucket_capacity(user)
        except BucketQuotaExceeded as error:
            raise LifecycleError("BUCKET_QUOTA_EXCEEDED") from error
        now = timezone.now()
        locked.action_generation += 1
        locked.action_owner_token = uuid.uuid4().hex
        locked.action_type = "recover"
        locked.action_acquired_at = now
        locked.action_lease_until = now + timedelta(seconds=OPERATION_LEASE_SECONDS)
        locked.save(
            update_fields=(
                "action_generation",
                "action_owner_token",
                "action_type",
                "action_acquired_at",
                "action_lease_until",
                "updated_at",
            )
        )
        generation = locked.action_generation
        owner_token = locked.action_owner_token
    with transaction.atomic():
        current = Bucket.objects.select_for_update().get(pk=locked.pk)
        if not _action_matches(current, generation, owner_token, "recover"):
            return current
        current.deletion_error_code = ""
        current.deletion_error_summary = ""
        current.save(
            update_fields=(
                "deletion_error_code",
                "deletion_error_summary",
                "updated_at",
            )
        )
    locked = Bucket.objects.select_related("cloud_identity", "resource_pool").get(
        pk=bucket.pk
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
        _freeze_bucket_action_failure(
            locked.pk,
            action_generation=generation,
            owner_token=owner_token,
            action_type="recover",
        )
        raise
    with transaction.atomic():
        current = Bucket.objects.select_for_update().get(pk=locked.pk)
        if not _action_matches(current, generation, owner_token, "recover"):
            return current
        current.state = Bucket.State.ACTIVE
        current.pending_delete_at = None
        _clear_action_claim(current)
        current.save(
            update_fields=(
                "state",
                "pending_delete_at",
                "action_owner_token",
                "action_type",
                "action_acquired_at",
                "action_lease_until",
                "updated_at",
            )
        )
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
    current = Bucket.objects.get(pk=bucket.pk)
    if current.state == Bucket.State.RELEASED:
        return current
    locked, generation, owner_token, claimed = _claim_bucket_action(
        bucket.pk,
        action_type="retry_delete",
        allowed_states=(Bucket.State.DELETION_BLOCKED,),
        transition_state=Bucket.State.RELEASING,
        error_code="BUCKET_DELETE_RETRY_NOT_ALLOWED",
    )
    if not claimed:
        return locked
    return _delete_bucket_cloud(
        locked.pk,
        action_generation=generation,
        owner_token=owner_token,
        action_type="retry_delete",
        provider=provider,
        actor=actor,
        reason=reason,
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
        locked, generation, owner_token, claimed = _claim_bucket_action(
            bucket.pk,
            action_type="delete",
            allowed_states=tuple(
                state
                for state, _label in Bucket.State.choices
                if state != Bucket.State.RELEASED
            ),
            transition_state=Bucket.State.RELEASING,
            error_code="BUCKET_DELETE_NOT_ALLOWED",
        )
        if not claimed:
            return locked
        return _delete_bucket_cloud(
            locked.pk,
            action_generation=generation,
            owner_token=owner_token,
            action_type="delete",
            provider=provider,
            actor=actor,
            reason=reason,
        )
    if bucket.state != Bucket.State.PENDING_DELETION:
        raise LifecycleError("BUCKET_EXPIRY_NOT_REACHED")
    if not bucket.pending_delete_at or bucket.pending_delete_at > timezone.now():
        raise LifecycleError("BUCKET_EXPIRY_NOT_REACHED")
    locked, generation, owner_token, claimed = _claim_bucket_action(
        bucket.pk,
        action_type="delete",
        allowed_states=(Bucket.State.PENDING_DELETION,),
        transition_state=Bucket.State.RELEASING,
        error_code="BUCKET_EXPIRY_NOT_REACHED",
    )
    if not claimed:
        return locked
    return _delete_bucket_cloud(
        locked.pk,
        action_generation=generation,
        owner_token=owner_token,
        action_type="delete",
        provider=provider,
        actor=actor,
        reason=reason,
    )


def _delete_bucket_cloud(
    bucket_id,
    *,
    action_generation,
    owner_token,
    action_type,
    provider=None,
    actor=None,
    reason="",
):
    bucket = Bucket.objects.select_related(
        "owner", "cloud_identity", "resource_pool"
    ).get(pk=bucket_id)
    if not _action_matches(bucket, action_generation, owner_token, action_type):
        return bucket
    if bucket.action_lease_until and bucket.action_lease_until <= timezone.now():
        return recover_expired_bucket_action_claim(
            bucket_id, provider=provider or _provider(bucket)
        )
    with transaction.atomic():
        locked = Bucket.objects.select_for_update().get(pk=bucket_id)
        if not _action_matches(locked, action_generation, owner_token, action_type):
            return locked
        owner_token = uuid.uuid4().hex
        locked.action_owner_token = owner_token
        locked.action_lease_until = timezone.now() + timedelta(
            seconds=OPERATION_LEASE_SECONDS
        )
        locked.save(
            update_fields=(
                "action_owner_token",
                "action_lease_until",
                "updated_at",
            )
        )
    bucket.action_owner_token = owner_token
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
            try:
                result = provider.delete_owned_bucket(bucket)
            except Exception:
                _freeze_bucket_action_failure(
                    bucket.pk,
                    action_generation=action_generation,
                    owner_token=owner_token,
                    action_type=action_type,
                )
                return Bucket.objects.get(pk=bucket.pk)
    except Exception as error:
        with transaction.atomic():
            locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
            if not _action_matches(locked, action_generation, owner_token, action_type):
                return locked
            _set_deletion_error(locked, _error_code(error, "BUCKET_DELETE_FAILED"))
            _clear_action_claim(locked)
            locked.save(
                update_fields=(
                    "action_owner_token",
                    "action_type",
                    "action_acquired_at",
                    "action_lease_until",
                    "updated_at",
                )
            )
        return Bucket.objects.get(pk=bucket.pk)
    with transaction.atomic():
        locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
        if not _action_matches(locked, action_generation, owner_token, action_type):
            return locked
        locked.state = Bucket.State.RELEASED
        locked.pending_delete_at = None
        locked.deletion_error_code = ""
        locked.deletion_error_summary = ""
        _clear_action_claim(locked)
        locked.save(
            update_fields=(
                "state",
                "pending_delete_at",
                "deletion_error_code",
                "deletion_error_summary",
                "action_owner_token",
                "action_type",
                "action_acquired_at",
                "action_lease_until",
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
    _retry=False,
):
    if not _is_admin(actor):
        raise BucketConfigurationError("ADMIN_REQUIRED")
    with transaction.atomic():
        locked = Bucket.objects.select_for_update().get(pk=bucket.pk)
        if locked.config_error_code == UNCERTAIN_MUTATION_ERROR:
            raise BucketConfigurationError(MANUAL_RECONCILIATION_ERROR)
        if locked.configuration_operation_token and (
            not locked.configuration_operation_lease_until
            or locked.configuration_operation_lease_until <= timezone.now()
        ):
            raise BucketConfigurationError(MANUAL_RECONCILIATION_ERROR)
        if _retry:
            if locked.config_state == Bucket.ConfigurationState.UNKNOWN:
                raise BucketConfigurationError("BUCKET_CONFIGURATION_STATE_UNKNOWN")
            if locked.config_state not in {
                Bucket.ConfigurationState.PENDING,
                Bucket.ConfigurationState.RETRYABLE_ERROR,
            }:
                raise BucketConfigurationError("BUCKET_CONFIGURATION_RETRY_NOT_ALLOWED")
            desired = locked.desired_config_snapshot
        if desired.get("acl") == "public_read":
            if not str(reason or "").strip():
                raise BucketConfigurationError("CONFIG_REASON_REQUIRED")
            _assert_confirmation(locked, bucket_name, confirmed)
        configuration = _configuration_from_desired(desired)
        snapshot = configuration.as_snapshot()
        locked.desired_config_snapshot = snapshot
        locked.config_state = Bucket.ConfigurationState.PENDING
        locked.config_error_code = ""
        locked.config_error_summary = ""
        locked.configuration_generation += 1
        claim_active = bool(locked.configuration_operation_token)
        if not claim_active:
            now = timezone.now()
            locked.configuration_operation_token = uuid.uuid4().hex
            locked.configuration_claim_generation = locked.configuration_generation
            locked.configuration_operation_acquired_at = now
            locked.configuration_operation_lease_until = now + timedelta(
                seconds=OPERATION_LEASE_SECONDS
            )
        locked.save(
            update_fields=(
                "desired_config_snapshot",
                "config_state",
                "config_error_code",
                "config_error_summary",
                "configuration_generation",
                "configuration_operation_token",
                "configuration_claim_generation",
                "configuration_operation_acquired_at",
                "configuration_operation_lease_until",
                "updated_at",
            )
        )
        configuration_generation = locked.configuration_claim_generation
        operation_token = locked.configuration_operation_token
    if claim_active:
        return locked
    if enqueue:
        from object_storage.tasks import update_bucket_configuration_task

        update_bucket_configuration_task.delay(
            bucket.pk,
            actor_id=getattr(actor, "pk", None),
            reason=reason,
            configuration_generation=configuration_generation,
            operation_token=operation_token,
        )
        return locked
    return _apply_bucket_configuration(
        bucket.pk,
        configuration_generation=configuration_generation,
        operation_token=operation_token,
        provider=provider,
        actor=actor,
        reason=reason,
    )


def _apply_bucket_configuration(
    bucket_id,
    *,
    configuration_generation,
    operation_token,
    provider=None,
    actor=None,
    reason="",
):
    initial = Bucket.objects.select_related("resource_pool").get(pk=bucket_id)
    if (
        initial.configuration_operation_token == operation_token
        and initial.configuration_claim_generation == configuration_generation
        and initial.config_error_code != UNCERTAIN_MUTATION_ERROR
        and initial.configuration_operation_lease_until
        and initial.configuration_operation_lease_until <= timezone.now()
    ):
        return recover_expired_bucket_configuration_claim(
            bucket_id,
            provider=provider or _provider(initial),
        )
    with transaction.atomic():
        locked = Bucket.objects.select_for_update().get(pk=bucket_id)
        if not (
            locked.configuration_operation_token == operation_token
            and locked.configuration_claim_generation == configuration_generation
            and locked.config_error_code != UNCERTAIN_MUTATION_ERROR
            and locked.configuration_operation_lease_until
            and locked.configuration_operation_lease_until > timezone.now()
        ):
            return locked
        operation_token = uuid.uuid4().hex
        locked.configuration_operation_token = operation_token
        locked.configuration_operation_lease_until = timezone.now() + timedelta(
            seconds=OPERATION_LEASE_SECONDS
        )
        locked.save(
            update_fields=(
                "configuration_operation_token",
                "configuration_operation_lease_until",
                "updated_at",
            )
        )
    first_iteration = True
    while True:
        with transaction.atomic():
            locked = (
                Bucket.objects.select_for_update()
                .select_related("resource_pool")
                .get(pk=bucket_id)
            )
            if not (
                locked.configuration_operation_token == operation_token
                and locked.config_error_code != UNCERTAIN_MUTATION_ERROR
                and locked.configuration_operation_lease_until
                and locked.configuration_operation_lease_until > timezone.now()
                and (
                    not first_iteration
                    or locked.configuration_claim_generation == configuration_generation
                )
            ):
                return locked
            target_generation = locked.configuration_generation
            desired = dict(locked.desired_config_snapshot)
            applied = dict(locked.applied_config_snapshot)
            now = timezone.now()
            locked.configuration_claim_generation = target_generation
            locked.configuration_operation_lease_until = now + timedelta(
                seconds=OPERATION_LEASE_SECONDS
            )
            locked.save(
                update_fields=(
                    "configuration_claim_generation",
                    "configuration_operation_lease_until",
                    "updated_at",
                )
            )
            bucket = locked
        first_iteration = False
        configuration = _configuration_from_desired(desired)
        previous_configuration = _configuration_from_applied(applied)
        provider = provider or _provider(bucket)
        try:
            provider.update_bucket_configuration(
                bucket,
                configuration,
                previous_configuration=previous_configuration,
                allow_public_read=(
                    configuration.acl == "public_read" and _is_admin(actor)
                ),
            )
        except Exception as error:
            error_code = str(
                getattr(error, "error_code", "") or "BUCKET_CONFIGURATION_UPDATE_FAILED"
            )
            with transaction.atomic():
                locked = Bucket.objects.select_for_update().get(pk=bucket_id)
                if not (
                    locked.configuration_operation_token == operation_token
                    and locked.configuration_claim_generation == target_generation
                    and locked.config_error_code != UNCERTAIN_MUTATION_ERROR
                    and locked.configuration_operation_lease_until
                    and locked.configuration_operation_lease_until > timezone.now()
                ):
                    return locked
                newer_generation = locked.configuration_generation != target_generation
                if (
                    newer_generation
                    and error_code != "BUCKET_CONFIGURATION_ROLLBACK_FAILED"
                ):
                    locked.config_state = Bucket.ConfigurationState.PENDING
                    locked.config_error_code = ""
                    locked.config_error_summary = ""
                    locked.save(
                        update_fields=(
                            "config_state",
                            "config_error_code",
                            "config_error_summary",
                            "updated_at",
                        )
                    )
                    continue
                locked.config_error_code = error_code
                locked.config_error_summary = str(error)[:255]
                locked.config_state = (
                    Bucket.ConfigurationState.UNKNOWN
                    if error_code == "BUCKET_CONFIGURATION_ROLLBACK_FAILED"
                    else Bucket.ConfigurationState.RETRYABLE_ERROR
                )
                locked.configuration_operation_token = ""
                locked.configuration_operation_acquired_at = None
                locked.configuration_operation_lease_until = None
                locked.save(
                    update_fields=(
                        "config_error_code",
                        "config_error_summary",
                        "config_state",
                        "configuration_operation_token",
                        "configuration_operation_acquired_at",
                        "configuration_operation_lease_until",
                        "updated_at",
                    )
                )
            raise BucketConfigurationError(error_code) from error
        with transaction.atomic():
            locked = Bucket.objects.select_for_update().get(pk=bucket_id)
            if not (
                locked.configuration_operation_token == operation_token
                and locked.configuration_claim_generation == target_generation
                and locked.config_error_code != UNCERTAIN_MUTATION_ERROR
                and locked.configuration_operation_lease_until
                and locked.configuration_operation_lease_until > timezone.now()
            ):
                return locked
            locked.applied_config_snapshot = desired
            locked.config_error_code = ""
            locked.config_error_summary = ""
            if locked.configuration_generation != target_generation:
                locked.config_state = Bucket.ConfigurationState.PENDING
                locked.save(
                    update_fields=(
                        "applied_config_snapshot",
                        "config_state",
                        "config_error_code",
                        "config_error_summary",
                        "updated_at",
                    )
                )
                continue
            locked.config_state = Bucket.ConfigurationState.APPLIED
            locked.configuration_operation_token = ""
            locked.configuration_operation_acquired_at = None
            locked.configuration_operation_lease_until = None
            locked.save(
                update_fields=(
                    "applied_config_snapshot",
                    "config_state",
                    "config_error_code",
                    "config_error_summary",
                    "configuration_operation_token",
                    "configuration_operation_acquired_at",
                    "configuration_operation_lease_until",
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
    return update_bucket_configuration(
        bucket=bucket,
        actor=actor,
        desired=bucket.desired_config_snapshot,
        provider=provider,
        enqueue=enqueue,
        reason=reason,
        bucket_name=bucket_name or bucket.name,
        confirmed=confirmed,
        _retry=True,
    )


def suspend_user_resources(*, user, actor, provider=None, enqueue=True, reason=""):
    if not _is_admin(actor):
        raise LifecycleError("ADMIN_REQUIRED")
    identity = CloudIdentity.objects.get(user=user)
    from object_storage.services.credentials import _claim_credential_operation

    identity, generation, token, _claimed = _claim_credential_operation(
        identity.pk,
        operation_type="suspend",
    )
    with transaction.atomic():
        locked = CloudIdentity.objects.select_for_update().get(pk=identity.pk)
        if not (
            locked.credential_operation_generation == generation
            and locked.credential_operation_token == token
            and locked.credential_operation_type == "suspend"
        ):
            raise LifecycleError("RESOURCE_OPERATION_IN_PROGRESS")
        locked.state = CloudIdentity.State.SUSPENDED
        locked.save(update_fields=("state", "updated_at"))
    if enqueue:
        from object_storage.tasks import suspend_user_resources_task

        suspend_user_resources_task.delay(
            identity.pk,
            actor_id=getattr(actor, "pk", None),
            reason=reason,
            operation_generation=generation,
            operation_token=token,
        )
        return locked
    return _disable_identity_keys(
        identity.pk,
        provider=provider,
        actor=actor,
        reason=reason,
        operation_generation=generation,
        operation_token=token,
    )


def reactivate_user_resources(*, user, actor, reason=""):
    if not _is_admin(actor):
        raise LifecycleError("ADMIN_REQUIRED")
    with transaction.atomic():
        identity = CloudIdentity.objects.select_for_update().get(user=user)
        if identity.credential_operation_error_code == UNCERTAIN_MUTATION_ERROR:
            raise LifecycleError(MANUAL_RECONCILIATION_ERROR)
        if identity.credential_operation_token:
            raise LifecycleError("RESOURCE_OPERATION_IN_PROGRESS")
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


def _disable_identity_keys(
    identity_id,
    *,
    provider=None,
    actor=None,
    reason="",
    operation_generation=None,
    operation_token=None,
):
    from object_storage.services.credentials import (
        UNCERTAIN_MUTATION_ERROR,
        _claim_credential_operation,
        _credential_operation_matches,
        _finish_credential_operation,
        assert_credential_operation_claim,
        provider_access_key,
    )

    identity, generation, token, _owns_claim = _claim_credential_operation(
        identity_id,
        operation_type="suspend",
        owner_token=operation_token,
        owner_generation=operation_generation,
    )
    with transaction.atomic():
        locked = CloudIdentity.objects.select_for_update().get(pk=identity_id)
        if not _credential_operation_matches(locked, generation, token, "suspend"):
            raise LifecycleError(MANUAL_RECONCILIATION_ERROR)
        locked.state = CloudIdentity.State.SUSPENDED
        locked.save(update_fields=("state", "updated_at"))
    if provider is None:
        from object_storage.providers.aliyun import build_aliyun_provider

        provider = build_aliyun_provider(identity.resource_pool)
    key_ids = list(
        identity.access_keys.filter(
            local_state__in=(
                AccessKey.LocalState.ISSUING,
                AccessKey.LocalState.DELIVERY_READY,
                AccessKey.LocalState.ACTIVE,
            ),
            deleted_at__isnull=True,
        )
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    for key_id in key_ids:
        with transaction.atomic():
            locked_identity = CloudIdentity.objects.select_for_update().get(
                pk=identity_id
            )
            key = AccessKey.objects.select_for_update().get(pk=key_id)
            if not _credential_operation_matches(
                locked_identity, generation, token, "suspend"
            ):
                raise LifecycleError(MANUAL_RECONCILIATION_ERROR)
            now = timezone.now()
            locked_identity.credential_operation_key_id = key.pk
            locked_identity.save(
                update_fields=("credential_operation_key_id", "updated_at")
            )
            key.operation_generation += 1
            key.operation_token = token
            key.operation_type = "suspend"
            key.operation_acquired_at = now
            key.operation_lease_until = locked_identity.credential_operation_lease_until
            key.operation_error_code = ""
            key.save(
                update_fields=(
                    "operation_generation",
                    "operation_token",
                    "operation_type",
                    "operation_acquired_at",
                    "operation_lease_until",
                    "operation_error_code",
                    "updated_at",
                )
            )
        try:
            assert_credential_operation_claim(identity_id, generation, token, "suspend")
            provider.deactivate_access_key(provider_access_key(key))
        except Exception:
            from object_storage.services.credentials import _freeze_credential_operation

            _freeze_credential_operation(identity_id, generation, token, "suspend")
            with transaction.atomic():
                locked_identity = CloudIdentity.objects.select_for_update().get(
                    pk=identity_id
                )
                for pending_key in AccessKey.objects.select_for_update().filter(
                    cloud_identity_id=identity_id,
                    pk__in=key_ids,
                    deleted_at__isnull=True,
                ):
                    if pending_key.local_state in {
                        AccessKey.LocalState.ISSUING,
                        AccessKey.LocalState.DELIVERY_READY,
                        AccessKey.LocalState.ACTIVE,
                    }:
                        pending_key.cloud_state = AccessKey.CloudState.UNKNOWN
                        pending_key.local_state = AccessKey.LocalState.ERROR
                        pending_key.operation_error_code = UNCERTAIN_MUTATION_ERROR
                        pending_key.save(
                            update_fields=(
                                "cloud_state",
                                "local_state",
                                "operation_error_code",
                                "updated_at",
                            )
                        )
            raise
        with transaction.atomic():
            locked_identity = CloudIdentity.objects.select_for_update().get(
                pk=identity_id
            )
            key = AccessKey.objects.select_for_update().get(pk=key_id)
            if not _credential_operation_matches(
                locked_identity, generation, token, "suspend"
            ):
                raise LifecycleError(MANUAL_RECONCILIATION_ERROR)
            key.operation_token = ""
            key.operation_type = ""
            key.operation_acquired_at = None
            key.operation_lease_until = None
            key.cloud_state = AccessKey.CloudState.INACTIVE
            key.local_state = AccessKey.LocalState.DISABLED
            key.deactivated_at = timezone.now()
            key.save(
                update_fields=(
                    "cloud_state",
                    "local_state",
                    "deactivated_at",
                    "operation_token",
                    "operation_type",
                    "operation_acquired_at",
                    "operation_lease_until",
                    "operation_error_code",
                    "updated_at",
                )
            )
    _finish_credential_operation(identity_id, generation, token, "suspend")
    identity = CloudIdentity.objects.get(pk=identity_id)
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
