from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("object_storage", "0012_platform_default_acl_private"),
    ]

    operations = [
        migrations.AddField(
            model_name="bucket",
            name="config_state",
            field=models.CharField(
                choices=[
                    ("applied", "Applied"),
                    ("pending", "Pending"),
                    ("retryable_error", "Retryable error"),
                    ("unknown", "Unknown"),
                ],
                default="applied",
                max_length=24,
            ),
        ),
    ]
