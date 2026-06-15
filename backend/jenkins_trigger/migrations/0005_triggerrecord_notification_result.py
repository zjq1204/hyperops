from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jenkins_trigger", "0004_triggerrecord_queue_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="triggerrecord",
            name="notification_result",
            field=models.JSONField(
                blank=True,
                default=dict,
                verbose_name="通知结果",
            ),
        ),
    ]
