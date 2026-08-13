from django.utils import timezone
from monitoring_stack.models import (
    AnsibleInstallJob,
    BlackboxProbeNode,
    MonitoringComponentStatus,
    MonitoringGovernanceFinding,
    MonitoringHost,
    MonitoringIntegrationConfig,
    MonitoringProfile,
    MonitoringSnapshotRun,
    MonitoringCredentialAudit,
    MonitoringCredentialValidation,
    MonitoringSshCredential,
    MonitoringSshCredentialVersion,
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
    n9e_runtime_for_host,
)
from monitoring_stack.services.ansible_progress import normalize_progress
from monitoring_stack.services.asset_state import (
    choose_next_action,
    host_roles,
    normalize_component_state,
)
from monitoring_stack.services.ssh_verification import (
    SshVerificationReceiptError,
    connection_fingerprint,
    connection_fingerprint_for_host,
    load_verification_receipt,
    unverified_verification_defaults,
    verified_verification_defaults,
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


class CredentialCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    private_key = serializers.CharField(write_only=True, trim_whitespace=False)
    passphrase = serializers.CharField(
        write_only=True, required=False, allow_blank=True, trim_whitespace=False
    )

    def validate_name(self, value):
        value = str(value or "").strip()
        if not value:
            raise serializers.ValidationError("name is required")
        if MonitoringSshCredential.objects.filter(name=value).exclude(
            status=MonitoringSshCredential.STATUS_ARCHIVED
        ).exists():
            raise serializers.ValidationError("credential name already exists")
        return value


class CredentialRotateSerializer(serializers.Serializer):
    private_key = serializers.CharField(write_only=True, trim_whitespace=False)
    passphrase = serializers.CharField(
        write_only=True, required=False, allow_blank=True, trim_whitespace=False
    )


class CredentialVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitoringSshCredentialVersion
        fields = [
            "id", "version", "has_passphrase", "algorithm", "key_size", "curve",
            "public_key_fingerprint", "validation_status", "validation_error_code",
            "created_at", "activated_at", "retired_at",
        ]
        read_only_fields = fields


class CredentialValidationSerializer(serializers.ModelSerializer):
    version_id = serializers.IntegerField(read_only=True)
    host_id = serializers.IntegerField(read_only=True, allow_null=True)
    checked_by_id = serializers.IntegerField(read_only=True, allow_null=True)
    host_name = serializers.CharField(source="host.hostname", read_only=True, default="")

    class Meta:
        model = MonitoringCredentialValidation
        fields = ["id", "version_id", "host_id", "host_name", "connection_fingerprint", "status", "error_code", "latency_ms", "checked_by_id", "checked_at"]
        read_only_fields = fields


class CredentialAuditSerializer(serializers.ModelSerializer):
    actor_id = serializers.IntegerField(read_only=True, allow_null=True)
    class Meta:
        model = MonitoringCredentialAudit
        fields = ["id", "credential_id_snapshot", "credential_name_snapshot", "version_id_snapshot", "action", "status", "actor_id", "source_ip", "request_id", "affected_host_ids", "metadata", "created_at"]
        read_only_fields = fields


class CredentialListSerializer(serializers.ModelSerializer):
    usage_count = serializers.IntegerField(read_only=True)
    health = serializers.SerializerMethodField()
    active_version = CredentialVersionSerializer(read_only=True)
    last_validation_time = serializers.SerializerMethodField()

    class Meta:
        model = MonitoringSshCredential
        fields = ["id", "name", "status", "active_version", "usage_count", "health", "last_validation_time", "created_at", "updated_at", "archived_at"]
        read_only_fields = fields

    def get_health(self, obj):
        if obj.status == obj.STATUS_NEEDS_REUPLOAD:
            return "needs_reupload"
        version = obj.active_version
        if not version:
            return "unavailable"
        try:
            from monitoring_stack.services.credential_crypto import decrypt_secret
            decrypt_secret(version.private_key_encrypted)
            if version.has_passphrase:
                decrypt_secret(version.passphrase_encrypted)
        except Exception:
            return "unavailable"
        return version.validation_status

    def get_last_validation_time(self, obj):
        validation = getattr(obj.active_version, "validations", None)
        latest = validation.order_by("-checked_at").first() if validation else None
        return latest.checked_at if latest else None


class CredentialDetailSerializer(CredentialListSerializer):
    hosts = serializers.SerializerMethodField()
    versions = CredentialVersionSerializer(many=True, read_only=True)
    validations = serializers.SerializerMethodField()
    audit = CredentialAuditSerializer(source="audit_records", many=True, read_only=True)

    class Meta(CredentialListSerializer.Meta):
        fields = CredentialListSerializer.Meta.fields + ["hosts", "versions", "validations", "audit"]

    def get_hosts(self, obj):
        return [{"id": host.id, "name": host.hostname, "enabled": host.enabled} for host in obj.hosts.order_by("id")]

    def get_validations(self, obj):
        queryset = MonitoringCredentialValidation.objects.filter(version__credential=obj).select_related("host")
        return CredentialValidationSerializer(queryset, many=True).data


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


class PrometheusProbeNodeOnboardSerializer(serializers.Serializer):
    address = serializers.CharField(max_length=255)
    port = serializers.CharField(max_length=16, default="9115")
    name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    bind_unassigned_targets = serializers.BooleanField(default=False)

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

    def validate_name(self, value):
        return str(value or "").strip()


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


class MonitoringHostConnectionTestSerializer(serializers.Serializer):
    host_id = serializers.PrimaryKeyRelatedField(
        source="saved_host",
        queryset=MonitoringHost.objects.select_related("ssh_key_credential"),
        required=False,
        allow_null=True,
    )
    address = serializers.CharField(max_length=255)
    ssh_user = serializers.CharField(max_length=80, default="root", allow_blank=True)
    ssh_port = serializers.IntegerField(default=22, min_value=1, max_value=65535)
    ssh_auth_type = serializers.ChoiceField(choices=MonitoringHost.SSH_AUTH_CHOICES)
    ssh_password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
    )
    ssh_key_id = serializers.PrimaryKeyRelatedField(
        source="ssh_key_credential",
        queryset=MonitoringSshCredential.objects.filter(status=MonitoringSshCredential.STATUS_ACTIVE),
        required=False,
        allow_null=True,
    )

    def validate_address(self, value):
        value = str(value or "").strip()
        if not value:
            raise serializers.ValidationError("address is required")
        return value

    def validate(self, attrs):
        auth_type = attrs["ssh_auth_type"]
        saved_host = attrs.get("saved_host")
        if auth_type == MonitoringHost.SSH_AUTH_PASSWORD:
            password = str(attrs.get("ssh_password") or "")
            if not password and saved_host:
                password = str(saved_host.ssh_password or "")
            if not password:
                raise serializers.ValidationError(
                    {"ssh_password": "SSH password is required"}
                )
            attrs["resolved_password"] = password
            attrs["ssh_key_credential"] = None
        else:
            credential = attrs.get("ssh_key_credential")
            if not credential and saved_host:
                credential = saved_host.ssh_key_credential
            if not credential:
                raise serializers.ValidationError(
                    {"ssh_key_id": "SSH key is required"}
                )
            if credential.active_version_id:
                from monitoring_stack.services.credential_lifecycle import (
                    CredentialLifecycleError,
                    assert_credential_assignable,
                )
                try:
                    assert_credential_assignable(credential)
                except CredentialLifecycleError as exc:
                    raise serializers.ValidationError(
                        {"ssh_key_id": exc.code}
                    ) from exc
            elif credential.status == credential.STATUS_NEEDS_REUPLOAD:
                raise serializers.ValidationError(
                    {"ssh_key_id": "CREDENTIAL_NEEDS_REUPLOAD"}
                )
            elif not saved_host or saved_host.ssh_key_credential_id != credential.id:
                raise serializers.ValidationError(
                    {"ssh_key_id": "CREDENTIAL_UNAVAILABLE"}
                )
            attrs["ssh_key_credential"] = credential
            attrs["resolved_password"] = None
        return attrs


class MonitoringHostSerializer(serializers.ModelSerializer):
    component_statuses = serializers.SerializerMethodField()
    ssh_verification = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    collection_state = serializers.SerializerMethodField()
    probe_state = serializers.SerializerMethodField()
    next_action = serializers.SerializerMethodField()
    ssh_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    ssh_key = serializers.CharField(write_only=True, required=False, allow_blank=True)
    ssh_key_id = serializers.PrimaryKeyRelatedField(
        source="ssh_key_credential",
        queryset=MonitoringSshCredential.objects.filter(status=MonitoringSshCredential.STATUS_ACTIVE),
        required=False,
        allow_null=True,
    )
    ssh_key_name = serializers.SerializerMethodField()
    has_ssh_password = serializers.SerializerMethodField()
    ssh_verification_receipt = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
    )

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
            "ssh_verification",
            "ssh_verification_receipt",
            "profiles",
            "labels",
            "params",
            "component_statuses",
            "roles",
            "collection_state",
            "probe_state",
            "next_action",
            "enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_ssh_key(self, value):
        return clean_ssh_key(value)

    def validate(self, attrs):
        receipt = str(attrs.pop("ssh_verification_receipt", "") or "").strip()
        auth_type = attrs.get(
            "ssh_auth_type", getattr(self.instance, "ssh_auth_type", MonitoringHost.SSH_AUTH_KEY)
        )
        if auth_type == MonitoringHost.SSH_AUTH_PASSWORD:
            attrs["ssh_key_credential"] = None
            attrs["ssh_key"] = ""
        credential = attrs.get("ssh_key_credential")
        if auth_type == MonitoringHost.SSH_AUTH_KEY and credential:
            from monitoring_stack.services.credential_lifecycle import (
                CredentialLifecycleError,
                assert_credential_assignable,
            )
            try:
                assert_credential_assignable(credential)
            except CredentialLifecycleError as exc:
                raise serializers.ValidationError({"ssh_key_id": exc.code}) from exc
            attrs["ssh_key"] = ""

        instance = self.instance
        address = attrs.get("address", getattr(instance, "address", ""))
        ssh_user = attrs.get("ssh_user", getattr(instance, "ssh_user", "root"))
        ssh_port = attrs.get("ssh_port", getattr(instance, "ssh_port", 22))
        password = attrs.get("ssh_password", getattr(instance, "ssh_password", ""))
        final_credential = attrs.get(
            "ssh_key_credential",
            getattr(instance, "ssh_key_credential", None),
        )
        ssh_key_name = attrs.get("ssh_key", getattr(instance, "ssh_key", ""))
        proposed_fingerprint = connection_fingerprint(
            address=address,
            ssh_user=ssh_user,
            ssh_port=ssh_port,
            ssh_auth_type=auth_type,
            password=password,
            ssh_key_id=getattr(final_credential, "id", None),
            ssh_key_name=ssh_key_name,
            ssh_credential_id=getattr(final_credential, "id", None),
            ssh_credential_version_id=getattr(getattr(final_credential, "active_version", None), "id", None),
            ssh_public_key_fingerprint=getattr(getattr(final_credential, "active_version", None), "public_key_fingerprint", ""),
        )

        if receipt:
            request = self.context.get("request")
            try:
                verification = load_verification_receipt(
                    receipt,
                    user_id=request.user.id,
                    host_id=getattr(instance, "id", None),
                    expected_fingerprint=proposed_fingerprint,
                )
            except (AttributeError, SshVerificationReceiptError) as exc:
                code = getattr(exc, "code", "SSH_VERIFICATION_MISMATCH")
                raise serializers.ValidationError(
                    {"ssh_verification_receipt": code}
                ) from exc
            attrs.update(verified_verification_defaults(verification))
        elif instance and proposed_fingerprint != connection_fingerprint_for_host(instance):
            attrs.update(unverified_verification_defaults())
        return attrs

    def get_ssh_key_name(self, obj):
        if obj.ssh_key_credential_id:
            return obj.ssh_key_credential.name
        return ""

    def get_has_ssh_password(self, obj):
        return bool(obj.ssh_password)

    def get_ssh_verification(self, obj):
        matches_current_settings = bool(
            obj.ssh_verification_signature
            and obj.ssh_verification_signature == connection_fingerprint_for_host(obj)
        )
        return {
            "status": obj.ssh_verification_status,
            "checked_at": (
                obj.ssh_verification_checked_at.isoformat()
                if obj.ssh_verification_checked_at
                else None
            ),
            "latency_ms": obj.ssh_verification_latency_ms,
            "error_code": obj.ssh_verification_error_code,
            "matches_current_settings": matches_current_settings,
        }

    def get_roles(self, obj):
        return self._asset_presentation(obj)["roles"]

    def get_collection_state(self, obj):
        return self._asset_presentation(obj)["collection_state"]

    def get_probe_state(self, obj):
        return self._asset_presentation(obj)["probe_state"]

    def get_next_action(self, obj):
        return self._asset_presentation(obj)["next_action"]

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

    def _component_status_rows(self, obj):
        presentation_cache = self.context.setdefault("host_component_rows", {})
        if obj.id in presentation_cache:
            return presentation_cache[obj.id]
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
            runtime = n9e_runtime_for_host(obj, cache=cache)
            rows.append(
                self._external_status(
                    obj,
                    AnsibleInstallJob.COMPONENT_CATEGRAF,
                    runtime,
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
        presentation_cache[obj.id] = rows
        return rows

    def get_component_statuses(self, obj):
        return self._component_status_rows(obj)

    def _asset_presentation(self, obj):
        cache = self.context.setdefault("host_asset_presentation", {})
        if obj.id in cache:
            return cache[obj.id]
        roles = host_roles(obj)
        rows = self._component_status_rows(obj)
        collection_state = normalize_component_state(rows, "categraf")
        probe_state = normalize_component_state(
            rows,
            "blackbox",
            required="probe_node" in roles,
        )
        next_action = choose_next_action(
            collection_state=collection_state,
            probe_state=probe_state,
            ssh_state=self.get_ssh_verification(obj),
        )
        cache[obj.id] = {
            "roles": roles,
            "collection_state": collection_state,
            "probe_state": probe_state,
            "next_action": next_action,
        }
        return cache[obj.id]


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
    progress = serializers.SerializerMethodField()

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
            "credential_snapshots",
            "base_url",
            "n9e_url",
            "install_dir",
            "image",
            "probe_name",
            "blackbox_port",
            "returncode",
            "logs",
            "results",
            "progress",
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
            "credential_snapshots",
            "returncode",
            "logs",
            "results",
            "progress",
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

    def get_progress(self, obj):
        return normalize_progress(obj.progress, obj.status)

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
            auth_type = host.get("ssh_auth_type") or MonitoringHost.SSH_AUTH_KEY
            key = host.get("ssh_key") or ""
            key_arg = (
                f" ansible_ssh_private_key_file={key}"
                if auth_type == MonitoringHost.SSH_AUTH_KEY and key
                else ""
            )
            password_arg = (
                " ansible_password=<configured>"
                if auth_type == MonitoringHost.SSH_AUTH_PASSWORD
                and host.get("has_ssh_password")
                else ""
            )
            lines.append(
                f"{hostname} ansible_host={address} "
                f"ansible_user={ssh_user} ansible_port={ssh_port} "
                f"ansible_connection=ssh{key_arg}{password_arg}"
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
