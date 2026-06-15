from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jenkins_trigger", "0006_userentrynotificationpreference"),
    ]

    operations = [
        migrations.AddField(
            model_name="triggerrecord",
            name="progress_percent",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                verbose_name="Pipeline 进度百分比",
            ),
        ),
        migrations.AddField(
            model_name="triggerrecord",
            name="current_stage",
            field=models.CharField(
                blank=True,
                default="",
                max_length=255,
                verbose_name="当前 Pipeline 阶段",
            ),
        ),
        migrations.AddField(
            model_name="triggerrecord",
            name="stage_summary",
            field=models.JSONField(
                blank=True,
                default=None,
                null=True,
                verbose_name="Pipeline 阶段摘要",
            ),
        ),
        migrations.AddField(
            model_name="triggerrecord",
            name="pipeline_supported",
            field=models.BooleanField(
                default=False,
                verbose_name="是否支持 Pipeline 阶段进度",
            ),
        ),
    ]
