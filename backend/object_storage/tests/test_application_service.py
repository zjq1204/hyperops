from types import SimpleNamespace
from datetime import timedelta

import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def stable_object_storage_secret(settings):
    settings.SECRET_KEY = "object-storage-tests-stable-root-secret"


class FakeProviderError(RuntimeError):
    def __init__(self, code, *, retryable=False):
        self.error_code = code
        self.retryable = retryable
        self.request_id = f"request-{code.lower()}"
        super().__init__(code)


class FakeProvider:
    def __init__(self):
        self.calls = []
        self.keys = []
        self.fail_policy = False
        self.fail_encryption = False
        self.fail_create_key = False
        self.reconciled_buckets = set()
        self.bucket_exists = set()

    def find_or_create_personal_principal(self, identity):
        self.calls.append(("principal", identity.ram_user_name))
        return SimpleNamespace(
            user_id="ram-user-id",
            user_name=identity.ram_user_name,
            created=True,
            request_id="request-principal",
        )

    def create_owned_bucket(self, bucket):
        self.calls.append(("bucket", bucket.name))
        if bucket.name in self.bucket_exists:
            raise FakeProviderError("BUCKET_NAME_CONFLICT")
        self.bucket_exists.add(bucket.name)
        return SimpleNamespace(created=True, request_id="request-bucket")

    def find_owned_bucket(self, bucket):
        self.calls.append(("reconcile_bucket", bucket.name))
        return bucket.name in self.reconciled_buckets

    def reconcile_object_policy(self, identity, buckets):
        self.calls.append(("policy", tuple(sorted(bucket.name for bucket in buckets))))
        if self.fail_policy:
            raise FakeProviderError("PROVIDER_PERMISSION_DENIED")
        return {"request_id": "request-policy"}

    def create_access_key(self, identity):
        self.calls.append(("create_key", identity.ram_user_name))
        if self.fail_create_key:
            raise FakeProviderError("PROVIDER_OPERATION_FAILED")
        key = SimpleNamespace(
            access_key_id=f"LTAI-key-{len(self.keys) + 1}",
            secret_access_key="employee-secret",
            request_id="request-key",
        )
        self.keys.append(key)
        return key

    def list_access_keys(self, identity):
        self.calls.append(("list_keys", identity.ram_user_name))
        return tuple(
            SimpleNamespace(
                access_key_id=key.access_key_id,
                fingerprint=applications_fingerprint(key.access_key_id),
                last_four=key.access_key_id[-4:],
                status="active",
            )
            for key in self.keys
        )

    def delete_access_key(self, key):
        self.calls.append(("delete_key", key.access_key_id))
        return {"request_id": "request-delete-key"}

    def inspect_bucket_emptiness(self, bucket):
        return SimpleNamespace(is_empty=True, request_id="request-empty")

    def deactivate_access_key(self, key):
        self.calls.append(("deactivate_key", key.access_key_id))
        return {"request_id": "request-deactivate"}


@pytest.fixture
def application_context(storage_membership_factory, storage_resource_pool_factory):
    membership = storage_membership_factory()
    pool = storage_resource_pool_factory(
        tenant=membership.tenant,
        enabled=True,
    )
    return membership, pool


def test_first_application_creates_principal_bucket_policy_and_key(
    application_context, monkeypatch
):
    from object_storage.models import (
        StorageApplication,
        StorageBucket,
        StorageAccessKey,
    )
    from object_storage.services import applications

    membership, pool = application_context
    provider = FakeProvider()
    monkeypatch.setattr(
        applications, "get_provider_for_pool", lambda selected: provider
    )
    application = applications.create_application(
        membership=membership,
        resource_pool=pool,
        action_type=StorageApplication.ActionType.FIRST_BUCKET_AND_CREDENTIAL,
        idempotency_key="first-application",
        request_fields={
            "project": "billing",
            "environment": "test",
            "purpose": "exports",
        },
        enqueue=False,
    )

    result = applications.execute_application(application.pk)

    assert result.status == StorageApplication.Status.DELIVERY_READY
    assert StorageBucket.objects.filter(owner=membership, state="active").count() == 1
    assert (
        StorageAccessKey.objects.filter(cloud_identity__membership=membership).count()
        == 1
    )
    assert [call[0] for call in provider.calls] == [
        "reconcile_bucket",
        "bucket",
        "principal",
        "policy",
        "list_keys",
        "create_key",
    ]
    assert list(result.events.values_list("stage", flat=True)) == [
        "IDENTITY_CHECKING",
        "QUOTA_CHECKING",
        "BUCKET_CREATING",
        "PRINCIPAL_BINDING",
        "POLICY_APPLYING",
        "KEY_CREATING",
        "SECRET_ENCRYPTING",
        "DELIVERY_CREATING",
    ]


def test_additional_bucket_reuses_principal_and_active_keys(
    application_context, monkeypatch, storage_membership_factory
):
    from object_storage.models import (
        StorageApplication,
        StorageBucket,
        StorageCloudIdentity,
    )
    from object_storage.services import applications

    membership, pool = application_context
    provider = FakeProvider()
    monkeypatch.setattr(
        applications, "get_provider_for_pool", lambda selected: provider
    )
    first = applications.create_application(
        membership=membership,
        resource_pool=pool,
        action_type=StorageApplication.ActionType.FIRST_BUCKET_AND_CREDENTIAL,
        idempotency_key="first-for-additional",
        request_fields={"project": "one", "environment": "test", "purpose": "data"},
        enqueue=False,
    )
    applications.execute_application(first.pk)
    provider.calls.clear()
    second = applications.create_application(
        membership=membership,
        resource_pool=pool,
        action_type=StorageApplication.ActionType.ADD_BUCKET,
        idempotency_key="second-bucket",
        request_fields={"project": "two", "environment": "test", "purpose": "data"},
        enqueue=False,
    )

    result = applications.execute_application(second.pk)

    assert result.status == StorageApplication.Status.SUCCEEDED
    assert (
        StorageCloudIdentity.objects.filter(
            membership=membership, resource_pool=pool
        ).count()
        == 1
    )
    assert StorageBucket.objects.filter(owner=membership, state="active").count() == 2
    assert [call[0] for call in provider.calls] == [
        "reconcile_bucket",
        "bucket",
        "policy",
    ]


def test_duplicate_idempotency_key_returns_existing_application(application_context):
    from object_storage.models import StorageApplication
    from object_storage.services import applications

    membership, pool = application_context
    first = applications.create_application(
        membership=membership,
        resource_pool=pool,
        action_type=StorageApplication.ActionType.ADD_BUCKET,
        idempotency_key="same-request",
        request_fields={"project": "one", "environment": "test", "purpose": "data"},
        enqueue=False,
    )
    second = applications.create_application(
        membership=membership,
        resource_pool=pool,
        action_type=StorageApplication.ActionType.ADD_BUCKET,
        idempotency_key="same-request",
        request_fields={"project": "changed", "environment": "test", "purpose": "data"},
        enqueue=False,
    )

    assert second.pk == first.pk
    assert StorageApplication.objects.filter(applicant=membership).count() == 1


def test_bucket_timeout_rechecks_cloud_before_retrying(
    application_context, monkeypatch
):
    from object_storage.models import StorageApplication
    from object_storage.services import applications

    membership, pool = application_context
    provider = FakeProvider()
    monkeypatch.setattr(
        applications, "get_provider_for_pool", lambda selected: provider
    )
    monkeypatch.setattr(
        provider,
        "create_owned_bucket",
        lambda bucket: (_ for _ in ()).throw(
            FakeProviderError("PROVIDER_TIMEOUT", retryable=True)
        ),
    )
    monkeypatch.setattr(
        provider,
        "find_owned_bucket",
        lambda bucket: provider.calls.append(("reconcile_bucket", bucket.name)) or True,
    )
    application = applications.create_application(
        membership=membership,
        resource_pool=pool,
        action_type=StorageApplication.ActionType.ADD_BUCKET,
        idempotency_key="timeout-bucket",
        request_fields={"project": "one", "environment": "test", "purpose": "data"},
        enqueue=False,
    )

    result = applications.execute_application(application.pk)

    assert result.status == StorageApplication.Status.SUCCEEDED
    assert any(call[0] == "reconcile_bucket" for call in provider.calls)


def test_policy_failure_does_not_issue_a_key(application_context, monkeypatch):
    from object_storage.models import StorageApplication, StorageAccessKey
    from object_storage.services import applications

    membership, pool = application_context
    provider = FakeProvider()
    provider.fail_policy = True
    monkeypatch.setattr(
        applications, "get_provider_for_pool", lambda selected: provider
    )
    application = applications.create_application(
        membership=membership,
        resource_pool=pool,
        action_type=StorageApplication.ActionType.FIRST_BUCKET_AND_CREDENTIAL,
        idempotency_key="policy-failure",
        request_fields={"project": "one", "environment": "test", "purpose": "data"},
        enqueue=False,
    )

    result = applications.execute_application(application.pk)

    assert result.status == StorageApplication.Status.MANUAL_REQUIRED
    assert StorageAccessKey.objects.count() == 0
    assert [call[0] for call in provider.calls] == [
        "reconcile_bucket",
        "bucket",
        "principal",
        "policy",
    ]


def test_encryption_failure_deletes_the_exact_new_key(application_context, monkeypatch):
    from object_storage.models import StorageApplication, StorageAccessKey
    from object_storage.services import applications

    membership, pool = application_context
    provider = FakeProvider()
    monkeypatch.setattr(
        applications, "get_provider_for_pool", lambda selected: provider
    )
    monkeypatch.setattr(
        applications,
        "encrypt_issued_access_key",
        lambda issued: (_ for _ in ()).throw(RuntimeError("encryption failed")),
    )
    application = applications.create_application(
        membership=membership,
        resource_pool=pool,
        action_type=StorageApplication.ActionType.FIRST_BUCKET_AND_CREDENTIAL,
        idempotency_key="encryption-failure",
        request_fields={"project": "one", "environment": "test", "purpose": "data"},
        enqueue=False,
    )

    result = applications.execute_application(application.pk)

    assert result.status == StorageApplication.Status.MANUAL_REQUIRED
    assert StorageAccessKey.objects.count() == 0
    assert ("delete_key", "LTAI-key-1") in provider.calls


def test_transient_provider_failure_is_retryable_but_business_error_is_not():
    from object_storage.services.applications import is_retryable_provider_error

    assert is_retryable_provider_error(
        FakeProviderError("PROVIDER_TIMEOUT", retryable=True)
    )
    assert not is_retryable_provider_error(FakeProviderError("BUCKET_NAME_CONFLICT"))


def test_retryable_provider_error_is_persisted_then_reraised(
    application_context, monkeypatch
):
    from object_storage.models import StorageApplication, StorageApplicationAttempt
    from object_storage.services import applications
    from object_storage.services.provider_errors import ObjectStorageProviderError

    membership, pool = application_context
    provider = FakeProvider()
    monkeypatch.setattr(
        applications, "get_provider_for_pool", lambda selected: provider
    )
    monkeypatch.setattr(
        provider,
        "create_owned_bucket",
        lambda bucket: (_ for _ in ()).throw(
            ObjectStorageProviderError("PROVIDER_TIMEOUT", retryable=True)
        ),
    )
    application = applications.create_application(
        membership=membership,
        resource_pool=pool,
        action_type=StorageApplication.ActionType.ADD_BUCKET,
        idempotency_key="retryable-bucket",
        request_fields={"project": "one", "environment": "test", "purpose": "data"},
        enqueue=False,
    )

    with pytest.raises(ObjectStorageProviderError, match="PROVIDER_TIMEOUT"):
        applications.execute_application(application.pk)

    application.refresh_from_db()
    attempt = application.attempts.get()
    assert application.status == StorageApplication.Status.RUNNING
    assert application.current_stage == "BUCKET_CREATING"
    assert attempt.status == StorageApplicationAttempt.Status.FAILED
    assert attempt.error_code == "PROVIDER_TIMEOUT"
    assert application.audit_events.filter(
        action="storage.application.retry_pending"
    ).exists()


def test_retry_reconciles_owned_bucket_before_creating_again(
    application_context, monkeypatch
):
    from object_storage.models import StorageApplication
    from object_storage.services import applications
    from object_storage.services.provider_errors import ObjectStorageProviderError

    membership, pool = application_context
    provider = FakeProvider()
    owned = False

    def find_owned_bucket(bucket):
        provider.calls.append(("reconcile_bucket", bucket.name))
        return owned

    def fail_create(bucket):
        provider.calls.append(("bucket", bucket.name))
        raise ObjectStorageProviderError("PROVIDER_TIMEOUT", retryable=True)

    monkeypatch.setattr(
        applications, "get_provider_for_pool", lambda selected: provider
    )
    monkeypatch.setattr(provider, "find_owned_bucket", find_owned_bucket)
    monkeypatch.setattr(provider, "create_owned_bucket", fail_create)
    application = applications.create_application(
        membership=membership,
        resource_pool=pool,
        action_type=StorageApplication.ActionType.ADD_BUCKET,
        idempotency_key="retry-reconcile",
        request_fields={"project": "one", "environment": "test", "purpose": "data"},
        enqueue=False,
    )

    with pytest.raises(ObjectStorageProviderError):
        applications.execute_application(application.pk)
    owned = True
    provider.calls.clear()
    result = applications.execute_application(application.pk)

    assert result.status == StorageApplication.Status.SUCCEEDED
    assert [call[0] for call in provider.calls] == [
        "reconcile_bucket",
        "principal",
        "policy",
    ]


def test_unsupported_application_action_never_uses_add_bucket_workflow(
    application_context, monkeypatch
):
    from object_storage.models import StorageApplication
    from object_storage.services import applications

    membership, pool = application_context
    provider = FakeProvider()
    monkeypatch.setattr(
        applications, "get_provider_for_pool", lambda selected: provider
    )
    application = applications.create_application(
        membership=membership,
        resource_pool=pool,
        action_type=StorageApplication.ActionType.ROTATE_CREDENTIAL,
        idempotency_key="unsupported-rotation",
        request_fields={},
        enqueue=False,
    )

    result = applications.execute_application(application.pk)

    assert result.status == StorageApplication.Status.MANUAL_REQUIRED
    assert result.error_code == "APPLICATION_ACTION_NOT_IMPLEMENTED"
    assert provider.calls == []
    assert application.audit_events.filter(
        action="storage.application.manual_required"
    ).exists()


def test_audit_cleanup_deletes_only_expired_audit_rows(
    application_context,
):
    from django.utils import timezone

    from object_storage.models import StorageApplication, StorageAuditEvent
    from object_storage.services.audit import delete_expired_audit_events
    from object_storage.services.applications import create_application

    membership, pool = application_context
    application = create_application(
        membership=membership,
        resource_pool=pool,
        action_type=StorageApplication.ActionType.ADD_BUCKET,
        idempotency_key="audit-retention",
        request_fields={"project": "one", "environment": "test", "purpose": "data"},
        enqueue=False,
    )
    old_event = StorageAuditEvent.objects.create(
        tenant=membership.tenant,
        actor=membership.user,
        application=application,
        action="storage.test.old",
        target_type="StorageApplication",
        target_id=application.pk,
        result="succeeded",
    )
    recent_event = StorageAuditEvent.objects.create(
        tenant=membership.tenant,
        actor=membership.user,
        application=application,
        action="storage.test.recent",
        target_type="StorageApplication",
        target_id=application.pk,
        result="succeeded",
    )
    now = timezone.now()
    StorageAuditEvent._base_manager.filter(pk=old_event.pk).update(
        created_at=now - timedelta(days=31)
    )

    deleted_count, cutoff = delete_expired_audit_events(now=now)

    assert deleted_count == 1
    assert cutoff == now - timedelta(days=30)
    assert StorageAuditEvent.objects.filter(pk=recent_event.pk).exists()
    assert StorageApplication.objects.filter(pk=application.pk).exists()


def applications_fingerprint(access_key_id):
    from object_storage.services.credentials import fingerprint_access_key

    return fingerprint_access_key(access_key_id)
