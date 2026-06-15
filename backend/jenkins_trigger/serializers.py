"""Jenkins Trigger serializers."""

from django.core.cache import cache
from rest_framework import serializers

from accounts.access import get_effective_feature_keys

from .models import JenkinsGlobalConfig, JenkinsInstance, TriggerEntry, TriggerRecord


class JenkinsInstanceSerializer(serializers.ModelSerializer):
    """Serializer for JenkinsInstance."""

    job_catalog_cache_fetched_at = serializers.SerializerMethodField()

    class Meta:
        model = JenkinsInstance
        fields = [
            "id",
            "name",
            "url",
            "username",
            "job_catalog_cache_ttl_days",
            "job_catalog_cache_fetched_at",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "job_catalog_cache_fetched_at", "created_at", "updated_at"]
        extra_kwargs = {
            "token": {"write_only": True},
        }

    def get_job_catalog_cache_fetched_at(self, obj):
        payload = cache.get(f"jenkins:job_catalog:v1:{obj.id}")
        if not isinstance(payload, dict):
            return None
        return payload.get("fetched_at")


class JenkinsInstanceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating JenkinsInstance with token."""

    class Meta:
        model = JenkinsInstance
        fields = [
            "id",
            "name",
            "url",
            "username",
            "token",
            "job_catalog_cache_ttl_days",
            "is_active",
        ]


class JenkinsInstanceConnectionTestSerializer(serializers.Serializer):
    """Serializer for testing Jenkins connection with draft form values."""

    url = serializers.URLField()
    username = serializers.CharField(max_length=255)
    token = serializers.CharField(max_length=512, required=False, allow_blank=True)
    instance_id = serializers.IntegerField(required=False)


class JenkinsGlobalConfigSerializer(serializers.ModelSerializer):
    """Serializer for Jenkins global config."""

    class Meta:
        model = JenkinsGlobalConfig
        fields = ["job_catalog_cache_ttl_seconds", "updated_at"]
        read_only_fields = ["updated_at"]


class ParamDefinitionSerializer(serializers.Serializer):
    """Serializer for Jenkins parameter definition."""

    name = serializers.CharField()
    type = serializers.CharField()
    default_value = serializers.CharField(allow_null=True, required=False)
    value_source = serializers.CharField(required=False)
    choices = serializers.ListField(allow_null=True, required=False)
    description = serializers.CharField(allow_null=True, required=False)


class TriggerEntrySerializer(serializers.ModelSerializer):
    """Serializer for TriggerEntry."""

    instance_name = serializers.CharField(source="instance.name", read_only=True)

    class Meta:
        model = TriggerEntry
        fields = [
            "id",
            "instance",
            "instance_name",
            "name",
            "job_name",
            "description",
            "params_config",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class TriggerEntryCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating TriggerEntry."""

    class Meta:
        model = TriggerEntry
        fields = [
            "instance",
            "name",
            "job_name",
            "description",
            "params_config",
            "is_active",
        ]


class TriggerRecordSerializer(serializers.ModelSerializer):
    """Serializer for TriggerRecord."""

    entry_name = serializers.CharField(source="entry.name", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    params = serializers.SerializerMethodField()
    notification_result = serializers.SerializerMethodField()

    class Meta:
        model = TriggerRecord
        fields = [
            "id",
            "entry",
            "entry_name",
            "user",
            "username",
            "params",
            "status",
            "build_number",
            "queue_url",
            "progress_percent",
            "current_stage",
            "stage_summary",
            "pipeline_supported",
            "artifacts",
            "notification_result",
            "triggered_at",
            "finished_at",
        ]
        read_only_fields = [
            "id",
            "params",
            "status",
            "build_number",
            "queue_url",
            "progress_percent",
            "current_stage",
            "stage_summary",
            "pipeline_supported",
            "artifacts",
            "notification_result",
            "triggered_at",
            "finished_at",
        ]

    def _viewer_can_see_notification_result(self):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            return "admin_jenkins" in get_effective_feature_keys(user)
        return False

    def get_notification_result(self, obj):
        if not self._viewer_can_see_notification_result():
            return None
        return obj.notification_result

    def get_params(self, obj):
        params = obj.params or {}
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            if "admin_jenkins" in get_effective_feature_keys(user):
                return params

        hidden_names = {
            str(name).lower()
            for name, config in (obj.entry.params_config or {}).items()
            if isinstance(config, dict) and config.get("mode") == "hidden"
        }
        if not hidden_names:
            return params

        return {
            name: "******" if str(name).lower() in hidden_names else value
            for name, value in params.items()
        }


class TriggerParamsSerializer(serializers.Serializer):
    """Serializer for triggering a build with params."""

    params = serializers.DictField(child=serializers.CharField(), required=False, default=dict)


class JobParamsResponseSerializer(serializers.Serializer):
    """Serializer for job params fetched from Jenkins."""

    params = ParamDefinitionSerializer(many=True)
    config = serializers.DictField(required=False)
