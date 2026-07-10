import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring_stack", "0004_monitoringcomponentstatus"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RuleImportRecord",
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
                ("rule_file", models.CharField(max_length=255)),
                ("group_id", models.IntegerField()),
                ("datasource_id", models.IntegerField()),
                ("enabled", models.BooleanField(default=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("success", "Success"),
                            ("partial", "Partial"),
                            ("failed", "Failed"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "template_category",
                    models.CharField(blank=True, default="", max_length=40),
                ),
                ("summary", models.JSONField(blank=True, default=dict)),
                ("result", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="monitoring_rule_imports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["rule_file", "status"],
                        name="monitoring__rule_fi_2f0a34_idx",
                    )
                ],
            },
        ),
    ]
