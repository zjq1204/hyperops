import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("monitoring_stack", "0015_ansibleinstalljob_progress"),
    ]
    operations = [
        migrations.RenameModel("MonitoringSshKey", "MonitoringSshCredential"),
        migrations.AlterModelTable(
            name="monitoringsshcredential",
            table="monitoring_stack_monitoringsshkey",
        ),
        migrations.RenameField(
            model_name="monitoringsshcredential",
            old_name="file_name",
            new_name="legacy_file_name",
        ),
        migrations.AlterField(
            model_name="monitoringsshcredential",
            name="name",
            field=models.CharField(max_length=120),
        ),
        migrations.AlterField(
            model_name="monitoringsshcredential",
            name="legacy_file_name",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="monitoringsshcredential",
            name="status",
            field=models.CharField(choices=[("active", "Active"), ("archived", "Archived"), ("needs_reupload", "Needs re-upload")], default="active", max_length=24),
        ),
        migrations.AddField(model_name="monitoringsshcredential", name="archived_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="monitoringsshcredential", name="created_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_monitoring_credentials", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="monitoringsshcredential", name="updated_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_monitoring_credentials", to=settings.AUTH_USER_MODEL)),
        migrations.CreateModel(
            name="MonitoringSshCredentialVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveIntegerField()),
                ("private_key_encrypted", models.TextField()),
                ("passphrase_encrypted", models.TextField(blank=True, default="")),
                ("has_passphrase", models.BooleanField(default=False)),
                ("algorithm", models.CharField(max_length=64)),
                ("key_size", models.PositiveIntegerField(blank=True, null=True)),
                ("curve", models.CharField(blank=True, default="", max_length=64)),
                ("public_key_fingerprint", models.CharField(db_index=True, max_length=160)),
                ("public_key_text", models.TextField()),
                ("validation_status", models.CharField(choices=[("draft", "Draft"), ("valid", "Valid"), ("invalid", "Invalid")], default="draft", max_length=16)),
                ("validation_error_code", models.CharField(blank=True, default="", max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("retired_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_monitoring_credential_versions", to=settings.AUTH_USER_MODEL)),
                ("credential", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="versions", to="monitoring_stack.monitoringsshcredential")),
            ],
            options={"ordering": ["credential_id", "-version"]},
        ),
        migrations.AddField(model_name="monitoringsshcredential", name="active_version", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="active_for_credentials", to="monitoring_stack.monitoringsshcredentialversion")),
        migrations.CreateModel(
            name="MonitoringCredentialValidation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("connection_fingerprint", models.CharField(db_index=True, max_length=160)),
                ("status", models.CharField(choices=[("success", "Success"), ("failed", "Failed")], max_length=16)),
                ("error_code", models.CharField(blank=True, default="", max_length=64)),
                ("latency_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("checked_at", models.DateTimeField(auto_now_add=True)),
                ("checked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="monitoring_credential_validations", to=settings.AUTH_USER_MODEL)),
                ("host", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="credential_validations", to="monitoring_stack.monitoringhost")),
                ("version", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="validations", to="monitoring_stack.monitoringsshcredentialversion")),
            ],
            options={"ordering": ["-checked_at", "-id"]},
        ),
        migrations.CreateModel(
            name="MonitoringCredentialAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("credential_id_snapshot", models.PositiveBigIntegerField(blank=True, null=True)),
                ("credential_name_snapshot", models.CharField(blank=True, default="", max_length=120)),
                ("version_id_snapshot", models.PositiveBigIntegerField(blank=True, null=True)),
                ("action", models.CharField(max_length=40)),
                ("status", models.CharField(max_length=24)),
                ("source_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("request_id", models.CharField(blank=True, default="", max_length=128)),
                ("affected_host_ids", models.JSONField(blank=True, default=list)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="monitoring_credential_audits", to=settings.AUTH_USER_MODEL)),
                ("credential", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_records", to="monitoring_stack.monitoringsshcredential")),
                ("version", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_records", to="monitoring_stack.monitoringsshcredentialversion")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddField(model_name="ansibleinstalljob", name="credential_snapshots", field=models.JSONField(blank=True, default=list)),
        migrations.AddConstraint(model_name="monitoringsshcredential", constraint=models.UniqueConstraint(condition=~Q(status="archived"), fields=("name",), name="unique_active_monitoring_credential_name")),
        migrations.AddConstraint(model_name="monitoringsshcredentialversion", constraint=models.UniqueConstraint(fields=("credential", "version"), name="unique_monitoring_credential_version")),
        migrations.AddIndex(model_name="monitoringsshcredential", index=models.Index(fields=["status"], name="monitoring_cred_status_idx")),
        migrations.AddIndex(model_name="monitoringsshcredential", index=models.Index(fields=["active_version"], name="monitoring_cred_active_idx")),
        migrations.AddIndex(model_name="monitoringsshcredentialversion", index=models.Index(fields=["credential", "validation_status"], name="monitoring_ver_valid_idx")),
        migrations.AddIndex(model_name="monitoringcredentialvalidation", index=models.Index(fields=["version", "host"], name="monitoring_val_host_idx")),
        migrations.AddIndex(model_name="monitoringcredentialaudit", index=models.Index(fields=["credential_id_snapshot", "created_at"], name="monitoring_audit_cred_idx")),
    ]
