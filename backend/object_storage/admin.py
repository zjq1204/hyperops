from django.contrib import admin

from object_storage.models import UserBucketQuota


@admin.register(UserBucketQuota)
class UserBucketQuotaAdmin(admin.ModelAdmin):
    list_display = ("user", "bucket_quota", "updated_at")
    search_fields = ("user__username",)
