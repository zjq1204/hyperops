"""
GitLab Resource Admin configuration.
"""

from django.contrib import admin

from .models import (
    GitLabBranch,
    GitLabCollectionRecord,
    GitLabInstance,
    GitLabTag,
    GitLabWebhook,
    RegisteredGroup,
    RegisteredProject,
)


@admin.register(GitLabInstance)
class GitLabInstanceAdmin(admin.ModelAdmin):
    list_display = ["name", "url", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "url"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(RegisteredGroup)
class RegisteredGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "instance", "gitlab_id", "is_active", "collected_at"]
    list_filter = ["instance", "is_active"]
    search_fields = ["name", "path"]
    readonly_fields = ["collected_at"]


@admin.register(RegisteredProject)
class RegisteredProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "group", "gitlab_id", "default_branch", "is_active", "collected_at"]
    list_filter = ["group__instance", "is_active"]
    search_fields = ["name", "path"]
    readonly_fields = ["collected_at"]


@admin.register(GitLabBranch)
class GitLabBranchAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "protected", "last_commit_date", "collected_at"]
    list_filter = ["protected", "project"]
    search_fields = ["name", "project__path"]
    readonly_fields = ["collected_at"]


@admin.register(GitLabTag)
class GitLabTagAdmin(admin.ModelAdmin):
    list_display = ["name", "project", "commit_sha", "released_at", "collected_at"]
    list_filter = ["project"]
    search_fields = ["name", "project__path"]
    readonly_fields = ["collected_at"]


@admin.register(GitLabWebhook)
class GitLabWebhookAdmin(admin.ModelAdmin):
    list_display = ["url", "project", "push_events", "tag_push_events", "merge_requests_events", "collected_at"]
    list_filter = ["push_events", "tag_push_events", "merge_requests_events", "project"]
    search_fields = ["url", "project__path"]
    readonly_fields = ["collected_at"]


@admin.register(GitLabCollectionRecord)
class GitLabCollectionRecordAdmin(admin.ModelAdmin):
    list_display = [
        "project_name",
        "project_path",
        "status",
        "branches_count",
        "tags_count",
        "webhooks_count",
        "finished_at",
    ]
    list_filter = ["status", "finished_at"]
    search_fields = ["project_name", "project_path", "error"]
    readonly_fields = ["started_at", "finished_at"]
