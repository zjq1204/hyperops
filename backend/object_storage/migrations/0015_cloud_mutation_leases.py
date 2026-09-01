from django.db import migrations, models
from django.utils import timezone


def expire_legacy_operation_tokens(apps, schema_editor):
    Bucket = apps.get_model("object_storage", "Bucket")
    AccessKey = apps.get_model("object_storage", "AccessKey")
    alias = schema_editor.connection.alias
    now = timezone.now()
    Bucket.objects.using(alias).filter(
        configuration_operation_token__gt="",
        configuration_operation_lease_until__isnull=True,
    ).update(
        configuration_operation_acquired_at=now,
        configuration_operation_lease_until=now,
    )
    Bucket.objects.using(alias).filter(
        action_owner_token__gt="",
        action_lease_until__isnull=True,
    ).update(
        action_acquired_at=now,
        action_lease_until=now,
    )
    AccessKey.objects.using(alias).filter(
        operation_token__gt="",
        operation_lease_until__isnull=True,
    ).update(
        operation_acquired_at=now,
        operation_lease_until=now,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("object_storage", "0014_resource_operation_fences"),
    ]

    operations = [
        migrations.AddField(
            model_name="bucket",
            name="action_acquired_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="bucket",
            name="action_lease_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="bucket",
            name="configuration_claim_generation",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="bucket",
            name="configuration_operation_acquired_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="bucket",
            name="configuration_operation_lease_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="accesskey",
            name="operation_acquired_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="accesskey",
            name="operation_error_code",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="accesskey",
            name="operation_lease_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cloudidentity",
            name="credential_operation_acquired_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cloudidentity",
            name="credential_operation_error_code",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="cloudidentity",
            name="credential_operation_generation",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="cloudidentity",
            name="credential_operation_key_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cloudidentity",
            name="credential_operation_lease_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cloudidentity",
            name="credential_operation_token",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="cloudidentity",
            name="credential_operation_type",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.RunPython(
            expire_legacy_operation_tokens,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
