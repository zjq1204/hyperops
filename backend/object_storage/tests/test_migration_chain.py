from importlib import import_module

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)


def test_0003_uses_a_migration_local_default_callable():
    migration = import_module("object_storage.migrations.0003_feishu_access_profile")

    assert migration.default_visible_features() == [
        "workspace_dashboard",
        "object_storage",
    ]
    assert (
        migration.default_visible_features() is not migration.default_visible_features()
    )
    visible_features = migration.Migration.operations[1].field
    assert visible_features.default is migration.default_visible_features


def test_0004_reverse_restores_legacy_role_users_before_forwarding_to_0005():
    executor = MigrationExecutor(connection)
    executor.migrate([("object_storage", "0003_feishu_access_profile")])
    old_apps = executor.loader.project_state(
        [("object_storage", "0003_feishu_access_profile")]
    ).apps
    User = old_apps.get_model("auth", "User")
    Role = old_apps.get_model("accounts", "Role")
    StorageTenant = old_apps.get_model("object_storage", "StorageTenant")
    StorageMembership = old_apps.get_model("object_storage", "StorageMembership")
    FeishuAppConfig = old_apps.get_model("object_storage", "FeishuAppConfig")

    user = User.objects.create_user(username="legacy-migration-user")
    legacy_role, _created = Role.objects.get_or_create(
        name="Object Storage User",
        defaults={
            "visible_features": ["object_storage"],
            "operation_permissions": [],
            "preferred_platform": "object_storage",
            "is_active": True,
            "is_system": True,
        },
    )
    legacy_role.users.add(user)
    tenant = StorageTenant.objects.create(code="legacy-migration", name="Legacy")
    StorageMembership.objects.create(
        tenant=tenant,
        user=user,
        feishu_open_id="legacy-open-id",
        display_name="Legacy User",
    )
    config = FeishuAppConfig.objects.create(
        tenant=tenant,
        app_id="legacy-app",
        app_secret_encrypted="legacy-secret",
        oauth_callback_url="https://example.test/callback",
        preferred_platform="object_storage",
        visible_features=["workspace_dashboard"],
    )

    executor = MigrationExecutor(connection)
    executor.migrate([("object_storage", "0004_feishu_access_group")])
    forward_apps = executor.loader.project_state(
        [("object_storage", "0004_feishu_access_group")]
    ).apps
    ForwardConfig = forward_apps.get_model("object_storage", "FeishuAppConfig")
    ForwardRole = forward_apps.get_model("accounts", "Role")
    forward_config = ForwardConfig.objects.get(pk=config.pk)
    forward_role = ForwardRole.objects.get(
        name="Feishu access · tenant-{}".format(tenant.pk),
        is_system=True,
    )
    assert forward_config.access_group_id is not None
    assert not forward_role.users.filter(pk=user.pk).exists()

    executor = MigrationExecutor(connection)
    executor.migrate([("object_storage", "0003_feishu_access_profile")])
    reverse_apps = executor.loader.project_state(
        [("object_storage", "0003_feishu_access_profile")]
    ).apps
    ReverseConfig = reverse_apps.get_model("object_storage", "FeishuAppConfig")
    ReverseRole = reverse_apps.get_model("accounts", "Role")
    restored_config = ReverseConfig.objects.get(pk=config.pk)
    restored_role = ReverseRole.objects.get(name="Object Storage User", is_system=True)
    assert restored_config.preferred_platform == "object_storage"
    assert restored_config.visible_features == ["workspace_dashboard"]
    assert restored_role.users.filter(pk=user.pk).exists()

    executor = MigrationExecutor(connection)
    executor.migrate([("object_storage", "0005_platform_model")])
