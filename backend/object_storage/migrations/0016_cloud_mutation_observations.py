from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("object_storage", "0015_cloud_mutation_leases"),
    ]

    operations = [
        migrations.AddField(
            model_name="bucket",
            name="action_observed_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="bucket",
            name="configuration_observed_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="cloudidentity",
            name="credential_observed_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
