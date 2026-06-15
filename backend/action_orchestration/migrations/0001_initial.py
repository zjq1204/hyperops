from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("jenkins_trigger", "0006_userentrynotificationpreference"),
    ]

    operations = [
        migrations.CreateModel(
            name="ActionTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("scope", models.CharField(choices=[("admin", "Admin"), ("personal", "Personal")], default="personal", max_length=16)),
                ("is_active", models.BooleanField(default=True)),
                ("parameter_schema", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="owned_action_templates", to=settings.AUTH_USER_MODEL)),
                ("visible_groups", models.ManyToManyField(blank=True, related_name="visible_action_templates", to="auth.group")),
                ("visible_users", models.ManyToManyField(blank=True, related_name="visible_action_templates", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-updated_at", "-id"]},
        ),
        migrations.CreateModel(
            name="ActionStep",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("order", models.PositiveIntegerField(default=1)),
                ("action_type", models.CharField(choices=[("jenkins_trigger", "Jenkins trigger"), ("gitlab_branch_create", "GitLab branch create"), ("gitlab_branch_operation", "GitLab branch operation"), ("gitlab_tag_operation", "GitLab tag operation"), ("gitlab_webhook_operation", "GitLab webhook operation"), ("manual_approval", "Manual approval")], max_length=64)),
                ("config", models.JSONField(blank=True, default=dict)),
                ("failure_policy", models.CharField(choices=[("stop", "Stop"), ("continue", "Continue")], default="stop", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="steps", to="action_orchestration.actiontemplate")),
            ],
            options={"ordering": ["template_id", "order", "id"], "unique_together": {("template", "order")}},
        ),
        migrations.CreateModel(
            name="ActionRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("input_params", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("waiting_approval", "Waiting approval"), ("success", "Success"), ("failed", "Failed"), ("rejected", "Rejected")], default="queued", max_length=32)),
                ("error_message", models.TextField(blank=True, default="")),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("current_step", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="action_orchestration.actionstep")),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="runs", to="action_orchestration.actiontemplate")),
                ("triggered_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="action_runs", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="ActionStepRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("running", "Running"), ("waiting_approval", "Waiting approval"), ("success", "Success"), ("failed", "Failed"), ("skipped", "Skipped"), ("rejected", "Rejected")], default="pending", max_length=32)),
                ("resolved_config", models.JSONField(blank=True, default=dict)),
                ("output", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True, default="")),
                ("approval_comment", models.TextField(blank=True, default="")),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_action_step_runs", to=settings.AUTH_USER_MODEL)),
                ("jenkins_record", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="action_step_runs", to="jenkins_trigger.triggerrecord")),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="step_runs", to="action_orchestration.actionrun")),
                ("step", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="step_runs", to="action_orchestration.actionstep")),
            ],
            options={"ordering": ["run_id", "step__order", "id"], "unique_together": {("run", "step")}},
        ),
    ]
