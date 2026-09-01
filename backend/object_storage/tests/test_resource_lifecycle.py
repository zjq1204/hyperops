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
        reactivate_user_resources,
        suspend_user_resources,
    )

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
    assert scheduled == [(identity.pk, {"actor_id": admin.pk, "reason": ""})]

    key.local_state = AccessKey.LocalState.DISABLED
    key.cloud_state = AccessKey.CloudState.INACTIVE
    key.save(update_fields=("local_state", "cloud_state", "updated_at"))
    reactivate_user_resources(user=owner, actor=admin)
    key.refresh_from_db()
    assert key.local_state == AccessKey.LocalState.DISABLED


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
