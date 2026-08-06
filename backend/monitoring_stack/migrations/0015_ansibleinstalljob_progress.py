from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("monitoring_stack", "0014_monitoringhost_ssh_verification"),
    ]

    operations = [
        migrations.AddField(
            model_name="ansibleinstalljob",
            name="progress",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
