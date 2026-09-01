from rest_framework import serializers

from object_storage.models import (
    AccessKey,
    ApplicationAttempt,
    ApplicationBatch,
    ApplicationEvent,
    ApplicationItem,
    Bucket,
    CloudIdentity,
)


class BucketEmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bucket
        fields = (
            "id",
            "business_name",
            "name",
            "project",
            "environment",
            "purpose",
            "notes",
            "region",
            "state",
            "pending_delete_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class AccessKeySummarySerializer(serializers.ModelSerializer):
    last_four = serializers.CharField(source="access_key_last_four")

    class Meta:
        model = AccessKey
        fields = (
            "id",
            "last_four",
            "cloud_state",
            "local_state",
            "last_synced_at",
            "deactivated_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CloudIdentityEmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CloudIdentity
        fields = ("id", "ram_user_name", "state", "last_synced_at")
        read_only_fields = fields


class ApplicationAttemptEmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicationAttempt
        fields = (
            "id",
            "attempt_number",
            "status",
            "error_code",
            "started_at",
            "finished_at",
        )
        read_only_fields = fields


class ApplicationEventEmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicationEvent
        fields = (
            "id",
            "attempt_id",
            "stage",
            "result",
            "error_code",
            "safe_metadata",
            "created_at",
        )
        read_only_fields = fields


class ApplicationItemEmployeeSerializer(serializers.ModelSerializer):
    bucket_id = serializers.IntegerField(read_only=True, allow_null=True)
    attempts = ApplicationAttemptEmployeeSerializer(many=True, read_only=True)
    events = ApplicationEventEmployeeSerializer(many=True, read_only=True)

    class Meta:
        model = ApplicationItem
        fields = (
            "id",
            "business_name",
            "project",
            "environment",
            "purpose",
            "notes",
            "rendered_bucket_name",
            "status",
            "current_stage",
            "retry_count",
            "error_code",
            "bucket_id",
            "attempts",
            "events",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ApplicationBatchEmployeeSerializer(serializers.ModelSerializer):
    counts = serializers.SerializerMethodField()

    class Meta:
        model = ApplicationBatch
        fields = (
            "id",
            "status",
            "current_stage",
            "counts",
            "error_code",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_counts(self, instance):
        return {
            "total": instance.item_count,
            "pending": instance.pending_count,
            "succeeded": instance.success_count,
            "failed": instance.failed_count,
        }


class ApplicationBatchDetailEmployeeSerializer(ApplicationBatchEmployeeSerializer):
    items = ApplicationItemEmployeeSerializer(many=True, read_only=True)

    class Meta(ApplicationBatchEmployeeSerializer.Meta):
        fields = ApplicationBatchEmployeeSerializer.Meta.fields + ("items",)


class ApplicationItemCreateSerializer(serializers.Serializer):
    business_name = serializers.CharField(max_length=80)
    purpose = serializers.CharField(max_length=255)
    project = serializers.CharField(max_length=80, required=False, allow_blank=True)
    environment = serializers.ChoiceField(
        choices=Bucket.Environment.choices,
        required=False,
    )
    notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    initial_suffix = serializers.CharField(max_length=8)
    rendered_bucket_name = serializers.CharField(max_length=63)


class ApplicationBatchCreateSerializer(serializers.Serializer):
    items = ApplicationItemCreateSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        allowed = {"items"}
        unsupported = set(getattr(self, "initial_data", {})).difference(allowed)
        if unsupported:
            raise serializers.ValidationError(
                {name: "CLIENT_OWNERSHIP_FIELD_UNSUPPORTED" for name in unsupported}
            )
        return attrs


class StrictBooleanField(serializers.BooleanField):
    def to_internal_value(self, data):
        if not isinstance(data, bool):
            self.fail("invalid")
        return data


class BucketActionSerializer(serializers.Serializer):
    bucket_name = serializers.CharField(max_length=63)
    confirmed = StrictBooleanField()
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)


class KeyActionSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
