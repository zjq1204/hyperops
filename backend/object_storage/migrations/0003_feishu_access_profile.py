from django.db import migrations, models


def default_visible_features():
    return ["workspace_dashboard", "object_storage"]


class Migration(migrations.Migration):
    dependencies = [
        ("object_storage", "0002_object_storage_user_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="feishuappconfig",
            name="preferred_platform",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Optional landing platform for users signing in through this app.",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="feishuappconfig",
            name="visible_features",
            field=models.JSONField(
                blank=True,
                default=default_visible_features,
                help_text="Feature keys granted to users signing in through this app.",
            ),
        ),
    ]
