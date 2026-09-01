from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.django_db


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.principal_exists = False
        self.cloud_keys = []
        self.buckets = {}
        self.create_errors = {}
        self.policy_errors = []
        self.configuration_errors = []
        self.configurations = []
        self.deleted_keys = []
        self.deleted_principals = []

    def find_or_create_personal_principal(self, identity):
        marker = f"hyperops:identity:{identity.pk}"
        self.calls.append(("principal", identity.ram_user_name, marker))
        created = not self.principal_exists
        self.principal_exists = True
        return SimpleNamespace(
            user_id="ram-user-id",
            user_name=identity.ram_user_name,
            marker=marker,
            created=created,
            request_id="request-principal",
        )

    def list_access_keys(self, identity):
        from object_storage.services.credentials import fingerprint_access_key

        self.calls.append(("list_keys", identity.ram_user_name))
        return SimpleNamespace(
            items=tuple(
                SimpleNamespace(
                    access_key_id=key.access_key_id,
                    fingerprint=fingerprint_access_key(key.access_key_id),
                    last_four=key.access_key_id[-4:],
                    status="active",
                )
                for key in self.cloud_keys
            )
        )

    def create_access_key(self, identity):
        self.calls.append(("create_key", identity.ram_user_name))
        key = SimpleNamespace(
            access_key_id=f"LTAI-batch-key-{len(self.cloud_keys) + 1}",
            secret_access_key="employee-secret",
            request_id="request-key",
        )
        self.cloud_keys.append(key)
        return key

    def delete_access_key(self, key):
        self.calls.append(("delete_key", key.access_key_id))
        self.deleted_keys.append(key.access_key_id)
        self.cloud_keys = [
            item for item in self.cloud_keys if item.access_key_id != key.access_key_id
        ]
        return SimpleNamespace(request_id="request-delete-key")

    def find_owned_bucket(self, bucket):
        self.calls.append(("find_bucket", bucket.name))
        marker = self.buckets.get(bucket.name, "")
        return SimpleNamespace(
            exists=bool(marker),
            owned=bool(marker) and marker == bucket.cloud_marker,
            marker=marker,
            request_id="request-find-bucket",
        )

    def create_owned_bucket(self, bucket, configuration=None):
        self.calls.append(("create_bucket", bucket.name))
        error = self.create_errors.get(bucket.business_name)
        if error is not None:
            raise error
        self.buckets[bucket.name] = bucket.cloud_marker
        self.update_bucket_configuration(bucket, configuration)
        return SimpleNamespace(created=True, request_id="request-create-bucket")

    def update_bucket_configuration(
        self,
        bucket,
        configuration,
        *,
        previous_configuration=None,
        allow_public_read=False,
    ):
        self.calls.append(("configure_bucket", bucket.name))
        if self.configuration_errors:
            raise self.configuration_errors.pop(0)
        self.configurations.append(
            (
                bucket.name,
                configuration,
                previous_configuration,
                allow_public_read,
            )
        )
        return SimpleNamespace(request_id="request-configure-bucket")

    def reconcile_object_policy(self, identity, buckets):
        names = tuple(sorted(bucket.name for bucket in buckets))
        self.calls.append(("policy", names))
        if self.policy_errors:
            raise self.policy_errors.pop(0)
        return SimpleNamespace(request_id="request-policy")

    def delete_personal_principal(self, identity):
        marker = f"hyperops:identity:{identity.pk}"
        self.calls.append(("delete_principal", identity.ram_user_name, marker))
        self.deleted_principals.append(identity.ram_user_name)
        self.principal_exists = False
        return SimpleNamespace(request_id="request-delete-principal")


@pytest.fixture(autouse=True)
def stable_object_storage_secret(settings):
    settings.SECRET_KEY = "object-storage-application-tests-stable-secret"


@pytest.fixture
def batch_context(
    user_factory,
    storage_resource_pool_factory,
    platform_object_storage_config,
    monkeypatch,
):
    from object_storage.services import applications
    from object_storage.services.applications import create_application_batch
    from object_storage.services.naming import render_bucket_name

    user = user_factory(username="batch-user")
    pool = storage_resource_pool_factory(enabled=True)
    monkeypatch.setattr(applications, "ensure_key_operations_allowed", lambda: None)

    def create(*, names=("Billing",), idempotency_key="batch-application"):
        items = []
        for index, business_name in enumerate(names, start=1):
            suffix = f"preview{index}"
            fields = {
                "business_name": business_name,
                "project": "platform",
                "environment": "test",
                "purpose": f"{business_name} data",
                "notes": "",
                "initial_suffix": suffix,
            }
            fields["rendered_bucket_name"] = render_bucket_name(
                template=platform_object_storage_config.naming_template,
                prefix="hyperops",
                user=user.get_username(),
                suffix=suffix,
                **{
                    key: fields[key]
                    for key in (
                        "business_name",
                        "project",
                        "environment",
                        "purpose",
                    )
                },
            )
            items.append(fields)
        return create_application_batch(
            user=user,
            resource_pool=pool,
            idempotency_key=idempotency_key,
            items=items,
            enqueue=False,
        )

    return user, pool, create


def test_first_batch_creates_principal_key_buckets_policy_and_delivery(
    batch_context, monkeypatch
):
    from object_storage.models import (
        AccessKey,
        ApplicationBatch,
        ApplicationItem,
        Bucket,
        CloudIdentity,
        DeliveryTicket,
    )
    from object_storage.services import applications

    user, _pool, create = batch_context
    batch = create(names=("Billing", "Archive"))
    provider = FakeProvider()
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)

    result = applications.execute_application_batch(
        batch.pk,
        execution_key="celery-task-1:0",
    )

    batch.refresh_from_db()
    identity = CloudIdentity.objects.get(user=user)
    assert result.pk == batch.pk
    assert batch.status == ApplicationBatch.Status.SUCCEEDED
    assert (batch.item_count, batch.pending_count, batch.success_count) == (2, 0, 2)
    assert set(batch.items.values_list("status", flat=True)) == {
        ApplicationItem.Status.SUCCEEDED
    }
    assert set(Bucket.objects.values_list("state", flat=True)) == {Bucket.State.ACTIVE}
    assert identity.state == CloudIdentity.State.ACTIVE
    assert AccessKey.objects.count() == 1
    assert DeliveryTicket.objects.filter(
        application_batch=batch,
        user=user,
        access_key=batch.issued_access_key,
    ).exists()
    assert [call[0] for call in provider.calls] == [
        "principal",
        "list_keys",
        "create_key",
        "find_bucket",
        "create_bucket",
        "configure_bucket",
        "find_bucket",
        "create_bucket",
        "configure_bucket",
        "find_bucket",
        "find_bucket",
        "policy",
    ]


def test_queued_application_rechecks_key_pause_before_cloud_key_creation(
    batch_context, monkeypatch
):
    from object_storage.models import AccessKey, ApplicationBatch
    from object_storage.services import applications
    from object_storage.services.platform import PlatformConfigurationError

    _user, _pool, create = batch_context
    batch = create()
    provider = FakeProvider()
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)
    monkeypatch.setattr(
        applications,
        "ensure_key_operations_allowed",
        lambda: (_ for _ in ()).throw(
            PlatformConfigurationError("KEY_OPERATIONS_PAUSED")
        ),
        raising=False,
    )

    applications.execute_application_batch(batch.pk)

    batch.refresh_from_db()
    assert batch.status == ApplicationBatch.Status.MANUAL_REQUIRED
    assert batch.error_code == "KEY_OPERATIONS_PAUSED"
    assert not AccessKey.objects.exists()
    assert "create_key" not in [call[0] for call in provider.calls]


def test_new_bucket_stores_only_desired_configuration_before_cloud_apply(
    batch_context,
):
    _user, _pool, create = batch_context

    bucket = create().items.get().bucket

    assert bucket.desired_config_snapshot == {
        "acl": "private",
        "storage_class": "Standard",
        "encryption": "AES256",
        "versioning": False,
        "lifecycle": {},
    }
    assert bucket.applied_config_snapshot == {}


def test_bucket_configuration_partial_failure_is_reconciled_on_owned_retry(
    batch_context, monkeypatch
):
    from object_storage.models import ApplicationItem, Bucket
    from object_storage.services import applications
    from object_storage.services.provider_errors import ObjectStorageProviderError

    _user, _pool, create = batch_context
    batch = create()
    provider = FakeProvider()
    provider.configuration_errors.append(
        ObjectStorageProviderError("PROVIDER_TIMEOUT", retryable=True)
    )
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)

    with pytest.raises(ObjectStorageProviderError, match="PROVIDER_TIMEOUT"):
        applications.execute_application_batch(batch.pk, execution_key="configure:0")

    bucket = batch.items.get().bucket
    bucket.refresh_from_db()
    assert bucket.name in provider.buckets
    assert bucket.state == Bucket.State.WAITING_RETRY
    assert bucket.desired_config_snapshot["acl"] == "private"
    assert bucket.applied_config_snapshot == {}
    assert bucket.config_error_code == "PROVIDER_TIMEOUT"
    assert batch.items.get().status == ApplicationItem.Status.WAITING_RETRY
    assert sum(call[0] == "create_bucket" for call in provider.calls) == 1

    provider.calls.clear()
    applications.execute_application_batch(batch.pk, execution_key="configure:1")

    bucket.refresh_from_db()
    assert bucket.state == Bucket.State.ACTIVE
    assert bucket.applied_config_snapshot == bucket.desired_config_snapshot
    assert bucket.config_error_code == ""
    assert "create_bucket" not in [call[0] for call in provider.calls]
    assert "configure_bucket" in [call[0] for call in provider.calls]


def test_non_temporary_initial_configuration_failure_remains_recoverable(
    batch_context, monkeypatch
):
    from object_storage.models import ApplicationBatch, ApplicationItem, Bucket
    from object_storage.services import applications
    from object_storage.services.policy import count_quota_consuming_buckets
    from object_storage.services.provider_errors import ObjectStorageProviderError

    user, _pool, create = batch_context
    batch = create()
    provider = FakeProvider()
    provider.configuration_errors.append(
        ObjectStorageProviderError("PROVIDER_PERMISSION_DENIED")
    )
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)

    with pytest.raises(
        ObjectStorageProviderError,
        match="BUCKET_CONFIGURATION_UPDATE_FAILED",
    ) as captured:
        applications.execute_application_batch(batch.pk, execution_key="configure:0")

    bucket = batch.items.get().bucket
    bucket.refresh_from_db()
    batch.refresh_from_db()
    assert captured.value.retryable is True
    assert bucket.name in provider.buckets
    assert bucket.state == Bucket.State.WAITING_RETRY
    assert bucket.applied_config_snapshot == {}
    assert bucket.config_error_code == "PROVIDER_PERMISSION_DENIED"
    assert batch.items.get().status == ApplicationItem.Status.WAITING_RETRY
    assert batch.status == ApplicationBatch.Status.RUNNING
    assert count_quota_consuming_buckets(user) == 1

    item = batch.items.get()
    item.status = ApplicationItem.Status.MANUAL_REQUIRED
    item.save(update_fields=("status", "updated_at"))
    batch.status = ApplicationBatch.Status.MANUAL_REQUIRED
    batch.save(update_fields=("status", "updated_at"))
    applications.retry_application_bucket_configuration(
        bucket.pk,
        enqueue=False,
    )
    item.refresh_from_db()
    batch.refresh_from_db()
    assert item.status == ApplicationItem.Status.WAITING_RETRY
    assert batch.status == ApplicationBatch.Status.PENDING

    provider.calls.clear()
    result = applications.execute_application_batch(
        batch.pk,
        execution_key="configure:1",
    )

    bucket.refresh_from_db()
    item = batch.items.get()
    result.refresh_from_db()
    assert bucket.state == Bucket.State.ACTIVE
    assert bucket.applied_config_snapshot == bucket.desired_config_snapshot
    assert bucket.config_error_code == ""
    assert item.status == ApplicationItem.Status.SUCCEEDED
    assert result.status == ApplicationBatch.Status.SUCCEEDED
    assert "create_bucket" not in [call[0] for call in provider.calls]
    assert "configure_bucket" in [call[0] for call in provider.calls]
    assert "policy" in [call[0] for call in provider.calls]


def test_initial_configuration_rollback_unknown_requires_manual_action_and_quota(
    batch_context, monkeypatch
):
    from object_storage.models import ApplicationBatch, ApplicationItem, Bucket
    from object_storage.services import applications
    from object_storage.services.policy import count_quota_consuming_buckets
    from object_storage.services.provider_errors import ObjectStorageProviderError

    user, _pool, create = batch_context
    batch = create()
    provider = FakeProvider()
    provider.configuration_errors.append(
        ObjectStorageProviderError("BUCKET_CONFIGURATION_ROLLBACK_FAILED")
    )
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)

    result = applications.execute_application_batch(
        batch.pk,
        execution_key="rollback-unknown",
    )

    bucket = result.items.get().bucket
    bucket.refresh_from_db()
    result.refresh_from_db()
    item = result.items.get()
    assert bucket.state == Bucket.State.WAITING_RETRY
    assert bucket.config_state == Bucket.ConfigurationState.UNKNOWN
    assert bucket.config_error_code == "BUCKET_CONFIGURATION_ROLLBACK_FAILED"
    assert item.status == ApplicationItem.Status.MANUAL_REQUIRED
    assert item.error_code == "BUCKET_CONFIGURATION_ROLLBACK_FAILED"
    assert result.status == ApplicationBatch.Status.MANUAL_REQUIRED
    assert count_quota_consuming_buckets(user) == 1


def test_permanent_item_failure_does_not_block_successful_sibling(
    batch_context, monkeypatch
):
    from object_storage.models import ApplicationBatch, ApplicationItem, DeliveryTicket
    from object_storage.services import applications
    from object_storage.services.provider_errors import ObjectStorageProviderError

    _user, _pool, create = batch_context
    batch = create(names=("Denied", "Working"))
    provider = FakeProvider()
    provider.create_errors["Denied"] = ObjectStorageProviderError(
        "PROVIDER_PERMISSION_DENIED"
    )
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)

    applications.execute_application_batch(batch.pk)

    batch.refresh_from_db()
    assert batch.status == ApplicationBatch.Status.PARTIALLY_SUCCEEDED
    assert (batch.success_count, batch.failed_count, batch.pending_count) == (1, 1, 0)
    assert list(batch.items.order_by("id").values_list("status", flat=True)) == [
        ApplicationItem.Status.FAILED,
        ApplicationItem.Status.SUCCEEDED,
    ]
    assert DeliveryTicket.objects.filter(application_batch=batch).exists()
    assert ("create_bucket", batch.items.order_by("id").last().bucket.name) in (
        provider.calls
    )


def test_temporary_item_failure_is_saved_after_siblings_are_processed(
    batch_context, monkeypatch
):
    from object_storage.models import ApplicationBatch, ApplicationItem, DeliveryTicket
    from object_storage.services import applications
    from object_storage.services.provider_errors import ObjectStorageProviderError

    _user, _pool, create = batch_context
    batch = create(names=("Retry", "Working"))
    provider = FakeProvider()
    provider.create_errors["Retry"] = ObjectStorageProviderError(
        "PROVIDER_TIMEOUT", retryable=True
    )
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)

    with pytest.raises(ObjectStorageProviderError, match="PROVIDER_TIMEOUT"):
        applications.execute_application_batch(batch.pk)

    batch.refresh_from_db()
    assert batch.status == ApplicationBatch.Status.RUNNING
    assert (batch.success_count, batch.failed_count, batch.pending_count) == (1, 0, 1)
    assert list(batch.items.order_by("id").values_list("status", flat=True)) == [
        ApplicationItem.Status.WAITING_RETRY,
        ApplicationItem.Status.SUCCEEDED,
    ]
    assert DeliveryTicket.objects.filter(application_batch=batch).exists()


def test_policy_retry_reuses_key_and_bucket_without_recreating_either(
    batch_context, monkeypatch
):
    from object_storage.models import AccessKey, ApplicationItem, DeliveryTicket
    from object_storage.services import applications
    from object_storage.services.provider_errors import ObjectStorageProviderError

    _user, _pool, create = batch_context
    batch = create()
    provider = FakeProvider()
    provider.policy_errors.append(
        ObjectStorageProviderError("PROVIDER_TIMEOUT", retryable=True)
    )
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)

    with pytest.raises(ObjectStorageProviderError, match="PROVIDER_TIMEOUT"):
        applications.execute_application_batch(batch.pk, execution_key="task:0")

    item = batch.items.get()
    item.refresh_from_db()
    assert item.status == ApplicationItem.Status.WAITING_RETRY
    assert item.current_stage == "POLICY_APPLYING"
    assert AccessKey.objects.count() == 1
    assert not DeliveryTicket.objects.filter(application_batch=batch).exists()
    provider.calls.clear()

    applications.execute_application_batch(batch.pk, execution_key="task:1")

    assert "create_key" not in [call[0] for call in provider.calls]
    assert "create_bucket" not in [call[0] for call in provider.calls]
    assert DeliveryTicket.objects.filter(application_batch=batch).exists()


def test_encryption_failure_deletes_exact_cloud_key_and_requires_manual_action(
    batch_context, monkeypatch
):
    from object_storage.models import AccessKey, ApplicationBatch, ApplicationItem
    from object_storage.services import applications

    _user, _pool, create = batch_context
    batch = create()
    provider = FakeProvider()
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)
    monkeypatch.setattr(
        applications,
        "encrypt_issued_access_key",
        lambda _issued: (_ for _ in ()).throw(RuntimeError("encrypt failed")),
    )

    applications.execute_application_batch(batch.pk)

    batch.refresh_from_db()
    assert batch.status == ApplicationBatch.Status.MANUAL_REQUIRED
    assert set(batch.items.values_list("status", flat=True)) == {
        ApplicationItem.Status.MANUAL_REQUIRED
    }
    assert provider.deleted_keys == ["LTAI-batch-key-1"]
    assert not AccessKey.objects.exists()


def test_full_failure_cancel_deletes_undelivered_key_and_empty_principal(
    batch_context, monkeypatch
):
    from object_storage.models import AccessKey, ApplicationBatch, ApplicationItem
    from object_storage.services import applications
    from object_storage.services.provider_errors import ObjectStorageProviderError

    _user, _pool, create = batch_context
    batch = create(names=("Denied",))
    provider = FakeProvider()
    provider.create_errors["Denied"] = ObjectStorageProviderError(
        "PROVIDER_PERMISSION_DENIED"
    )
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)
    applications.execute_application_batch(batch.pk)

    cancelled = applications.cancel_application_batch(batch.pk)

    assert cancelled.status == ApplicationBatch.Status.CANCELLED
    assert set(cancelled.items.values_list("status", flat=True)) == {
        ApplicationItem.Status.CANCELLED
    }
    assert not AccessKey.objects.filter(
        cloud_identity__user=cancelled.applicant
    ).exists()
    assert provider.deleted_keys == ["LTAI-batch-key-1"]
    assert provider.deleted_principals


def test_later_full_failure_cancel_keeps_prior_success_resources_and_principal(
    batch_context, monkeypatch
):
    from object_storage.models import ApplicationBatch, ApplicationItem, Bucket
    from object_storage.services import applications
    from object_storage.services.provider_errors import ObjectStorageProviderError

    _user, _pool, create = batch_context
    provider = FakeProvider()
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)
    first = create(names=("AlreadyWorking",), idempotency_key="first")
    applications.execute_application_batch(first.pk)
    previous_bucket = first.items.get().bucket
    provider.create_errors["DeniedLater"] = ObjectStorageProviderError(
        "PROVIDER_PERMISSION_DENIED"
    )
    second = create(names=("DeniedLater",), idempotency_key="second")

    applications.execute_application_batch(second.pk)
    applications.cancel_application_batch(second.pk)

    first.refresh_from_db()
    second.refresh_from_db()
    previous_bucket.refresh_from_db()
    assert first.status == ApplicationBatch.Status.SUCCEEDED
    assert second.status == ApplicationBatch.Status.CANCELLED
    assert second.items.get().status == ApplicationItem.Status.CANCELLED
    assert previous_bucket.state == Bucket.State.ACTIVE
    assert provider.deleted_principals == []
    assert provider.principal_exists is True


def test_cancel_with_cloud_bucket_keeps_item_manual_and_resource(
    batch_context, monkeypatch
):
    from object_storage.models import ApplicationBatch, ApplicationItem, Bucket
    from object_storage.services import applications
    from object_storage.services.provider_errors import ObjectStorageProviderError

    _user, _pool, create = batch_context
    batch = create()
    provider = FakeProvider()
    provider.policy_errors.append(
        ObjectStorageProviderError("PROVIDER_PERMISSION_DENIED")
    )
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)

    applications.execute_application_batch(batch.pk)
    cancelled = applications.cancel_application_batch(batch.pk)

    item = cancelled.items.get()
    item.bucket.refresh_from_db()
    assert cancelled.status == ApplicationBatch.Status.MANUAL_REQUIRED
    assert item.status == ApplicationItem.Status.MANUAL_REQUIRED
    assert item.bucket.state == Bucket.State.ACTIVE
    assert provider.deleted_principals == []


def test_repeated_execution_for_completed_batch_has_no_new_attempt_or_mutation(
    batch_context, monkeypatch
):
    from object_storage.services import applications

    _user, _pool, create = batch_context
    batch = create()
    provider = FakeProvider()
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)

    applications.execute_application_batch(batch.pk, execution_key="same-task:0")
    attempt_count = batch.items.get().attempts.count()
    provider.calls.clear()
    result = applications.execute_application_batch(
        batch.pk, execution_key="same-task:0"
    )

    assert result.status == "succeeded"
    assert batch.items.get().attempts.count() == attempt_count
    assert provider.calls == []


def test_expired_running_lease_has_explicit_recovery_path(batch_context, monkeypatch):
    from datetime import timedelta

    from django.utils import timezone

    from object_storage.models import ApplicationBatch, ApplicationItem
    from object_storage.services import applications

    _user, _pool, create = batch_context
    batch = create()
    batch, claimed, owner_token = applications._claim_batch(
        batch.pk, "possibly-slow-worker"
    )
    assert claimed is True
    batch.refresh_from_db()
    assert owner_token
    assert batch.owner_token == owner_token
    assert batch.running_task_id == "possibly-slow-worker"
    assert (
        applications._claim_item(
            batch.items.get().pk,
            "possibly-slow-worker",
            owner_token,
        )
        is not None
    )
    batch.run_lease_until = timezone.now() - timedelta(seconds=1)
    batch.save(update_fields=("run_lease_until",))
    provider = FakeProvider()
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)

    recovered, recovery_generation = applications.recover_expired_application_claim(
        batch.pk,
        now=timezone.now(),
    )

    recovered.refresh_from_db()
    assert recovery_generation == recovered.claim_version
    item = recovered.items.get()
    assert recovered.status == ApplicationBatch.Status.RUNNING
    assert recovered.running_task_id == ""
    assert recovered.owner_token == ""
    assert recovered.run_lease_until is None
    assert item.status == ApplicationItem.Status.WAITING_RETRY
    assert item.attempts.get().error_code == "CLAIM_EXPIRED"
    assert item.events.filter(stage="CLAIM_RECOVERY").exists()

    result = applications.execute_application_batch(
        batch.pk,
        execution_key="replacement-worker",
    )

    assert result.status == ApplicationBatch.Status.SUCCEEDED
    assert result.running_task_id == ""


def test_claim_recovery_returns_no_generation_when_claim_is_still_active(
    batch_context,
):
    from datetime import timedelta

    from django.utils import timezone

    from object_storage.services import applications

    _user, _pool, create = batch_context
    batch = create()
    claimed_batch, claimed, owner_token = applications._claim_batch(
        batch.pk,
        "active-worker",
    )
    assert claimed is True
    claimed_batch.run_lease_until = timezone.now() + timedelta(minutes=1)
    claimed_batch.save(update_fields=("run_lease_until",))

    recovered, recovery_generation = applications.recover_expired_application_claim(
        batch.pk,
        now=timezone.now(),
    )

    assert recovered.pk == batch.pk
    assert recovered.owner_token == owner_token
    assert recovery_generation is None


def test_stale_final_failure_cannot_overwrite_replacement_claim(batch_context):
    from object_storage.models import ApplicationBatch, ApplicationItem
    from object_storage.services import applications
    from object_storage.services.provider_errors import ObjectStorageProviderError

    _user, _pool, create = batch_context
    batch = create()
    old_claim, claimed, old_owner_token = applications._claim_batch(
        batch.pk,
        "old-worker",
    )
    assert claimed is True
    old_generation = old_claim.claim_version
    assert applications._release_batch_lease(batch.pk, old_owner_token) == 1

    replacement, claimed, replacement_token = applications._claim_batch(
        batch.pk,
        "replacement-worker",
    )
    assert claimed is True
    error = ObjectStorageProviderError("PROVIDER_TIMEOUT", retryable=True)

    result = applications.mark_batch_manual_required(
        batch.pk,
        error,
        expected_claim_version=old_generation,
    )

    result.refresh_from_db()
    item = ApplicationItem.objects.get(batch=batch)
    assert result.status == ApplicationBatch.Status.RUNNING
    assert result.claim_version == replacement.claim_version
    assert result.running_task_id == "replacement-worker"
    assert result.owner_token == replacement_token
    assert item.status == ApplicationItem.Status.PENDING


def test_claim_recovery_moves_unstarted_items_to_waiting_retry(
    batch_context, monkeypatch
):
    from datetime import timedelta

    from django.utils import timezone

    from object_storage.models import ApplicationItem, Bucket
    from object_storage.services import applications

    _user, _pool, create = batch_context
    batch = create()
    batch, claimed, _owner_token = applications._claim_batch(
        batch.pk,
        "expired-before-item-claim",
    )
    assert claimed is True
    batch.run_lease_until = timezone.now() - timedelta(seconds=1)
    batch.save(update_fields=("run_lease_until",))
    provider = FakeProvider()
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)

    recovered, recovery_generation = applications.recover_expired_application_claim(
        batch.pk,
        now=timezone.now(),
    )

    item = recovered.items.get()
    assert recovery_generation == recovered.claim_version
    item.bucket.refresh_from_db()
    assert item.status == ApplicationItem.Status.WAITING_RETRY
    assert item.bucket.state == Bucket.State.WAITING_RETRY
    assert item.events.filter(stage="CLAIM_RECOVERY", result="recovered").exists()


@pytest.mark.django_db(transaction=True)
def test_claim_recovery_provider_check_runs_outside_atomic(batch_context):
    from datetime import timedelta

    from django.db import transaction
    from django.utils import timezone

    from object_storage.services import applications

    _user, _pool, create = batch_context
    batch = create()
    batch, claimed, _owner_token = applications._claim_batch(
        batch.pk,
        "expired-atomic-check",
    )
    assert claimed is True
    batch.run_lease_until = timezone.now() - timedelta(seconds=1)
    batch.save(update_fields=("run_lease_until",))
    item = batch.items.get()
    assert item.bucket_id is not None
    assert item.status == "pending"

    class AtomicCheckingProvider(FakeProvider):
        atomic_states = []

        def find_owned_bucket(self, bucket):
            self.atomic_states.append(transaction.get_connection().in_atomic_block)
            return super().find_owned_bucket(bucket)

    provider = AtomicCheckingProvider()
    recovered, generation = applications.recover_expired_application_claim(
        batch.pk,
        now=timezone.now(),
        provider=provider,
    )
    assert generation == recovered.claim_version
    assert "find_bucket" in [call[0] for call in provider.calls]
    assert provider.atomic_states == [False]


@pytest.mark.django_db(transaction=True)
def test_cancel_provider_cleanup_runs_outside_atomic(batch_context, monkeypatch):
    from django.db import transaction

    from object_storage.services import applications
    from object_storage.services.provider_errors import ObjectStorageProviderError

    _user, _pool, create = batch_context
    batch = create(names=("Denied",))

    class AtomicCheckingProvider(FakeProvider):
        atomic_states = []

        def _outside_atomic(self):
            self.atomic_states.append(transaction.get_connection().in_atomic_block)

        def find_owned_bucket(self, bucket):
            self._outside_atomic()
            return super().find_owned_bucket(bucket)

        def list_access_keys(self, identity):
            self._outside_atomic()
            return super().list_access_keys(identity)

        def delete_access_key(self, key):
            self._outside_atomic()
            return super().delete_access_key(key)

        def delete_personal_principal(self, identity):
            self._outside_atomic()
            return super().delete_personal_principal(identity)

    setup_provider = FakeProvider()
    setup_provider.create_errors["Denied"] = ObjectStorageProviderError(
        "PROVIDER_PERMISSION_DENIED"
    )
    monkeypatch.setattr(
        applications, "get_provider_for_pool", lambda _pool: setup_provider
    )
    applications.execute_application_batch(batch.pk)

    provider = AtomicCheckingProvider()
    provider.principal_exists = setup_provider.principal_exists
    provider.cloud_keys = list(setup_provider.cloud_keys)
    provider.buckets = dict(setup_provider.buckets)
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)
    applications.cancel_application_batch(batch.pk)
    call_names = [call[0] for call in provider.calls]
    assert "find_bucket" in call_names
    assert "list_keys" in call_names
    assert "delete_key" in call_names
    assert "delete_principal" in call_names
    assert provider.atomic_states == [False, False, False, False]


def test_claim_recovery_marks_terminal_state_without_delivery_manual(
    batch_context,
):
    from datetime import timedelta

    from django.utils import timezone

    from object_storage.models import (
        ApplicationBatch,
        ApplicationAttempt,
        ApplicationItem,
    )
    from object_storage.services import applications

    _user, _pool, create = batch_context
    batch = create()
    batch, claimed, owner_token = applications._claim_batch(
        batch.pk,
        "expired-before-delivery",
    )
    assert claimed is True
    item, attempt = applications._claim_item(
        batch.items.get().pk,
        "expired-before-delivery",
        owner_token,
    )
    item.status = ApplicationItem.Status.SUCCEEDED
    item.save(update_fields=("status", "updated_at"))
    applications._finish_attempt(attempt, ApplicationAttempt.Status.SUCCEEDED)
    batch.run_lease_until = timezone.now() - timedelta(seconds=1)
    batch.save(update_fields=("run_lease_until",))

    recovered, recovery_generation = applications.recover_expired_application_claim(
        batch.pk,
        now=timezone.now(),
    )

    item.refresh_from_db()
    assert recovery_generation == recovered.claim_version
    assert recovered.status == ApplicationBatch.Status.MANUAL_REQUIRED
    assert recovered.error_code == "CLAIM_EXPIRED_TERMINAL_STATE_UNKNOWN"
    assert item.status == ApplicationItem.Status.SUCCEEDED
    assert recovered.running_task_id == ""
    assert recovered.owner_token == ""


def test_stale_worker_cannot_write_success_policy_or_delivery_after_claim_switch(
    batch_context, monkeypatch
):
    from datetime import timedelta

    from django.utils import timezone

    from object_storage.models import (
        ApplicationBatch,
        ApplicationItem,
        Bucket,
        DeliveryTicket,
    )
    from object_storage.services import applications

    _user, _pool, create = batch_context
    batch = create()
    provider = FakeProvider()
    original_create_bucket = provider.create_owned_bucket
    switched_claim = {}

    def create_bucket_and_switch_claim(bucket, configuration):
        result = original_create_bucket(bucket, configuration)
        ApplicationBatch.objects.filter(pk=batch.pk).update(
            run_lease_until=timezone.now() - timedelta(seconds=1)
        )
        applications.recover_expired_application_claim(
            batch.pk,
            now=timezone.now(),
            provider=provider,
        )
        replacement, claimed, replacement_token = applications._claim_batch(
            batch.pk,
            "replacement-worker",
        )
        assert claimed is True
        switched_claim.update(
            batch=replacement,
            owner_token=replacement_token,
        )
        return result

    provider.create_owned_bucket = create_bucket_and_switch_claim
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)
    stale_claim_error = getattr(applications, "StaleApplicationClaim", RuntimeError)

    with pytest.raises(stale_claim_error, match="STALE_APPLICATION_CLAIM"):
        applications.execute_application_batch(
            batch.pk,
            execution_key="expired-worker",
        )

    batch.refresh_from_db()
    item = batch.items.get()
    item.bucket.refresh_from_db()
    assert batch.status == ApplicationBatch.Status.RUNNING
    assert batch.running_task_id == "replacement-worker"
    assert batch.owner_token == switched_claim["owner_token"]
    assert item.status == ApplicationItem.Status.WAITING_RETRY
    assert item.bucket.state == Bucket.State.WAITING_RETRY
    assert not any(call[0] == "policy" for call in provider.calls)
    assert not item.events.filter(stage="POLICY_APPLYING", result="succeeded").exists()
    assert not DeliveryTicket.objects.filter(application_batch=batch).exists()

    applications._release_batch_lease(batch.pk, switched_claim["owner_token"])
    result = applications.execute_application_batch(
        batch.pk,
        execution_key="replacement-worker-retry",
    )

    assert result.status == ApplicationBatch.Status.SUCCEEDED
    assert sum(call[0] == "create_bucket" for call in provider.calls) == 1
    assert DeliveryTicket.objects.filter(application_batch=batch).exists()


def test_stale_worker_deletes_exact_key_created_before_post_call_fence(
    batch_context, monkeypatch
):
    from object_storage.models import AccessKey, ApplicationBatch, DeliveryTicket
    from object_storage.services import applications

    _user, _pool, create = batch_context
    batch = create()
    provider = FakeProvider()
    original_create_key = provider.create_access_key

    def create_key_and_switch_claim(identity):
        issued = original_create_key(identity)
        ApplicationBatch.objects.filter(pk=batch.pk).update(
            running_task_id="replacement-worker",
            owner_token="replacement-owner-token",
        )
        return issued

    provider.create_access_key = create_key_and_switch_claim
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)

    with pytest.raises(applications.StaleApplicationClaim):
        applications.execute_application_batch(batch.pk, execution_key="stale-worker")

    batch.refresh_from_db()
    assert provider.deleted_keys == ["LTAI-batch-key-1"]
    assert provider.cloud_keys == []
    assert AccessKey.objects.count() == 0
    assert batch.issued_access_key_id is None
    assert not DeliveryTicket.objects.filter(application_batch=batch).exists()


def test_stale_key_cleanup_failure_marks_manual_without_deleting_other_key(
    batch_context, monkeypatch
):
    from object_storage.models import (
        AccessKey,
        ApplicationBatch,
        ApplicationItem,
        AuditEvent,
        DeliveryTicket,
    )
    from object_storage.services import applications
    from object_storage.services.credentials import fingerprint_access_key

    _user, _pool, create = batch_context
    batch = create()
    provider = FakeProvider()
    original_create_key = provider.create_access_key
    existing_key = SimpleNamespace(
        access_key_id="LTAI-existing-key",
        secret_access_key="existing-secret",
        request_id="existing-request",
    )

    def create_key_and_switch_claim(identity):
        issued = original_create_key(identity)
        provider.cloud_keys.append(existing_key)
        ApplicationBatch.objects.filter(pk=batch.pk).update(
            running_task_id="replacement-worker",
            owner_token="replacement-owner-token",
        )
        return issued

    def fail_exact_delete(key):
        provider.calls.append(("delete_key", key.access_key_id))
        raise RuntimeError("delete result unknown")

    provider.create_access_key = create_key_and_switch_claim
    provider.delete_access_key = fail_exact_delete
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)

    with pytest.raises(applications.StaleApplicationClaim):
        applications.execute_application_batch(batch.pk, execution_key="stale-worker")

    batch.refresh_from_db()
    item = batch.items.get()
    audit = AuditEvent.objects.get(
        action="storage.application.stale_claim_key_cleanup_uncertain"
    )
    assert batch.status == ApplicationBatch.Status.MANUAL_REQUIRED
    assert batch.error_code == "STALE_CLAIM_KEY_CLEANUP_UNCERTAIN"
    assert batch.running_task_id == ""
    assert batch.owner_token == ""
    assert item.status == ApplicationItem.Status.MANUAL_REQUIRED
    assert item.error_code == "STALE_CLAIM_KEY_CLEANUP_UNCERTAIN"
    assert provider.calls.count(("delete_key", "LTAI-batch-key-1")) == 1
    assert [key.access_key_id for key in provider.cloud_keys] == [
        "LTAI-batch-key-1",
        existing_key.access_key_id,
    ]
    assert AccessKey.objects.count() == 0
    assert not DeliveryTicket.objects.filter(application_batch=batch).exists()
    assert audit.safe_metadata == {
        "application_id": batch.pk,
        "error_code": "STALE_CLAIM_KEY_CLEANUP_UNCERTAIN",
        "fingerprint": fingerprint_access_key("LTAI-batch-key-1"),
        "last_four": "ey-1",
    }


def test_unexpired_running_lease_is_still_a_worker_noop(batch_context, monkeypatch):
    from datetime import timedelta

    from django.utils import timezone

    from object_storage.models import ApplicationBatch
    from object_storage.services import applications

    _user, _pool, create = batch_context
    batch = create()
    batch.status = ApplicationBatch.Status.RUNNING
    batch.running_task_id = "active-worker"
    batch.run_lease_until = timezone.now() + timedelta(minutes=1)
    batch.save(update_fields=("status", "running_task_id", "run_lease_until"))
    monkeypatch.setattr(
        applications,
        "get_provider_for_pool",
        lambda _pool: (_ for _ in ()).throw(AssertionError("provider not called")),
    )

    result = applications.execute_application_batch(
        batch.pk,
        execution_key="replacement-worker",
    )

    assert result.status == ApplicationBatch.Status.RUNNING
    assert result.running_task_id == "active-worker"


def test_cancel_first_makes_worker_terminal_noop(batch_context, monkeypatch):
    from object_storage.services import applications

    _user, _pool, create = batch_context
    batch = create()
    provider = FakeProvider()
    monkeypatch.setattr(applications, "get_provider_for_pool", lambda _pool: provider)

    cancelled = applications.cancel_application_batch(batch.pk)
    provider.calls.clear()
    result = applications.execute_application_batch(
        batch.pk,
        execution_key="worker-after-cancel",
    )

    assert cancelled.status == "cancelled"
    assert result.status == "cancelled"
    assert batch.items.get().attempts.count() == 0
    assert provider.calls == []


def test_worker_claim_first_makes_cancel_report_in_progress(batch_context):
    from datetime import timedelta

    from django.utils import timezone

    from object_storage.models import ApplicationBatch, ApplicationItem
    from object_storage.services.applications import (
        ApplicationServiceError,
        cancel_application_batch,
    )

    _user, _pool, create = batch_context
    batch = create()
    batch.status = ApplicationBatch.Status.RUNNING
    batch.running_task_id = "claimed-worker"
    batch.run_lease_until = timezone.now() + timedelta(minutes=1)
    batch.save(update_fields=("status", "running_task_id", "run_lease_until"))

    with pytest.raises(ApplicationServiceError, match="CANCEL_IN_PROGRESS"):
        cancel_application_batch(batch.pk)

    batch.refresh_from_db()
    assert batch.status == ApplicationBatch.Status.RUNNING
    assert batch.running_task_id == "claimed-worker"
    assert batch.items.get().status == ApplicationItem.Status.PENDING


def test_provider_retryability_uses_stable_temporary_code_classification():
    from object_storage.services.applications import is_retryable_provider_error
    from object_storage.services.provider_errors import ObjectStorageProviderError

    assert is_retryable_provider_error(
        ObjectStorageProviderError("PROVIDER_TIMEOUT", retryable=True)
    )
    assert not is_retryable_provider_error(
        ObjectStorageProviderError("PROVIDER_PERMISSION_DENIED")
    )
