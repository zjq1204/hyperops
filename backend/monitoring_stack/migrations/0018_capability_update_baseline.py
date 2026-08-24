from django.db import migrations, models
import django.db.models.deletion


def populate_active_jobs(apps, schema_editor):
    ComponentStatus = apps.get_model("monitoring_stack", "MonitoringComponentStatus")
    ComponentStatus.objects.filter(
        status="success",
        last_job__status="success",
    ).update(active_job_id=models.F("last_job_id"))


def clear_active_jobs(apps, schema_editor):
    ComponentStatus = apps.get_model("monitoring_stack", "MonitoringComponentStatus")
    ComponentStatus.objects.update(active_job_id=None)


class Migration(migrations.Migration):
    dependencies = [
        ("monitoring_stack", "0017_unified_ssh_credentials"),
    ]

    operations = [
        migrations.AddField(
            model_name="ansibleinstalljob",
            name="base_job",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="capability_update_jobs",
                to="monitoring_stack.ansibleinstalljob",
            ),
        ),
        migrations.AddField(
            model_name="monitoringcomponentstatus",
            name="active_job",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="active_component_statuses",
                to="monitoring_stack.ansibleinstalljob",
            ),
        ),
        migrations.RunPython(populate_active_jobs, clear_active_jobs),
    ]
