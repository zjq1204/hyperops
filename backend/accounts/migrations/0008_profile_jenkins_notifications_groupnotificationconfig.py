from django.db import migrations, models


def create_group_notification_configs(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    GroupNotificationConfig = apps.get_model(
        "accounts", "GroupNotificationConfig"
    )
    for group in Group.objects.all():
        GroupNotificationConfig.objects.get_or_create(group=group)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0007_role_profile_preferred_platform"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="jenkins_notification_emails",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Extra email recipients for Jenkins notifications.",
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="jenkins_notification_strategy",
            field=models.CharField(
                choices=[
                    ("user_only", "仅个人"),
                    ("group_only", "仅群组"),
                    ("user_first_fallback_group", "个人优先，无个人则群组"),
                    ("user_and_group", "个人 + 群组"),
                ],
                default="user_only",
                help_text="How Jenkins completion notifications resolve recipients.",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="jenkins_notification_webhooks",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Webhook URLs for Jenkins notifications.",
            ),
        ),
        migrations.CreateModel(
            name="GroupNotificationConfig",
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
                    "notification_emails",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="Group-level email recipients for Jenkins notifications.",
                    ),
                ),
                (
                    "notification_webhooks",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="Group-level webhook URLs for Jenkins notifications.",
                    ),
                ),
                (
                    "group",
                    models.OneToOneField(
                        on_delete=models.deletion.CASCADE,
                        related_name="jenkins_notification_config",
                        to="auth.group",
                    ),
                ),
            ],
        ),
        migrations.RunPython(
            create_group_notification_configs,
            migrations.RunPython.noop,
        ),
    ]
