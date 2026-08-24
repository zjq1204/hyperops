import logging

from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from accounts.permissions import HasRequiredFeature
from action_orchestration.models import ActionRun, ActionTemplate
from action_orchestration.serializers import (
    ActionApprovalSerializer,
    ActionRunCreateSerializer,
    ActionRunSerializer,
    ActionTemplateSerializer,
)
from action_orchestration.services import (
    approve_action_run,
    can_user_access_template,
    create_action_run,
    reject_action_run,
)
from action_orchestration.tasks import execute_action_run_task

logger = logging.getLogger(__name__)


class AdminActionTemplateViewSet(ModelViewSet):
    serializer_class = ActionTemplateSerializer
    permission_classes = [HasRequiredFeature]
    required_feature = "admin_actions"

    def get_queryset(self):
        return (
            ActionTemplate.objects
            .prefetch_related("steps", "visible_users", "visible_groups")
            .select_related("owner")
            .all()
        )

    def perform_create(self, serializer):
        owner = serializer.validated_data.get("owner") or self.request.user
        serializer.save(owner=owner)


class WorkspaceActionTemplateView(APIView):
    permission_classes = [HasRequiredFeature]
    required_feature = "workspace_actions"

    def get(self, request):
        group_ids = request.user.groups.values_list("id", flat=True)
        queryset = (
            ActionTemplate.objects
            .filter(is_active=True)
            .filter(
                Q(scope=ActionTemplate.SCOPE_PERSONAL, owner=request.user)
                | Q(scope=ActionTemplate.SCOPE_ADMIN, visible_users=request.user)
                | Q(scope=ActionTemplate.SCOPE_ADMIN, visible_groups__id__in=group_ids)
                | Q(owner=request.user)
            )
            .prefetch_related("steps", "visible_users", "visible_groups")
            .select_related("owner")
            .distinct()
        )
        serializer = ActionTemplateSerializer(queryset, many=True)
        return Response(serializer.data)


class ActionRunViewSet(ReadOnlyModelViewSet):
    serializer_class = ActionRunSerializer
    permission_classes = [HasRequiredFeature]
    required_feature = "workspace_actions"

    def get_queryset(self):
        user = self.request.user
        queryset = (
            ActionRun.objects
            .select_related("template", "triggered_by", "current_step")
            .prefetch_related("step_runs", "step_runs__step")
        )
        if not getattr(user, "is_staff", False):
            queryset = queryset.filter(triggered_by=user)
        return queryset

    def create(self, request):
        serializer = ActionRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = serializer.validated_data["template"]
        if not can_user_access_template(request.user, template):
            return Response(
                {"message": "Action template not found or not accessible"},
                status=status.HTTP_404_NOT_FOUND,
            )
        run = create_action_run(
            template,
            request.user,
            serializer.validated_data.get("input_params") or {},
        )
        task = execute_action_run_task.delay(run.id)
        logger.info(
            "已创建并提交动作编排 | run_id=%s template_id=%s user_id=%s "
            "step_count=%s celery_task_id=%s",
            run.id,
            template.id,
            request.user.id,
            run.step_runs.count(),
            task.id,
        )
        return Response(ActionRunSerializer(run).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        approval = ActionApprovalSerializer(data=request.data)
        approval.is_valid(raise_exception=True)
        try:
            run = approve_action_run(
                self.get_object(),
                request.user,
                approval.validated_data.get("comment", ""),
            )
            task = execute_action_run_task.delay(run.id)
            logger.info(
                "已提交审批后的动作编排 | run_id=%s user_id=%s celery_task_id=%s",
                run.id,
                request.user.id,
                task.id,
            )
            run.refresh_from_db()
            return Response(ActionRunSerializer(run).data)
        except PermissionError as exc:
            return Response({"message": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as exc:
            return Response({"message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        approval = ActionApprovalSerializer(data=request.data)
        approval.is_valid(raise_exception=True)
        try:
            run = reject_action_run(
                self.get_object(),
                request.user,
                approval.validated_data.get("comment", ""),
            )
            return Response(ActionRunSerializer(run).data)
        except PermissionError as exc:
            return Response({"message": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as exc:
            return Response({"message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
