import json
from io import StringIO

import pytest
from django.db import IntegrityError, transaction

pytestmark = pytest.mark.django_db


def test_storage_tenant_uses_approved_phase_one_defaults(storage_tenant_factory):
    tenant = storage_tenant_factory()

    assert tenant.default_bucket_quota == 5
    assert tenant.delivery_lifetime_seconds == 86400
    assert tenant.audit_retention_days == 30
    assert tenant.naming_template_version == 1


def test_storage_membership_is_unique_by_tenant_and_feishu_open_id(
    storage_membership_factory,
):
    membership = storage_membership_factory()

    with pytest.raises(IntegrityError), transaction.atomic():
        storage_membership_factory(
            tenant=membership.tenant,
            feishu_open_id=membership.feishu_open_id,
        )


def test_django_user_can_have_only_one_storage_membership(
    storage_membership_factory, storage_tenant_factory
):
    membership = storage_membership_factory()

    with pytest.raises(IntegrityError), transaction.atomic():
        storage_membership_factory(
            tenant=storage_tenant_factory(),
            user=membership.user,
        )


def test_storage_pool_has_one_active_aliyun_pool_per_tenant(
    storage_resource_pool_factory,
):
    pool = storage_resource_pool_factory(enabled=True)

    with pytest.raises(IntegrityError), transaction.atomic():
        storage_resource_pool_factory(tenant=pool.tenant, enabled=True)

    disabled_pool = storage_resource_pool_factory(tenant=pool.tenant, enabled=False)
    assert disabled_pool.pk is not None


def test_bucket_is_unique_by_resource_pool_and_name(storage_bucket_factory):
    bucket = storage_bucket_factory()

    with pytest.raises(IntegrityError), transaction.atomic():
        storage_bucket_factory(
            cloud_identity=bucket.cloud_identity,
            name=bucket.name,
        )


def test_one_membership_has_one_cloud_identity_per_pool(
    storage_cloud_identity_factory,
):
    identity = storage_cloud_identity_factory()

    with pytest.raises(IntegrityError), transaction.atomic():
        storage_cloud_identity_factory(
            membership=identity.membership,
            resource_pool=identity.resource_pool,
        )


def test_application_idempotency_key_is_unique_per_applicant_and_tenant(
    storage_membership_factory,
):
    from object_storage.models import StorageApplication

    membership = storage_membership_factory()
    values = {
        "tenant": membership.tenant,
        "applicant": membership,
        "action_type": StorageApplication.ActionType.FIRST_BUCKET_AND_CREDENTIAL,
        "idempotency_key": "request-123",
    }
    StorageApplication.objects.create(**values)

    with pytest.raises(IntegrityError), transaction.atomic():
        StorageApplication.objects.create(**values)


def test_audit_event_is_immutable(storage_tenant_factory, django_user_model):
    from object_storage.models import (
        StorageAuditEvent,
        StorageAuditEventImmutableError,
    )

    tenant = storage_tenant_factory()
    actor = django_user_model.objects.create_user(username="audit-actor")
    event = StorageAuditEvent.objects.create(
        tenant=tenant,
        actor=actor,
        action="storage.application.created",
        target_type="StorageApplication",
        target_id="42",
        result="accepted",
    )

    event.result = "changed"
    with pytest.raises(StorageAuditEventImmutableError):
        event.save()
    with pytest.raises(StorageAuditEventImmutableError):
        StorageAuditEvent.objects.filter(pk=event.pk).update(result="changed")


def test_application_event_is_immutable(storage_membership_factory):
    from object_storage.models import (
        StorageApplication,
        StorageApplicationEvent,
        StorageApplicationEventImmutableError,
    )

    membership = storage_membership_factory()
    application = StorageApplication.objects.create(
        tenant=membership.tenant,
        applicant=membership,
        action_type=StorageApplication.ActionType.ADD_BUCKET,
        idempotency_key="event-immutability",
    )
    event = StorageApplicationEvent.objects.create(
        tenant=membership.tenant,
        application=application,
        stage="BUCKET_CREATING",
        result="running",
    )

    event.result = "changed"
    with pytest.raises(StorageApplicationEventImmutableError):
        event.save()
    with pytest.raises(StorageApplicationEventImmutableError):
        StorageApplicationEvent.objects.filter(pk=event.pk).update(result="changed")


def test_every_business_model_has_an_explicit_tenant_field():
    from object_storage.models import OBJECT_STORAGE_BUSINESS_MODELS

    for model in OBJECT_STORAGE_BUSINESS_MODELS:
        assert model._meta.get_field("tenant").name == "tenant"


def test_secret_models_expose_only_encrypted_secret_fields():
    from object_storage.models import (
        FeishuAppConfig,
        StorageAccessKey,
        StorageResourcePool,
    )

    field_names = {
        model.__name__: {field.name for field in model._meta.fields}
        for model in (FeishuAppConfig, StorageResourcePool, StorageAccessKey)
    }

    assert "app_secret_encrypted" in field_names["FeishuAppConfig"]
    assert "management_secret_key_encrypted" in field_names["StorageResourcePool"]
    assert "secret_access_key_encrypted" in field_names["StorageAccessKey"]
    assert "app_secret" not in field_names["FeishuAppConfig"]
    assert "management_secret_key" not in field_names["StorageResourcePool"]
    assert "secret_access_key" not in field_names["StorageAccessKey"]


def test_reencrypt_command_targets_all_real_secret_model_fields(
    monkeypatch,
    storage_cloud_identity_factory,
):
    from object_storage.crypto import (
        _decrypt_secret_with_root,
        _encrypt_secret_with_root,
    )
    from object_storage.management.commands.reencrypt_object_storage_secrets import (
        Command,
    )
    from object_storage.models import FeishuAppConfig, StorageAccessKey

    old_root = "old-model-integration-root"
    new_root = "new-model-integration-root"
    identity = storage_cloud_identity_factory()
    pool = identity.resource_pool
    pool.management_access_key_encrypted = _encrypt_secret_with_root(
        "manager-ak", old_root
    )
    pool.management_secret_key_encrypted = _encrypt_secret_with_root(
        "manager-sk", old_root
    )
    pool.save(
        update_fields=(
            "management_access_key_encrypted",
            "management_secret_key_encrypted",
        )
    )
    app_config = FeishuAppConfig.objects.create(
        tenant=identity.tenant,
        app_id="cli_test_app",
        app_secret_encrypted=_encrypt_secret_with_root("feishu-sk", old_root),
        oauth_callback_url="https://hyperops.example.com/callback",
    )
    access_key = StorageAccessKey.objects.create(
        tenant=identity.tenant,
        cloud_identity=identity,
        access_key_id_encrypted=_encrypt_secret_with_root("employee-ak", old_root),
        secret_access_key_encrypted=_encrypt_secret_with_root("employee-sk", old_root),
        access_key_fingerprint="employee-key-fingerprint",
        access_key_last_four="1234",
    )
    answers = iter([old_root, new_root])
    monkeypatch.setattr("getpass.getpass", lambda prompt: next(answers))
    output = StringIO()

    Command(stdout=output).handle(confirm=True, batch_size=2)

    app_config.refresh_from_db()
    pool.refresh_from_db()
    access_key.refresh_from_db()
    assert json.loads(output.getvalue())["updated_fields"] == 5
    assert (
        _decrypt_secret_with_root(app_config.app_secret_encrypted, new_root)
        == "feishu-sk"
    )
    assert (
        _decrypt_secret_with_root(pool.management_access_key_encrypted, new_root)
        == "manager-ak"
    )
    assert (
        _decrypt_secret_with_root(pool.management_secret_key_encrypted, new_root)
        == "manager-sk"
    )
    assert (
        _decrypt_secret_with_root(access_key.access_key_id_encrypted, new_root)
        == "employee-ak"
    )
    assert (
        _decrypt_secret_with_root(access_key.secret_access_key_encrypted, new_root)
        == "employee-sk"
    )
