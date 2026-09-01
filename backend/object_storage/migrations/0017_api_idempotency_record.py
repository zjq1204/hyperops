from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("object_storage", "0016_cloud_mutation_observations"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApiIdempotencyRecord",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "scope",
                    models.CharField(max_length=512),
                ),
                (
                    "idempotency_key",
                    models.CharField(max_length=128),
                ),
                (
                    "payload_digest",
                    models.CharField(max_length=64),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("in_progress", "In progress"),
                            ("completed", "Completed"),
                        ],
                        default="in_progress",
                        max_length=16,
                    ),
                ),
                (
                    "response_status",
                    models.PositiveSmallIntegerField(blank=True, null=True),
                ),
                (
                    "response_body",
                    models.JSONField(blank=True, null=True),
                ),
                (
                    "actor",
                    models.ForeignKey(
                        on_delete=models.deletion.PROTECT,
                        related_name="object_storage_api_idempotency_records",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(
                        fields=["actor", "status", "created_at"],
                        name="os_api_idempotency_actor_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("actor", "scope", "idempotency_key"),
                        name="storage_api_idempotency_actor_scope_key",
                    )
                ],
            },
        ),
    ]
