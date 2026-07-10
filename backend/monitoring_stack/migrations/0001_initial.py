import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MonitoringProfile",
            fields=[
                (
                    "id",
                    models.CharField(max_length=80, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=160)),
                ("category", models.CharField(blank=True, default="", max_length=80)),
                ("description", models.TextField(blank=True, default="")),
                ("plugins", models.JSONField(blank=True, default=list)),
                ("is_builtin", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["category", "id"]},
        ),
        migrations.CreateModel(
            name="ProbeTarget",
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
                    "external_id",
                    models.CharField(blank=True, max_length=80, null=True, unique=True),
                ),
                (
                    "type",
                    models.CharField(
                        choices=[("http", "HTTP"), ("tcp", "TCP"), ("icmp", "ICMP")],
                        max_length=16,
                    ),
                ),
                ("target", models.CharField(max_length=512)),
                ("enabled", models.BooleanField(default=True)),
                ("labels", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["type", "target", "id"]},
        ),
        migrations.CreateModel(
            name="MonitoringHost",
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
                    "external_id",
                    models.CharField(blank=True, max_length=80, null=True, unique=True),
                ),
                ("hostname", models.CharField(max_length=160)),
                ("address", models.CharField(max_length=255)),
                (
                    "ssh_user",
                    models.CharField(blank=True, default="root", max_length=80),
                ),
                ("ssh_port", models.PositiveIntegerField(default=22)),
                ("ssh_key", models.CharField(blank=True, default="", max_length=255)),
                ("profiles", models.JSONField(blank=True, default=list)),
                ("labels", models.JSONField(blank=True, default=dict)),
                ("params", models.JSONField(blank=True, default=dict)),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["hostname", "id"]},
        ),
        migrations.CreateModel(
            name="AnsibleInstallJob",
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
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                        ],
                        default="queued",
                        max_length=20,
                    ),
                ),
                ("profiles", models.JSONField(blank=True, default=list)),
                ("host_ids", models.JSONField(blank=True, default=list)),
                ("hosts_snapshot", models.JSONField(blank=True, default=list)),
                ("base_url", models.URLField(max_length=512)),
                ("n9e_url", models.URLField(max_length=512)),
                (
                    "install_dir",
                    models.CharField(default="/opt/categraf", max_length=255),
                ),
                (
                    "image",
                    models.CharField(
                        default="flashcatcloud/categraf:latest", max_length=255
                    ),
                ),
                ("returncode", models.IntegerField(blank=True, null=True)),
                ("logs", models.JSONField(blank=True, default=list)),
                ("results", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="monitoring_ansible_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="probetarget",
            index=models.Index(
                fields=["type", "enabled"], name="monitoring__type_846303_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="monitoringhost",
            index=models.Index(
                fields=["enabled"], name="monitoring__enabled_940a22_idx"
            ),
        ),
    ]
