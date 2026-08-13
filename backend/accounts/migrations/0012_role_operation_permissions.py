from django.db import migrations, models


PERMISSIONS = [
    "monitoring_credentials_view",
    "monitoring_credentials_use",
    "monitoring_credentials_manage",
    "monitoring_credentials_delete",
]


def grant_existing_monitoring_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    for role in Role.objects.filter(is_active=True).iterator():
        if "admin_monitoring" in (role.visible_features or []):
            role.operation_permissions = list(PERMISSIONS)
            role.save(update_fields=["operation_permissions"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0011_ldap_group_mapping_scope")]
    operations = [
        migrations.AddField(
            model_name="role",
            name="operation_permissions",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(grant_existing_monitoring_roles, migrations.RunPython.noop),
    ]
