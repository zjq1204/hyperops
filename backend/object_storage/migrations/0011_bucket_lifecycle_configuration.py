from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("object_storage", "0010_application_claim_version")]

    operations = [
        migrations.AddField(
            model_name="platformobjectstorageconfig",
            name="default_bucket_acl",
            field=models.CharField(default="private", max_length=20),
        ),
        migrations.AddField(
            model_name="platformobjectstorageconfig",
            name="default_encryption",
            field=models.CharField(default="AES256", max_length=32),
        ),
        migrations.AddField(
            model_name="platformobjectstorageconfig",
            name="default_lifecycle",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="platformobjectstorageconfig",
            name="default_storage_class",
            field=models.CharField(default="Standard", max_length=32),
        ),
        migrations.AddField(
            model_name="platformobjectstorageconfig",
            name="default_versioning",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="bucket",
            name="applied_config_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="bucket",
            name="config_error_code",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="bucket",
            name="config_error_summary",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="bucket",
            name="deletion_error_code",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="bucket",
            name="deletion_error_summary",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="bucket",
            name="desired_config_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="accesskey",
            name="local_state",
            field=models.CharField(
                choices=[
                    ("issuing", "Issuing"),
                    ("delivery_ready", "Delivery ready"),
                    ("active", "Active"),
                    ("disabled", "Disabled"),
                    ("retiring", "Retiring"),
                    ("retired", "Retired"),
                    ("error", "Error"),
                ],
                default="issuing",
                max_length=24,
            ),
        ),
    ]
