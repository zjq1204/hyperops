from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jenkins_trigger", "0005_triggerrecord_notification_result"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="UserEntryNotificationPreference",
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
                    "notify_personal_email",
                    models.BooleanField(default=False, verbose_name="通知个人邮箱"),
                ),
                (
                    "notify_personal_webhook",
                    models.BooleanField(default=False, verbose_name="通知个人 Webhook"),
                ),
                (
                    "notify_group_email",
                    models.BooleanField(default=False, verbose_name="通知群组邮箱"),
                ),
                (
                    "notify_group_webhook",
                    models.BooleanField(default=False, verbose_name="通知群组 Webhook"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="更新时间"),
                ),
                (
                    "entry",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="user_notification_preferences",
                        to="jenkins_trigger.triggerentry",
                        verbose_name="触发入口",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="jenkins_entry_notification_preferences",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="用户",
                    ),
                ),
            ],
            options={
                "verbose_name": "用户触发入口通知偏好",
                "verbose_name_plural": "用户触发入口通知偏好",
                "unique_together": {("entry", "user")},
            },
        ),
    ]
