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

CONDITIONAL_OPERATORS = {"equals", "not_equals", "contains", "is_empty", "is_not_empty"}
NESTED_ACTION_TYPES = {
    ActionStep.TYPE_JENKINS_TRIGGER,
    ActionStep.TYPE_GITLAB_BRANCH_CREATE,
    ActionStep.TYPE_GITLAB_BRANCH_OPERATION,
    ActionStep.TYPE_GITLAB_TAG_OPERATION,
    ActionStep.TYPE_GITLAB_WEBHOOK_OPERATION,
    ActionStep.TYPE_MANUAL_APPROVAL,
}


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

    def validate(self, attrs):
        attrs = super().validate(attrs)
        steps = attrs.get("steps")
        if steps is None:
            return attrs

        parameter_schema = attrs.get("parameter_schema")
        if parameter_schema is None and self.instance is not None:
            parameter_schema = self.instance.parameter_schema
        parameter_names = {
            item.get("name")
            for item in (parameter_schema or [])
            if isinstance(item, dict) and item.get("name")
        }

        for index, step in enumerate(steps, start=1):
            if step.get("action_type") != ActionStep.TYPE_CONDITIONAL_BRANCH:
                continue
            self._validate_conditional_branch_config(
                step.get("config") or {},
                parameter_names,
                index,
            )
        return attrs

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

    def _validate_conditional_branch_config(self, config, parameter_names, step_index):
        branches = config.get("branches")
        if not isinstance(branches, list) or not branches:
            raise serializers.ValidationError({
                "steps": f"Step {step_index} conditional branch requires branches."
            })

        seen_branch_ids = set()
        for branch_index, branch in enumerate(branches, start=1):
            if not isinstance(branch, dict):
                raise serializers.ValidationError({
                    "steps": f"Step {step_index} branch {branch_index} must be an object."
                })
            branch_id = str(branch.get("id") or "").strip()
            if not branch_id:
                raise serializers.ValidationError({
                    "steps": f"Step {step_index} branch {branch_index} requires an id."
                })
            if branch_id in seen_branch_ids:
                raise serializers.ValidationError({
                    "steps": f"Step {step_index} branch id {branch_id} is duplicated."
                })
            seen_branch_ids.add(branch_id)

            condition = branch.get("condition") or {}
            param = condition.get("param")
            operator = condition.get("operator") or "equals"
            if param not in parameter_names:
                raise serializers.ValidationError({
                    "steps": (
                        f"Step {step_index} branch {branch_id} references unknown "
                        f"parameter {param}."
                    )
                })
            if operator not in CONDITIONAL_OPERATORS:
                raise serializers.ValidationError({
                    "steps": (
                        f"Step {step_index} branch {branch_id} uses unsupported "
                        f"operator {operator}."
                    )
                })

            nested_steps = branch.get("steps")
            if not isinstance(nested_steps, list) or not nested_steps:
                raise serializers.ValidationError({
                    "steps": f"Step {step_index} branch {branch_id} requires nested steps."
                })
            for nested_index, nested_step in enumerate(nested_steps, start=1):
                action_type = nested_step.get("action_type")
                if action_type == ActionStep.TYPE_CONDITIONAL_BRANCH:
                    raise serializers.ValidationError({
                        "steps": (
                            f"Step {step_index} branch {branch_id} nested step "
                            f"{nested_index} cannot be a conditional branch."
                        )
                    })
                if action_type not in NESTED_ACTION_TYPES:
                    raise serializers.ValidationError({
                        "steps": (
                            f"Step {step_index} branch {branch_id} nested step "
                            f"{nested_index} has unsupported action type {action_type}."
                        )
                    })


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
