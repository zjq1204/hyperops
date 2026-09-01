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

    def create_owned_bucket(self, bucket):
        self.calls.append(("create_bucket", bucket.name))
        error = self.create_errors.get(bucket.business_name)
        if error is not None:
            raise error
        self.buckets[bucket.name] = bucket.cloud_marker
        return SimpleNamespace(created=True, request_id="request-create-bucket")

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
):
    from object_storage.services.applications import create_application_batch
    from object_storage.services.naming import render_bucket_name

    user = user_factory(username="batch-user")
    pool = storage_resource_pool_factory(enabled=True)

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
        "find_bucket",
        "create_bucket",
        "find_bucket",
        "find_bucket",
        "policy",
    ]


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


def test_expired_running_lease_fails_closed_without_cloud_mutation(
    batch_context, monkeypatch
):
    from datetime import timedelta

    from django.utils import timezone

    from object_storage.models import ApplicationBatch
    from object_storage.services import applications

    _user, _pool, create = batch_context
    batch = create()
    batch.status = ApplicationBatch.Status.RUNNING
    batch.running_task_id = "possibly-slow-worker"
    batch.run_lease_until = timezone.now() - timedelta(seconds=1)
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
    assert result.running_task_id == "possibly-slow-worker"
    assert not batch.items.get().attempts.exists()


def test_provider_retryability_uses_stable_temporary_code_classification():
    from object_storage.services.applications import is_retryable_provider_error
    from object_storage.services.provider_errors import ObjectStorageProviderError

    assert is_retryable_provider_error(
        ObjectStorageProviderError("PROVIDER_TIMEOUT", retryable=True)
    )
    assert not is_retryable_provider_error(
        ObjectStorageProviderError("PROVIDER_PERMISSION_DENIED")
    )
