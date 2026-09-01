from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("object_storage", "0011_bucket_lifecycle_configuration"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="platformobjectstorageconfig",
            constraint=models.CheckConstraint(
                condition=models.Q(default_bucket_acl="private"),
                name="storage_platform_default_acl_private",
            ),
        ),
    ]
