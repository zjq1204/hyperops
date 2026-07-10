import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("monitoring_stack", "0011_monitoringintegrationconfig_prometheus_http_sd_token"),
    ]

    operations = [
        migrations.CreateModel(
            name="BlackboxProbeNode",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=120, unique=True)),
                ("address", models.CharField(max_length=255)),
                ("port", models.CharField(default="9115", max_length=16)),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("manual", "Manual"),
                            ("install", "HyperOps install"),
                        ],
                        default="manual",
                        max_length=20,
                    ),
                ),
                ("install_dir", models.CharField(blank=True, default="", max_length=255)),
                ("labels", models.JSONField(blank=True, default=dict)),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "host",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="blackbox_probe_nodes",
                        to="monitoring_stack.monitoringhost",
                    ),
                ),
                (
                    "last_job",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="blackbox_probe_nodes",
                        to="monitoring_stack.ansibleinstalljob",
                    ),
                ),
            ],
            options={
                "ordering": ["name", "id"],
            },
        ),
        migrations.AddField(
            model_name="probetarget",
            name="probe_node",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="probe_targets",
                to="monitoring_stack.blackboxprobenode",
            ),
        ),
        migrations.AddIndex(
            model_name="blackboxprobenode",
            index=models.Index(
                fields=["enabled", "source"],
                name="monitoring__probe_n_4f7fb1_idx",
            ),
        ),
    ]
