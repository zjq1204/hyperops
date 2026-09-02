from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("object_storage", "0019_api_recovery_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="feishusyncconfirmation",
            name="local_baseline_hash",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
