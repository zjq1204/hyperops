from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("monitoring_stack", "0010_monitoringsshkey_monitoringhost_ssh_auth_type_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="monitoringintegrationconfig",
            name="prometheus_http_sd_token",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
