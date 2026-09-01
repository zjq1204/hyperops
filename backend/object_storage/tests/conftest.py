import itertools
import os

import pytest

# This test package is the only scope that opts the optional app in by default.
os.environ.setdefault("ENABLE_OBJECT_STORAGE", "true")


@pytest.fixture(scope="session", autouse=True)
def object_storage_installed_app():
    from django.apps import apps
    from django.conf import settings

    if apps.is_installed("object_storage"):
        yield
        return

    original_installed_apps = settings.INSTALLED_APPS
    original_enabled = settings.ENABLE_OBJECT_STORAGE
    installed_apps = [
        (
            "django.contrib.admin.apps.SimpleAdminConfig"
            if app == "django.contrib.admin"
            else app
        )
        for app in original_installed_apps
    ]
    installed_apps.append("object_storage")
    settings.ENABLE_OBJECT_STORAGE = True
    settings.INSTALLED_APPS = installed_apps
    apps.set_installed_apps(installed_apps)
    try:
        yield
    finally:
        apps.unset_installed_apps()
        settings.INSTALLED_APPS = original_installed_apps
        settings.ENABLE_OBJECT_STORAGE = original_enabled


@pytest.fixture(autouse=True)
def object_storage_test_settings(settings):
    settings.ENABLE_OBJECT_STORAGE = True
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "object-storage-tests",
        }
    }


@pytest.fixture
def user_factory(db, django_user_model):
    sequence = itertools.count(1)

    def create(**overrides):
        number = next(sequence)
        values = {"username": f"storage-user-{number}"}
        values.update(overrides)
        user = django_user_model.objects.create_user(**values)
        from accounts.models import Role

        role, _created = Role.objects.get_or_create(
            name="Object storage workspace user",
            defaults={"visible_features": ["object_storage"]},
        )
        user.platform_roles.add(role)
        return user

    return create


@pytest.fixture
def platform_object_storage_config(db):
    from object_storage.models import PlatformObjectStorageConfig

    config, _created = PlatformObjectStorageConfig.objects.get_or_create(
        singleton_key="default"
    )
    return config


@pytest.fixture
def storage_resource_pool_factory(db, platform_object_storage_config):
    from object_storage.models import StorageResourcePool

    sequence = itertools.count(1)

    def create(**overrides):
        number = next(sequence)
        config = overrides.pop("config", platform_object_storage_config)
        values = {
            "config": config,
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
def feishu_identity_factory(db, user_factory):
    from object_storage.models import FeishuIdentity

    sequence = itertools.count(1)

    def create(**overrides):
        number = next(sequence)
        user = overrides.pop("user", None) or user_factory()
        values = {
            "user": user,
            "open_id": f"open-id-{number}",
            "display_name": f"Storage User {number}",
        }
        values.update(overrides)
        return FeishuIdentity.objects.create(**values)

    return create


@pytest.fixture
def cloud_identity_factory(db, user_factory, storage_resource_pool_factory):
    from object_storage.models import CloudIdentity

    sequence = itertools.count(1)

    def create(**overrides):
        number = next(sequence)
        user = overrides.pop("user", None) or user_factory()
        resource_pool = overrides.pop("resource_pool", None)
        if resource_pool is None:
            resource_pool = storage_resource_pool_factory()
        values = {
            "user": user,
            "resource_pool": resource_pool,
            "ram_user_id": f"ram-id-{number}",
            "ram_user_name": f"ram-user-{number}",
        }
        values.update(overrides)
        return CloudIdentity.objects.create(**values)

    return create


@pytest.fixture
def bucket_factory(db, cloud_identity_factory):
    from object_storage.models import Bucket

    sequence = itertools.count(1)

    def create(**overrides):
        number = next(sequence)
        identity = overrides.pop("cloud_identity", None) or cloud_identity_factory()
        values = {
            "owner": identity.user,
            "resource_pool": identity.resource_pool,
            "cloud_identity": identity,
            "business_name": f"Business {number}",
            "name": f"hyperops-user-project-{number}",
            "project": "project",
            "environment": Bucket.Environment.TEST,
            "purpose": "integration testing",
            "region": identity.resource_pool.region,
            "cloud_resource_id": f"oss-resource-{number}",
        }
        values.update(overrides)
        return Bucket.objects.create(**values)

    return create


@pytest.fixture
def access_key_factory(db, cloud_identity_factory):
    from object_storage.models import AccessKey

    sequence = itertools.count(1)

    def create(**overrides):
        number = next(sequence)
        identity = overrides.pop("cloud_identity", None) or cloud_identity_factory()
        values = {
            "cloud_identity": identity,
            "access_key_id_encrypted": f"encrypted-user-ak-{number}",
            "secret_access_key_encrypted": f"encrypted-user-sk-{number}",
            "access_key_fingerprint": f"user-fingerprint-{number}",
            "access_key_last_four": f"{number:04d}",
        }
        values.update(overrides)
        return AccessKey.objects.create(**values)

    return create


@pytest.fixture
def application_batch_factory(db, user_factory):
    from object_storage.models import ApplicationBatch, ApplicationItem

    sequence = itertools.count(1)

    def create(item_count=0, **overrides):
        number = next(sequence)
        applicant = overrides.pop("applicant", None) or user_factory()
        values = {
            "applicant": applicant,
            "idempotency_key": f"application-{number}",
            "item_count": item_count,
            "pending_count": item_count,
        }
        values.update(overrides)
        batch = ApplicationBatch.objects.create(**values)
        for item_number in range(1, item_count + 1):
            ApplicationItem.objects.create(
                batch=batch,
                business_name=f"Business {item_number}",
                project="project",
                environment="test",
                purpose="integration testing",
                initial_suffix="preview1",
                rendered_bucket_name=f"hyperops-batch-{number}-{item_number}",
            )
        return batch

    return create
