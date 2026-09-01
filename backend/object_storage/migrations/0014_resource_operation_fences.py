from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("object_storage", "0013_bucket_configuration_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="bucket",
            name="action_generation",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="bucket",
            name="action_owner_token",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="bucket",
            name="action_type",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="bucket",
            name="configuration_generation",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="bucket",
            name="configuration_operation_token",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="accesskey",
            name="operation_generation",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="accesskey",
            name="operation_token",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="accesskey",
            name="operation_type",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
    ]
