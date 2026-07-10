from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("monitoring_stack", "0002_ansibleinstalljob_component_blackbox"),
    ]

    operations = [
        migrations.AddField(
            model_name="ansibleinstalljob",
            name="labels",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="ansibleinstalljob",
            name="params",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
