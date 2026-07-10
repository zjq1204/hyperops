import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring_stack", "0007_monitoringintegrationconfig"),
    ]

    operations = [
        migrations.CreateModel(
            name="MonitoringSnapshotRun",
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
                    "source",
                    models.CharField(
                        choices=[
                            ("all", "All"),
                            ("n9e", "n9e"),
                            ("prometheus", "Prometheus"),
                        ],
                        default="all",
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "Running"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                        ],
                        default="running",
                        max_length=20,
                    ),
                ),
                ("started_at", models.DateTimeField()),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("error", models.TextField(blank=True, default="")),
                ("summary", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "ordering": ["-started_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="N9eBusinessGroupSnapshot",
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
                ("external_id", models.CharField(max_length=120, unique=True)),
                ("name", models.CharField(blank=True, default="", max_length=255)),
                ("raw", models.JSONField(blank=True, default=dict)),
                ("last_seen_at", models.DateTimeField()),
                (
                    "last_seen_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="n9e_business_groups",
                        to="monitoring_stack.monitoringsnapshotrun",
                    ),
                ),
            ],
            options={
                "ordering": ["name", "external_id"],
            },
        ),
        migrations.CreateModel(
            name="N9eDatasourceSnapshot",
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
                ("external_id", models.CharField(max_length=120, unique=True)),
                ("name", models.CharField(blank=True, default="", max_length=255)),
                ("type", models.CharField(blank=True, default="", max_length=80)),
                ("raw", models.JSONField(blank=True, default=dict)),
                ("last_seen_at", models.DateTimeField()),
                (
                    "last_seen_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="n9e_datasources",
                        to="monitoring_stack.monitoringsnapshotrun",
                    ),
                ),
            ],
            options={
                "ordering": ["type", "name", "external_id"],
            },
        ),
        migrations.CreateModel(
            name="N9eRuleSnapshot",
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
                ("identity", models.CharField(max_length=255, unique=True)),
                ("group_id", models.CharField(blank=True, default="", max_length=120)),
                ("name", models.CharField(blank=True, default="", max_length=255)),
                ("enabled", models.BooleanField(default=True)),
                ("severity", models.CharField(blank=True, default="", max_length=80)),
                ("raw", models.JSONField(blank=True, default=dict)),
                ("last_seen_at", models.DateTimeField()),
                (
                    "last_seen_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="n9e_rules",
                        to="monitoring_stack.monitoringsnapshotrun",
                    ),
                ),
            ],
            options={
                "ordering": ["group_id", "name", "identity"],
            },
        ),
        migrations.CreateModel(
            name="N9eTargetSnapshot",
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
                ("identity", models.CharField(max_length=255, unique=True)),
                ("hostname", models.CharField(blank=True, default="", max_length=255)),
                ("address", models.CharField(blank=True, default="", max_length=255)),
                ("labels", models.JSONField(blank=True, default=dict)),
                ("raw", models.JSONField(blank=True, default=dict)),
                ("last_seen_at", models.DateTimeField()),
                (
                    "last_seen_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="n9e_targets",
                        to="monitoring_stack.monitoringsnapshotrun",
                    ),
                ),
            ],
            options={
                "ordering": ["hostname", "address", "identity"],
            },
        ),
        migrations.CreateModel(
            name="PrometheusTargetSnapshot",
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
                ("identity", models.CharField(max_length=512, unique=True)),
                ("job", models.CharField(blank=True, default="", max_length=255)),
                ("instance", models.CharField(blank=True, default="", max_length=512)),
                ("scrape_pool", models.CharField(blank=True, default="", max_length=255)),
                (
                    "health",
                    models.CharField(blank=True, default="unknown", max_length=40),
                ),
                ("probe_type", models.CharField(blank=True, default="", max_length=16)),
                ("probe_target", models.CharField(blank=True, default="", max_length=512)),
                ("last_error", models.TextField(blank=True, default="")),
                ("raw", models.JSONField(blank=True, default=dict)),
                ("last_seen_at", models.DateTimeField()),
                (
                    "last_seen_run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="prometheus_targets",
                        to="monitoring_stack.monitoringsnapshotrun",
                    ),
                ),
            ],
            options={
                "ordering": ["scrape_pool", "instance", "identity"],
            },
        ),
        migrations.AddIndex(
            model_name="monitoringsnapshotrun",
            index=models.Index(
                fields=["source", "status"],
                name="monitoring__snapsho_91c2d1_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="prometheustargetsnapshot",
            index=models.Index(fields=["health"], name="monitoring__health_123508_idx"),
        ),
        migrations.AddIndex(
            model_name="prometheustargetsnapshot",
            index=models.Index(fields=["probe_type"], name="monitoring__probe_t_178f9e_idx"),
        ),
    ]
