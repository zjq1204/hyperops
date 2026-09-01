from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("object_storage", "0017_api_idempotency_record"),
    ]

    operations = [
        migrations.AlterField(
            model_name="apiidempotencyrecord",
            name="actor",
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name="object_storage_api_idempotency_records",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
