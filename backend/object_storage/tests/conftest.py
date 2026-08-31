import itertools

import pytest


@pytest.fixture
def storage_tenant_factory(db):
    from object_storage.models import StorageTenant

    sequence = itertools.count(1)

    def create(**overrides):
        number = next(sequence)
        values = {
            "code": f"tenant-{number}",
            "name": f"Tenant {number}",
        }
        values.update(overrides)
        return StorageTenant.objects.create(**values)

    return create


@pytest.fixture
def storage_membership_factory(db, django_user_model, storage_tenant_factory):
    from object_storage.models import StorageMembership

    sequence = itertools.count(1)

    def create(**overrides):
        number = next(sequence)
        tenant = overrides.pop("tenant", None) or storage_tenant_factory()
        user = overrides.pop("user", None) or django_user_model.objects.create_user(
            username=f"storage-user-{number}"
        )
        values = {
            "tenant": tenant,
            "user": user,
            "feishu_open_id": f"open-id-{number}",
            "display_name": f"Storage User {number}",
        }
        values.update(overrides)
        return StorageMembership.objects.create(**values)

    return create


@pytest.fixture
def storage_resource_pool_factory(db, storage_tenant_factory):
    from object_storage.models import StorageResourcePool

    sequence = itertools.count(1)

    def create(**overrides):
        number = next(sequence)
        tenant = overrides.pop("tenant", None) or storage_tenant_factory()
        values = {
            "tenant": tenant,
            "cloud_account_id": f"cloud-account-{number}",
            "region": "cn-hangzhou",
            "management_access_key_encrypted": f"encrypted-ak-{number}",
            "management_secret_key_encrypted": f"encrypted-sk-{number}",
            "credential_fingerprint": f"fingerprint-{number}",
            "access_key_last_four": f"{number:04d}",
        }
        values.update(overrides)
        return StorageResourcePool.objects.create(**values)

    return create


@pytest.fixture
def storage_cloud_identity_factory(
    db, storage_membership_factory, storage_resource_pool_factory
):
    from object_storage.models import StorageCloudIdentity

    sequence = itertools.count(1)

    def create(**overrides):
        number = next(sequence)
        membership = overrides.pop("membership", None) or storage_membership_factory()
        pool = overrides.pop("resource_pool", None)
        if pool is None:
            pool = storage_resource_pool_factory(tenant=membership.tenant)
        values = {
            "tenant": membership.tenant,
            "membership": membership,
            "resource_pool": pool,
            "ram_user_id": f"ram-id-{number}",
            "ram_user_name": f"ram-user-{number}",
        }
        values.update(overrides)
        return StorageCloudIdentity.objects.create(**values)

    return create


@pytest.fixture
def storage_bucket_factory(db, storage_cloud_identity_factory):
    from object_storage.models import StorageBucket

    sequence = itertools.count(1)

    def create(**overrides):
        number = next(sequence)
        identity = (
            overrides.pop("cloud_identity", None) or storage_cloud_identity_factory()
        )
        values = {
            "tenant": identity.tenant,
            "resource_pool": identity.resource_pool,
            "owner": identity.membership,
            "cloud_identity": identity,
            "name": f"tenant-user-project-{number}",
            "project": "project",
            "environment": "test",
            "purpose": "integration testing",
            "region": identity.resource_pool.region,
            "cloud_resource_id": f"oss-resource-{number}",
        }
        values.update(overrides)
        return StorageBucket.objects.create(**values)

    return create
