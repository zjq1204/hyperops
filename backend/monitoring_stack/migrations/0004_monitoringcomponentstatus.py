import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring_stack", "0003_ansibleinstalljob_labels_params"),
    ]

    operations = [
        migrations.CreateModel(
            name="MonitoringComponentStatus",
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
                (
                    "component",
                    models.CharField(
                        choices=[
                            ("categraf", "Categraf"),
                            ("blackbox", "blackbox-exporter"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("unknown", "Unknown"),
                            ("installing", "Installing"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                        ],
                        default="unknown",
                        max_length=20,
                    ),
                ),
                ("version", models.CharField(blank=True, default="", max_length=80)),
                (
                    "install_dir",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("last_error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "host",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="component_statuses",
                        to="monitoring_stack.monitoringhost",
                    ),
                ),
                (
                    "last_job",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="component_statuses",
                        to="monitoring_stack.ansibleinstalljob",
                    ),
                ),
            ],
            options={
                "ordering": ["host__hostname", "component"],
                "indexes": [
                    models.Index(
                        fields=["component", "status"],
                        name="monitoring__compone_51d3e5_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("host", "component"),
                        name="unique_monitoring_component_status",
                    )
                ],
            },
        ),
    ]
