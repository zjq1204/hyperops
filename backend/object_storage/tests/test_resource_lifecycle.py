from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

pytestmark = pytest.mark.django_db


class LifecycleProvider:
    def __init__(self, *, emptiness=None, ownership=True):
        self.emptiness = {
            "object_count": 0,
            "version_count": 0,
            "delete_marker_count": 0,
            "multipart_upload_count": 0,
        }
        if emptiness:
            self.emptiness.update(emptiness)
        self.ownership = ownership
        self.calls = []
        self.updated_configurations = []
        self.configuration_options = []
        self.keys = {}

    def inspect_bucket_emptiness(self, bucket):
        self.calls.append(("inspect", bucket.name))
        return SimpleNamespace(
            is_empty=not any(self.emptiness.values()),
            request_id="inspect-request",
            **self.emptiness,
        )

    def find_owned_bucket(self, bucket):
        self.calls.append(("find", bucket.name))
        return SimpleNamespace(
            exists=True,
            owned=self.ownership,
            marker=bucket.cloud_marker if self.ownership else "foreign-marker",
            request_id="find-request",
        )

    def reconcile_object_policy(self, identity, buckets):
        self.calls.append(
            ("policy", identity.pk, tuple(bucket.name for bucket in buckets))
        )
        return SimpleNamespace(request_id="policy-request")

    def delete_owned_bucket(self, bucket):
        self.calls.append(("delete", bucket.name))
        return SimpleNamespace(request_id="delete-request")

    def update_bucket_configuration(self, bucket, configuration, **kwargs):
        self.calls.append(("configure", bucket.name))
        self.updated_configurations.append(configuration)
        self.configuration_options.append(kwargs)
        return SimpleNamespace(request_id="config-request")

    def get_bucket_configuration(self, bucket):
        self.calls.append(("read-configuration", bucket.name))
        snapshot = bucket.applied_config_snapshot or bucket.desired_config_snapshot
        from object_storage.providers.base import BucketConfiguration

        return BucketConfiguration.from_snapshot(snapshot)

    def deactivate_access_key(self, key):
        self.calls.append(("disable-key", key.pk))

    def activate_access_key(self, key):
        self.calls.append(("enable-key", key.pk))

    def delete_access_key(self, key):
        self.calls.append(("revoke-key", key.pk))


def _admin(user_factory):
    return user_factory(is_staff=True, is_superuser=True)


def _feature_admin(user_factory):
    from accounts.models import Role

    user = user_factory()
    role = Role.objects.create(
        name=f"Object storage admin {user.pk}",
        visible_features=["admin_object_storage"],
    )
    role.users.add(user)
    return user


def test_staff_without_object_storage_feature_cannot_administer_bucket(
    bucket_factory, user_factory
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import (
        BucketConfigurationError,
        update_bucket_configuration,
    )

    bucket = bucket_factory(owner=user_factory(), state=Bucket.State.ACTIVE)
    staff = user_factory(is_staff=True)

    with pytest.raises(BucketConfigurationError, match="ADMIN_REQUIRED"):
        update_bucket_configuration(
            bucket=bucket,
            actor=staff,
            desired={"acl": "private"},
            provider=LifecycleProvider(),
            enqueue=False,
        )


def test_object_storage_feature_allows_bucket_administration(
    bucket_factory, user_factory
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import update_bucket_configuration

    bucket = bucket_factory(owner=user_factory(), state=Bucket.State.ACTIVE)
    actor = _feature_admin(user_factory)

    updated = update_bucket_configuration(
        bucket=bucket,
        actor=actor,
        desired={"acl": "private"},
        provider=LifecycleProvider(),
        enqueue=False,
    )

    assert updated.applied_config_snapshot["acl"] == "private"


def test_staff_without_object_storage_feature_cannot_administer_another_users_key(
    access_key_factory, user_factory, monkeypatch
):
    from object_storage.services import credentials
    from object_storage.services.credentials import CredentialRotationError

    key = access_key_factory()
    staff = user_factory(is_staff=True)
    monkeypatch.setattr(
        credentials,
        "provider_access_key",
        lambda selected: SimpleNamespace(
            pk=selected.pk,
            cloud_identity=selected.cloud_identity,
            access_key_id=selected.pk,
        ),
    )

    with pytest.raises(CredentialRotationError, match="ACCESS_KEY_OWNERSHIP_REQUIRED"):
        credentials.disable_access_key(
            access_key=key,
            actor=staff,
            provider=LifecycleProvider(),
        )


def test_object_storage_feature_allows_single_key_administration(
    access_key_factory, user_factory, monkeypatch
):
    from object_storage.models import AccessKey
    from object_storage.services import credentials

    key = access_key_factory()
    actor = _feature_admin(user_factory)
    monkeypatch.setattr(
        credentials,
        "provider_access_key",
        lambda selected: SimpleNamespace(
            pk=selected.pk,
            cloud_identity=selected.cloud_identity,
            access_key_id=selected.pk,
        ),
    )

    credentials.disable_access_key(
        access_key=key,
        actor=actor,
        provider=LifecycleProvider(),
    )

    key.refresh_from_db()
    assert key.local_state == AccessKey.LocalState.DISABLED


def test_release_requires_exact_bucket_name_and_confirmation(
    bucket_factory, user_factory
):
    from object_storage.services.lifecycle import LifecycleError, release_bucket

    bucket = bucket_factory(owner=user_factory(), state="active")
    provider = LifecycleProvider()

    with pytest.raises(LifecycleError, match="BUCKET_NAME_CONFIRMATION_REQUIRED"):
        release_bucket(
            bucket=bucket,
            actor=bucket.owner,
            bucket_name=bucket.name,
            confirmed=False,
            provider=provider,
            enqueue=False,
        )
    with pytest.raises(LifecycleError, match="BUCKET_NAME_CONFIRMATION_MISMATCH"):
        release_bucket(
            bucket=bucket,
            actor=bucket.owner,
            bucket_name="another-bucket",
            confirmed=True,
            provider=provider,
            enqueue=False,
        )


@pytest.mark.parametrize(
    "inspection",
    [
        {"object_count": 1},
        {"version_count": 1},
        {"delete_marker_count": 1},
        {"multipart_upload_count": 1},
    ],
)
def test_release_refuses_bucket_with_any_retained_content(
    bucket_factory, user_factory, inspection
):
    from object_storage.services.lifecycle import LifecycleError, release_bucket

    bucket = bucket_factory(owner=user_factory(), state="active")
    with pytest.raises(LifecycleError, match="BUCKET_NOT_EMPTY"):
        release_bucket(
            bucket=bucket,
            actor=bucket.owner,
            bucket_name=bucket.name,
            confirmed=True,
            provider=LifecycleProvider(emptiness=inspection),
            enqueue=False,
        )

    bucket.refresh_from_db()
    assert bucket.state == "active"


def test_empty_release_detaches_policy_enters_pending_and_frees_quota(
    bucket_factory, user_factory, platform_object_storage_config
):
    from object_storage.models import AuditEvent, Bucket
    from object_storage.services.lifecycle import release_bucket
    from object_storage.services.policy import count_quota_consuming_buckets

    owner = user_factory()
    bucket = bucket_factory(owner=owner, state=Bucket.State.ACTIVE)
    provider = LifecycleProvider()
    before = timezone.now()

    release_bucket(
        bucket=bucket,
        actor=owner,
        bucket_name=bucket.name,
        confirmed=True,
        provider=provider,
        enqueue=False,
    )

    bucket.refresh_from_db()
    assert bucket.state == Bucket.State.PENDING_DELETION
    assert before + timedelta(days=7) <= bucket.pending_delete_at
    assert bucket.pending_delete_at <= timezone.now() + timedelta(days=7)
    assert count_quota_consuming_buckets(owner) == 0
    assert ("policy", bucket.cloud_identity_id, ()) in provider.calls
    assert AuditEvent.objects.filter(
        action="storage.bucket.release", target_id=str(bucket.pk), result="succeeded"
    ).exists()

    first_deadline = bucket.pending_delete_at
    provider.calls.clear()
    repeated = release_bucket(
        bucket=bucket,
        actor=owner,
        bucket_name=bucket.name,
        confirmed=True,
        provider=provider,
        enqueue=False,
    )
    assert repeated.pending_delete_at == first_deadline
    assert provider.calls == []


def test_interleaved_duplicate_release_reuses_claim_and_clears_it_once(
    bucket_factory, user_factory, monkeypatch
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import release_bucket

    owner = user_factory()
    bucket = bucket_factory(owner=owner, state=Bucket.State.ACTIVE)
    scheduled = []
    monkeypatch.setattr(
        "object_storage.tasks.release_bucket_task.delay",
        lambda bucket_id, **kwargs: scheduled.append((bucket_id, kwargs)),
    )

    class InterleavingProvider(LifecycleProvider):
        def inspect_bucket_emptiness(self, selected):
            release_bucket(
                bucket=selected,
                actor=owner,
                bucket_name=selected.name,
                confirmed=True,
                enqueue=True,
            )
            return super().inspect_bucket_emptiness(selected)

    release_bucket(
        bucket=bucket,
        actor=owner,
        bucket_name=bucket.name,
        confirmed=True,
        provider=InterleavingProvider(),
        enqueue=False,
    )

    bucket.refresh_from_db()
    assert scheduled == []
    assert bucket.state == Bucket.State.PENDING_DELETION
    assert bucket.action_generation == 1
    assert bucket.action_owner_token == ""
    assert bucket.action_type == ""


def test_recover_rechecks_quota_and_reauthorizes_without_enabling_keys(
    bucket_factory, user_factory, platform_object_storage_config
):
    from object_storage.models import AccessKey, Bucket
    from object_storage.services.lifecycle import recover_bucket

    owner = user_factory()
    bucket = bucket_factory(
        owner=owner,
        state=Bucket.State.PENDING_DELETION,
        pending_delete_at=timezone.now() + timedelta(days=1),
    )
    key = AccessKey.objects.create(
        cloud_identity=bucket.cloud_identity,
        access_key_id_encrypted="encrypted-ak",
        secret_access_key_encrypted="encrypted-sk",
        access_key_fingerprint="recover-key",
        access_key_last_four="-key",
        local_state=AccessKey.LocalState.DISABLED,
        cloud_state=AccessKey.CloudState.INACTIVE,
    )
    provider = LifecycleProvider()

    recover_bucket(
        bucket=bucket,
        actor=owner,
        bucket_name=bucket.name,
        confirmed=True,
        provider=provider,
    )

    bucket.refresh_from_db()
    key.refresh_from_db()
    assert bucket.state == Bucket.State.ACTIVE
    assert bucket.pending_delete_at is None
    assert key.local_state == AccessKey.LocalState.DISABLED
    assert ("policy", bucket.cloud_identity_id, (bucket.name,)) in provider.calls


def test_immediate_delete_cannot_overlap_recover_cloud_mutation(
    bucket_factory, user_factory
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import (
        LifecycleError,
        delete_bucket,
        recover_bucket,
    )

    owner = user_factory()
    admin = _admin(user_factory)
    bucket = bucket_factory(
        owner=owner,
        state=Bucket.State.PENDING_DELETION,
        pending_delete_at=timezone.now() + timedelta(days=1),
    )
    delete_provider = LifecycleProvider()

    class RecoverProvider(LifecycleProvider):
        def reconcile_object_policy(self, identity, buckets):
            with pytest.raises(LifecycleError, match="RESOURCE_OPERATION_IN_PROGRESS"):
                delete_bucket(
                    bucket=Bucket.objects.get(pk=bucket.pk),
                    actor=admin,
                    reason="supersede recovery",
                    bucket_name=bucket.name,
                    confirmed=True,
                    immediate=True,
                    provider=delete_provider,
                )
            return super().reconcile_object_policy(identity, buckets)

    recover_bucket(
        bucket=bucket,
        actor=owner,
        bucket_name=bucket.name,
        confirmed=True,
        provider=RecoverProvider(),
    )

    bucket.refresh_from_db()
    assert bucket.state == Bucket.State.ACTIVE
    assert bucket.action_generation == 1
    assert bucket.action_owner_token == ""
    assert bucket.action_type == ""
    assert delete_provider.calls == []


def test_expired_bucket_configuration_claim_fails_closed_after_reconciliation(
    bucket_factory, user_factory
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import (
        recover_expired_bucket_configuration_claim,
    )

    bucket = bucket_factory(owner=user_factory(), state=Bucket.State.ACTIVE)
    bucket.config_state = Bucket.ConfigurationState.PENDING
    bucket.configuration_operation_token = "expired-config-token"
    bucket.configuration_claim_generation = 3
    bucket.configuration_operation_acquired_at = timezone.now() - timedelta(minutes=10)
    bucket.configuration_operation_lease_until = timezone.now() - timedelta(minutes=5)
    bucket.save(
        update_fields=(
            "config_state",
            "configuration_operation_token",
            "configuration_claim_generation",
            "configuration_operation_acquired_at",
            "configuration_operation_lease_until",
            "updated_at",
        )
    )
    provider = LifecycleProvider()

    recover_expired_bucket_configuration_claim(bucket.pk, provider=provider)

    bucket.refresh_from_db()
    assert provider.calls == [("read-configuration", bucket.name)]
    assert bucket.config_state == Bucket.ConfigurationState.UNKNOWN
    assert bucket.config_error_code == "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    assert bucket.configuration_operation_token == "expired-config-token"
    assert bucket.configuration_operation_lease_until is not None


def test_expired_release_claim_reconciles_without_replaying_cloud_mutation(
    bucket_factory, user_factory
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import recover_expired_bucket_action_claim

    bucket = bucket_factory(owner=user_factory(), state=Bucket.State.RELEASING)
    bucket.action_generation = 4
    bucket.action_owner_token = "expired-release-token"
    bucket.action_type = "release"
    bucket.action_acquired_at = timezone.now() - timedelta(minutes=10)
    bucket.action_lease_until = timezone.now() - timedelta(minutes=5)
    bucket.save(
        update_fields=(
            "state",
            "action_generation",
            "action_owner_token",
            "action_type",
            "action_acquired_at",
            "action_lease_until",
            "updated_at",
        )
    )
    provider = LifecycleProvider()

    recover_expired_bucket_action_claim(bucket.pk, provider=provider)

    bucket.refresh_from_db()
    assert provider.calls == [("find", bucket.name), ("inspect", bucket.name)]
    assert bucket.state == Bucket.State.DELETION_BLOCKED
    assert bucket.deletion_error_code == "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    assert bucket.action_owner_token == "expired-release-token"
    assert bucket.action_lease_until is not None
    assert not any(call[0] in {"policy", "delete"} for call in provider.calls)


def test_expired_delete_claim_fails_closed_when_ownership_is_uncertain(
    bucket_factory, user_factory
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import recover_expired_bucket_action_claim

    bucket = bucket_factory(owner=user_factory(), state=Bucket.State.RELEASING)
    bucket.action_generation = 5
    bucket.action_owner_token = "expired-delete-token"
    bucket.action_type = "delete"
    bucket.action_acquired_at = timezone.now() - timedelta(minutes=10)
    bucket.action_lease_until = timezone.now() - timedelta(minutes=5)
    bucket.save(
        update_fields=(
            "state",
            "action_generation",
            "action_owner_token",
            "action_type",
            "action_acquired_at",
            "action_lease_until",
            "updated_at",
        )
    )

    class UncertainProvider(LifecycleProvider):
        def find_owned_bucket(self, selected):
            self.calls.append(("find", selected.name))
            raise RuntimeError("ownership lookup unavailable")

    provider = UncertainProvider()
    recover_expired_bucket_action_claim(bucket.pk, provider=provider)

    bucket.refresh_from_db()
    assert provider.calls == [("find", bucket.name)]
    assert bucket.state == Bucket.State.DELETION_BLOCKED
    assert bucket.deletion_error_code == "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    assert bucket.action_owner_token == "expired-delete-token"
    assert bucket.action_lease_until is not None


def test_frozen_bucket_claims_reject_normal_mutations(bucket_factory, user_factory):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import (
        BucketConfigurationError,
        LifecycleError,
        delete_bucket,
        update_bucket_configuration,
    )

    actor = _feature_admin(user_factory)
    config_bucket = bucket_factory(state=Bucket.State.ACTIVE)
    config_bucket.config_state = Bucket.ConfigurationState.UNKNOWN
    config_bucket.config_error_code = "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    config_bucket.configuration_operation_token = "frozen-config-token"
    config_bucket.save(
        update_fields=(
            "config_state",
            "config_error_code",
            "configuration_operation_token",
            "updated_at",
        )
    )
    action_bucket = bucket_factory(state=Bucket.State.DELETION_BLOCKED)
    action_bucket.deletion_error_code = "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    action_bucket.action_owner_token = "frozen-action-token"
    action_bucket.action_type = "delete"
    action_bucket.save(
        update_fields=(
            "state",
            "deletion_error_code",
            "action_owner_token",
            "action_type",
            "updated_at",
        )
    )
    expired_config_bucket = bucket_factory(state=Bucket.State.ACTIVE)
    expired_config_bucket.configuration_operation_token = "expired-config-token"
    expired_config_bucket.configuration_operation_lease_until = (
        timezone.now() - timedelta(seconds=1)
    )
    expired_config_bucket.save(
        update_fields=(
            "configuration_operation_token",
            "configuration_operation_lease_until",
            "updated_at",
        )
    )
    provider = LifecycleProvider()

    with pytest.raises(
        BucketConfigurationError, match="MANUAL_RECONCILIATION_REQUIRED"
    ):
        update_bucket_configuration(
            bucket=config_bucket,
            actor=actor,
            desired={"acl": "private"},
            provider=provider,
            enqueue=False,
        )
    with pytest.raises(
        BucketConfigurationError, match="MANUAL_RECONCILIATION_REQUIRED"
    ):
        update_bucket_configuration(
            bucket=expired_config_bucket,
            actor=actor,
            desired={"acl": "private", "versioning": True},
            provider=provider,
            enqueue=False,
        )
    with pytest.raises(LifecycleError, match="MANUAL_RECONCILIATION_REQUIRED"):
        delete_bucket(
            bucket=action_bucket,
            actor=actor,
            reason="confirmed after incident",
            bucket_name=action_bucket.name,
            confirmed=True,
            immediate=True,
            provider=provider,
        )

    assert provider.calls == []


def test_bucket_configuration_reconciliation_records_observation_without_unfreezing(
    bucket_factory, user_factory
):
    from object_storage.models import AuditEvent, Bucket
    from object_storage.services.lifecycle import (
        reconcile_bucket_configuration_uncertainty,
    )

    desired = {
        "acl": "private",
        "storage_class": "Standard",
        "encryption": "AES256",
        "versioning": False,
        "lifecycle": {},
    }
    bucket = bucket_factory(state=Bucket.State.ACTIVE)
    bucket.desired_config_snapshot = desired
    bucket.applied_config_snapshot = {}
    bucket.config_state = Bucket.ConfigurationState.UNKNOWN
    bucket.config_error_code = "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    bucket.configuration_operation_token = "frozen-config-token"
    bucket.save(
        update_fields=(
            "desired_config_snapshot",
            "applied_config_snapshot",
            "config_state",
            "config_error_code",
            "configuration_operation_token",
            "updated_at",
        )
    )
    provider = LifecycleProvider()

    reconciled = reconcile_bucket_configuration_uncertainty(
        bucket=bucket,
        actor=_feature_admin(user_factory),
        provider=provider,
        reason="provider request confirmed complete",
    )

    assert reconciled.config_state == Bucket.ConfigurationState.UNKNOWN
    assert reconciled.applied_config_snapshot == {}
    assert reconciled.configuration_operation_token == "frozen-config-token"
    assert reconciled.configuration_observed_snapshot == desired
    assert AuditEvent.objects.filter(
        action="storage.bucket.configuration.reconciled",
        target_id=str(bucket.pk),
        reason="provider request confirmed complete",
    ).exists()


def test_bucket_configuration_manual_resolution_requires_current_fence_and_admin(
    bucket_factory, user_factory
):
    from object_storage.models import AuditEvent, Bucket
    from object_storage.services.lifecycle import (
        LifecycleError,
        acknowledge_bucket_configuration_uncertainty,
    )

    desired = {"acl": "private"}
    bucket = bucket_factory(state=Bucket.State.ACTIVE)
    bucket.desired_config_snapshot = desired
    bucket.config_state = Bucket.ConfigurationState.UNKNOWN
    bucket.config_error_code = "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    bucket.configuration_generation = 7
    bucket.configuration_operation_token = "frozen-config-token"
    bucket.save(
        update_fields=(
            "desired_config_snapshot",
            "config_state",
            "config_error_code",
            "configuration_generation",
            "configuration_operation_token",
            "updated_at",
        )
    )
    actor = _feature_admin(user_factory)
    ordinary_owner = bucket.owner

    arguments = {
        "bucket": bucket,
        "reason": "cloud request verified outside platform",
        "bucket_name": bucket.name,
        "operation_type": "configuration",
        "operation_generation": 7,
        "operation_token": "frozen-config-token",
        "resolution": "desired",
    }

    with pytest.raises(LifecycleError, match="ADMIN_REQUIRED"):
        acknowledge_bucket_configuration_uncertainty(
            actor=ordinary_owner,
            **arguments,
        )

    with pytest.raises(LifecycleError, match="RECONCILIATION_REASON_REQUIRED"):
        acknowledge_bucket_configuration_uncertainty(
            actor=actor,
            reason="",
            **{key: value for key, value in arguments.items() if key != "reason"},
        )
    with pytest.raises(
        LifecycleError, match="RESOURCE_OPERATION_CONFIRMATION_MISMATCH"
    ):
        acknowledge_bucket_configuration_uncertainty(
            actor=actor,
            **{**arguments, "operation_token": "stale-token"},
        )

    acknowledged = acknowledge_bucket_configuration_uncertainty(
        actor=actor,
        **arguments,
    )

    assert acknowledged.configuration_operation_token == ""
    assert acknowledged.config_state == Bucket.ConfigurationState.APPLIED
    assert AuditEvent.objects.filter(
        action="storage.bucket.configuration.acknowledged",
        target_id=str(bucket.pk),
        reason="cloud request verified outside platform",
    ).exists()


def test_bucket_lifecycle_reconciliation_records_absence_without_unfreezing(
    bucket_factory, user_factory
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import reconcile_bucket_action_uncertainty

    bucket = bucket_factory(state=Bucket.State.DELETION_BLOCKED)
    bucket.deletion_error_code = "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    bucket.action_owner_token = "frozen-delete-token"
    bucket.action_type = "delete"
    bucket.save(
        update_fields=(
            "state",
            "deletion_error_code",
            "action_owner_token",
            "action_type",
            "updated_at",
        )
    )

    class AbsentProvider(LifecycleProvider):
        def find_owned_bucket(self, selected):
            self.calls.append(("find", selected.name))
            return SimpleNamespace(exists=False, owned=False, marker="")

    reconciled = reconcile_bucket_action_uncertainty(
        bucket=bucket,
        actor=_feature_admin(user_factory),
        provider=AbsentProvider(),
        reason="provider confirms bucket absent",
    )

    assert reconciled.state == Bucket.State.DELETION_BLOCKED
    assert reconciled.action_owner_token == "frozen-delete-token"
    assert reconciled.deletion_error_code == "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    assert reconciled.action_observed_snapshot == {
        "exists": False,
        "owned": False,
    }


def test_bucket_action_manual_resolution_requires_exact_operation_confirmation(
    bucket_factory, user_factory
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import (
        LifecycleError,
        acknowledge_bucket_action_uncertainty,
    )

    bucket = bucket_factory(state=Bucket.State.DELETION_BLOCKED)
    bucket.action_generation = 4
    bucket.action_owner_token = "frozen-delete-token"
    bucket.action_type = "delete"
    bucket.deletion_error_code = "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    bucket.save(
        update_fields=(
            "state",
            "action_generation",
            "action_owner_token",
            "action_type",
            "deletion_error_code",
            "updated_at",
        )
    )
    actor = _feature_admin(user_factory)
    arguments = {
        "bucket": bucket,
        "actor": actor,
        "reason": "bucket absence confirmed in cloud console",
        "bucket_name": bucket.name,
        "operation_type": "delete",
        "operation_generation": 4,
        "operation_token": "frozen-delete-token",
        "resolved_state": Bucket.State.RELEASED,
    }

    with pytest.raises(
        LifecycleError, match="RESOURCE_OPERATION_CONFIRMATION_MISMATCH"
    ):
        acknowledge_bucket_action_uncertainty(
            **{**arguments, "operation_generation": 3}
        )

    resolved = acknowledge_bucket_action_uncertainty(**arguments)

    assert resolved.state == Bucket.State.RELEASED
    assert resolved.action_owner_token == ""


def test_late_bucket_configuration_result_cannot_overwrite_expiry_freeze(
    bucket_factory, user_factory, monkeypatch
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import (
        _apply_bucket_configuration,
        recover_expired_bucket_configuration_claim,
        update_bucket_configuration,
    )

    bucket = bucket_factory(state=Bucket.State.ACTIVE)
    actor = _feature_admin(user_factory)
    scheduled = []
    monkeypatch.setattr(
        "object_storage.tasks.update_bucket_configuration_task.delay",
        lambda bucket_id, **kwargs: scheduled.append((bucket_id, kwargs)),
    )
    update_bucket_configuration(
        bucket=bucket,
        actor=actor,
        desired={"acl": "private", "versioning": True},
    )
    generation = scheduled[0][1]["configuration_generation"]
    token = scheduled[0][1]["operation_token"]

    class LateProvider(LifecycleProvider):
        def update_bucket_configuration(self, selected, configuration, **kwargs):
            Bucket.objects.filter(pk=selected.pk).update(
                configuration_operation_lease_until=timezone.now()
                - timedelta(seconds=1)
            )
            recover_expired_bucket_configuration_claim(
                selected.pk,
                provider=self,
            )
            self.calls.append(("late-configure", selected.name))
            return SimpleNamespace(request_id="late-success")

    provider = LateProvider()
    _apply_bucket_configuration(
        bucket.pk,
        configuration_generation=generation,
        operation_token=token,
        provider=provider,
        actor=actor,
    )

    bucket.refresh_from_db()
    assert bucket.config_state == Bucket.ConfigurationState.UNKNOWN
    assert bucket.config_error_code == "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    assert bucket.configuration_operation_token
    assert bucket.applied_config_snapshot != bucket.desired_config_snapshot


def test_late_release_result_cannot_overwrite_expiry_freeze(
    bucket_factory, user_factory
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import (
        recover_expired_bucket_action_claim,
        release_bucket,
    )

    owner = user_factory()
    bucket = bucket_factory(owner=owner, state=Bucket.State.ACTIVE)

    class LateReleaseProvider(LifecycleProvider):
        recovering = False

        def inspect_bucket_emptiness(self, selected):
            if self.recovering:
                return super().inspect_bucket_emptiness(selected)
            Bucket.objects.filter(pk=selected.pk).update(
                action_lease_until=timezone.now() - timedelta(seconds=1)
            )
            self.recovering = True
            try:
                recover_expired_bucket_action_claim(selected.pk, provider=self)
            finally:
                self.recovering = False
            return super().inspect_bucket_emptiness(selected)

    provider = LateReleaseProvider()
    release_bucket(
        bucket=bucket,
        actor=owner,
        bucket_name=bucket.name,
        confirmed=True,
        provider=provider,
        enqueue=False,
    )

    bucket.refresh_from_db()
    assert bucket.state == Bucket.State.DELETION_BLOCKED
    assert bucket.deletion_error_code == "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    assert bucket.action_owner_token
    assert not any(call[0] == "policy" for call in provider.calls)


def test_recover_rejects_when_quota_is_full(
    bucket_factory, user_factory, platform_object_storage_config
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import LifecycleError, recover_bucket

    owner = user_factory()
    platform_object_storage_config.default_bucket_quota = 1
    platform_object_storage_config.save(update_fields=("default_bucket_quota",))
    bucket = bucket_factory(
        owner=owner,
        state=Bucket.State.PENDING_DELETION,
        pending_delete_at=timezone.now() + timedelta(days=1),
    )
    bucket_factory(owner=owner, state=Bucket.State.ACTIVE, name="other-active-bucket")

    with pytest.raises(LifecycleError, match="BUCKET_QUOTA_EXCEEDED"):
        recover_bucket(
            bucket=bucket,
            actor=owner,
            bucket_name=bucket.name,
            confirmed=True,
            provider=LifecycleProvider(),
        )


def test_recover_rejects_after_seven_day_window(bucket_factory, user_factory):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import LifecycleError, recover_bucket

    owner = user_factory()
    bucket = bucket_factory(
        owner=owner,
        state=Bucket.State.PENDING_DELETION,
        pending_delete_at=timezone.now() - timedelta(seconds=1),
    )

    with pytest.raises(LifecycleError, match="BUCKET_RECOVERY_WINDOW_EXPIRED"):
        recover_bucket(
            bucket=bucket,
            actor=owner,
            bucket_name=bucket.name,
            confirmed=True,
            provider=LifecycleProvider(),
        )


@pytest.mark.parametrize(
    "emptiness,ownership",
    [
        ({"object_count": 1}, True),
        ({"version_count": 0}, False),
    ],
)
def test_expiry_never_deletes_nonempty_or_foreign_bucket(
    bucket_factory, user_factory, emptiness, ownership
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import delete_bucket

    bucket = bucket_factory(
        owner=user_factory(),
        state=Bucket.State.PENDING_DELETION,
        pending_delete_at=timezone.now() - timedelta(minutes=1),
    )
    provider = LifecycleProvider(emptiness=emptiness, ownership=ownership)

    delete_bucket(bucket=bucket, provider=provider)

    bucket.refresh_from_db()
    assert bucket.state == Bucket.State.DELETION_BLOCKED
    assert not any(call[0] == "delete" for call in provider.calls)


def test_expiry_deletes_only_owned_empty_bucket(bucket_factory, user_factory):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import delete_bucket

    bucket = bucket_factory(
        owner=user_factory(),
        state=Bucket.State.PENDING_DELETION,
        pending_delete_at=timezone.now() - timedelta(minutes=1),
    )
    provider = LifecycleProvider()

    delete_bucket(bucket=bucket, provider=provider)

    bucket.refresh_from_db()
    assert bucket.state == Bucket.State.RELEASED
    assert ("delete", bucket.name) in provider.calls
    provider.calls.clear()
    assert (
        delete_bucket(bucket=bucket, provider=provider).state == Bucket.State.RELEASED
    )
    assert provider.calls == []


def test_delete_provider_timeout_freezes_action_and_blocks_retry(
    bucket_factory, user_factory
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import (
        LifecycleError,
        delete_bucket,
        reconcile_bucket_action_uncertainty,
        retry_delete_bucket,
    )

    owner = user_factory()
    bucket = bucket_factory(
        owner=owner,
        state=Bucket.State.PENDING_DELETION,
        pending_delete_at=timezone.now() - timedelta(minutes=1),
    )

    class TimeoutProvider(LifecycleProvider):
        def delete_owned_bucket(self, selected):
            self.calls.append(("delete", selected.name))
            raise RuntimeError("provider timeout")

    provider = TimeoutProvider()
    deleted = delete_bucket(bucket=bucket, provider=provider)

    deleted.refresh_from_db()
    assert deleted.state == Bucket.State.DELETION_BLOCKED
    assert deleted.deletion_error_code == "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    assert deleted.action_type == "delete"
    assert deleted.action_owner_token
    generation = deleted.action_generation
    token = deleted.action_owner_token

    with pytest.raises(LifecycleError, match="MANUAL_RECONCILIATION_REQUIRED"):
        retry_delete_bucket(
            bucket=deleted,
            actor=owner,
            bucket_name=deleted.name,
            confirmed=True,
            provider=provider,
        )

    observed = reconcile_bucket_action_uncertainty(
        bucket=deleted,
        actor=_feature_admin(user_factory),
        provider=provider,
        reason="read cloud state after timeout",
    )
    assert observed.action_generation == generation
    assert observed.action_owner_token == token
    assert observed.deletion_error_code == "CLOUD_MUTATION_OUTCOME_UNKNOWN"


def test_release_policy_timeout_freezes_action_and_blocks_release(
    bucket_factory, user_factory
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import LifecycleError, release_bucket

    owner = user_factory()
    bucket = bucket_factory(owner=owner, state=Bucket.State.ACTIVE)

    class TimeoutProvider(LifecycleProvider):
        def reconcile_object_policy(self, identity, buckets):
            self.calls.append(("policy", identity.pk))
            raise RuntimeError("provider timeout")

    provider = TimeoutProvider()
    with pytest.raises(RuntimeError, match="provider timeout"):
        release_bucket(
            bucket=bucket,
            actor=owner,
            bucket_name=bucket.name,
            confirmed=True,
            provider=provider,
            enqueue=False,
        )

    bucket.refresh_from_db()
    assert bucket.state == Bucket.State.DELETION_BLOCKED
    assert bucket.deletion_error_code == "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    assert bucket.action_type == "release"
    assert bucket.action_owner_token

    with pytest.raises(LifecycleError, match="MANUAL_RECONCILIATION_REQUIRED"):
        release_bucket(
            bucket=bucket,
            actor=owner,
            bucket_name=bucket.name,
            confirmed=True,
            provider=provider,
            enqueue=False,
        )


def test_recover_policy_timeout_freezes_action_and_blocks_recovery(
    bucket_factory, user_factory
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import LifecycleError, recover_bucket

    owner = user_factory()
    bucket = bucket_factory(
        owner=owner,
        state=Bucket.State.PENDING_DELETION,
        pending_delete_at=timezone.now() + timedelta(days=1),
    )

    class TimeoutProvider(LifecycleProvider):
        def reconcile_object_policy(self, identity, buckets):
            self.calls.append(("policy", identity.pk))
            raise RuntimeError("provider timeout")

    provider = TimeoutProvider()
    with pytest.raises(RuntimeError, match="provider timeout"):
        recover_bucket(
            bucket=bucket,
            actor=owner,
            bucket_name=bucket.name,
            confirmed=True,
            provider=provider,
        )

    bucket.refresh_from_db()
    assert bucket.state == Bucket.State.DELETION_BLOCKED
    assert bucket.deletion_error_code == "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    assert bucket.action_type == "recover"
    assert bucket.action_owner_token

    with pytest.raises(LifecycleError, match="MANUAL_RECONCILIATION_REQUIRED"):
        recover_bucket(
            bucket=bucket,
            actor=owner,
            bucket_name=bucket.name,
            confirmed=True,
            provider=provider,
        )


def test_admin_can_retry_blocked_bucket_and_immediately_delete_with_reason(
    bucket_factory, user_factory
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import delete_bucket, retry_delete_bucket

    owner = user_factory()
    admin = _admin(user_factory)
    bucket = bucket_factory(owner=owner, state=Bucket.State.DELETION_BLOCKED)
    provider = LifecycleProvider()

    retry_delete_bucket(
        bucket=bucket,
        actor=admin,
        bucket_name=bucket.name,
        confirmed=True,
        provider=provider,
    )
    bucket.refresh_from_db()
    assert bucket.state == Bucket.State.RELEASED

    bucket = bucket_factory(owner=owner, name="admin-immediate-bucket")
    with pytest.raises(Exception, match="DELETE_REASON_REQUIRED"):
        delete_bucket(
            bucket=bucket,
            actor=admin,
            reason="",
            bucket_name=bucket.name,
            confirmed=True,
            immediate=True,
            provider=provider,
        )
    with pytest.raises(Exception, match="BUCKET_NAME_CONFIRMATION_REQUIRED"):
        delete_bucket(
            bucket=bucket,
            actor=admin,
            reason="approved cleanup",
            bucket_name=bucket.name,
            confirmed=False,
            immediate=True,
            provider=provider,
        )


def test_bucket_configuration_keeps_applied_snapshot_when_provider_fails(
    bucket_factory, user_factory, monkeypatch
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import (
        BucketConfigurationError,
        update_bucket_configuration,
    )

    bucket = bucket_factory(owner=user_factory(), state=Bucket.State.ACTIVE)
    bucket.applied_config_snapshot = {"acl": "private"}
    bucket.save(update_fields=("applied_config_snapshot", "updated_at"))
    provider = LifecycleProvider()
    provider.update_bucket_configuration = lambda *args, **kwargs: (
        _ for _ in ()
    ).throw(RuntimeError("provider unavailable"))

    with pytest.raises(
        BucketConfigurationError, match="BUCKET_CONFIGURATION_UPDATE_FAILED"
    ):
        update_bucket_configuration(
            bucket=bucket,
            actor=_admin(user_factory),
            desired={"acl": "public_read", "versioning": True},
            provider=provider,
            enqueue=False,
            reason="public access review",
            bucket_name=bucket.name,
            confirmed=True,
        )

    bucket.refresh_from_db()
    assert bucket.desired_config_snapshot == {
        "acl": "public_read",
        "storage_class": "Standard",
        "encryption": "AES256",
        "versioning": True,
        "lifecycle": {},
    }
    assert bucket.applied_config_snapshot == {"acl": "private"}
    assert bucket.config_error_code == "BUCKET_CONFIGURATION_UPDATE_FAILED"
    assert bucket.config_state == Bucket.ConfigurationState.RETRYABLE_ERROR


def test_bucket_configuration_rollback_failure_marks_cloud_state_unknown(
    bucket_factory, user_factory
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import (
        BucketConfigurationError,
        update_bucket_configuration,
    )
    from object_storage.services.provider_errors import ObjectStorageProviderError

    bucket = bucket_factory(owner=user_factory(), state=Bucket.State.ACTIVE)
    bucket.applied_config_snapshot = {
        "acl": "private",
        "storage_class": "Standard",
        "encryption": "AES256",
        "versioning": False,
        "lifecycle": {},
    }
    bucket.save(update_fields=("applied_config_snapshot", "updated_at"))
    provider = LifecycleProvider()
    provider.update_bucket_configuration = lambda *args, **kwargs: (
        _ for _ in ()
    ).throw(ObjectStorageProviderError("BUCKET_CONFIGURATION_ROLLBACK_FAILED"))

    with pytest.raises(
        BucketConfigurationError,
        match="BUCKET_CONFIGURATION_ROLLBACK_FAILED",
    ):
        update_bucket_configuration(
            bucket=bucket,
            actor=_feature_admin(user_factory),
            desired={"acl": "public_read"},
            provider=provider,
            enqueue=False,
            reason="approved public documentation",
            bucket_name=bucket.name,
            confirmed=True,
        )

    bucket.refresh_from_db()
    assert bucket.applied_config_snapshot["acl"] == "private"
    assert bucket.desired_config_snapshot["acl"] == "public_read"
    assert bucket.config_error_code == "BUCKET_CONFIGURATION_ROLLBACK_FAILED"
    assert bucket.config_state == Bucket.ConfigurationState.UNKNOWN


def test_unknown_bucket_configuration_cannot_be_retried(bucket_factory, user_factory):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import (
        BucketConfigurationError,
        retry_bucket_configuration,
    )

    bucket = bucket_factory(owner=user_factory(), state=Bucket.State.ACTIVE)
    bucket.desired_config_snapshot = {"acl": "public_read"}
    bucket.applied_config_snapshot = {"acl": "private"}
    bucket.config_state = Bucket.ConfigurationState.UNKNOWN
    bucket.config_error_code = "BUCKET_CONFIGURATION_ROLLBACK_FAILED"
    bucket.save(
        update_fields=(
            "desired_config_snapshot",
            "applied_config_snapshot",
            "config_state",
            "config_error_code",
            "updated_at",
        )
    )
    provider = LifecycleProvider()

    with pytest.raises(
        BucketConfigurationError,
        match="BUCKET_CONFIGURATION_STATE_UNKNOWN",
    ):
        retry_bucket_configuration(
            bucket=bucket,
            actor=_feature_admin(user_factory),
            provider=provider,
            enqueue=False,
            reason="manual investigation required",
            bucket_name=bucket.name,
            confirmed=True,
        )

    bucket.refresh_from_db()
    assert provider.calls == []
    assert bucket.config_state == Bucket.ConfigurationState.UNKNOWN
    assert bucket.config_error_code == "BUCKET_CONFIGURATION_ROLLBACK_FAILED"
    assert bucket.desired_config_snapshot == {"acl": "public_read"}
    assert bucket.applied_config_snapshot == {"acl": "private"}


@pytest.mark.parametrize(
    "config_state",
    [
        "pending",
        "retryable_error",
    ],
)
def test_pending_and_retryable_bucket_configuration_can_be_retried(
    bucket_factory, user_factory, config_state
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import retry_bucket_configuration

    bucket = bucket_factory(owner=user_factory(), state=Bucket.State.ACTIVE)
    bucket.desired_config_snapshot = {"acl": "private"}
    bucket.config_state = config_state
    bucket.config_error_code = "BUCKET_CONFIGURATION_UPDATE_FAILED"
    bucket.save(
        update_fields=(
            "desired_config_snapshot",
            "config_state",
            "config_error_code",
            "updated_at",
        )
    )
    provider = LifecycleProvider()

    retry_bucket_configuration(
        bucket=bucket,
        actor=_feature_admin(user_factory),
        provider=provider,
        enqueue=False,
    )

    bucket.refresh_from_db()
    assert provider.calls == [("configure", bucket.name)]
    assert bucket.config_state == Bucket.ConfigurationState.APPLIED


def test_bucket_configuration_worker_serially_catches_up_to_latest_generation(
    bucket_factory, user_factory, monkeypatch
):
    from object_storage.models import Bucket
    from object_storage.services.lifecycle import (
        _apply_bucket_configuration,
        update_bucket_configuration,
    )

    bucket = bucket_factory(owner=user_factory(), state=Bucket.State.ACTIVE)
    bucket.applied_config_snapshot = {
        "acl": "private",
        "storage_class": "Standard",
        "encryption": "AES256",
        "versioning": False,
        "lifecycle": {},
    }
    bucket.save(update_fields=("applied_config_snapshot", "updated_at"))
    actor = _feature_admin(user_factory)
    scheduled = []
    monkeypatch.setattr(
        "object_storage.tasks.update_bucket_configuration_task.delay",
        lambda bucket_id, **kwargs: scheduled.append((bucket_id, kwargs)),
    )
    update_bucket_configuration(
        bucket=bucket,
        actor=actor,
        desired={"acl": "public_read"},
        reason="publish approved content",
        bucket_name=bucket.name,
        confirmed=True,
    )
    old_generation = scheduled[0][1]["configuration_generation"]
    old_token = scheduled[0][1]["operation_token"]

    class InterleavingProvider(LifecycleProvider):
        submitted_private = False

        def update_bucket_configuration(self, selected, configuration, **kwargs):
            self.updated_configurations.append(configuration)
            if not self.submitted_private:
                self.submitted_private = True
                update_bucket_configuration(
                    bucket=selected,
                    actor=actor,
                    desired={"acl": "private"},
                )
            return SimpleNamespace(request_id="config-request")

    provider = InterleavingProvider()
    _apply_bucket_configuration(
        bucket.pk,
        configuration_generation=old_generation,
        operation_token=old_token,
        provider=provider,
        actor=actor,
    )

    bucket.refresh_from_db()
    assert len(scheduled) == 1
    assert bucket.configuration_generation == old_generation + 1
    assert bucket.configuration_operation_token == ""
    assert [item.acl for item in provider.updated_configurations] == [
        "public_read",
        "private",
    ]
    assert bucket.desired_config_snapshot["acl"] == "private"
    assert bucket.applied_config_snapshot == bucket.desired_config_snapshot
    assert bucket.config_state == Bucket.ConfigurationState.APPLIED
    assert bucket.config_error_code == ""


def test_confirmed_admin_public_read_update_reaches_provider_authorized(
    bucket_factory, user_factory
):
    from object_storage.models import AuditEvent, Bucket
    from object_storage.services.lifecycle import update_bucket_configuration

    bucket = bucket_factory(owner=user_factory(), state=Bucket.State.ACTIVE)
    previous = {
        "acl": "private",
        "storage_class": "Standard",
        "encryption": "AES256",
        "versioning": False,
        "lifecycle": {},
    }
    bucket.applied_config_snapshot = previous
    bucket.save(update_fields=("applied_config_snapshot", "updated_at"))
    provider = LifecycleProvider()

    update_bucket_configuration(
        bucket=bucket,
        actor=_admin(user_factory),
        desired={"acl": "public_read"},
        provider=provider,
        enqueue=False,
        reason="approved public documentation",
        bucket_name=bucket.name,
        confirmed=True,
    )

    bucket.refresh_from_db()
    assert bucket.applied_config_snapshot["acl"] == "public_read"
    options = provider.configuration_options[0]
    assert options["previous_configuration"].as_snapshot() == previous
    assert options["allow_public_read"] is True
    audit = AuditEvent.objects.get(
        action="storage.bucket.configuration.updated",
        target_id=str(bucket.pk),
    )
    assert audit.reason == "approved public documentation"
    assert audit.actor_id is not None


def test_aliyun_configuration_uses_sdk_versioning_and_lifecycle_models(monkeypatch):
    from object_storage.providers.aliyun import AliyunOssGateway
    from object_storage.providers.base import BucketConfiguration

    class FakeBucket:
        def __init__(self):
            self.calls = []

        def put_bucket_acl(self, acl):
            self.calls.append(("acl", acl))
            return SimpleNamespace(request_id="acl-request")

        def put_bucket_encryption(self, rule):
            self.calls.append(("encryption", rule))

        def put_bucket_versioning(self, config):
            self.calls.append(("versioning", config))

        def put_bucket_lifecycle(self, config):
            self.calls.append(("lifecycle", config))

    bucket = FakeBucket()
    gateway = AliyunOssGateway(
        access_key_id="management-ak",
        access_key_secret="management-sk",
        region="cn-hangzhou",
    )
    monkeypatch.setattr(gateway, "_bucket", lambda _name: bucket)

    gateway.update_bucket_configuration(
        bucket_name="managed-bucket",
        configuration=BucketConfiguration(
            versioning=True,
            lifecycle={
                "rules": [
                    {
                        "id": "expire-logs",
                        "prefix": "logs/",
                        "expiration_days": 30,
                    }
                ]
            },
        ),
    )

    versioning = next(value for action, value in bucket.calls if action == "versioning")
    lifecycle = next(value for action, value in bucket.calls if action == "lifecycle")
    assert type(versioning).__name__ == "BucketVersioningConfig"
    assert versioning.status == "Enabled"
    assert type(lifecycle).__name__ == "BucketLifecycle"
    assert lifecycle.rules[0].id == "expire-logs"
    assert lifecycle.rules[0].expiration.days == 30


def test_admin_manages_one_key_without_touching_another(
    access_key_factory, cloud_identity_factory, user_factory, monkeypatch
):
    from object_storage.models import AccessKey
    from object_storage.services import credentials

    identity = cloud_identity_factory(user=user_factory())
    first = access_key_factory(cloud_identity=identity, access_key_fingerprint="first")
    second = access_key_factory(
        cloud_identity=identity, access_key_fingerprint="second"
    )
    provider = LifecycleProvider()
    monkeypatch.setattr(
        credentials,
        "provider_access_key",
        lambda key: SimpleNamespace(
            pk=key.pk, cloud_identity=key.cloud_identity, access_key_id=key.pk
        ),
    )

    credentials.disable_access_key(
        access_key=first, actor=_admin(user_factory), provider=provider
    )
    credentials.revoke_access_key(
        access_key=second, actor=_admin(user_factory), provider=provider
    )

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.local_state == AccessKey.LocalState.DISABLED
    assert second.local_state == AccessKey.LocalState.RETIRED
    assert ("disable-key", first.pk) in provider.calls
    assert ("revoke-key", second.pk) in provider.calls
    assert not any(
        call[1] == second.pk for call in provider.calls if call[0] == "disable-key"
    )


@pytest.mark.parametrize("stale_action", ["disable", "enable"])
def test_revoke_cannot_overlap_active_key_mutation(
    access_key_factory, user_factory, monkeypatch, stale_action
):
    from object_storage.models import AccessKey
    from object_storage.services import credentials

    monkeypatch.setattr(
        "object_storage.services.platform.ensure_key_operations_allowed",
        lambda: None,
    )

    key = access_key_factory(
        local_state=(
            AccessKey.LocalState.DISABLED
            if stale_action == "enable"
            else AccessKey.LocalState.ACTIVE
        ),
        cloud_state=(
            AccessKey.CloudState.INACTIVE
            if stale_action == "enable"
            else AccessKey.CloudState.ACTIVE
        ),
    )
    actor = key.cloud_identity.user
    monkeypatch.setattr(
        credentials,
        "provider_access_key",
        lambda selected: SimpleNamespace(
            pk=selected.pk,
            cloud_identity=selected.cloud_identity,
            access_key_id=selected.pk,
        ),
    )

    class InterleavingProvider(LifecycleProvider):
        conflict_code = ""

        def _revoke_during_stale_action(self, selected):
            try:
                credentials.revoke_access_key(
                    access_key=AccessKey.objects.get(pk=selected.pk),
                    actor=actor,
                    provider=self,
                )
            except credentials.CredentialRotationError as error:
                self.conflict_code = error.error_code

        def deactivate_access_key(self, selected):
            self.calls.append(("disable-key", selected.pk))
            self._revoke_during_stale_action(selected)

        def activate_access_key(self, selected):
            self.calls.append(("enable-key", selected.pk))
            self._revoke_during_stale_action(selected)

    provider = InterleavingProvider()
    if stale_action == "disable":
        credentials.disable_access_key(
            access_key=key,
            actor=actor,
            provider=provider,
        )
    else:
        credentials.enable_access_key(
            access_key=key,
            actor=actor,
            provider=provider,
        )

    key.refresh_from_db()
    assert provider.conflict_code == "RESOURCE_OPERATION_IN_PROGRESS"
    assert key.cloud_state == (
        AccessKey.CloudState.INACTIVE
        if stale_action == "disable"
        else AccessKey.CloudState.ACTIVE
    )
    assert key.local_state == (
        AccessKey.LocalState.DISABLED
        if stale_action == "disable"
        else AccessKey.LocalState.ACTIVE
    )
    assert key.deleted_at is None
    assert key.operation_generation == 1
    assert key.operation_token == ""
    assert key.operation_type == ""


def test_suspension_disables_all_keys_but_preserves_identity_and_buckets(
    cloud_identity_factory,
    access_key_factory,
    bucket_factory,
    user_factory,
    monkeypatch,
):
    from object_storage.models import AccessKey, Bucket, CloudIdentity
    from object_storage.services.lifecycle import suspend_user_resources

    owner = user_factory()
    identity = cloud_identity_factory(user=owner, state=CloudIdentity.State.ACTIVE)
    first = access_key_factory(
        cloud_identity=identity, local_state=AccessKey.LocalState.ACTIVE
    )
    second = access_key_factory(
        cloud_identity=identity, local_state=AccessKey.LocalState.ACTIVE
    )
    bucket = bucket_factory(
        cloud_identity=identity, owner=owner, state=Bucket.State.ACTIVE
    )
    provider = LifecycleProvider()
    from object_storage.services import credentials

    monkeypatch.setattr(
        credentials,
        "provider_access_key",
        lambda key: SimpleNamespace(
            pk=key.pk, cloud_identity=key.cloud_identity, access_key_id=key.pk
        ),
    )

    suspend_user_resources(
        user=owner, actor=_admin(user_factory), provider=provider, enqueue=False
    )

    identity.refresh_from_db()
    first.refresh_from_db()
    second.refresh_from_db()
    assert identity.state == CloudIdentity.State.SUSPENDED
    assert first.local_state == AccessKey.LocalState.DISABLED
    assert second.local_state == AccessKey.LocalState.DISABLED
    assert Bucket.objects.filter(pk=bucket.pk).exists()
    assert CloudIdentity.objects.filter(pk=identity.pk).exists()


def test_suspension_schedules_async_key_disable_and_reactivation_does_not_restore_keys(
    cloud_identity_factory, access_key_factory, user_factory, monkeypatch
):
    from object_storage.models import AccessKey, CloudIdentity
    from object_storage.services.lifecycle import (
        _disable_identity_keys,
        LifecycleError,
        reactivate_user_resources,
        suspend_user_resources,
    )
    from object_storage.services import credentials

    owner = user_factory()
    identity = cloud_identity_factory(user=owner, state=CloudIdentity.State.ACTIVE)
    key = access_key_factory(
        cloud_identity=identity, local_state=AccessKey.LocalState.ACTIVE
    )
    scheduled = []
    monkeypatch.setattr(
        "object_storage.tasks.suspend_user_resources_task.delay",
        lambda identity_id, **kwargs: scheduled.append((identity_id, kwargs)),
    )
    admin = _admin(user_factory)

    suspend_user_resources(user=owner, actor=admin)
    identity.refresh_from_db()
    key.refresh_from_db()
    assert identity.state == CloudIdentity.State.SUSPENDED
    assert key.local_state == AccessKey.LocalState.ACTIVE
    assert len(scheduled) == 1
    assert scheduled[0][0] == identity.pk
    assert scheduled[0][1]["actor_id"] == admin.pk
    assert scheduled[0][1]["reason"] == ""
    assert scheduled[0][1]["operation_generation"] == 1
    assert scheduled[0][1]["operation_token"]

    with pytest.raises(LifecycleError, match="RESOURCE_OPERATION_IN_PROGRESS"):
        reactivate_user_resources(user=owner, actor=admin)

    monkeypatch.setattr(
        credentials,
        "provider_access_key",
        lambda selected: SimpleNamespace(
            pk=selected.pk,
            cloud_identity=selected.cloud_identity,
            access_key_id=selected.pk,
        ),
    )
    _disable_identity_keys(
        identity.pk,
        provider=LifecycleProvider(),
        actor=admin,
        operation_generation=scheduled[0][1]["operation_generation"],
        operation_token=scheduled[0][1]["operation_token"],
    )
    reactivate_user_resources(user=owner, actor=admin)
    key.refresh_from_db()
    assert key.local_state == AccessKey.LocalState.DISABLED


def test_completed_suspend_claim_rejects_duplicate_old_task(
    cloud_identity_factory, access_key_factory, user_factory, monkeypatch
):
    from object_storage.models import AccessKey, CloudIdentity
    from object_storage.services import credentials
    from object_storage.services.credentials import CredentialRotationError
    from object_storage.services.lifecycle import (
        _disable_identity_keys,
        suspend_user_resources,
    )

    owner = user_factory()
    identity = cloud_identity_factory(user=owner, state=CloudIdentity.State.ACTIVE)
    access_key_factory(
        cloud_identity=identity,
        local_state=AccessKey.LocalState.ACTIVE,
    )
    scheduled = []
    monkeypatch.setattr(
        "object_storage.tasks.suspend_user_resources_task.delay",
        lambda identity_id, **kwargs: scheduled.append((identity_id, kwargs)),
    )
    monkeypatch.setattr(
        credentials,
        "provider_access_key",
        lambda selected: SimpleNamespace(
            pk=selected.pk,
            cloud_identity=selected.cloud_identity,
            access_key_id=selected.pk,
        ),
    )
    admin = _admin(user_factory)
    suspend_user_resources(user=owner, actor=admin)
    operation = scheduled[0][1]
    provider = LifecycleProvider()
    _disable_identity_keys(
        identity.pk,
        provider=provider,
        actor=admin,
        operation_generation=operation["operation_generation"],
        operation_token=operation["operation_token"],
    )
    first_calls = list(provider.calls)

    with pytest.raises(
        CredentialRotationError, match="CREDENTIAL_OPERATION_SUPERSEDED"
    ):
        _disable_identity_keys(
            identity.pk,
            provider=provider,
            actor=admin,
            operation_generation=operation["operation_generation"],
            operation_token=operation["operation_token"],
        )

    assert provider.calls == first_calls


def test_suspended_identity_blocks_object_storage_member_permission(
    cloud_identity_factory, user_factory
):
    from types import SimpleNamespace

    from object_storage.models import CloudIdentity
    from object_storage.permissions import (
        IsActiveObjectStorageMember,
        ObjectStorageSuspended,
    )

    user = user_factory()
    cloud_identity_factory(user=user, state=CloudIdentity.State.SUSPENDED)
    user.object_storage_membership = SimpleNamespace(
        is_active=True, tenant=SimpleNamespace(enabled=True)
    )
    request = SimpleNamespace(user=user)

    with pytest.raises(ObjectStorageSuspended):
        IsActiveObjectStorageMember().has_permission(request, None)


def test_local_user_delete_is_protected_while_bucket_is_associated(
    bucket_factory, user_factory
):
    owner = user_factory()
    bucket = bucket_factory(owner=owner)

    with pytest.raises(IntegrityError):
        get_user_model().objects.filter(pk=owner.pk).delete()

    assert bucket.owner_id == owner.pk


def test_expired_bucket_cleanup_is_registered_daily():
    from core.periodic_registry import TASK_REGISTRY
    from object_storage import periodic_tasks

    TASK_REGISTRY.clear()
    periodic_tasks.register_periodic_tasks()

    entry = TASK_REGISTRY._entries["object-storage.bucket-deletion"]
    assert entry["task"] == "object_storage.delete_expired_buckets"
    assert entry["schedule"] == "15 3 * * *"
    assert entry["queue"] == "object_storage"
    recovery = TASK_REGISTRY._entries["object-storage.operation-recovery"]
    assert recovery["task"] == "object_storage.recover_expired_resource_operations"
    assert recovery["schedule"] == "*/5 * * * *"
    assert recovery["queue"] == "object_storage"
