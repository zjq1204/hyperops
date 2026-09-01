from django.db import migrations, models

UNKNOWN_CONFIGURATION_ERROR_CODES = {
    "BUCKET_CONFIGURATION_ROLLBACK_FAILED",
    "BUCKET_CONFIGURATION_STATE_UNKNOWN",
}


def backfill_bucket_configuration_state(apps, schema_editor):
    Bucket = apps.get_model("object_storage", "Bucket")
    alias = schema_editor.connection.alias
    buckets = Bucket.objects.using(alias).all().iterator()
    for bucket in buckets:
        desired = bucket.desired_config_snapshot or {}
        applied = bucket.applied_config_snapshot or {}
        error_code = str(bucket.config_error_code or "")
        if error_code in UNKNOWN_CONFIGURATION_ERROR_CODES:
            config_state = "unknown"
        elif error_code:
            config_state = "retryable_error"
        elif desired and desired == applied:
            config_state = "applied"
        elif not applied and (not desired or bucket.state in {"requested", "creating"}):
            config_state = "pending"
        else:
            config_state = "retryable_error"
        Bucket.objects.using(alias).filter(pk=bucket.pk).update(
            config_state=config_state
        )


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
        migrations.RunPython(
            backfill_bucket_configuration_state,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
