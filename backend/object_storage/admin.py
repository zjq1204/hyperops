from django.contrib import admin

from object_storage.models import (
    AccessKey,
    ApplicationBatch,
    AuditEvent,
    Bucket,
    CloudIdentity,
    PlatformFeishuConfig,
    PlatformObjectStorageConfig,
    StorageResourcePool,
    UserBucketQuota,
)


@admin.register(PlatformFeishuConfig, PlatformObjectStorageConfig)
class PlatformSingletonAdmin(admin.ModelAdmin):
    list_display = ("singleton_key", "updated_at")


@admin.register(StorageResourcePool)
class StorageResourcePoolAdmin(admin.ModelAdmin):
    list_display = (
        "provider",
        "cloud_account_id",
        "region",
        "validation_status",
        "enabled",
    )
    exclude = ("management_access_key_encrypted", "management_secret_key_encrypted")


@admin.register(UserBucketQuota)
class UserBucketQuotaAdmin(admin.ModelAdmin):
    list_display = ("user", "bucket_quota", "updated_at")
    search_fields = ("user__username",)


@admin.register(CloudIdentity)
class CloudIdentityAdmin(admin.ModelAdmin):
    list_display = ("user", "ram_user_name", "state", "last_synced_at")


@admin.register(Bucket)
class BucketAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "region", "state", "config_state")
    search_fields = ("name", "owner__username")


@admin.register(AccessKey)
class AccessKeyAdmin(admin.ModelAdmin):
    list_display = (
        "cloud_identity",
        "access_key_last_four",
        "cloud_state",
        "local_state",
    )
    exclude = ("access_key_id_encrypted", "secret_access_key_encrypted")


@admin.register(ApplicationBatch)
class ApplicationBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "applicant", "status", "item_count", "created_at")


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("action", "target_type", "target_id", "result", "created_at")
    readonly_fields = [field.name for field in AuditEvent._meta.fields]
