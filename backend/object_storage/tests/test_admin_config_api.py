import pytest

pytestmark = pytest.mark.django_db


def _payload(response):
    body = response.json()
    return body.get("data", body)


@pytest.fixture(autouse=True)
def stable_secret(settings):
    settings.SECRET_KEY = "admin-config-api-contract-stable-secret"


@pytest.fixture
def admin_client(client, django_user_model):
    user = django_user_model.objects.create_superuser(
        username="storage-platform-admin", password="secret123"
    )
    client.force_login(user)
    return client, user


def test_management_requires_explicit_object_storage_feature(client, django_user_model):
    from accounts.models import Role

    staff = django_user_model.objects.create_user(username="staff-only", is_staff=True)
    client.force_login(staff)
    denied = client.get("/api/v1/object-storage/management/settings/")

    feature_user = django_user_model.objects.create_user(username="storage-admin")
    Role.objects.create(
        name="Object storage administrators",
        visible_features=["admin_object_storage"],
    ).users.add(feature_user)
    client.force_login(feature_user)
    allowed = client.get("/api/v1/object-storage/management/settings/")

    assert denied.status_code == 403
    assert allowed.status_code == 200


def test_platform_settings_are_singleton_and_mutations_require_idempotency(
    admin_client,
):
    client, admin = admin_client
    initial = client.get("/api/v1/object-storage/management/settings/")
    missing = client.patch(
        "/api/v1/object-storage/management/settings/",
        {"default_bucket_quota": 8},
        content_type="application/json",
    )
    updated = client.patch(
        "/api/v1/object-storage/management/settings/",
        {
            "default_bucket_quota": 8,
            "pause_new_applications": False,
            "default_storage_class": "IA",
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="settings-update-1",
    )

    assert initial.status_code == 200
    assert missing.status_code == 400
    assert updated.status_code == 200
    assert _payload(updated)["singleton_key"] == "default"
    assert _payload(updated)["default_bucket_quota"] == 8
    assert _payload(updated)["default_storage_class"] == "IA"


def test_platform_enable_endpoint_requires_valid_dependencies(
    admin_client, storage_resource_pool_factory
):
    from object_storage.models import PlatformFeishuConfig, StorageResourcePool

    client, _admin = admin_client
    feishu = PlatformFeishuConfig.objects.create(singleton_key="default")
    pool = storage_resource_pool_factory(
        validation_status=StorageResourcePool.ValidationStatus.PENDING
    )

    rejected = client.post(
        "/api/v1/object-storage/management/enable/",
        {"resource_pool_id": pool.id},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="platform-enable-rejected",
    )

    assert rejected.status_code == 400
    assert _payload(rejected)["error_code"] == "CONFIG_NOT_VALIDATED"

    feishu.validation_status = PlatformFeishuConfig.ValidationStatus.VALID
    feishu.save(update_fields=("validation_status", "updated_at"))
    pool.validation_status = StorageResourcePool.ValidationStatus.VALID
    pool.save(update_fields=("validation_status", "updated_at"))

    enabled = client.post(
        "/api/v1/object-storage/management/enable/",
        {"resource_pool_id": pool.id},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="platform-enable-valid",
    )

    feishu.refresh_from_db()
    pool.refresh_from_db()
    assert enabled.status_code == 200
    assert _payload(enabled)["enabled"] is True
    assert _payload(enabled)["resource_pool_id"] == pool.id
    assert feishu.enabled is True
    assert pool.enabled is True


def test_platform_feishu_settings_encrypt_secret_and_preserve_group_intent(
    admin_client,
):
    from django.contrib.auth.models import Group

    from object_storage.crypto import decrypt_secret
    from object_storage.models import FeishuIdentity, PlatformFeishuConfig

    client, admin = admin_client
    group = Group.objects.create(name="Storage Employees")
    identity = FeishuIdentity.objects.create(
        user=admin,
        open_id="open-id-platform-api",
        display_name="Storage Admin",
    )
    response = client.patch(
        "/api/v1/object-storage/management/feishu-settings/",
        {
            "app_id": "cli_platform",
            "app_secret": "feishu-plain-secret",
            "oauth_callback_url": "https://example.test/feishu/callback",
            "access_group": group.id,
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="feishu-settings-1",
    )

    config = PlatformFeishuConfig.objects.get(singleton_key="default")
    assert response.status_code == 200
    assert "app_secret" not in _payload(response)
    assert "encrypted" not in response.content.decode()
    assert decrypt_secret(config.app_secret_encrypted) == "feishu-plain-secret"
    assert identity.user.groups.filter(pk=group.id).exists()


def test_platform_feishu_settings_roll_back_when_access_group_sync_fails(
    admin_client, monkeypatch
):
    from django.contrib.auth.models import Group

    from object_storage.models import PlatformFeishuConfig

    client, _admin = admin_client
    original_group = Group.objects.create(name="Original Feishu Group")
    replacement_group = Group.objects.create(name="Replacement Feishu Group")
    config = PlatformFeishuConfig.objects.create(
        singleton_key="default",
        app_id="cli_original",
        app_secret_encrypted="encrypted-original-secret",
        oauth_callback_url="https://example.test/feishu/original",
        access_group=original_group,
    )
    monkeypatch.setattr(
        "object_storage.serializers_admin.sync_platform_feishu_access_group",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("sync failed")),
    )

    response = client.patch(
        "/api/v1/object-storage/management/feishu-settings/",
        {
            "app_id": "cli_replacement",
            "access_group": replacement_group.id,
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="feishu-settings-atomic-failure",
    )

    config.refresh_from_db()
    assert response.status_code == 500
    assert config.app_id == "cli_original"
    assert config.access_group_id == original_group.id
    assert config.oauth_callback_url == "https://example.test/feishu/original"


def test_feishu_enable_requires_validated_complete_platform_config(admin_client):
    from django.contrib.auth.models import Group
    from object_storage.models import PlatformFeishuConfig

    client, _admin = admin_client
    group = Group.objects.create(name="Validated Feishu Users")
    incomplete = client.patch(
        "/api/v1/object-storage/management/feishu-settings/",
        {
            "enabled": True,
            "app_id": "cli_unvalidated",
            "app_secret": "secret",
            "access_group": group.id,
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="feishu-enable-incomplete",
    )
    config = PlatformFeishuConfig.objects.get(singleton_key="default")
    config.app_id = "cli_validated"
    config.app_secret_encrypted = "encrypted-secret"
    config.access_group = group
    config.validation_status = PlatformFeishuConfig.ValidationStatus.VALID
    config.save()
    enabled = client.patch(
        "/api/v1/object-storage/management/feishu-settings/",
        {"enabled": True},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="feishu-enable-complete",
    )

    assert incomplete.status_code == 400
    assert _payload(incomplete)["field_errors"]["enabled"] == ["VALIDATION_REQUIRED"]
    assert enabled.status_code == 200
    assert _payload(enabled)["enabled"] is True


def test_feishu_connection_change_cannot_remain_enabled(admin_client):
    from django.contrib.auth.models import Group
    from object_storage.models import PlatformFeishuConfig

    client, _admin = admin_client
    group = Group.objects.create(name="Enabled Feishu Users")
    config = PlatformFeishuConfig.objects.create(
        singleton_key="default",
        app_id="cli_validated",
        app_secret_encrypted="encrypted-secret",
        oauth_callback_url="https://example.test/feishu/callback",
        access_group=group,
        validation_status=PlatformFeishuConfig.ValidationStatus.VALID,
        enabled=True,
    )

    response = client.patch(
        "/api/v1/object-storage/management/feishu-settings/",
        {"app_id": "cli_changed", "enabled": True},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="feishu-change-while-enabled",
    )

    config.refresh_from_db()
    assert response.status_code == 400
    assert _payload(response)["field_errors"]["enabled"] == ["VALIDATION_REQUIRED"]
    assert config.app_id == "cli_validated"
    assert config.validation_status == PlatformFeishuConfig.ValidationStatus.VALID
    assert config.enabled is True


def test_resource_pool_connection_validation_never_returns_provider_exception(
    admin_client, storage_resource_pool_factory, monkeypatch
):
    from object_storage.services.platform import PlatformConfigurationError

    client, _admin = admin_client
    pool = storage_resource_pool_factory()

    def fail(*args, **kwargs):
        raise PlatformConfigurationError(
            "PROVIDER_VALIDATION_FAILED",
            cause=RuntimeError("SDK traceback with secret credential"),
        )

    monkeypatch.setattr("object_storage.views_admin.validate_resource_pool", fail)
    response = client.post(
        f"/api/v1/object-storage/management/resource-pools/{pool.id}/validate/",
        {},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="validate-pool-1",
    )

    assert response.status_code == 400
    assert _payload(response)["error_code"] == "PROVIDER_VALIDATION_FAILED"
    assert "traceback" not in response.content.decode().lower()
    assert "credential" not in response.content.decode().lower()


def test_resource_pool_account_is_locked_after_real_resources_exist(
    admin_client, cloud_identity_factory, bucket_factory
):
    client, _admin = admin_client
    identity = cloud_identity_factory()
    bucket_factory(cloud_identity=identity)

    response = client.patch(
        f"/api/v1/object-storage/management/resource-pools/{identity.resource_pool_id}/",
        {"cloud_account_id": "different-cloud-account"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="locked-resource-pool-1",
    )

    identity.resource_pool.refresh_from_db()
    assert response.status_code == 409
    assert _payload(response)["error_code"] == "RESOURCE_POOL_ID_LOCKED"
    assert identity.resource_pool.cloud_account_id != "different-cloud-account"


def test_user_quota_override_is_platform_scoped(admin_client, user_factory):
    client, _admin = admin_client
    user = user_factory()
    created = client.put(
        f"/api/v1/object-storage/management/user-quotas/{user.id}/",
        {"bucket_quota": 12},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="quota-user-1",
    )
    listed = client.get("/api/v1/object-storage/management/user-quotas/")

    assert created.status_code == 200
    assert _payload(created)["user_id"] == user.id
    assert _payload(created)["bucket_quota"] == 12
    assert [row["user_id"] for row in _payload(listed)] == [user.id]


def test_user_quota_override_requires_a_valid_quota(admin_client, user_factory):
    from object_storage.models import UserBucketQuota

    client, _admin = admin_client
    user = user_factory()

    response = client.put(
        f"/api/v1/object-storage/management/user-quotas/{user.id}/",
        {},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="quota-user-invalid",
    )

    assert response.status_code == 400
    assert not UserBucketQuota.objects.filter(user=user).exists()


def test_user_quota_delete_rolls_back_when_audit_write_fails(
    admin_client, user_factory, monkeypatch
):
    from object_storage.models import AuditEvent, UserBucketQuota
    from object_storage.services.audit import record_audit_event as real_record

    client, _admin = admin_client
    user = user_factory()
    quota = UserBucketQuota.objects.create(user=user, bucket_quota=7)

    def fail_after_write(**kwargs):
        real_record(**kwargs)
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(
        "object_storage.views_admin.record_audit_event", fail_after_write
    )

    response = client.delete(
        f"/api/v1/object-storage/management/user-quotas/{user.id}/",
        HTTP_IDEMPOTENCY_KEY="quota-delete-audit-failure",
    )

    assert response.status_code == 500
    assert UserBucketQuota.objects.filter(pk=quota.pk).exists()
    assert not AuditEvent.objects.filter(
        action="storage.api.user_quota.delete",
        request_id="quota-delete-audit-failure",
    ).exists()


def test_legacy_tenant_configuration_routes_do_not_exist(admin_client):
    client, _admin = admin_client

    response = client.get("/api/v1/object-storage/management/tenants/")

    assert response.status_code == 404
