from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import serializers

from action_orchestration.models import (
    ActionRun,
    ActionStep,
    ActionStepRun,
    ActionTemplate,
)

User = get_user_model()


class ActionStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActionStep
        fields = [
            "id",
            "name",
            "order",
            "action_type",
            "config",
            "failure_policy",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ActionTemplateSerializer(serializers.ModelSerializer):
    steps = ActionStepSerializer(many=True, required=False)
    visible_user_ids = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        many=True,
        required=False,
        write_only=True,
        source="visible_users",
    )
    visible_group_ids = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(),
        many=True,
        required=False,
        write_only=True,
        source="visible_groups",
    )
    visible_users = serializers.SerializerMethodField()
    visible_groups = serializers.SerializerMethodField()
    owner_name = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = ActionTemplate
        fields = [
            "id",
            "name",
            "description",
            "scope",
            "owner",
            "owner_name",
            "is_active",
            "parameter_schema",
            "visible_users",
            "visible_groups",
            "visible_user_ids",
            "visible_group_ids",
            "steps",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "owner_name", "created_at", "updated_at"]

    def get_visible_users(self, obj):
        return [
            {"id": user.id, "username": user.username, "email": user.email}
            for user in obj.visible_users.all()
        ]

    def get_visible_groups(self, obj):
        return [
            {"id": group.id, "name": group.name}
            for group in obj.visible_groups.all()
        ]

    def create(self, validated_data):
        steps = validated_data.pop("steps", [])
        visible_users = validated_data.pop("visible_users", [])
        visible_groups = validated_data.pop("visible_groups", [])
        template = ActionTemplate.objects.create(**validated_data)
        if visible_users:
            template.visible_users.set(visible_users)
        if visible_groups:
            template.visible_groups.set(visible_groups)
        self._sync_steps(template, steps)
        return template

    def update(self, instance, validated_data):
        steps = validated_data.pop("steps", None)
        visible_users = validated_data.pop("visible_users", None)
        visible_groups = validated_data.pop("visible_groups", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if visible_users is not None:
            instance.visible_users.set(visible_users)
        if visible_groups is not None:
            instance.visible_groups.set(visible_groups)
        if steps is not None:
            self._replace_active_steps(instance, steps)
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        active_steps = instance.steps.filter(is_archived=False).order_by("order", "id")
        data["steps"] = ActionStepSerializer(active_steps, many=True).data
        return data

    def _sync_steps(self, template, steps):
        for index, step in enumerate(steps, start=1):
            ActionStep.objects.create(
                template=template,
                order=step.get("order") or index,
                name=step.get("name") or f"Step {index}",
                action_type=step.get("action_type"),
                config=step.get("config") or {},
                failure_policy=step.get("failure_policy") or ActionStep.FAILURE_STOP,
            )

    def _replace_active_steps(self, template, steps):
        existing_steps = {
            step.id: step
            for step in template.steps.filter(is_archived=False)
        }
        referenced_step_ids = set(
            template.steps
            .filter(step_runs__isnull=False)
            .values_list("id", flat=True)
            .distinct()
        )

        # Free active ordering first. Referenced steps must remain for historical runs,
        # but they should no longer participate in the current template definition.
        template.steps.filter(is_archived=False).update(is_archived=True)

        for index, step in enumerate(steps, start=1):
            step_id = step.get("id")
            reusable = existing_steps.get(step_id) if step_id else None
            if reusable and reusable.id not in referenced_step_ids:
                reusable.order = step.get("order") or index
                reusable.name = step.get("name") or f"Step {index}"
                reusable.action_type = step.get("action_type")
                reusable.config = step.get("config") or {}
                reusable.failure_policy = (
                    step.get("failure_policy") or ActionStep.FAILURE_STOP
                )
                reusable.is_archived = False
                reusable.save()
                continue

            ActionStep.objects.create(
                template=template,
                order=step.get("order") or index,
                name=step.get("name") or f"Step {index}",
                action_type=step.get("action_type"),
                config=step.get("config") or {},
                failure_policy=step.get("failure_policy") or ActionStep.FAILURE_STOP,
                is_archived=False,
            )


class ActionStepRunSerializer(serializers.ModelSerializer):
    step_name = serializers.CharField(source="step.name", read_only=True)
    step_order = serializers.IntegerField(source="step.order", read_only=True)
    action_type = serializers.CharField(source="step.action_type", read_only=True)
    jenkins_record_id = serializers.IntegerField(source="jenkins_record.id", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.username", read_only=True)

    class Meta:
        model = ActionStepRun
        fields = [
            "id",
            "step",
            "step_name",
            "step_order",
            "action_type",
            "status",
            "resolved_config",
            "output",
            "error_message",
            "jenkins_record_id",
            "approved_by",
            "approved_by_name",
            "approval_comment",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
        ]


class ActionRunSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)
    triggered_by_name = serializers.CharField(source="triggered_by.username", read_only=True)
    current_step_name = serializers.CharField(source="current_step.name", read_only=True)
    step_runs = ActionStepRunSerializer(many=True, read_only=True)

    class Meta:
        model = ActionRun
        fields = [
            "id",
            "template",
            "template_name",
            "triggered_by",
            "triggered_by_name",
            "input_params",
            "status",
            "current_step",
            "current_step_name",
            "error_message",
            "step_runs",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "triggered_by",
            "status",
            "current_step",
            "error_message",
            "step_runs",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
        ]


class ActionRunCreateSerializer(serializers.Serializer):
    template = serializers.PrimaryKeyRelatedField(queryset=ActionTemplate.objects.all())
    input_params = serializers.DictField(required=False, default=dict)


class ActionApprovalSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True, default="")
