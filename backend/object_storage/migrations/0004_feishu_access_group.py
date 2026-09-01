from django.db import migrations, models

FEISHU_ROLE_NAME = "Feishu access · tenant-{}"
FEISHU_GROUP_NAME = "Feishu users · tenant-{}"
DEFAULT_VISIBLE_FEATURES = ["workspace_dashboard", "object_storage"]


def bind_existing_configs_to_groups(apps, schema_editor):
    FeishuAppConfig = apps.get_model("object_storage", "FeishuAppConfig")
    StorageMembership = apps.get_model("object_storage", "StorageMembership")
    Group = apps.get_model("auth", "Group")
    Role = apps.get_model("accounts", "Role")
    legacy_role = Role.objects.filter(
        name="Object Storage User",
        is_system=True,
    ).first()

    for config in FeishuAppConfig.objects.all().iterator():
        group, _created = Group.objects.get_or_create(
            name=FEISHU_GROUP_NAME.format(config.tenant_id)
        )
        role, _created = Role.objects.update_or_create(
            name=FEISHU_ROLE_NAME.format(config.tenant_id),
            defaults={
                "visible_features": config.visible_features or DEFAULT_VISIBLE_FEATURES,
                "operation_permissions": [],
                "preferred_platform": config.preferred_platform or "",
                "is_active": True,
                "is_system": True,
            },
        )
        group.platform_roles.add(role)
        member_user_ids = list(
            StorageMembership.objects.filter(tenant_id=config.tenant_id).values_list(
                "user_id", flat=True
            )
        )
        group.user_set.add(*member_user_ids)
        if legacy_role is not None:
            legacy_role.users.remove(*member_user_ids)
        config.access_group_id = group.pk
        config.save(update_fields=("access_group",))


def restore_legacy_access_profile(apps, schema_editor):
    FeishuAppConfig = apps.get_model("object_storage", "FeishuAppConfig")
    StorageMembership = apps.get_model("object_storage", "StorageMembership")
    Role = apps.get_model("accounts", "Role")
    legacy_role = Role.objects.filter(
        name="Object Storage User",
        is_system=True,
    ).first()
    for config in FeishuAppConfig.objects.all().iterator():
        role = Role.objects.filter(
            name=FEISHU_ROLE_NAME.format(config.tenant_id), is_system=True
        ).first()
        if role is None:
            continue
        config.visible_features = role.visible_features or DEFAULT_VISIBLE_FEATURES
        config.preferred_platform = role.preferred_platform or ""
        config.save(update_fields=("visible_features", "preferred_platform"))
        if legacy_role is not None:
            member_user_ids = list(
                StorageMembership.objects.filter(
                    tenant_id=config.tenant_id
                ).values_list("user_id", flat=True)
            )
            legacy_role.users.add(*member_user_ids)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0013_role_is_system"),
        ("object_storage", "0003_feishu_access_profile"),
    ]

    operations = [
        migrations.AddField(
            model_name="feishuappconfig",
            name="access_group",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Local group whose roles are granted to users signing in through "
                    "this app."
                ),
                null=True,
                on_delete=models.deletion.PROTECT,
                related_name="feishu_app_configs",
                to="auth.group",
            ),
        ),
        migrations.RunPython(
            bind_existing_configs_to_groups,
            restore_legacy_access_profile,
        ),
        migrations.RemoveField(
            model_name="feishuappconfig",
            name="preferred_platform",
        ),
        migrations.RemoveField(
            model_name="feishuappconfig",
            name="visible_features",
        ),
    ]
