from django.db import migrations

ROLE_NAME = "Object Storage User"


def create_object_storage_role(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.update_or_create(
        name=ROLE_NAME,
        defaults={
            "visible_features": ["object_storage"],
            "operation_permissions": [],
            "preferred_platform": "object_storage",
            "is_active": True,
            "is_system": True,
        },
    )


def remove_object_storage_role(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.filter(name=ROLE_NAME, is_system=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0013_role_is_system"),
        ("object_storage", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            create_object_storage_role,
            remove_object_storage_role,
        ),
    ]
