from rest_framework import serializers

from object_storage.models import StorageAccessKey, StorageApplication, StorageBucket


class StorageBucketEmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = StorageBucket
        fields = (
            "id",
            "name",
            "project",
            "environment",
            "purpose",
            "notes",
            "region",
            "state",
            "created_at",
            "updated_at",
        )


class StorageAccessKeySummarySerializer(serializers.ModelSerializer):
    last_four = serializers.CharField(source="access_key_last_four")

    class Meta:
        model = StorageAccessKey
        fields = (
            "id",
            "last_four",
            "cloud_state",
            "local_state",
            "created_at",
            "updated_at",
        )


class StorageApplicationEmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = StorageApplication
        fields = (
            "id",
            "action_type",
            "status",
            "current_stage",
            "error_code",
            "error_summary",
            "target_bucket_id",
            "target_access_key_id",
            "created_at",
            "updated_at",
        )


class StorageApplicationCreateSerializer(serializers.Serializer):
    action_type = serializers.ChoiceField(
        choices=(
            StorageApplication.ActionType.FIRST_BUCKET_AND_CREDENTIAL,
            StorageApplication.ActionType.ADD_BUCKET,
        ),
        required=False,
    )
    project = serializers.CharField(max_length=80)
    environment = serializers.ChoiceField(choices=StorageBucket.Environment.choices)
    purpose = serializers.CharField(max_length=255)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class DeliveryTokenSerializer(serializers.Serializer):
    token = serializers.CharField(trim_whitespace=False, max_length=256)


class RevealAccessKeySerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, allow_blank=False)


class ReleaseBucketSerializer(serializers.Serializer):
    bucket_name = serializers.CharField(required=False, max_length=63)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class RotationRequestSerializer(serializers.Serializer):
    candidate_access_key_id = serializers.IntegerField(required=False, min_value=1)
    confirmed = serializers.BooleanField(default=False)


class MembershipActionSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, allow_blank=False)
