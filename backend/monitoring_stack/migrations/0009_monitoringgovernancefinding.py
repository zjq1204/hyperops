from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring_stack", "0008_monitoring_governance_snapshots"),
    ]

    operations = [
        migrations.CreateModel(
            name="MonitoringGovernanceFinding",
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
                ("category", models.CharField(max_length=80)),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("critical", "Critical"),
                            ("warning", "Warning"),
                            ("info", "Info"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("resolved", "Resolved"),
                            ("ignored", "Ignored"),
                        ],
                        default="open",
                        max_length=20,
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("subject_type", models.CharField(max_length=40)),
                ("subject_key", models.CharField(max_length=512)),
                ("source", models.CharField(blank=True, default="", max_length=40)),
                ("details", models.JSONField(blank=True, default=dict)),
                (
                    "recommended_action",
                    models.CharField(blank=True, default="", max_length=80),
                ),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["severity", "category", "subject_key", "-updated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="monitoringgovernancefinding",
            index=models.Index(
                fields=["status", "severity"],
                name="monitoring__status_1d4814_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="monitoringgovernancefinding",
            index=models.Index(
                fields=["subject_type", "status"],
                name="monitoring__subject_7c2d6c_idx",
            ),
        ),
    ]
