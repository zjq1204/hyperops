import hashlib

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import serializers

from object_storage.crypto import encrypt_secret
from object_storage.serializers import StrictBooleanField
from object_storage.models import (
    AccessKey,
    ApplicationAttempt,
    ApplicationBatch,
    ApplicationEvent,
    ApplicationItem,
    AuditEvent,
    Bucket,
    CloudIdentity,
    PlatformFeishuConfig,
    PlatformObjectStorageConfig,
    StorageResourcePool,
    UserBucketQuota,
)
from object_storage.services.platform import (
    sync_platform_feishu_access_group,
    update_resource_pool_configuration,
)


class AccessGroupSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ("id", "name")
        read_only_fields = fields


class PlatformObjectStorageConfigAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformObjectStorageConfig
        fields = (
            "id",
            "singleton_key",
            "naming_template",
            "naming_template_version",
            "default_bucket_quota",
            "delivery_lifetime_seconds",
            "audit_retention_days",
            "pause_new_applications",
            "pause_key_operations",
            "default_bucket_acl",
            "default_storage_class",
            "default_encryption",
            "default_versioning",
            "default_lifecycle",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "singleton_key", "created_at", "updated_at")

    def validate_default_bucket_acl(self, value):
        if value != "private":
            raise serializers.ValidationError("PLATFORM_DEFAULT_ACL_MUST_BE_PRIVATE")
        return value


class PlatformFeishuConfigAdminSerializer(serializers.ModelSerializer):
    app_secret = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        trim_whitespace=False,
    )
    access_group_name = serializers.CharField(
        source="access_group.name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = PlatformFeishuConfig
        fields = (
            "id",
            "singleton_key",
            "app_id",
            "app_secret",
            "oauth_callback_url",
            "access_group",
            "access_group_name",
            "validation_status",
            "validation_error_code",
            "last_validated_at",
            "enabled",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "singleton_key",
            "validation_status",
            "validation_error_code",
            "last_validated_at",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        instance = self.instance
        enabled = attrs.get("enabled", instance.enabled if instance else False)
        connection_changed = bool(attrs.get("app_secret")) or any(
            field in attrs
            and (instance is None or attrs[field] != getattr(instance, field))
            for field in ("app_id", "oauth_callback_url")
        )
        if enabled and connection_changed:
            raise serializers.ValidationError({"enabled": "VALIDATION_REQUIRED"})
        if enabled:
            app_id = attrs.get("app_id", instance.app_id if instance else "")
            secret = attrs.get(
                "app_secret",
                instance.app_secret_encrypted if instance else "",
            )
            access_group = attrs.get(
                "access_group", instance.access_group if instance else None
            )
            if not app_id:
                raise serializers.ValidationError({"app_id": "APP_ID_REQUIRED"})
            if not secret:
                raise serializers.ValidationError({"app_secret": "APP_SECRET_REQUIRED"})
            if access_group is None:
                raise serializers.ValidationError(
                    {"access_group": "ACCESS_GROUP_REQUIRED"}
                )
            if (
                instance is None
                or instance.validation_status
                != PlatformFeishuConfig.ValidationStatus.VALID
            ):
                raise serializers.ValidationError(
                    {"enabled": "FEISHU_CONFIG_NOT_VALIDATED"}
                )
        return attrs

    def update(self, instance, validated_data):
        secret = validated_data.pop("app_secret", None)
        previous_group_id = instance.access_group_id
        connection_changed = secret or any(
            field in validated_data
            and validated_data[field] != getattr(instance, field)
            for field in ("app_id", "oauth_callback_url")
        )
        if secret:
            instance.app_secret_encrypted = encrypt_secret(secret)
        if connection_changed:
            instance.validation_status = PlatformFeishuConfig.ValidationStatus.PENDING
            instance.validation_error_code = ""
            instance.last_validated_at = None
            instance.enabled = False
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if previous_group_id != instance.access_group_id:
            sync_platform_feishu_access_group(
                instance, previous_group_id=previous_group_id
            )
        return instance


class StorageResourcePoolAdminSerializer(serializers.ModelSerializer):
    management_access_key = serializers.CharField(
        write_only=True, required=False, allow_blank=False, trim_whitespace=False
    )
    management_secret_key = serializers.CharField(
        write_only=True, required=False, allow_blank=False, trim_whitespace=False
    )

    class Meta:
        model = StorageResourcePool
        fields = (
            "id",
            "provider",
            "cloud_account_id",
            "region",
            "management_access_key",
            "management_secret_key",
            "credential_fingerprint",
            "access_key_last_four",
            "validation_status",
            "validation_error_code",
            "last_validated_at",
            "enabled",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "credential_fingerprint",
            "access_key_last_four",
            "validation_status",
            "validation_error_code",
            "last_validated_at",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        access_key = attrs.get("management_access_key")
        secret_key = attrs.get("management_secret_key")
        if self.instance is None and not (access_key and secret_key):
            raise serializers.ValidationError(
                {"credentials": "MANAGEMENT_CREDENTIALS_REQUIRED"}
            )
        if bool(access_key) != bool(secret_key):
            raise serializers.ValidationError(
                {"credentials": "MANAGEMENT_CREDENTIALS_INCOMPLETE"}
            )
        if attrs.get("enabled") and (
            self.instance is None
            or self.instance.validation_status
            != StorageResourcePool.ValidationStatus.VALID
        ):
            raise serializers.ValidationError({"enabled": "VALIDATION_REQUIRED"})
        connection_changed = bool(access_key or secret_key) or any(
            field in attrs and attrs[field] != getattr(self.instance, field)
            for field in ("provider", "cloud_account_id", "region")
        )
        if attrs.get("enabled") and connection_changed:
            raise serializers.ValidationError({"enabled": "VALIDATION_REQUIRED"})
        return attrs

    @staticmethod
    def _credentials(access_key, secret_key):
        return {
            "management_access_key_encrypted": encrypt_secret(access_key),
            "management_secret_key_encrypted": encrypt_secret(secret_key),
            "credential_fingerprint": hashlib.sha256(
                access_key.encode("utf-8")
            ).hexdigest(),
            "access_key_last_four": access_key[-4:],
        }

    def create(self, validated_data):
        access_key = validated_data.pop("management_access_key")
        secret_key = validated_data.pop("management_secret_key")
        config = PlatformObjectStorageConfig.objects.get_or_create(
            singleton_key="default"
        )[0]
        return StorageResourcePool.objects.create(
            config=config,
            **self._credentials(access_key, secret_key),
            **validated_data,
        )

    def update(self, instance, validated_data):
        access_key = validated_data.pop("management_access_key", None)
        secret_key = validated_data.pop("management_secret_key", None)
        enabled = validated_data.pop("enabled", None)
        provider = validated_data.pop("provider", None)
        cloud_account_id = validated_data.pop("cloud_account_id", None)
        region = validated_data.pop("region", None)
        return update_resource_pool_configuration(
            instance,
            provider=provider,
            cloud_account_id=cloud_account_id,
            region=region,
            access_key=access_key,
            secret_key=secret_key,
            enabled=enabled,
        )


class UserBucketQuotaAdminSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.get_username", read_only=True)

    class Meta:
        model = UserBucketQuota
        fields = (
            "id",
            "user_id",
            "username",
            "bucket_quota",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "user_id", "username", "created_at", "updated_at")


class CloudIdentityAdminSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.get_username", read_only=True)

    class Meta:
        model = CloudIdentity
        fields = (
            "id",
            "user_id",
            "username",
            "resource_pool_id",
            "ram_user_id",
            "ram_user_name",
            "state",
            "last_synced_at",
            "credential_operation_error_code",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CloudIdentityDetailAdminSerializer(CloudIdentityAdminSerializer):
    operation_confirmation = serializers.SerializerMethodField()

    class Meta(CloudIdentityAdminSerializer.Meta):
        fields = CloudIdentityAdminSerializer.Meta.fields + ("operation_confirmation",)

    def get_operation_confirmation(self, instance):
        if not instance.credential_operation_token:
            return None
        return {
            "type": instance.credential_operation_type,
            "generation": instance.credential_operation_generation,
            "token": instance.credential_operation_token,
            "key_id": instance.credential_operation_key_id,
        }


class BucketAdminSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="owner.get_username", read_only=True)

    class Meta:
        model = Bucket
        fields = (
            "id",
            "owner_id",
            "username",
            "resource_pool_id",
            "cloud_identity_id",
            "business_name",
            "name",
            "project",
            "environment",
            "purpose",
            "notes",
            "region",
            "template_version",
            "cloud_resource_id",
            "state",
            "pending_delete_at",
            "desired_config_snapshot",
            "applied_config_snapshot",
            "config_state",
            "config_error_code",
            "deletion_error_code",
            "last_synced_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class BucketDetailAdminSerializer(BucketAdminSerializer):
    operation_confirmation = serializers.SerializerMethodField()
    configuration_confirmation = serializers.SerializerMethodField()

    class Meta(BucketAdminSerializer.Meta):
        fields = BucketAdminSerializer.Meta.fields + (
            "operation_confirmation",
            "configuration_confirmation",
            "action_observed_snapshot",
            "configuration_observed_snapshot",
        )

    def get_operation_confirmation(self, instance):
        if not instance.action_owner_token:
            return None
        return {
            "type": instance.action_type,
            "generation": instance.action_generation,
            "token": instance.action_owner_token,
        }

    def get_configuration_confirmation(self, instance):
        if not instance.configuration_operation_token:
            return None
        return {
            "type": "configuration",
            "generation": instance.configuration_generation,
            "token": instance.configuration_operation_token,
        }


class AccessKeyAdminSerializer(serializers.ModelSerializer):
    last_four = serializers.CharField(source="access_key_last_four")
    fingerprint = serializers.CharField(source="access_key_fingerprint")
    user_id = serializers.IntegerField(source="cloud_identity.user_id", read_only=True)

    class Meta:
        model = AccessKey
        fields = (
            "id",
            "user_id",
            "cloud_identity_id",
            "fingerprint",
            "last_four",
            "cloud_state",
            "local_state",
            "last_synced_at",
            "deactivated_at",
            "deleted_at",
            "operation_error_code",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ApplicationAttemptAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicationAttempt
        fields = (
            "id",
            "application_item_id",
            "attempt_number",
            "status",
            "provider_request_id",
            "error_code",
            "started_at",
            "finished_at",
        )
        read_only_fields = fields


class ApplicationEventAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicationEvent
        fields = (
            "id",
            "application_item_id",
            "attempt_id",
            "stage",
            "result",
            "error_code",
            "safe_metadata",
            "created_at",
        )
        read_only_fields = fields


class ApplicationItemAdminSerializer(serializers.ModelSerializer):
    attempts = ApplicationAttemptAdminSerializer(many=True, read_only=True)
    events = ApplicationEventAdminSerializer(many=True, read_only=True)

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


class ApplicationBatchAdminSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="applicant.get_username", read_only=True)
    counts = serializers.SerializerMethodField()

    class Meta:
        model = ApplicationBatch
        fields = (
            "id",
            "applicant_id",
            "username",
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


class ApplicationBatchDetailAdminSerializer(ApplicationBatchAdminSerializer):
    items = ApplicationItemAdminSerializer(many=True, read_only=True)

    class Meta(ApplicationBatchAdminSerializer.Meta):
        fields = ApplicationBatchAdminSerializer.Meta.fields + ("items",)


class AuditEventAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = (
            "id",
            "actor_id_snapshot",
            "actor_name_snapshot",
            "action",
            "target_type",
            "target_id",
            "reason",
            "ip_address",
            "request_id",
            "result",
            "safe_metadata",
            "created_at",
        )
        read_only_fields = fields


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500, allow_blank=False)


class BucketAdminActionSerializer(ReasonSerializer):
    bucket_name = serializers.CharField(max_length=63)
    confirmed = StrictBooleanField()


class BucketConfigurationSerializer(BucketAdminActionSerializer):
    desired = serializers.DictField()


class BucketActionAcknowledgementSerializer(BucketAdminActionSerializer):
    operation_type = serializers.CharField(max_length=32)
    operation_generation = serializers.IntegerField(min_value=1)
    operation_token = serializers.CharField(max_length=64)
    resolved_state = serializers.ChoiceField(choices=Bucket.State.choices)


class BucketConfigurationAcknowledgementSerializer(BucketAdminActionSerializer):
    operation_type = serializers.CharField(max_length=32)
    operation_generation = serializers.IntegerField(min_value=1)
    operation_token = serializers.CharField(max_length=64)
    resolution = serializers.ChoiceField(choices=("desired", "applied", "unknown"))


class CredentialAcknowledgementSerializer(ReasonSerializer):
    identity_name = serializers.CharField(max_length=128)
    operation_type = serializers.CharField(max_length=32)
    operation_generation = serializers.IntegerField(min_value=1)
    operation_token = serializers.CharField(max_length=64)
    cloud_console_resolved = StrictBooleanField()
    observation_summary = serializers.CharField(max_length=2000)
    resolved_state = serializers.ChoiceField(choices=CloudIdentity.State.choices)
    resolved_key_state = serializers.ChoiceField(
        choices=AccessKey.CloudState.choices, required=False, allow_null=True
    )


class AuditEventQuerySerializer(serializers.Serializer):
    action = serializers.CharField(max_length=120, required=False)
    target_type = serializers.CharField(max_length=120, required=False)
    actor_id = serializers.IntegerField(min_value=1, required=False)
    since = serializers.DateTimeField(required=False)
    result = serializers.ChoiceField(
        choices=("accepted", "succeeded", "failed", "manual_required", "observed"),
        required=False,
    )


def get_quota_user(user_id):
    return get_user_model().objects.get(pk=user_id)
