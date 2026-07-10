import os
import secrets

from django.utils import timezone
from django.utils.text import slugify
from monitoring_stack.models import (
    AnsibleInstallJob,
    BlackboxProbeNode,
    MonitoringComponentStatus,
    MonitoringGovernanceFinding,
    MonitoringHost,
    MonitoringIntegrationConfig,
    MonitoringProfile,
    MonitoringSnapshotRun,
    MonitoringSshKey,
    ProbeTarget,
)
from monitoring_stack.services.core import (
    EXTERNAL_COMPONENT_STATUS,
    blackbox_health_for_host,
    clean_labels,
    clean_ssh_key,
    clean_string_list,
    component_runtime_health,
    host_visible_in_n9e,
)
from rest_framework import serializers


class MonitoringProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitoringProfile
        fields = [
            "id",
            "name",
            "category",
            "description",
            "plugins",
            "is_builtin",
            "created_at",
            "updated_at",
        ]


class MonitoringIntegrationConfigSerializer(serializers.ModelSerializer):
    n9e_password = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = MonitoringIntegrationConfig
        fields = [
            "n9e_url",
            "n9e_username",
            "n9e_password",
            "prometheus_url",
            "grafana_url",
            "installer_base_url",
            "categraf_install_dir",
            "blackbox_install_dir",
            "blackbox_port",
            "blackbox_image",
        ]

    def update(self, instance, validated_data):
        password = validated_data.pop("n9e_password", None)
        for field, value in validated_data.items():
            setattr(instance, field, str(value or "").strip())
        if password:
            instance.n9e_password = str(password)
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            instance.updated_by = request.user
        instance.save()
        return instance


class MonitoringSshKeySerializer(serializers.ModelSerializer):
    private_key = serializers.CharField(
        write_only=True, required=True, trim_whitespace=False
    )

    class Meta:
        model = MonitoringSshKey
        fields = ["id", "name", "file_name", "private_key", "created_at", "updated_at"]
        read_only_fields = ["id", "file_name", "created_at", "updated_at"]

    def validate_name(self, value):
        value = str(value or "").strip()
        if not value:
            raise serializers.ValidationError("name is required")
        return value

    def validate_private_key(self, value):
        value = str(value or "").strip()
        if "PRIVATE KEY" not in value:
            raise serializers.ValidationError("invalid private key")
        return value + "\n"

    def create(self, validated_data):
        private_key = validated_data.pop("private_key")
        slug = slugify(validated_data["name"]) or "ssh-key"
        validated_data["file_name"] = f"{slug}-{secrets.token_hex(4)}.pem"
        instance = super().create(validated_data)
        path = instance.storage_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(private_key, encoding="utf-8")
        os.chmod(path, 0o600)
        return instance


class BlackboxProbeNodeSerializer(serializers.ModelSerializer):
    blackbox_address = serializers.CharField(source="endpoint", read_only=True)

    class Meta:
        model = BlackboxProbeNode
        fields = [
            "id",
            "name",
            "address",
            "port",
            "blackbox_address",
            "source",
            "host",
            "install_dir",
            "labels",
            "enabled",
            "last_job",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "blackbox_address", "created_at", "updated_at"]

    def validate_name(self, value):
        value = str(value or "").strip()
        if not value:
            raise serializers.ValidationError("name is required")
        return value

    def validate_address(self, value):
        value = str(value or "").strip()
        if not value:
            raise serializers.ValidationError("address is required")
        return value

    def validate_port(self, value):
        value = str(value or "").strip() or "9115"
        if not value.isdigit():
            raise serializers.ValidationError("port must be numeric")
        return value

    def validate_labels(self, value):
        return clean_labels(value)


class ProbeTargetSerializer(serializers.ModelSerializer):
    probe_node_name = serializers.CharField(source="probe_node.name", read_only=True)
    blackbox_address = serializers.CharField(
        source="probe_node.endpoint", read_only=True
    )

    class Meta:
        model = ProbeTarget
        fields = [
            "id",
            "external_id",
            "type",
            "target",
            "probe_node",
            "probe_node_name",
            "blackbox_address",
            "enabled",
            "labels",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_labels(self, value):
        return clean_labels(value)

    def validate_external_id(self, value):
        return str(value).strip() or None


class MonitoringComponentStatusSerializer(serializers.ModelSerializer):
    last_job_id = serializers.IntegerField(source="last_job.id", read_only=True)
    runtime_status = serializers.SerializerMethodField()
    runtime_reason = serializers.SerializerMethodField()
    runtime_endpoint = serializers.SerializerMethodField()
    runtime_checked_at = serializers.SerializerMethodField()

    class Meta:
        model = MonitoringComponentStatus
        fields = [
            "id",
            "component",
            "status",
            "version",
            "install_dir",
            "last_job_id",
            "last_error",
            "runtime_status",
            "runtime_reason",
            "runtime_endpoint",
            "runtime_checked_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def _runtime_health(self, obj):
        cache = self.context.setdefault("component_runtime_health_cache", {})
        status_cache = cache.setdefault("status_results", {})
        if obj.id not in status_cache:
            status_cache[obj.id] = component_runtime_health(obj, cache=cache)
        return status_cache[obj.id]

    def get_runtime_status(self, obj):
        return self._runtime_health(obj)["runtime_status"]

    def get_runtime_reason(self, obj):
        return self._runtime_health(obj)["runtime_reason"]

    def get_runtime_endpoint(self, obj):
        return self._runtime_health(obj)["runtime_endpoint"]

    def get_runtime_checked_at(self, obj):
        return self._runtime_health(obj)["runtime_checked_at"]


class MonitoringHostSerializer(serializers.ModelSerializer):
    component_statuses = serializers.SerializerMethodField()
    ssh_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    ssh_key_id = serializers.PrimaryKeyRelatedField(
        source="ssh_key_credential",
        queryset=MonitoringSshKey.objects.all(),
        required=False,
        allow_null=True,
    )
    ssh_key_name = serializers.SerializerMethodField()
    has_ssh_password = serializers.SerializerMethodField()

    class Meta:
        model = MonitoringHost
        fields = [
            "id",
            "external_id",
            "hostname",
            "address",
            "ssh_user",
            "ssh_port",
            "ssh_auth_type",
            "ssh_password",
            "ssh_key",
            "ssh_key_id",
            "ssh_key_name",
            "has_ssh_password",
            "profiles",
            "labels",
            "params",
            "component_statuses",
            "enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_ssh_key(self, value):
        return clean_ssh_key(value)

    def validate(self, attrs):
        auth_type = attrs.get(
            "ssh_auth_type", getattr(self.instance, "ssh_auth_type", MonitoringHost.SSH_AUTH_KEY)
        )
        if auth_type == MonitoringHost.SSH_AUTH_PASSWORD:
            attrs["ssh_key_credential"] = None
            attrs["ssh_key"] = ""
        credential = attrs.get("ssh_key_credential")
        if auth_type == MonitoringHost.SSH_AUTH_KEY and credential and not attrs.get("ssh_key"):
            attrs["ssh_key"] = credential.file_name
        return attrs

    def get_ssh_key_name(self, obj):
        if obj.ssh_key_credential_id:
            return obj.ssh_key_credential.name
        return ""

    def get_has_ssh_password(self, obj):
        return bool(obj.ssh_password)

    def validate_external_id(self, value):
        return str(value).strip() or None

    def validate_profiles(self, value):
        return clean_string_list(value)

    def validate_labels(self, value):
        return clean_labels(value)

    def validate_params(self, value):
        return clean_labels(value)

    def _external_status(self, host, component, runtime):
        return {
            "id": None,
            "component": component,
            "status": EXTERNAL_COMPONENT_STATUS,
            "version": "",
            "install_dir": "",
            "last_job_id": None,
            "last_error": "",
            "runtime_status": runtime.get("runtime_status", "unknown"),
            "runtime_reason": runtime.get("runtime_reason", ""),
            "runtime_endpoint": runtime.get("runtime_endpoint", ""),
            "runtime_checked_at": timezone.now().isoformat(),
            "created_at": None,
            "updated_at": None,
        }

    def get_component_statuses(self, obj):
        cache = self.context.setdefault("component_runtime_health_cache", {})
        existing = list(obj.component_statuses.all())
        rows = MonitoringComponentStatusSerializer(
            existing,
            many=True,
            context=self.context,
        ).data
        existing_components = {item.component for item in existing}
        if (
            AnsibleInstallJob.COMPONENT_CATEGRAF not in existing_components
            and host_visible_in_n9e(obj, cache=cache)
        ):
            rows.append(
                self._external_status(
                    obj,
                    AnsibleInstallJob.COMPONENT_CATEGRAF,
                    {
                        "runtime_status": "online",
                        "runtime_reason": "",
                        "runtime_endpoint": "",
                    },
                )
            )
        if AnsibleInstallJob.COMPONENT_BLACKBOX not in existing_components:
            runtime = blackbox_health_for_host(obj, cache=cache)
            if runtime.get("runtime_status") == "online":
                rows.append(
                    self._external_status(
                        obj,
                        AnsibleInstallJob.COMPONENT_BLACKBOX,
                        runtime,
                    )
                )
        return rows


class AnsiblePreviewSerializer(serializers.Serializer):
    component = serializers.ChoiceField(
        choices=AnsibleInstallJob.COMPONENT_CHOICES,
        required=False,
        default=AnsibleInstallJob.COMPONENT_CATEGRAF,
    )
    host_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
    )
    profiles = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list,
    )
    labels = serializers.DictField(required=False, default=dict)
    params = serializers.DictField(required=False, default=dict)
    base_url = serializers.CharField(required=False, allow_blank=True, default="")
    n9e_url = serializers.CharField(required=False, allow_blank=True, default="")
    install_dir = serializers.CharField(required=False, allow_blank=True, default="")
    image = serializers.CharField(required=False, allow_blank=True, default="")
    probe_name = serializers.CharField(required=False, allow_blank=True, default="")
    blackbox_port = serializers.CharField(required=False, allow_blank=True, default="")


class AnsibleInstallJobSerializer(serializers.ModelSerializer):
    base_url = serializers.CharField(max_length=512)
    n9e_url = serializers.CharField(
        max_length=512,
        required=False,
        allow_blank=True,
        default="",
    )
    total_hosts = serializers.SerializerMethodField()
    success_hosts = serializers.SerializerMethodField()
    failed_hosts = serializers.SerializerMethodField()
    duration_seconds = serializers.SerializerMethodField()
    last_error = serializers.SerializerMethodField()
    inventory = serializers.SerializerMethodField()
    vars = serializers.SerializerMethodField()
    manual_command = serializers.SerializerMethodField()
    failed_hostnames = serializers.SerializerMethodField()

    class Meta:
        model = AnsibleInstallJob
        fields = [
            "id",
            "status",
            "component",
            "profiles",
            "labels",
            "params",
            "host_ids",
            "hosts_snapshot",
            "base_url",
            "n9e_url",
            "install_dir",
            "image",
            "probe_name",
            "blackbox_port",
            "returncode",
            "logs",
            "results",
            "retry_of",
            "total_hosts",
            "success_hosts",
            "failed_hosts",
            "duration_seconds",
            "last_error",
            "inventory",
            "vars",
            "manual_command",
            "failed_hostnames",
            "created_by",
            "created_at",
            "started_at",
            "finished_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "hosts_snapshot",
            "returncode",
            "logs",
            "results",
            "retry_of",
            "total_hosts",
            "success_hosts",
            "failed_hosts",
            "duration_seconds",
            "last_error",
            "inventory",
            "vars",
            "manual_command",
            "failed_hostnames",
            "created_by",
            "created_at",
            "started_at",
            "finished_at",
        ]

    def validate_profiles(self, value):
        return clean_string_list(value)

    def validate_labels(self, value):
        return clean_labels(value)

    def validate_params(self, value):
        return clean_labels(value)

    def get_total_hosts(self, obj):
        return len(obj.hosts_snapshot or [])

    def get_success_hosts(self, obj):
        return sum(
            1
            for item in obj.results or []
            if str(item.get("status") or "").lower()
            in {"success", "succeeded", "completed", "done"}
        )

    def get_failed_hosts(self, obj):
        failed = len(self.get_failed_hostnames(obj))
        if failed:
            return failed
        if obj.status == AnsibleInstallJob.STATUS_FAILED and obj.hosts_snapshot:
            return len(obj.hosts_snapshot)
        return 0

    def get_duration_seconds(self, obj):
        if not obj.started_at or not obj.finished_at:
            return None
        return int((obj.finished_at - obj.started_at).total_seconds())

    def get_last_error(self, obj):
        if obj.status != AnsibleInstallJob.STATUS_FAILED:
            return ""
        logs = obj.logs or []
        return "\n".join(str(item) for item in logs[-8:])

    def get_inventory(self, obj):
        lines = ["[categraf_targets]"]
        for host in obj.hosts_snapshot or []:
            hostname = host.get("hostname") or f"host-{host.get('id')}"
            address = host.get("address") or ""
            ssh_user = host.get("ssh_user") or "root"
            ssh_port = host.get("ssh_port") or 22
            key = host.get("ssh_key") or ""
            key_arg = f" ansible_ssh_private_key_file={key}" if key else ""
            lines.append(
                f"{hostname} ansible_host={address} "
                f"ansible_user={ssh_user} ansible_port={ssh_port} "
                f"ansible_connection=paramiko{key_arg}"
            )
        return "\n".join(lines) + "\n"

    def get_vars(self, obj):
        return {
            "component": obj.component,
            "profiles": obj.profiles or [],
            "labels": obj.labels or {},
            "params": obj.params or {},
            "hosts": obj.hosts_snapshot or [],
        }

    def get_manual_command(self, obj):
        commands = []
        for host in obj.hosts_snapshot or []:
            hostname = host.get("hostname") or f"host-{host.get('id')}"
            command = host.get("install_command") or ""
            if command:
                commands.append(f"# {hostname}\n{command}")
        return "\n\n".join(commands)

    def get_failed_hostnames(self, obj):
        failed = {
            str(item.get("hostname") or "")
            for item in obj.results or []
            if str(item.get("status") or "").lower() in {"failed", "error", "timeout"}
        }
        if failed:
            return sorted(item for item in failed if item)
        if obj.status == AnsibleInstallJob.STATUS_FAILED and obj.hosts_snapshot:
            return [
                host.get("hostname") or f"host-{host.get('id')}"
                for host in obj.hosts_snapshot
            ]
        return []


class MonitoringSnapshotRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitoringSnapshotRun
        fields = [
            "id",
            "source",
            "status",
            "started_at",
            "finished_at",
            "error",
            "summary",
        ]
        read_only_fields = fields


class MonitoringGovernanceFindingSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitoringGovernanceFinding
        fields = [
            "id",
            "category",
            "severity",
            "status",
            "title",
            "subject_type",
            "subject_key",
            "source",
            "details",
            "recommended_action",
            "resolved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
