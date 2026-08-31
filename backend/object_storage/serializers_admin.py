import hashlib

from rest_framework import serializers

from object_storage.crypto import encrypt_secret
from object_storage.models import (
    FeishuAppConfig,
    StorageResourcePool,
    StorageTenant,
)


class StorageTenantAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = StorageTenant
        fields = (
            "id",
            "code",
            "name",
            "enabled",
            "bucket_naming_template",
            "naming_template_version",
            "default_bucket_quota",
            "delivery_lifetime_seconds",
            "audit_retention_days",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "naming_template_version",
            "audit_retention_days",
            "created_at",
            "updated_at",
        )


class FeishuAppConfigAdminSerializer(serializers.ModelSerializer):
    app_secret = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        trim_whitespace=False,
    )

    class Meta:
        model = FeishuAppConfig
        fields = (
            "id",
            "tenant_id",
            "app_id",
            "app_secret",
            "oauth_callback_url",
            "validation_status",
            "validation_error_code",
            "last_validated_at",
            "enabled",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "tenant_id",
            "validation_status",
            "validation_error_code",
            "last_validated_at",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        instance = self.instance
        if instance is None and not attrs.get("app_secret"):
            raise serializers.ValidationError({"app_secret": "APP_SECRET_REQUIRED"})
        if attrs.get("enabled") and (
            instance is None
            or instance.validation_status != FeishuAppConfig.ValidationStatus.VALID
        ):
            raise serializers.ValidationError({"enabled": "VALIDATION_REQUIRED"})
        return attrs

    def create(self, validated_data):
        secret = validated_data.pop("app_secret")
        return FeishuAppConfig.objects.create(
            tenant=self.context["tenant"],
            app_secret_encrypted=encrypt_secret(secret),
            **validated_data,
        )

    def update(self, instance, validated_data):
        secret = validated_data.pop("app_secret", None)
        if secret:
            instance.app_secret_encrypted = encrypt_secret(secret)
            instance.validation_status = FeishuAppConfig.ValidationStatus.PENDING
            instance.validation_error_code = ""
            instance.last_validated_at = None
            instance.enabled = False
        for name, value in validated_data.items():
            setattr(instance, name, value)
        instance.save()
        return instance


class StorageResourcePoolAdminSerializer(serializers.ModelSerializer):
    management_access_key = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        trim_whitespace=False,
    )
    management_secret_key = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        trim_whitespace=False,
    )

    class Meta:
        model = StorageResourcePool
        fields = (
            "id",
            "tenant_id",
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
            "tenant_id",
            "provider",
            "credential_fingerprint",
            "access_key_last_four",
            "validation_status",
            "validation_error_code",
            "last_validated_at",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        instance = self.instance
        access_key = attrs.get("management_access_key")
        secret_key = attrs.get("management_secret_key")
        if instance is None and (not access_key or not secret_key):
            raise serializers.ValidationError(
                {"credentials": "MANAGEMENT_CREDENTIALS_REQUIRED"}
            )
        if bool(access_key) != bool(secret_key):
            raise serializers.ValidationError(
                {"credentials": "MANAGEMENT_CREDENTIALS_INCOMPLETE"}
            )
        if attrs.get("enabled") and (
            instance is None
            or instance.validation_status != StorageResourcePool.ValidationStatus.VALID
        ):
            raise serializers.ValidationError({"enabled": "VALIDATION_REQUIRED"})
        if attrs.get("enabled"):
            tenant = instance.tenant if instance else self.context["tenant"]
            provider = (
                instance.provider if instance else StorageResourcePool.Provider.ALIYUN
            )
            active_pools = StorageResourcePool.objects.filter(
                tenant=tenant,
                provider=provider,
                enabled=True,
            )
            if instance:
                active_pools = active_pools.exclude(pk=instance.pk)
            if active_pools.exists():
                raise serializers.ValidationError(
                    {"enabled": "ACTIVE_POOL_ALREADY_EXISTS"}
                )
        return attrs

    def _credential_fields(self, access_key, secret_key):
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
        return StorageResourcePool.objects.create(
            tenant=self.context["tenant"],
            **self._credential_fields(access_key, secret_key),
            **validated_data,
        )

    def update(self, instance, validated_data):
        access_key = validated_data.pop("management_access_key", None)
        secret_key = validated_data.pop("management_secret_key", None)
        if access_key and secret_key:
            for name, value in self._credential_fields(access_key, secret_key).items():
                setattr(instance, name, value)
            instance.validation_status = StorageResourcePool.ValidationStatus.PENDING
            instance.validation_error_code = ""
            instance.last_validated_at = None
            instance.enabled = False
        for name, value in validated_data.items():
            setattr(instance, name, value)
        instance.save()
        return instance
