from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from object_storage.crypto import encrypt_secret

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def stable_object_storage_secret(settings):
    settings.SECRET_KEY = "object-storage-platform-config-stable-secret"


def test_platform_config_accessors_create_singletons_with_safe_defaults(db):
    from object_storage.services.platform import (
        get_feishu_config,
        get_object_storage_config,
    )

    feishu = get_feishu_config()
    storage = get_object_storage_config()

    assert get_feishu_config().pk == feishu.pk
    assert get_object_storage_config().pk == storage.pk
    assert storage.default_bucket_quota == 5
    assert storage.delivery_lifetime_seconds == 86400
    assert storage.audit_retention_days == 30
    assert storage.pause_new_applications is True
    assert storage.pause_key_operations is True


def test_platform_config_database_constraints_allow_only_default_singletons(db):
    from object_storage.models import PlatformFeishuConfig, PlatformObjectStorageConfig

    PlatformFeishuConfig.objects.create(singleton_key="default")
    PlatformObjectStorageConfig.objects.create(singleton_key="default")

    with transaction.atomic():
        with pytest.raises(IntegrityError):
            PlatformFeishuConfig.objects.create(singleton_key="default")
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            PlatformObjectStorageConfig.objects.create(singleton_key="default")


def test_pause_switches_are_independent(platform_object_storage_config):
    from object_storage.services.platform import (
        pause_key_operations,
        pause_new_applications,
    )

    pause_new_applications(False)
    pause_key_operations(True)
    platform_object_storage_config.refresh_from_db()
    assert platform_object_storage_config.pause_new_applications is False
    assert platform_object_storage_config.pause_key_operations is True

    pause_key_operations(False)
    platform_object_storage_config.refresh_from_db()
    assert platform_object_storage_config.pause_new_applications is False
    assert platform_object_storage_config.pause_key_operations is False


def test_validate_and_save_platform_config_persists_allowlisted_storage_fields(db):
    from object_storage.services.platform import (
        get_object_storage_config,
        validate_and_save_platform_config,
    )

    config = get_object_storage_config()
    validate_and_save_platform_config(
        object_storage_config=config,
        object_storage_fields={
            "naming_template": "hyperops-{user}-{suffix}",
            "naming_template_version": 2,
            "default_bucket_quota": 9,
            "delivery_lifetime_seconds": 7200,
            "audit_retention_days": 45,
            "pause_new_applications": False,
            "pause_key_operations": True,
        },
    )

    config.refresh_from_db()
    assert config.naming_template == "hyperops-{user}-{suffix}"
    assert config.naming_template_version == 2
    assert config.default_bucket_quota == 9
    assert config.delivery_lifetime_seconds == 7200
    assert config.audit_retention_days == 45
    assert config.pause_new_applications is False
    assert config.pause_key_operations is True


def test_validate_and_save_platform_config_rejects_fields_outside_allowlist(db):
    from object_storage.services.platform import (
        PlatformConfigurationError,
        get_object_storage_config,
        validate_and_save_platform_config,
    )

    with pytest.raises(
        PlatformConfigurationError, match="UNSUPPORTED_PLATFORM_CONFIG_FIELD"
    ):
        validate_and_save_platform_config(
            object_storage_config=get_object_storage_config(),
            object_storage_fields={"enabled": True},
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("naming_template", ""),
        ("naming_template", "hyperops-without-suffix"),
        ("naming_template", "hyperops-{unknown}-{suffix}"),
        ("naming_template", "hyperops-{user-{suffix}"),
        ("naming_template_version", 0),
        ("default_bucket_quota", 0),
        ("delivery_lifetime_seconds", 599),
        ("delivery_lifetime_seconds", 604801),
        ("audit_retention_days", 0),
        ("audit_retention_days", 3651),
        ("pause_new_applications", "false"),
    ],
)
def test_validate_and_save_platform_config_rejects_invalid_values(db, field, value):
    from object_storage.services.platform import (
        PlatformConfigurationError,
        get_object_storage_config,
        validate_and_save_platform_config,
    )

    with pytest.raises(PlatformConfigurationError, match="INVALID_PLATFORM_CONFIG"):
        validate_and_save_platform_config(
            object_storage_config=get_object_storage_config(),
            object_storage_fields={field: value},
        )


def test_platform_cannot_be_enabled_until_feishu_and_pool_are_valid(
    storage_resource_pool_factory,
):
    from object_storage.models import PlatformFeishuConfig, StorageResourcePool
    from object_storage.services.platform import (
        PlatformConfigurationError,
        enable_platform,
        get_feishu_config,
        get_object_storage_config,
    )

    feishu = get_feishu_config()
    storage = get_object_storage_config()
    pool = storage_resource_pool_factory(
        config=storage,
        cloud_account_id="account-1",
        validation_status=StorageResourcePool.ValidationStatus.PENDING,
    )

    with pytest.raises(PlatformConfigurationError, match="CONFIG_NOT_VALIDATED"):
        enable_platform()
    feishu.refresh_from_db()
    pool.refresh_from_db()
    assert feishu.enabled is False
    assert pool.enabled is False

    feishu.validation_status = PlatformFeishuConfig.ValidationStatus.VALID
    feishu.save(update_fields=("validation_status", "updated_at"))
    pool.validation_status = StorageResourcePool.ValidationStatus.VALID
    pool.save(update_fields=("validation_status", "updated_at"))
    enable_platform()

    feishu.refresh_from_db()
    pool.refresh_from_db()
    assert feishu.enabled is True
    assert pool.enabled is True


def test_validation_failure_disables_config_without_touching_cloud_resources(
    storage_resource_pool_factory,
):
    from object_storage.models import StorageResourcePool
    from object_storage.services.platform import (
        PlatformConfigurationError,
        validate_resource_pool,
    )

    pool = storage_resource_pool_factory(
        cloud_account_id="account-1",
        enabled=True,
        validation_status=StorageResourcePool.ValidationStatus.VALID,
    )
    original_credentials = pool.management_secret_key_encrypted

    def reject(_pool):
        raise RuntimeError("provider rejected credentials")

    with pytest.raises(PlatformConfigurationError, match="PROVIDER_VALIDATION_FAILED"):
        validate_resource_pool(pool, validator=reject)

    pool.refresh_from_db()
    assert pool.enabled is False
    assert pool.validation_status == StorageResourcePool.ValidationStatus.INVALID
    assert pool.management_secret_key_encrypted == original_credentials


def test_provider_and_account_id_are_locked_after_real_resources_exist(
    storage_resource_pool_factory,
    cloud_identity_factory,
):
    from object_storage.services.platform import (
        PlatformConfigurationError,
        update_resource_pool,
    )

    pool = storage_resource_pool_factory(cloud_account_id="account-1")
    cloud_identity_factory(resource_pool=pool)

    with pytest.raises(PlatformConfigurationError, match="RESOURCE_POOL_ID_LOCKED"):
        update_resource_pool(pool, provider="aliyun", cloud_account_id="account-2")


def test_management_credential_replacement_requires_the_same_cloud_account(
    storage_resource_pool_factory,
):
    from object_storage.crypto import decrypt_secret
    from object_storage.models import StorageResourcePool
    from object_storage.services.platform import (
        PlatformConfigurationError,
        replace_management_credentials,
    )

    pool = storage_resource_pool_factory(
        cloud_account_id="account-1",
        enabled=True,
        validation_status=StorageResourcePool.ValidationStatus.VALID,
        management_secret_key_encrypted=encrypt_secret("old-secret"),
    )

    with pytest.raises(PlatformConfigurationError, match="CLOUD_ACCOUNT_MISMATCH"):
        replace_management_credentials(
            pool,
            access_key="new-access-key",
            secret_key="new-secret",
            validator=lambda _candidate: SimpleNamespace(account_id="account-2"),
        )
    pool.refresh_from_db()
    assert decrypt_secret(pool.management_secret_key_encrypted) == "old-secret"

    replace_management_credentials(
        pool,
        access_key="new-access-key",
        secret_key="new-secret",
        validator=lambda _candidate: {"account_id": "account-1"},
    )
    pool.refresh_from_db()
    assert decrypt_secret(pool.management_secret_key_encrypted) == "new-secret"
    assert pool.validation_status == StorageResourcePool.ValidationStatus.PENDING
    assert pool.validation_error_code == ""
    assert pool.last_validated_at is None
    assert pool.enabled is False


@pytest.mark.parametrize(
    "field, value",
    [
        ("cloud_account_id", "account-2"),
        ("provider", "aliyun-v2"),
        ("region", "cn-shanghai"),
    ],
)
def test_resource_pool_identity_changes_require_revalidation(
    storage_resource_pool_factory, field, value
):
    from object_storage.models import StorageResourcePool
    from object_storage.services.platform import update_resource_pool

    pool = storage_resource_pool_factory(
        enabled=True,
        validation_status=StorageResourcePool.ValidationStatus.VALID,
        validation_error_code="",
        last_validated_at=timezone.now(),
    )

    update_resource_pool(pool, **{field: value})

    pool.refresh_from_db()
    assert pool.validation_status == StorageResourcePool.ValidationStatus.PENDING
    assert pool.validation_error_code == ""
    assert pool.last_validated_at is None
    assert pool.enabled is False


def test_audit_records_actor_snapshot_and_rejects_secret_metadata(user_factory):
    from object_storage.models import AuditEvent
    from object_storage.services.audit import record_audit_event

    actor = user_factory(first_name="Audit", last_name="Actor")
    event = record_audit_event(
        actor=actor,
        action="storage.config.updated",
        target_type="PlatformObjectStorageConfig",
        target_id="default",
        reason="maintenance",
        result="succeeded",
        ip_address="192.0.2.10",
        request_id="request-123",
        safe_metadata={"provider": "aliyun", "changed_fields": ["region"]},
    )

    assert event.actor_id_snapshot == actor.pk
    assert event.actor_name_snapshot == "Audit Actor"
    assert event.request_id == "request-123"
    assert event.ip_address == "192.0.2.10"
    assert AuditEvent.objects.filter(pk=event.pk).exists()

    with pytest.raises(ValueError, match="sensitive audit metadata"):
        record_audit_event(
            action="storage.credential.revealed",
            target_type="AccessKey",
            target_id="1",
            result="succeeded",
            safe_metadata={"secret_access_key": "plain-secret"},
        )


@pytest.mark.parametrize(
    "safe_metadata",
    [
        {"access_key": "LTAIabcdefghijkl1234"},
        {"value": "plain-secret"},
        {"apiKey": "opaque-value"},
        {"nested": {"credentials": "opaque-value"}},
        {"nested": {"authorization": "Bearer abc123"}},
        {"nested": [{"token": "opaque-token-value"}]},
        {"value": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature-value"},
        {"value": "-----BEGIN PRIVATE KEY-----\\nsecret\\n-----END PRIVATE KEY-----"},
        {"value": "v1:aesgcm:YWJjZGVmZ2hpamts:Y2lwaGVydGV4dC1ub3QtcGxhaW4="},
    ],
)
def test_audit_rejects_sensitive_values_recursively(user_factory, safe_metadata):
    from object_storage.services.audit import record_audit_event

    with pytest.raises(ValueError, match="sensitive audit metadata"):
        record_audit_event(
            actor=user_factory(),
            action="storage.audit.test",
            target_type="AccessKey",
            target_id="1",
            result="succeeded",
            safe_metadata=safe_metadata,
        )


def test_audit_allows_safe_identifiers_and_key_summaries(user_factory):
    from object_storage.services.audit import record_audit_event

    event = record_audit_event(
        actor=user_factory(),
        action="storage.audit.test",
        target_type="AccessKey",
        target_id="1",
        result="succeeded",
        safe_metadata={
            "access_key": "external-id-123",
            "last_four": "1234",
            "request_id": "request-123",
        },
    )

    assert event.safe_metadata == {
        "access_key": "external-id-123",
        "last_four": "1234",
        "request_id": "request-123",
    }


def test_audit_retention_uses_platform_setting_and_preserves_business_records(
    platform_object_storage_config,
    user_factory,
):
    from object_storage.models import ApplicationBatch, AuditEvent
    from object_storage.services.audit import delete_expired_audit_events

    actor = user_factory()
    old_event = AuditEvent.objects.create(
        actor=actor,
        action="storage.old",
        target_type="Bucket",
        target_id="1",
        result="succeeded",
    )
    recent_event = AuditEvent.objects.create(
        actor=actor,
        action="storage.recent",
        target_type="Bucket",
        target_id="2",
        result="succeeded",
    )
    platform_object_storage_config.audit_retention_days = 45
    platform_object_storage_config.save(update_fields=("audit_retention_days",))
    now = timezone.now()
    AuditEvent._base_manager.filter(pk=old_event.pk).update(
        created_at=now - timedelta(days=46)
    )
    boundary_event = AuditEvent.objects.create(
        actor=actor,
        action="storage.boundary",
        target_type="Bucket",
        target_id="3",
        result="succeeded",
    )
    AuditEvent._base_manager.filter(pk=boundary_event.pk).update(
        created_at=now - timedelta(days=45)
    )
    ApplicationBatch.objects.create(
        applicant=actor,
        idempotency_key="retention-business-record",
    )

    deleted_count, cutoff = delete_expired_audit_events(now=now)

    assert deleted_count == 1
    assert cutoff == now - timedelta(days=45)
    assert not AuditEvent.objects.filter(pk=old_event.pk).exists()
    assert AuditEvent.objects.filter(pk=recent_event.pk).exists()
    assert AuditEvent.objects.filter(pk=boundary_event.pk).exists()
    assert ApplicationBatch.objects.filter(
        idempotency_key="retention-business-record"
    ).exists()
