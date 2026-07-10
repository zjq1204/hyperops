import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring_stack", "0005_ruleimportrecord"),
    ]

    operations = [
        migrations.AddField(
            model_name="ansibleinstalljob",
            name="retry_of",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="retry_jobs",
                to="monitoring_stack.ansibleinstalljob",
            ),
        ),
    ]
