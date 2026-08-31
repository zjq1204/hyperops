from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0012_role_operation_permissions"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="is_system",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "System roles are managed by platform modules, not administrators."
                ),
            ),
        ),
    ]
