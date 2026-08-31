import pytest

pytestmark = pytest.mark.django_db


def _payload(response):
    body = response.json()
    return body.get("data", body)


@pytest.fixture
def stable_secret_key(settings):
    settings.SECRET_KEY = "stable-admin-config-test-root"


@pytest.fixture
def superuser_client(client, django_user_model):
    user = django_user_model.objects.create_superuser(
        username="storage-superuser",
        email="root@example.com",
        password="secret123",
    )
    client.force_login(user)
    client.defaults["HTTP_IDEMPOTENCY_KEY"] = "admin-config-test"
    return client


def test_management_configuration_apis_require_superuser(
    client, django_user_model, storage_tenant_factory
):
    user = django_user_model.objects.create_user(
        username="ordinary-admin",
        password="secret123",
        is_staff=True,
    )
    client.force_login(user)

    response = client.get("/api/v1/object-storage/management/tenants/")

    assert response.status_code == 403


def test_superuser_creates_tenant_and_receives_only_safe_fields(
    superuser_client,
):
    response = superuser_client.post(
        "/api/v1/object-storage/management/tenants/",
        {
            "code": "example-corp",
            "name": "Example Corp",
            "default_bucket_quota": 5,
            "delivery_lifetime_seconds": 86400,
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    assert _payload(response)["code"] == "example-corp"


def test_superuser_updates_tenant_product_limits(
    superuser_client, storage_tenant_factory
):
    tenant = storage_tenant_factory()

    response = superuser_client.patch(
        f"/api/v1/object-storage/management/tenants/{tenant.id}/",
        {
            "default_bucket_quota": 7,
            "delivery_lifetime_seconds": 7200,
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    assert _payload(response)["default_bucket_quota"] == 7
    assert _payload(response)["delivery_lifetime_seconds"] == 7200


@pytest.mark.parametrize("seconds", [599, 604801])
def test_delivery_lifetime_rejects_values_outside_enterprise_range(
    superuser_client, storage_tenant_factory, seconds
):
    tenant = storage_tenant_factory()

    response = superuser_client.patch(
        f"/api/v1/object-storage/management/tenants/{tenant.id}/",
        {"delivery_lifetime_seconds": seconds},
        content_type="application/json",
    )

    assert response.status_code == 400


def test_feishu_config_encrypts_secret_and_never_returns_it(
    stable_secret_key, superuser_client, storage_tenant_factory
):
    from object_storage.crypto import decrypt_secret
    from object_storage.models import FeishuAppConfig

    tenant = storage_tenant_factory()
    response = superuser_client.put(
        f"/api/v1/object-storage/management/tenants/{tenant.id}/feishu/",
        {
            "app_id": "cli_app_id",
            "app_secret": "feishu-secret",
            "oauth_callback_url": "https://hyperops.example.com/callback",
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    payload = _payload(response)
    assert "app_secret" not in payload
    assert "app_secret_encrypted" not in payload
    config = FeishuAppConfig.objects.get(tenant=tenant)
    assert decrypt_secret(config.app_secret_encrypted) == "feishu-secret"
    assert config.enabled is False


def test_resource_pool_encrypts_credentials_and_returns_fingerprint_only(
    stable_secret_key, superuser_client, storage_tenant_factory
):
    from object_storage.crypto import decrypt_secret
    from object_storage.models import StorageResourcePool

    tenant = storage_tenant_factory()
    response = superuser_client.post(
        f"/api/v1/object-storage/management/tenants/{tenant.id}/resource-pools/",
        {
            "cloud_account_id": "123456789",
            "region": "cn-hangzhou",
            "management_access_key": "LTAIabcdefghijkl1234",
            "management_secret_key": "management-secret",
        },
        content_type="application/json",
    )

    assert response.status_code == 201
    payload = _payload(response)
    assert payload["access_key_last_four"] == "1234"
    assert payload["credential_fingerprint"]
    assert "management_access_key" not in payload
    assert "management_secret_key" not in payload
    pool = StorageResourcePool.objects.get(tenant=tenant)
    assert decrypt_secret(pool.management_access_key_encrypted).endswith("1234")
    assert decrypt_secret(pool.management_secret_key_encrypted) == "management-secret"


def test_pool_can_only_be_enabled_after_successful_validation(
    stable_secret_key,
    superuser_client,
    storage_resource_pool_factory,
    monkeypatch,
):
    from object_storage import views_admin
    from object_storage.models import StorageResourcePool
    from object_storage.providers.base import ManagementCapabilities

    pool = storage_resource_pool_factory(enabled=False)
    rejected = superuser_client.patch(
        f"/api/v1/object-storage/management/resource-pools/{pool.id}/",
        {"enabled": True},
        content_type="application/json",
    )
    monkeypatch.setattr(
        views_admin,
        "validate_resource_pool",
        lambda selected_pool: ManagementCapabilities(
            account_id=selected_pool.cloud_account_id,
            can_manage_ram=True,
            can_manage_oss=True,
            request_ids=("safe-request",),
        ),
    )
    validated = superuser_client.post(
        f"/api/v1/object-storage/management/resource-pools/{pool.id}/validate/"
    )
    enabled = superuser_client.patch(
        f"/api/v1/object-storage/management/resource-pools/{pool.id}/",
        {"enabled": True},
        content_type="application/json",
    )

    assert rejected.status_code == 400
    assert validated.status_code == 200
    assert enabled.status_code == 200
    pool.refresh_from_db()
    assert pool.validation_status == StorageResourcePool.ValidationStatus.VALID
    assert pool.enabled is True


def test_second_enabled_pool_for_tenant_is_rejected_as_validation_error(
    stable_secret_key,
    superuser_client,
    storage_resource_pool_factory,
):
    from object_storage.models import StorageResourcePool

    first = storage_resource_pool_factory(
        enabled=True,
        validation_status=StorageResourcePool.ValidationStatus.VALID,
    )
    second = storage_resource_pool_factory(
        tenant=first.tenant,
        enabled=False,
        validation_status=StorageResourcePool.ValidationStatus.VALID,
    )

    response = superuser_client.patch(
        f"/api/v1/object-storage/management/resource-pools/{second.id}/",
        {"enabled": True},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert _payload(response)["field_errors"]["enabled"] == [
        "ACTIVE_POOL_ALREADY_EXISTS"
    ]
