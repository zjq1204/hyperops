from django.contrib import admin

from object_storage.models import (
    FeishuAppConfig,
    StorageAccessKey,
    StorageApplication,
    StorageApplicationAttempt,
    StorageApplicationEvent,
    StorageAuditEvent,
    StorageBucket,
    StorageCloudIdentity,
    StorageDeliveryTicket,
    StorageMembership,
    StorageResourcePool,
    StorageTenant,
)


@admin.register(StorageTenant)
class StorageTenantAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "enabled", "default_bucket_quota")
    search_fields = ("code", "name")


@admin.register(FeishuAppConfig)
class FeishuAppConfigAdmin(admin.ModelAdmin):
    exclude = ("app_secret_encrypted",)
    list_display = ("tenant", "app_id", "validation_status", "enabled")
    list_filter = ("validation_status", "enabled")


@admin.register(StorageMembership)
class StorageMembershipAdmin(admin.ModelAdmin):
    list_display = ("display_name", "tenant", "user", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("display_name", "feishu_open_id", "user__username")


@admin.register(StorageResourcePool)
class StorageResourcePoolAdmin(admin.ModelAdmin):
    exclude = (
        "management_access_key_encrypted",
        "management_secret_key_encrypted",
    )
    list_display = (
        "tenant",
        "provider",
        "cloud_account_id",
        "region",
        "validation_status",
        "enabled",
    )
    list_filter = ("provider", "validation_status", "enabled")


@admin.register(StorageCloudIdentity)
class StorageCloudIdentityAdmin(admin.ModelAdmin):
    list_display = ("ram_user_name", "tenant", "membership", "state")
    list_filter = ("tenant", "state")
    search_fields = ("ram_user_name", "ram_user_id")


@admin.register(StorageBucket)
class StorageBucketAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "owner", "region", "state")
    list_filter = ("tenant", "environment", "state")
    search_fields = ("name", "project", "owner__display_name")


@admin.register(StorageAccessKey)
class StorageAccessKeyAdmin(admin.ModelAdmin):
    exclude = ("access_key_id_encrypted", "secret_access_key_encrypted")
    list_display = (
        "access_key_last_four",
        "tenant",
        "cloud_identity",
        "cloud_state",
        "local_state",
        "created_at",
    )
    list_filter = ("tenant", "cloud_state", "local_state")


@admin.register(StorageApplication)
class StorageApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant",
        "applicant",
        "action_type",
        "status",
        "created_at",
    )
    list_filter = ("tenant", "action_type", "status")
    readonly_fields = ("idempotency_key",)


@admin.register(StorageApplicationAttempt)
class StorageApplicationAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "application",
        "attempt_number",
        "tenant",
        "status",
        "started_at",
    )
    list_filter = ("tenant", "status")


@admin.register(StorageApplicationEvent)
class StorageApplicationEventAdmin(admin.ModelAdmin):
    list_display = ("application", "stage", "result", "created_at")
    list_filter = ("tenant", "stage", "result")
    readonly_fields = tuple(
        field.name for field in StorageApplicationEvent._meta.fields
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StorageDeliveryTicket)
class StorageDeliveryTicketAdmin(admin.ModelAdmin):
    exclude = ("token_digest",)
    list_display = (
        "id",
        "tenant",
        "membership",
        "status",
        "expires_at",
        "consumed_at",
    )
    list_filter = ("tenant", "status")


@admin.register(StorageAuditEvent)
class StorageAuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "tenant", "actor", "action", "result")
    list_filter = ("tenant", "action", "result")
    search_fields = ("request_id", "target_id", "actor__username")
    readonly_fields = tuple(field.name for field in StorageAuditEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
