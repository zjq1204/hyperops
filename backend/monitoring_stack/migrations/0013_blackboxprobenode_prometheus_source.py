from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("monitoring_stack", "0012_blackbox_probe_node_probe_target_binding"),
    ]

    operations = [
        migrations.AlterField(
            model_name="blackboxprobenode",
            name="source",
            field=models.CharField(
                choices=[
                    ("manual", "Manual"),
                    ("install", "HyperOps install"),
                    ("prometheus", "Prometheus discovery"),
                ],
                default="manual",
                max_length=20,
            ),
        ),
    ]
