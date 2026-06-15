"""
GitLab Resource serializers.
"""

from rest_framework import serializers

from django.utils.text import slugify

from .models import (
    GitLabBranch,
    GitLabCollectionRecord,
    GitLabInstance,
    GitLabOperationRecord,
    GitLabProjectLabel,
    GitLabTag,
    GitLabWebhook,
    RegisteredGroup,
    RegisteredProject,
)


class GitLabInstanceSerializer(serializers.ModelSerializer):
    """Serializer for GitLabInstance."""

    class Meta:
        model = GitLabInstance
        fields = [
            "id",
            "name",
            "url",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "private_token": {"write_only": True},
        }


class GitLabInstanceCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating GitLabInstance with token."""

    token = serializers.CharField(write_only=True, required=False, allow_blank=False)

    class Meta:
        model = GitLabInstance
        fields = [
            "id",
            "name",
            "url",
            "private_token",
            "token",
            "is_active",
        ]
        extra_kwargs = {
            "private_token": {"write_only": True, "required": False},
        }

    def validate(self, attrs):
        token = attrs.pop("token", None)
        if token and not attrs.get("private_token"):
            attrs["private_token"] = token

        if self.instance is None and not attrs.get("private_token"):
            raise serializers.ValidationError({
                "private_token": "This field is required.",
            })

        return attrs


class RegisteredGroupSerializer(serializers.ModelSerializer):
    """Serializer for RegisteredGroup."""

    instance_name = serializers.CharField(source="instance.name", read_only=True)

    class Meta:
        model = RegisteredGroup
        fields = [
            "id",
            "instance",
            "instance_name",
            "gitlab_id",
            "name",
            "path",
            "description",
            "is_active",
            "collected_at",
        ]
        read_only_fields = ["id", "collected_at"]


class RegisteredProjectSerializer(serializers.ModelSerializer):
    """Serializer for RegisteredProject."""

    instance_name = serializers.CharField(source="instance.name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)
    labels = serializers.SerializerMethodField()
    label_ids = serializers.PrimaryKeyRelatedField(
        queryset=GitLabProjectLabel.objects.all(),
        many=True,
        write_only=True,
        source="labels",
        required=False,
    )

    class Meta:
        model = RegisteredProject
        fields = [
            "id",
            "instance",
            "instance_name",
            "group",
            "group_name",
            "gitlab_id",
            "name",
            "path",
            "default_branch",
            "labels",
            "label_ids",
            "is_active",
            "collected_at",
        ]
        read_only_fields = ["id", "collected_at"]

    def get_labels(self, obj):
        return ProjectLabelSerializer(obj.labels.all(), many=True).data


class GitLabBranchSerializer(serializers.ModelSerializer):
    """Serializer for GitLabBranch."""

    project_path = serializers.CharField(source="project.path", read_only=True)

    class Meta:
        model = GitLabBranch
        fields = [
            "id",
            "project",
            "project_path",
            "name",
            "protected",
            "last_commit_date",
            "last_commit_sha",
            "collected_at",
        ]
        read_only_fields = ["id", "collected_at"]


class GitLabTagSerializer(serializers.ModelSerializer):
    """Serializer for GitLabTag."""

    project_path = serializers.CharField(source="project.path", read_only=True)

    class Meta:
        model = GitLabTag
        fields = [
            "id",
            "project",
            "project_path",
            "name",
            "commit_sha",
            "released_at",
            "collected_at",
        ]
        read_only_fields = ["id", "collected_at"]


class GitLabWebhookSerializer(serializers.ModelSerializer):
    """Serializer for GitLabWebhook."""

    project_path = serializers.CharField(source="project.path", read_only=True)

    class Meta:
        model = GitLabWebhook
        fields = [
            "id",
            "project",
            "project_path",
            "webhook_id",
            "url",
            "push_events",
            "tag_push_events",
            "merge_requests_events",
            "enable_ssl_verification",
            "collected_at",
        ]
        read_only_fields = ["id", "collected_at"]


class GitLabCollectionRecordSerializer(serializers.ModelSerializer):
    """Serializer for GitLab collection records."""

    project_id = serializers.IntegerField(source="project.id", read_only=True)

    class Meta:
        model = GitLabCollectionRecord
        fields = [
            "id",
            "project",
            "project_id",
            "project_name",
            "project_path",
            "status",
            "branches_count",
            "tags_count",
            "webhooks_count",
            "message",
            "error",
            "started_at",
            "finished_at",
        ]
        read_only_fields = fields


class GitLabOperationRecordSerializer(serializers.ModelSerializer):
    """Serializer for GitLab operation audit records."""

    actor_name = serializers.SerializerMethodField()
    action_label = serializers.CharField(source="get_action_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    instance_name = serializers.CharField(source="instance.name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)
    project_path = serializers.CharField(source="project.path", read_only=True)

    class Meta:
        model = GitLabOperationRecord
        fields = [
            "id",
            "actor",
            "actor_name",
            "action",
            "action_label",
            "status",
            "status_label",
            "instance",
            "instance_name",
            "group",
            "group_name",
            "project",
            "project_path",
            "target_summary",
            "request_data",
            "result_data",
            "total_count",
            "success_count",
            "failed_count",
            "error",
            "started_at",
            "finished_at",
        ]
        read_only_fields = fields

    def get_actor_name(self, obj):
        if not obj.actor:
            return ""
        return obj.actor.get_full_name() or obj.actor.username


class GitLabWebhookCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating GitLabWebhook."""

    class Meta:
        model = GitLabWebhook
        fields = [
            "project",
            "url",
            "push_events",
            "tag_push_events",
            "merge_requests_events",
            "enable_ssl_verification",
        ]


class ProjectLabelSerializer(serializers.ModelSerializer):
    """Serializer for GitLab project labels."""

    project_count = serializers.SerializerMethodField()

    class Meta:
        model = GitLabProjectLabel
        fields = [
            "id",
            "name",
            "slug",
            "project_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "project_count", "created_at", "updated_at"]

    def validate_name(self, value):
        normalized_name = value.strip()
        if not normalized_name:
            raise serializers.ValidationError("Label name cannot be empty.")

        normalized_slug = slugify(normalized_name, allow_unicode=True)
        if not normalized_slug:
            raise serializers.ValidationError("Label name is invalid.")

        queryset = GitLabProjectLabel.objects.filter(slug=normalized_slug)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Label name already exists.")
        return normalized_name

    def get_project_count(self, obj):
        annotated_count = getattr(obj, "project_count", None)
        if annotated_count is not None:
            return annotated_count
        return obj.projects.count()


class GroupChoiceSerializer(serializers.Serializer):
    """Serializer for group choice from GitLab API."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    path = serializers.CharField()
    description = serializers.CharField(allow_blank=True)


class ProjectChoiceSerializer(serializers.Serializer):
    """Serializer for project choice from GitLab API."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    path = serializers.CharField()
    path_with_namespace = serializers.CharField()
    default_branch = serializers.CharField()
