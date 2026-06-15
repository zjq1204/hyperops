"""
Jenkins Trigger Admin configuration.
"""

from django.contrib import admin

from .models import JenkinsInstance, TriggerEntry, TriggerRecord


@admin.register(JenkinsInstance)
class JenkinsInstanceAdmin(admin.ModelAdmin):
    list_display = ["name", "url", "username", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "url", "username"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(TriggerEntry)
class TriggerEntryAdmin(admin.ModelAdmin):
    list_display = ["name", "instance", "job_name", "notify_enabled", "is_active", "created_at"]
    list_filter = ["instance", "is_active", "notify_enabled"]
    search_fields = ["name", "job_name", "description"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(TriggerRecord)
class TriggerRecordAdmin(admin.ModelAdmin):
    list_display = ["entry", "user", "status", "build_number", "queue_url", "triggered_at", "finished_at"]
    list_filter = ["status", "entry"]
    search_fields = ["entry__name", "user__username"]
    readonly_fields = ["triggered_at"]
