import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring_stack", "0006_ansibleinstalljob_retry_of"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MonitoringIntegrationConfig",
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
                ("n9e_url", models.CharField(blank=True, default="", max_length=512)),
                (
                    "n9e_username",
                    models.CharField(blank=True, default="", max_length=120),
                ),
                (
                    "n9e_password",
                    models.CharField(blank=True, default="", max_length=512),
                ),
                (
                    "prometheus_url",
                    models.CharField(blank=True, default="", max_length=512),
                ),
                (
                    "grafana_url",
                    models.CharField(blank=True, default="", max_length=512),
                ),
                (
                    "installer_base_url",
                    models.CharField(blank=True, default="", max_length=512),
                ),
                (
                    "categraf_install_dir",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "blackbox_install_dir",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "blackbox_port",
                    models.CharField(blank=True, default="", max_length=16),
                ),
                (
                    "blackbox_image",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_monitoring_configs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Monitoring integration config",
                "verbose_name_plural": "Monitoring integration configs",
            },
        ),
    ]
