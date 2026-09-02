from importlib import import_module

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db(transaction=True)
CURRENT_LEAF = ("object_storage", "0019_api_recovery_state")


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


def _assert_0004_reverse_restores_legacy_role_users():
    executor = MigrationExecutor(connection)
    executor.migrate([("object_storage", "0003_feishu_access_profile")])
    old_apps = executor.loader.project_state(
        [("object_storage", "0003_feishu_access_profile")]
    ).apps
    User = old_apps.get_model("auth", "User")
    Group = old_apps.get_model("auth", "Group")
    Role = old_apps.get_model("accounts", "Role")
    StorageTenant = old_apps.get_model("object_storage", "StorageTenant")
    StorageMembership = old_apps.get_model("object_storage", "StorageMembership")
    FeishuAppConfig = old_apps.get_model("object_storage", "FeishuAppConfig")

    user = User.objects.create_user(username="legacy-migration-user")
    extra_group_user = User.objects.create_user(username="extra-group-user")
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
    group = Group.objects.create(name="Feishu users · tenant-{}".format(tenant.pk))
    group.user_set.add(extra_group_user)
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
    assert not restored_role.users.filter(pk=extra_group_user.pk).exists()


def test_0004_reverse_restores_legacy_role_users_before_forwarding_to_0005():
    try:
        _assert_0004_reverse_restores_legacy_role_users()
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate([CURRENT_LEAF])


def test_0013_backfills_bucket_configuration_state_without_losing_uncertainty():
    executor = MigrationExecutor(connection)
    try:
        executor.migrate([("object_storage", "0012_platform_default_acl_private")])
        old_apps = executor.loader.project_state(
            [("object_storage", "0012_platform_default_acl_private")]
        ).apps
        User = old_apps.get_model("auth", "User")
        Config = old_apps.get_model("object_storage", "PlatformObjectStorageConfig")
        Pool = old_apps.get_model("object_storage", "StorageResourcePool")
        Identity = old_apps.get_model("object_storage", "CloudIdentity")
        Bucket = old_apps.get_model("object_storage", "Bucket")

        user = User.objects.create_user(username="configuration-migration-user")
        config, _created = Config.objects.get_or_create(singleton_key="default")
        pool = Pool.objects.create(
            config=config,
            cloud_account_id="configuration-migration-account",
            region="cn-hangzhou",
            management_access_key_encrypted="encrypted-ak",
            management_secret_key_encrypted="encrypted-sk",
            credential_fingerprint="configuration-migration-fingerprint",
            access_key_last_four="1234",
        )
        identity = Identity.objects.create(
            user=user,
            resource_pool=pool,
            ram_user_name="configuration-migration-user",
        )
        private = {
            "acl": "private",
            "storage_class": "Standard",
            "encryption": "AES256",
            "versioning": False,
            "lifecycle": {},
        }
        public = {**private, "acl": "public_read"}
        rows = {
            "applied": (private, private, "", "active"),
            "pending-empty": ({}, {}, "", "active"),
            "pending-requested": (private, {}, "", "requested"),
            "unapplied-active": (private, {}, "", "active"),
            "mismatch": (public, private, "", "active"),
            "provider-error": (
                private,
                private,
                "PROVIDER_PERMISSION_DENIED",
                "active",
            ),
            "rollback-failed": (
                public,
                private,
                "BUCKET_CONFIGURATION_ROLLBACK_FAILED",
                "active",
            ),
            "cloud-state-unknown": (
                public,
                private,
                "BUCKET_CONFIGURATION_STATE_UNKNOWN",
                "active",
            ),
        }
        bucket_ids = {}
        for label, (desired, applied, error_code, state) in rows.items():
            bucket_ids[label] = Bucket.objects.create(
                owner=user,
                resource_pool=pool,
                cloud_identity=identity,
                business_name=label,
                name=f"configuration-migration-{label}",
                purpose="migration test",
                region=pool.region,
                desired_config_snapshot=desired,
                applied_config_snapshot=applied,
                config_error_code=error_code,
                state=state,
            ).pk

        executor = MigrationExecutor(connection)
        executor.migrate([("object_storage", "0013_bucket_configuration_state")])
        new_apps = executor.loader.project_state(
            [("object_storage", "0013_bucket_configuration_state")]
        ).apps
        MigratedBucket = new_apps.get_model("object_storage", "Bucket")
        states = {
            label: MigratedBucket.objects.get(pk=bucket_id).config_state
            for label, bucket_id in bucket_ids.items()
        }

        assert states == {
            "applied": "applied",
            "pending-empty": "pending",
            "pending-requested": "pending",
            "unapplied-active": "retryable_error",
            "mismatch": "retryable_error",
            "provider-error": "retryable_error",
            "rollback-failed": "unknown",
            "cloud-state-unknown": "unknown",
        }

        executor = MigrationExecutor(connection)
        executor.migrate([("object_storage", "0014_resource_operation_fences")])
        fence_apps = executor.loader.project_state(
            [("object_storage", "0014_resource_operation_fences")]
        ).apps
        FencedBucket = fence_apps.get_model("object_storage", "Bucket")
        FencedBucket.objects.filter(pk=bucket_ids["mismatch"]).update(
            configuration_operation_token="legacy-config-token"
        )
        FencedBucket.objects.filter(pk=bucket_ids["provider-error"]).update(
            action_owner_token="legacy-action-token",
            action_type="release",
        )

        executor = MigrationExecutor(connection)
        executor.migrate([("object_storage", "0015_cloud_mutation_leases")])
        lease_apps = executor.loader.project_state(
            [("object_storage", "0015_cloud_mutation_leases")]
        ).apps
        LeasedBucket = lease_apps.get_model("object_storage", "Bucket")
        config_claim = LeasedBucket.objects.get(pk=bucket_ids["mismatch"])
        action_claim = LeasedBucket.objects.get(pk=bucket_ids["provider-error"])
        assert config_claim.configuration_operation_acquired_at is not None
        assert config_claim.configuration_operation_lease_until is not None
        assert action_claim.action_acquired_at is not None
        assert action_claim.action_lease_until is not None

        executor = MigrationExecutor(connection)
        executor.migrate([("object_storage", "0012_platform_default_acl_private")])
        reversed_apps = executor.loader.project_state(
            [("object_storage", "0012_platform_default_acl_private")]
        ).apps
        ReversedBucket = reversed_apps.get_model("object_storage", "Bucket")
        rollback_row = ReversedBucket.objects.get(pk=bucket_ids["rollback-failed"])
        assert rollback_row.desired_config_snapshot == public
        assert rollback_row.applied_config_snapshot == private
        assert rollback_row.config_error_code == "BUCKET_CONFIGURATION_ROLLBACK_FAILED"
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate([CURRENT_LEAF])
