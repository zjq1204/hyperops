from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("object_storage", "0018_api_idempotency_actor_cascade"),
    ]

    operations = [
        migrations.AddField(
            model_name="apiidempotencyrecord",
            name="attempt_count",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="apiidempotencyrecord",
            name="lease_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="apiidempotencyrecord",
            name="owner_token",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="apiidempotencyrecord",
            name="status",
            field=models.CharField(
                choices=[
                    ("in_progress", "In progress"),
                    ("completed", "Completed"),
                    ("outcome_unknown", "Outcome unknown"),
                ],
                default="in_progress",
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="FeishuSyncConfirmation",
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
                ("token_digest", models.CharField(max_length=64, unique=True)),
                ("config_fingerprint", models.CharField(max_length=64)),
                ("snapshot_hash", models.CharField(max_length=64)),
                ("snapshot", models.JSONField()),
                ("actions", models.JSONField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ready", "Ready"),
                            ("consumed", "Consumed"),
                            ("expired", "Expired"),
                        ],
                        default="ready",
                        max_length=16,
                    ),
                ),
                ("expires_at", models.DateTimeField()),
                ("consumed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="object_storage_feishu_sync_confirmations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "config",
                    models.ForeignKey(
                        on_delete=models.deletion.PROTECT,
                        related_name="sync_confirmations",
                        to="object_storage.platformfeishuconfig",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="FeishuSyncResult",
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
                ("idempotency_key", models.CharField(max_length=128)),
                ("snapshot_hash", models.CharField(max_length=64)),
                ("result", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="object_storage_feishu_sync_results",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("actor", "idempotency_key"),
                        name="storage_feishu_sync_actor_idempotency_unique",
                    )
                ],
            },
        ),
    ]
