from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("monitoring_stack", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="ansibleinstalljob",
            name="component",
            field=models.CharField(
                choices=[
                    ("categraf", "Categraf"),
                    ("blackbox", "blackbox-exporter"),
                ],
                default="categraf",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="ansibleinstalljob",
            name="n9e_url",
            field=models.URLField(blank=True, default="", max_length=512),
        ),
        migrations.AddField(
            model_name="ansibleinstalljob",
            name="probe_name",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="ansibleinstalljob",
            name="blackbox_port",
            field=models.CharField(blank=True, default="9115", max_length=16),
        ),
    ]
