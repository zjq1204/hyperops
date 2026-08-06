from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("monitoring_stack", "0013_blackboxprobenode_prometheus_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="monitoringhost",
            name="ssh_verification_checked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="monitoringhost",
            name="ssh_verification_error_code",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="monitoringhost",
            name="ssh_verification_latency_ms",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="monitoringhost",
            name="ssh_verification_signature",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="monitoringhost",
            name="ssh_verification_status",
            field=models.CharField(
                choices=[
                    ("unverified", "Unverified"),
                    ("verified", "Verified"),
                    ("failed", "Failed"),
                ],
                default="unverified",
                max_length=16,
            ),
        ),
        migrations.AddIndex(
            model_name="monitoringhost",
            index=models.Index(
                fields=["ssh_verification_status"],
                name="monitoring__ssh_ver_4dcbda_idx",
            ),
        ),
    ]
