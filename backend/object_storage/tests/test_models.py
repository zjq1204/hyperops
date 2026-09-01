import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import CASCADE, PROTECT, SET_NULL
from django.db.models.deletion import ProtectedError

pytestmark = pytest.mark.django_db


def test_platform_migration_depends_on_linear_feishu_migration_chain():
    from importlib import import_module

    migration = import_module("object_storage.migrations.0005_platform_model").Migration

    assert ("object_storage", "0004_feishu_access_group") in migration.dependencies


def test_user_bucket_quota_migration_extends_platform_model_migration():
    from importlib import import_module

    migration = import_module(
        "object_storage.migrations.0006_user_bucket_quota"
    ).Migration

    assert migration.dependencies == [("object_storage", "0005_platform_model")]


@pytest.mark.django_db(transaction=True)
def test_platform_migration_assigns_existing_pool_to_default_config():
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    executor.migrate([("object_storage", "0002_object_storage_user_role")])
    old_apps = executor.loader.project_state(
        [("object_storage", "0002_object_storage_user_role")]
    ).apps
    StorageTenant = old_apps.get_model("object_storage", "StorageTenant")
    StorageResourcePool = old_apps.get_model("object_storage", "StorageResourcePool")
    tenant = StorageTenant.objects.create(code="legacy", name="Legacy")
    pool = StorageResourcePool.objects.create(
        tenant=tenant,
        cloud_account_id="legacy-account",
        region="cn-hangzhou",
        management_access_key_encrypted="legacy-ak",
        management_secret_key_encrypted="legacy-sk",
        credential_fingerprint="legacy-fingerprint",
        access_key_last_four="1234",
    )

    executor = MigrationExecutor(connection)
    executor.migrate([("object_storage", "0005_platform_model")])
    new_apps = executor.loader.project_state(
        [("object_storage", "0005_platform_model")]
    ).apps
    PlatformObjectStorageConfig = new_apps.get_model(
        "object_storage", "PlatformObjectStorageConfig"
    )
    MigratedPool = new_apps.get_model("object_storage", "StorageResourcePool")

    config = PlatformObjectStorageConfig.objects.get(singleton_key="default")
    assert MigratedPool.objects.get(pk=pool.pk).config_id == config.pk


def test_platform_settings_are_singletons_and_use_phase_one_defaults(db):
    from object_storage.models import (
        PlatformFeishuConfig,
        PlatformObjectStorageConfig,
    )

    feishu = PlatformFeishuConfig.objects.create()
    storage, _created = PlatformObjectStorageConfig.objects.get_or_create(
        singleton_key="default"
    )

    assert feishu.singleton_key == "default"
    assert storage.singleton_key == "default"
    assert storage.default_bucket_quota == 5
    assert storage.delivery_lifetime_seconds == 86400
    assert storage.audit_retention_days == 30
    assert storage.naming_template_version == 1

    with pytest.raises(IntegrityError), transaction.atomic():
        PlatformFeishuConfig.objects.create()
    with pytest.raises(IntegrityError), transaction.atomic():
        PlatformObjectStorageConfig.objects.create()
    with pytest.raises(IntegrityError), transaction.atomic():
        PlatformFeishuConfig.objects.create(singleton_key="other")
    with pytest.raises(IntegrityError), transaction.atomic():
        PlatformObjectStorageConfig.objects.create(singleton_key="other")


def test_platform_storage_settings_enforce_approved_ranges(db):
    from object_storage.models import PlatformObjectStorageConfig

    invalid_values = (
        {"default_bucket_quota": 0},
        {"delivery_lifetime_seconds": 599},
        {"delivery_lifetime_seconds": 604801},
        {"audit_retention_days": 0},
        {"audit_retention_days": 3651},
    )
    for values in invalid_values:
        with pytest.raises(IntegrityError), transaction.atomic():
            PlatformObjectStorageConfig.objects.create(**values)


def test_user_bucket_quota_is_one_to_one_positive_and_protected(user_factory):
    from object_storage.models import UserBucketQuota

    user = user_factory()
    quota = UserBucketQuota.objects.create(user=user, bucket_quota=8)

    assert quota.bucket_quota == 8
    assert quota.created_at is not None
    assert quota.updated_at is not None
    assert quota._meta.get_field("user").remote_field.on_delete is PROTECT
    with pytest.raises(IntegrityError), transaction.atomic():
        UserBucketQuota.objects.create(user=user, bucket_quota=9)
    with pytest.raises(IntegrityError), transaction.atomic():
        UserBucketQuota.objects.create(user=user_factory(), bucket_quota=0)
    with pytest.raises(ProtectedError):
        user.delete()


def test_resource_pool_belongs_to_platform_storage_config(
    storage_resource_pool_factory, platform_object_storage_config
):
    pool = storage_resource_pool_factory()

    assert pool.config_id == platform_object_storage_config.id
    assert pool._meta.get_field("config").remote_field.on_delete is PROTECT


def test_only_one_aliyun_resource_pool_can_be_enabled(
    storage_resource_pool_factory,
):
    storage_resource_pool_factory(enabled=True)

    with pytest.raises(IntegrityError), transaction.atomic():
        storage_resource_pool_factory(enabled=True)

    assert storage_resource_pool_factory(enabled=False).pk is not None


def test_feishu_identity_maps_open_id_and_user_once(
    feishu_identity_factory, user_factory
):
    identity = feishu_identity_factory()

    with pytest.raises(IntegrityError), transaction.atomic():
        feishu_identity_factory(user=user_factory(), open_id=identity.open_id)
    with pytest.raises(IntegrityError), transaction.atomic():
        feishu_identity_factory(user=identity.user)


def test_user_has_only_one_cloud_identity_in_phase_one(
    cloud_identity_factory, storage_resource_pool_factory
):
    identity = cloud_identity_factory()

    with pytest.raises(IntegrityError), transaction.atomic():
        cloud_identity_factory(
            user=identity.user,
            resource_pool=storage_resource_pool_factory(),
        )


def test_ram_user_name_is_unique_within_resource_pool(
    cloud_identity_factory, user_factory
):
    identity = cloud_identity_factory()

    with pytest.raises(IntegrityError), transaction.atomic():
        cloud_identity_factory(
            user=user_factory(),
            resource_pool=identity.resource_pool,
            ram_user_name=identity.ram_user_name,
        )


def test_bucket_is_unique_by_resource_pool_and_final_name(bucket_factory):
    bucket = bucket_factory()

    with pytest.raises(IntegrityError), transaction.atomic():
        bucket_factory(
            cloud_identity=bucket.cloud_identity,
            name=bucket.name,
        )


def test_bucket_directly_references_owner_pool_and_identity(bucket_factory):
    bucket = bucket_factory()

    assert bucket.owner_id == bucket.cloud_identity.user_id
    assert bucket.resource_pool_id == bucket.cloud_identity.resource_pool_id
    for field_name in ("owner", "resource_pool", "cloud_identity"):
        assert BucketField(bucket, field_name).on_delete is PROTECT


def BucketField(bucket, field_name):
    return bucket._meta.get_field(field_name).remote_field


def test_access_key_belongs_to_cloud_identity_and_protects_it(access_key_factory):
    key = access_key_factory()

    assert key._meta.get_field("cloud_identity").remote_field.on_delete is PROTECT
    with pytest.raises(ProtectedError):
        key.cloud_identity.delete()


def test_access_key_rejects_third_provider_slot(
    access_key_factory, cloud_identity_factory
):
    identity = cloud_identity_factory()
    access_key_factory(cloud_identity=identity)
    access_key_factory(cloud_identity=identity)

    with pytest.raises(ValidationError, match="ACCESS_KEY_LIMIT_EXCEEDED"):
        access_key_factory(cloud_identity=identity)


@pytest.mark.django_db(transaction=True)
def test_access_key_save_locks_cloud_identity_inside_atomic_transaction(
    access_key_factory, cloud_identity_factory, monkeypatch
):
    from django.db.models.query import QuerySet

    from object_storage.models import CloudIdentity

    locked_models = []
    lock_atomic_states = []
    original_select_for_update = QuerySet.select_for_update

    def tracked_select_for_update(queryset, *args, **kwargs):
        locked_models.append(queryset.model)
        lock_atomic_states.append(
            transaction.get_connection(queryset.db).in_atomic_block
        )
        return original_select_for_update(queryset, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "select_for_update", tracked_select_for_update)

    # SQLite ignores row locks; PostgreSQL enforces this exercised lock path.
    access_key_factory(cloud_identity=cloud_identity_factory())

    assert CloudIdentity in locked_models
    assert lock_atomic_states == [True]


@pytest.mark.django_db(transaction=True)
def test_concurrent_access_key_creates_finish_at_provider_limit(
    access_key_factory, cloud_identity_factory
):
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL select_for_update is required for this race test")

    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import close_old_connections

    from object_storage.models import AccessKey, CloudIdentity

    identity = cloud_identity_factory()
    access_key_factory(cloud_identity=identity)
    barrier = Barrier(2)

    def create_key(number):
        close_old_connections()
        try:
            barrier.wait()
            AccessKey.objects.create(
                cloud_identity_id=identity.pk,
                access_key_id_encrypted=f"concurrent-ak-{number}",
                secret_access_key_encrypted=f"concurrent-sk-{number}",
                access_key_fingerprint=f"concurrent-fingerprint-{number}",
                access_key_last_four=f"{number:04d}",
            )
            return "created"
        except ValidationError:
            return "rejected"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(create_key, (1, 2)))

    assert sorted(results) == ["created", "rejected"]
    assert CloudIdentity.objects.get(pk=identity.pk).access_keys.count() == 2


def test_access_key_bulk_create_cannot_bypass_provider_slot_limit(
    cloud_identity_factory,
):
    from object_storage.models import AccessKey

    identity = cloud_identity_factory()
    key = AccessKey(
        cloud_identity=identity,
        access_key_id_encrypted="bulk-encrypted-ak",
        secret_access_key_encrypted="bulk-encrypted-sk",
        access_key_fingerprint="bulk-fingerprint",
        access_key_last_four="9999",
    )

    with pytest.raises(RuntimeError, match="ACCESS_KEY_BULK_CREATE_REQUIRES_SAVE"):
        AccessKey.objects.bulk_create([key])


def test_access_key_bulk_upsert_cannot_move_released_key_into_full_identity(
    access_key_factory, cloud_identity_factory
):
    from object_storage.models import AccessKey

    target_identity = cloud_identity_factory()
    access_key_factory(cloud_identity=target_identity)
    access_key_factory(cloud_identity=target_identity)
    source_key = access_key_factory(cloud_identity=cloud_identity_factory())
    candidate = AccessKey(
        pk=source_key.pk,
        cloud_identity=target_identity,
        access_key_id_encrypted="upsert-encrypted-ak",
        secret_access_key_encrypted="upsert-encrypted-sk",
        access_key_fingerprint=source_key.access_key_fingerprint,
        access_key_last_four="8888",
        local_state=AccessKey.LocalState.RETIRED,
    )

    with pytest.raises(RuntimeError, match="ACCESS_KEY_BULK_CREATE_REQUIRES_SAVE"):
        AccessKey.objects.bulk_create(
            [candidate],
            update_conflicts=True,
            update_fields=["cloud_identity", "local_state"],
            unique_fields=["id"],
        )

    assert AccessKey.objects.filter(cloud_identity=target_identity).count() == 2
    assert AccessKey.objects.get(pk=source_key.pk).cloud_identity_id == (
        source_key.cloud_identity_id
    )


def test_access_key_queryset_update_cannot_restore_released_slot(
    access_key_factory, cloud_identity_factory
):
    from object_storage.models import AccessKey

    key = access_key_factory(
        cloud_identity=cloud_identity_factory(),
        local_state=AccessKey.LocalState.RETIRED,
    )

    with pytest.raises(RuntimeError, match="ACCESS_KEY_STATE_UPDATE_REQUIRES_SAVE"):
        AccessKey.objects.filter(pk=key.pk).update(
            local_state=AccessKey.LocalState.ACTIVE
        )

    key.refresh_from_db()
    assert key.local_state == AccessKey.LocalState.RETIRED


def test_inactive_key_occupies_slot_but_deleted_or_retired_key_does_not(
    access_key_factory, cloud_identity_factory
):
    from object_storage.models import AccessKey

    assert AccessKey.CloudState.INACTIVE in AccessKey.PROVIDER_SLOT_CLOUD_STATES
    assert AccessKey.CloudState.DELETED not in AccessKey.PROVIDER_SLOT_CLOUD_STATES
    assert AccessKey.LocalState.RETIRED not in AccessKey.PROVIDER_SLOT_LOCAL_STATES

    identity = cloud_identity_factory()
    inactive = access_key_factory(
        cloud_identity=identity,
        cloud_state=AccessKey.CloudState.INACTIVE,
    )
    retired = access_key_factory(cloud_identity=identity)

    with pytest.raises(ValidationError, match="ACCESS_KEY_LIMIT_EXCEEDED"):
        access_key_factory(cloud_identity=identity)

    retired.local_state = AccessKey.LocalState.RETIRED
    retired.save(update_fields=("local_state",))
    replacement = access_key_factory(cloud_identity=identity)
    inactive.cloud_state = AccessKey.CloudState.DELETED
    inactive.save(update_fields=("cloud_state",))

    assert access_key_factory(cloud_identity=identity).pk is not None
    assert replacement.occupies_provider_slot is True


def test_application_batch_is_idempotent_per_applicant(application_batch_factory):
    batch = application_batch_factory()

    with pytest.raises(IntegrityError), transaction.atomic():
        application_batch_factory(
            applicant=batch.applicant,
            idempotency_key=batch.idempotency_key,
        )


def test_application_batch_has_independent_items(application_batch_factory):
    from object_storage.models import ApplicationItem

    batch = application_batch_factory(item_count=2)
    first, second = batch.items.order_by("id")
    first.status = ApplicationItem.Status.SUCCEEDED
    first.save(update_fields=("status",))
    second.status = ApplicationItem.Status.FAILED
    second.save(update_fields=("status",))

    assert batch.items.count() == 2
    assert list(batch.items.order_by("id").values_list("status", flat=True)) == [
        ApplicationItem.Status.SUCCEEDED,
        ApplicationItem.Status.FAILED,
    ]


def test_application_attempt_event_and_delivery_ticket_have_no_tenant_field():
    from object_storage.models import (
        ApplicationAttempt,
        ApplicationEvent,
        AuditEvent,
        DeliveryTicket,
    )

    for model in (ApplicationAttempt, ApplicationEvent, DeliveryTicket, AuditEvent):
        assert "tenant" not in {field.name for field in model._meta.fields}


def test_application_event_is_immutable(application_batch_factory):
    from object_storage.models import (
        ApplicationEvent,
        ApplicationEventImmutableError,
    )

    item = application_batch_factory(item_count=1).items.get()
    event = ApplicationEvent.objects.create(
        application_item=item,
        stage="BUCKET_CREATING",
        result="running",
    )

    event.result = "changed"
    with pytest.raises(ApplicationEventImmutableError):
        event.save()
    with pytest.raises(ApplicationEventImmutableError):
        ApplicationEvent.objects.filter(pk=event.pk).update(result="changed")


def test_audit_event_is_immutable_and_snapshots_actor(django_user_model):
    from object_storage.models import AuditEvent, AuditEventImmutableError

    actor = django_user_model.objects.create_user(
        username="audit-actor",
        first_name="Audit",
        last_name="Actor",
    )
    event = AuditEvent.objects.create(
        actor=actor,
        action="storage.application.created",
        target_type="ApplicationBatch",
        target_id="42",
        result="accepted",
    )

    assert event.actor_id_snapshot == actor.id
    assert event.actor_name_snapshot == actor.get_full_name()
    assert event._meta.get_field("actor").remote_field.on_delete is SET_NULL
    event.result = "changed"
    with pytest.raises(AuditEventImmutableError):
        event.save()
    with pytest.raises(AuditEventImmutableError):
        AuditEvent.objects.filter(pk=event.pk).update(result="changed")


def test_user_with_cloud_resources_cannot_be_deleted(bucket_factory):
    bucket = bucket_factory()

    with pytest.raises(ProtectedError):
        bucket.owner.delete()


def test_feishu_identity_is_removed_with_resource_free_user(feishu_identity_factory):
    identity = feishu_identity_factory()
    user = identity.user

    assert identity._meta.get_field("user").remote_field.on_delete is CASCADE
    user.delete()

    assert not type(identity).objects.filter(pk=identity.pk).exists()


def test_runtime_models_have_no_tenant_or_membership_fields():
    from object_storage.models import OBJECT_STORAGE_BUSINESS_MODELS

    for model in OBJECT_STORAGE_BUSINESS_MODELS:
        field_names = {field.name for field in model._meta.fields}
        assert "tenant" not in field_names
        assert "membership" not in field_names


def test_old_tenant_runtime_models_are_removed():
    from object_storage import models

    assert not hasattr(models, "StorageTenant")
    assert not hasattr(models, "StorageMembership")
    assert not hasattr(models, "FeishuAppConfig")


def test_secret_models_expose_only_encrypted_secret_fields():
    from object_storage.models import (
        AccessKey,
        PlatformFeishuConfig,
        StorageResourcePool,
    )

    models = (PlatformFeishuConfig, StorageResourcePool, AccessKey)
    field_names = {
        model.__name__: {field.name for field in model._meta.fields} for model in models
    }

    assert "app_secret_encrypted" in field_names["PlatformFeishuConfig"]
    assert "management_secret_key_encrypted" in field_names["StorageResourcePool"]
    assert "secret_access_key_encrypted" in field_names["AccessKey"]
    assert "app_secret" not in field_names["PlatformFeishuConfig"]
    assert "management_secret_key" not in field_names["StorageResourcePool"]
    assert "secret_access_key" not in field_names["AccessKey"]
