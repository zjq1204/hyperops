"""
GitLab Resource views.
"""

import logging
import time

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import HasRequiredFeature

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
from .serializers import (
    GitLabCollectionRecordSerializer,
    GitLabInstanceCreateSerializer,
    GitLabInstanceSerializer,
    GitLabOperationRecordSerializer,
    GitLabWebhookCreateSerializer,
    GitLabWebhookSerializer,
    GroupChoiceSerializer,
    ProjectLabelSerializer,
    ProjectChoiceSerializer,
    RegisteredGroupSerializer,
    RegisteredProjectSerializer,
)
from .services.gitlab_client import GitLabClient

logger = logging.getLogger(__name__)
SENSITIVE_AUDIT_KEYS = {"error", "message", "private_token", "token", "url"}


def sanitize_audit_data(value):
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if key.lower() in SENSITIVE_AUDIT_KEYS
                else sanitize_audit_data(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_audit_data(item) for item in value]
    return value


def log_gitlab_operation(
    operation,
    total_count,
    success_count,
    failed_count,
    started_at,
    *,
    instance_id=None,
    project_id=None,
):
    if failed_count and not success_count:
        log_method = logger.error
    elif failed_count:
        log_method = logger.warning
    else:
        log_method = logger.info
    log_method(
        "GitLab 操作完成 | integration=gitlab operation=%s instance_id=%s "
        "project_id=%s total_count=%s success_count=%s failed_count=%s "
        "duration_ms=%s",
        operation,
        instance_id,
        project_id,
        total_count,
        success_count,
        failed_count,
        int((time.monotonic() - started_at) * 1000),
    )


def get_gitlab_client(instance: GitLabInstance) -> GitLabClient:
    """Create GitLab client from instance."""
    return GitLabClient(url=instance.url, private_token=instance.private_token)


def get_cached_gitlab_client(client_cache, instance: GitLabInstance) -> GitLabClient:
    """Reuse one GitLab client per instance inside a single request."""
    if instance.id not in client_cache:
        client_cache[instance.id] = get_gitlab_client(instance)
    return client_cache[instance.id]


def get_operation_status(success_count, failed_count):
    """Map success/failure counts to a stable operation status."""
    if failed_count and success_count:
        return GitLabOperationRecord.STATUS_PARTIAL_SUCCESS
    if failed_count:
        return GitLabOperationRecord.STATUS_FAILED
    return GitLabOperationRecord.STATUS_SUCCESS


def create_operation_record(
    *,
    request,
    action,
    target_summary="",
    request_data=None,
    result_data=None,
    total_count=0,
    success_count=0,
    failed_count=0,
    error="",
    instance=None,
    group=None,
    project=None,
):
    """Persist a GitLab operation audit row without changing API responses."""
    actor = (
        request.user
        if getattr(request, "user", None) and request.user.is_authenticated
        else None
    )
    return GitLabOperationRecord.objects.create(
        actor=actor,
        action=action,
        status=get_operation_status(success_count, failed_count),
        instance=instance,
        group=group,
        project=project,
        target_summary=target_summary,
        request_data=sanitize_audit_data(request_data or {}),
        result_data=sanitize_audit_data(result_data or {}),
        total_count=total_count,
        success_count=success_count,
        failed_count=failed_count,
        error="operation_failed" if error else "",
        finished_at=timezone.now(),
    )


BRANCH_OPERATION_ACTIONS = {
    "create": GitLabOperationRecord.ACTION_BRANCH_CREATE,
    "delete": GitLabOperationRecord.ACTION_BRANCH_DELETE,
    "protect": GitLabOperationRecord.ACTION_BRANCH_PROTECT,
    "unprotect": GitLabOperationRecord.ACTION_BRANCH_UNPROTECT,
}


class GitLabInstanceViewSet(viewsets.ModelViewSet):
    """ViewSet for GitLabInstance."""

    queryset = GitLabInstance.objects.all()
    permission_classes = [HasRequiredFeature]
    required_feature = "admin_gitlab"

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return GitLabInstanceCreateSerializer
        return GitLabInstanceSerializer

    @action(detail=True, methods=["post"])
    def test_connection(self, request, pk=None):
        """Test GitLab connection."""
        instance = self.get_object()
        client = get_gitlab_client(instance)
        success = client.test_connection()

        if success:
            return Response({"message": "连接成功"})
        return Response(
            {"message": "连接失败"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=True, methods=["get"])
    def list_groups(self, request, pk=None):
        """List groups from GitLab."""
        instance = self.get_object()
        client = get_gitlab_client(instance)
        try:
            groups = client.list_groups()
            serializer = GroupChoiceSerializer(groups, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.exception(
                "GitLab 群组列表获取失败 | integration=gitlab operation=list_groups "
                "instance_id=%s error_type=%s",
                instance.id,
                type(e).__name__,
            )
            return Response(
                {"message": f"获取群组列表失败: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class RegisteredGroupViewSet(viewsets.ModelViewSet):
    """ViewSet for RegisteredGroup."""

    queryset = RegisteredGroup.objects.all()
    serializer_class = RegisteredGroupSerializer
    permission_classes = [HasRequiredFeature]
    required_feature = "admin_gitlab"

    def get_queryset(self):
        queryset = super().get_queryset()
        instance_id = self.request.query_params.get("instance")
        if instance_id:
            queryset = queryset.filter(instance_id=instance_id)
        return queryset

    @action(detail=True, methods=["get"])
    def list_projects(self, request, pk=None):
        """List projects in this group from GitLab."""
        group = self.get_object()
        client = get_gitlab_client(group.instance)
        try:
            projects = client.list_projects_in_group(group.gitlab_id)
            serializer = ProjectChoiceSerializer(projects, many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.exception(
                "GitLab 项目列表获取失败 | integration=gitlab operation=list_projects "
                "instance_id=%s group_id=%s error_type=%s",
                group.instance_id,
                group.id,
                type(e).__name__,
            )
            return Response(
                {"message": f"获取项目列表失败: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"])
    def collect_projects(self, request, pk=None):
        """Collect projects from GitLab and register them."""
        group = self.get_object()
        client = get_gitlab_client(group.instance)
        started_at = time.monotonic()
        try:
            projects = client.list_projects_in_group(group.gitlab_id)
            created_count = 0
            for p in projects:
                obj, created = RegisteredProject.objects.update_or_create(
                    instance=group.instance,
                    gitlab_id=p.id,
                    defaults={
                        "group": group,
                        "name": p.name,
                        "path": p.path_with_namespace,
                        "default_branch": p.default_branch,
                        "collected_at": timezone.now(),
                    },
                )
                if created:
                    created_count += 1

            group.collected_at = timezone.now()
            group.save()

            response_data = {
                "message": f"采集成功，新增 {created_count} 个项目",
                "total": len(projects),
                "created": created_count,
            }
            create_operation_record(
                request=request,
                action=GitLabOperationRecord.ACTION_COLLECT_PROJECTS,
                instance=group.instance,
                group=group,
                target_summary=f"{group.name} / {len(projects)} 个项目",
                request_data={"group_id": group.id, "gitlab_group_id": group.gitlab_id},
                result_data=response_data,
                total_count=len(projects),
                success_count=len(projects),
                failed_count=0,
            )
            logger.info(
                "GitLab 项目采集完成 | integration=gitlab operation=collect_projects "
                "instance_id=%s group_id=%s total_count=%s created_count=%s "
                "duration_ms=%s",
                group.instance_id,
                group.id,
                len(projects),
                created_count,
                int((time.monotonic() - started_at) * 1000),
            )
            return Response(response_data)
        except Exception as e:
            logger.exception(
                "GitLab 项目采集失败 | integration=gitlab operation=collect_projects "
                "instance_id=%s group_id=%s error_type=%s duration_ms=%s",
                group.instance_id,
                group.id,
                type(e).__name__,
                int((time.monotonic() - started_at) * 1000),
            )
            create_operation_record(
                request=request,
                action=GitLabOperationRecord.ACTION_COLLECT_PROJECTS,
                instance=group.instance,
                group=group,
                target_summary=f"{group.name} / 采集项目",
                request_data={"group_id": group.id, "gitlab_group_id": group.gitlab_id},
                result_data={},
                total_count=1,
                success_count=0,
                failed_count=1,
                error=str(e),
            )
            return Response(
                {"message": f"采集失败: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class RegisteredProjectViewSet(viewsets.ModelViewSet):
    """ViewSet for RegisteredProject."""

    queryset = RegisteredProject.objects.all()
    serializer_class = RegisteredProjectSerializer
    permission_classes = [HasRequiredFeature]
    required_feature = "admin_gitlab"

    def get_queryset(self):
        queryset = super().get_queryset().prefetch_related("labels")
        instance_id = self.request.query_params.get("instance")
        group_id = self.request.query_params.get("group")
        label_ids = self.request.query_params.get("label_ids")
        if instance_id:
            queryset = queryset.filter(instance_id=instance_id)
        if group_id:
            queryset = queryset.filter(group_id=group_id)
        if label_ids:
            parsed_label_ids = []
            for raw_id in str(label_ids).split(","):
                raw_id = raw_id.strip()
                if not raw_id:
                    continue
                try:
                    parsed_label_ids.append(int(raw_id))
                except (TypeError, ValueError):
                    continue
            if parsed_label_ids:
                queryset = queryset.filter(labels__id__in=parsed_label_ids).distinct()
        return queryset

    def _collect_project_resources(self, project):
        """Collect branches, tags, and webhooks for one registered project."""
        client = get_gitlab_client(project.instance)

        branches = client.list_branches(project.gitlab_id)
        for b in branches:
            GitLabBranch.objects.update_or_create(
                project=project,
                name=b.name,
                defaults={
                    "protected": b.protected,
                    "last_commit_sha": b.commit_sha,
                    "last_commit_date": b.commit_date,
                },
            )

        tags = client.list_tags(project.gitlab_id)
        for t in tags:
            GitLabTag.objects.update_or_create(
                project=project,
                name=t.name,
                defaults={
                    "commit_sha": t.commit_sha,
                    "released_at": t.released_at,
                },
            )

        webhooks = client.list_webhooks(project.gitlab_id)
        gitlab_ids = set()
        for w in webhooks:
            gitlab_ids.add(w.id)
            GitLabWebhook.objects.update_or_create(
                project=project,
                webhook_id=w.id,
                defaults={
                    "url": w.url,
                    "token": w.token or "",
                    "push_events": w.push_events or False,
                    "push_events_branch_filter": w.push_events_branch_filter or "",
                    "tag_push_events": w.tag_push_events or False,
                    "merge_requests_events": w.merge_requests_events or False,
                    "issues_events": w.issues_events or False,
                    "confidential_issues_events": w.confidential_issues_events or False,
                    "note_events": w.note_events or False,
                    "confidential_note_events": w.confidential_note_events or False,
                    "pipeline_events": w.pipeline_events or False,
                    "job_events": w.job_events or False,
                    "wiki_page_events": w.wiki_page_events or False,
                    "deployment_events": w.deployment_events or False,
                    "releases_events": w.releases_events or False,
                    "feature_flag_events": w.feature_flag_events or False,
                    "repository_update_events": w.repository_update_events or False,
                    "resource_access_token_events": w.resource_access_token_events or False,
                    "enable_ssl_verification": w.enable_ssl_verification,
                },
            )

        # Remove webhooks that were deleted from GitLab
        GitLabWebhook.objects.filter(project=project).exclude(
            webhook_id__in=gitlab_ids
        ).delete()

        project.collected_at = timezone.now()
        project.save(update_fields=["collected_at"])

        return {
            "branches": len(branches),
            "tags": len(tags),
            "webhooks": len(webhooks),
        }

    def _create_collection_record(self, project, status_value, result=None, error=""):
        """Write a collection audit record with project snapshot fields."""
        result = result or {}
        return GitLabCollectionRecord.objects.create(
            project=project,
            project_name=project.name,
            project_path=project.path,
            status=status_value,
            branches_count=result.get("branches", 0),
            tags_count=result.get("tags", 0),
            webhooks_count=result.get("webhooks", 0),
            message="采集成功" if status_value == GitLabCollectionRecord.STATUS_SUCCESS else "采集失败",
            error=error,
            finished_at=timezone.now(),
        )

    @action(detail=True, methods=["post"])
    def collect(self, request, pk=None):
        """Collect branches, tags, webhooks from GitLab."""
        project = self.get_object()
        started_at = time.monotonic()

        try:
            result = self._collect_project_resources(project)
            self._create_collection_record(
                project,
                GitLabCollectionRecord.STATUS_SUCCESS,
                result=result,
            )
            response_data = {
                "message": "采集成功",
                **result,
            }
            create_operation_record(
                request=request,
                action=GitLabOperationRecord.ACTION_COLLECT_RESOURCES,
                instance=project.instance,
                group=project.group,
                project=project,
                target_summary=project.path,
                request_data={"project_id": project.id},
                result_data=response_data,
                total_count=1,
                success_count=1,
                failed_count=0,
            )
            logger.info(
                "GitLab 资源采集完成 | integration=gitlab operation=collect_resources "
                "instance_id=%s project_id=%s branch_count=%s tag_count=%s "
                "webhook_count=%s duration_ms=%s",
                project.instance_id,
                project.id,
                result["branches"],
                result["tags"],
                result["webhooks"],
                int((time.monotonic() - started_at) * 1000),
            )
            return Response(response_data)
        except Exception as e:
            logger.exception(
                "GitLab 资源采集失败 | integration=gitlab operation=collect_resources "
                "instance_id=%s project_id=%s error_type=%s duration_ms=%s",
                project.instance_id,
                project.id,
                type(e).__name__,
                int((time.monotonic() - started_at) * 1000),
            )
            self._create_collection_record(
                project,
                GitLabCollectionRecord.STATUS_FAILED,
                error=type(e).__name__,
            )
            create_operation_record(
                request=request,
                action=GitLabOperationRecord.ACTION_COLLECT_RESOURCES,
                instance=project.instance,
                group=project.group,
                project=project,
                target_summary=project.path,
                request_data={"project_id": project.id},
                result_data={},
                total_count=1,
                success_count=0,
                failed_count=1,
                error=str(e),
            )
            return Response(
                {"message": f"采集失败: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["post"])
    def bulk_collect(self, request):
        """Collect GitLab resources for multiple registered projects."""
        raw_project_ids = request.data.get("project_ids", [])
        if not isinstance(raw_project_ids, list) or not raw_project_ids:
            return Response(
                {"message": "project_ids is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project_ids = []
        invalid_project_ids = []
        for raw_project_id in raw_project_ids:
            try:
                project_ids.append(int(raw_project_id))
            except (TypeError, ValueError):
                invalid_project_ids.append(raw_project_id)

        if invalid_project_ids:
            return Response(
                {"message": "project_ids must contain only numeric ids"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        projects = list(
            self.get_queryset()
            .filter(id__in=project_ids)
            .select_related("instance", "group")
        )
        project_map = {project.id: project for project in projects}
        missing_project_ids = [
            project_id for project_id in project_ids if project_id not in project_map
        ]
        if missing_project_ids:
            return Response(
                {"message": f"项目不存在: {', '.join(map(str, missing_project_ids))}"},
                status=status.HTTP_404_NOT_FOUND,
            )

        results = []
        success_count = 0
        failed_count = 0
        started_at = time.monotonic()
        for project_id in project_ids:
            project = project_map[project_id]
            try:
                result = self._collect_project_resources(project)
                self._create_collection_record(
                    project,
                    GitLabCollectionRecord.STATUS_SUCCESS,
                    result=result,
                )
                success_count += 1
                results.append({
                    "project_id": project.id,
                    "project_name": project.name,
                    "project_path": project.path,
                    "status": GitLabCollectionRecord.STATUS_SUCCESS,
                    **result,
                })
            except Exception as e:
                self._create_collection_record(
                    project,
                    GitLabCollectionRecord.STATUS_FAILED,
                    error=type(e).__name__,
                )
                failed_count += 1
                results.append({
                    "project_id": project.id,
                    "project_name": project.name,
                    "project_path": project.path,
                    "status": GitLabCollectionRecord.STATUS_FAILED,
                    "error": str(e),
                    "branches": 0,
                    "tags": 0,
                    "webhooks": 0,
                })

        response_data = {
            "message": "批量采集完成",
            "total": len(project_ids),
            "success_count": success_count,
            "failed_count": failed_count,
            "results": results,
        }
        create_operation_record(
            request=request,
            action=GitLabOperationRecord.ACTION_COLLECT_RESOURCES,
            instance=projects[0].instance if projects else None,
            target_summary=f"{len(project_ids)} 个项目资源采集",
            request_data={"project_ids": project_ids},
            result_data=response_data,
            total_count=len(project_ids),
            success_count=success_count,
            failed_count=failed_count,
        )
        log_method = logger.warning if failed_count else logger.info
        log_method(
            "GitLab 批量采集完成 | integration=gitlab operation=bulk_collect_resources "
            "total_count=%s success_count=%s failed_count=%s duration_ms=%s",
            len(project_ids),
            success_count,
            failed_count,
            int((time.monotonic() - started_at) * 1000),
        )
        return Response(response_data)


class GitLabBranchViewSet(viewsets.ModelViewSet):
    """ViewSet for GitLabBranch."""

    queryset = GitLabBranch.objects.all()
    serializer_class = None
    permission_classes = [HasRequiredFeature]
    required_feature = "admin_gitlab"

    def get_serializer_class(self):
        from .serializers import GitLabBranchSerializer
        return GitLabBranchSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        project_id = self.request.query_params.get("project_id")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        """Bulk create branches."""
        project_id = request.data.get("project_id")
        project_ids = request.data.get("project_ids")
        branch_names = request.data.get("branch_names", [])
        ref = request.data.get("ref", "main")

        if project_ids:
            return self._bulk_apply_to_project_branch_names(
                project_ids=project_ids,
                branch_names=branch_names,
                operation="create",
                ref=ref,
            )

        if not project_id or not branch_names:
            return Response(
                {"message": "project_id and branch_names are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            project = RegisteredProject.objects.get(id=project_id)
        except RegisteredProject.DoesNotExist:
            return Response(
                {"message": "Project not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        client = get_gitlab_client(project.instance)
        created = []
        errors = []
        started_at = time.monotonic()

        for name in branch_names:
            try:
                branch = client.create_branch(project.gitlab_id, name, ref)
                GitLabBranch.objects.update_or_create(
                    project=project,
                    name=branch.name,
                    defaults={
                        "protected": branch.protected,
                        "last_commit_sha": branch.commit_sha,
                        "last_commit_date": branch.commit_date,
                    },
                )
                created.append(name)
            except Exception as e:
                errors.append({"name": name, "error": str(e)})

        response_data = {
            "created": created,
            "errors": errors,
        }
        create_operation_record(
            request=request,
            action=GitLabOperationRecord.ACTION_BRANCH_CREATE,
            instance=project.instance,
            group=project.group,
            project=project,
            target_summary=f"{project.path} / {len(branch_names)} 个分支",
            request_data={"project_id": project.id, "branch_names": branch_names, "ref": ref},
            result_data=response_data,
            total_count=len(branch_names),
            success_count=len(created),
            failed_count=len(errors),
        )
        log_gitlab_operation(
            "branch_create",
            len(branch_names),
            len(created),
            len(errors),
            started_at,
            instance_id=project.instance_id,
            project_id=project.id,
        )
        return Response(response_data)

    @action(detail=False, methods=["post"])
    def bulk_apply(self, request):
        """Apply branch create/delete/protect/unprotect across projects by branch name."""
        return self._bulk_apply_to_project_branch_names(
            project_ids=request.data.get("project_ids", []),
            branch_names=request.data.get("branch_names", []),
            operation=request.data.get("operation"),
            ref=request.data.get("ref", "main"),
        )

    def _bulk_apply_to_project_branch_names(self, project_ids, branch_names, operation, ref="main"):
        allowed_operations = {"create", "delete", "protect", "unprotect"}
        if operation not in allowed_operations:
            return Response(
                {"message": "operation must be one of create, delete, protect, unprotect"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not project_ids or not branch_names:
            return Response(
                {"message": "project_ids and branch_names are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        normalized_project_ids = []
        invalid_project_ids = []
        for project_id in project_ids:
            try:
                normalized_project_ids.append(int(project_id))
            except (TypeError, ValueError):
                invalid_project_ids.append(project_id)

        projects = list(
            RegisteredProject.objects
            .select_related("instance")
            .filter(id__in=normalized_project_ids)
        )
        found_project_ids = {project.id for project in projects}
        missing_project_ids = [
            project_id for project_id in normalized_project_ids
            if project_id not in found_project_ids
        ]

        results = []
        errors = []
        client_cache = {}
        started_at = time.monotonic()

        for missing_id in [*invalid_project_ids, *missing_project_ids]:
            errors.append({
                "project_id": missing_id,
                "branch": None,
                "error": "Project not found",
            })

        for project in projects:
            client = get_cached_gitlab_client(client_cache, project.instance)
            for name in branch_names:
                try:
                    if operation == "create":
                        branch = client.create_branch(project.gitlab_id, name, ref)
                        GitLabBranch.objects.update_or_create(
                            project=project,
                            name=branch.name,
                            defaults={
                                "protected": branch.protected,
                                "last_commit_sha": branch.commit_sha,
                                "last_commit_date": branch.commit_date,
                            },
                        )
                    elif operation == "delete":
                        client.delete_branch(project.gitlab_id, name)
                        GitLabBranch.objects.filter(project=project, name=name).delete()
                    elif operation == "protect":
                        client.protect_branch(project.gitlab_id, name)
                        GitLabBranch.objects.filter(project=project, name=name).update(protected=True)
                    elif operation == "unprotect":
                        client.unprotect_branch(project.gitlab_id, name)
                        GitLabBranch.objects.filter(project=project, name=name).update(protected=False)

                    results.append({
                        "project_id": project.id,
                        "project": project.path,
                        "branch": name,
                        "operation": operation,
                    })
                except Exception as e:
                    errors.append({
                        "project_id": project.id,
                        "project": project.path,
                        "branch": name,
                        "operation": operation,
                        "error": str(e),
                    })

        response_data = {
            "operation": operation,
            "succeeded": results,
            "errors": errors,
            "success_count": len(results),
            "error_count": len(errors),
        }
        create_operation_record(
            request=self.request,
            action=BRANCH_OPERATION_ACTIONS[operation],
            instance=projects[0].instance if projects else None,
            target_summary=f"{len(normalized_project_ids)} 个项目 / {len(branch_names)} 个分支",
            request_data={
                "project_ids": normalized_project_ids,
                "branch_names": branch_names,
                "operation": operation,
                "ref": ref,
            },
            result_data=response_data,
            total_count=len(normalized_project_ids) * len(branch_names),
            success_count=len(results),
            failed_count=len(errors),
        )
        log_gitlab_operation(
            f"branch_{operation}",
            len(normalized_project_ids) * len(branch_names),
            len(results),
            len(errors),
            started_at,
            instance_id=projects[0].instance_id if projects else None,
        )
        return Response(response_data)

    @action(detail=False, methods=["post"])
    def bulk_delete(self, request):
        """Bulk delete branches.

        Uses atomic transaction: GitLab deletion and DB deletion are atomic.
        If any GitLab deletion fails, the entire operation is rolled back.
        """
        branch_ids = request.data.get("branch_ids", [])

        if not branch_ids:
            return Response(
                {"message": "branch_ids are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # First pass: collect branches and validate they exist
        branches_to_delete = []
        for branch_id in branch_ids:
            try:
                branch = GitLabBranch.objects.select_related('project', 'project__instance').get(id=branch_id)
                branches_to_delete.append(branch)
            except GitLabBranch.DoesNotExist:
                return Response(
                    {"message": f"Branch with id {branch_id} not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Second pass: delete from GitLab first (if any fails, DB stays intact)
        errors = []
        started_at = time.monotonic()
        for branch in branches_to_delete:
            try:
                client = get_gitlab_client(branch.project.instance)
                client.delete_branch(branch.project.gitlab_id, branch.name)
            except Exception as e:
                errors.append({"id": branch.id, "name": branch.name, "error": str(e)})

        # If any GitLab deletions failed, abort entire operation
        if errors:
            create_operation_record(
                request=request,
                action=GitLabOperationRecord.ACTION_BRANCH_DELETE,
                instance=branches_to_delete[0].project.instance if branches_to_delete else None,
                target_summary=f"{len(branches_to_delete)} 个分支",
                request_data={"branch_ids": branch_ids},
                result_data={"deleted": [], "errors": errors},
                total_count=len(branches_to_delete),
                success_count=0,
                failed_count=len(errors),
                error="部分分支删除失败，操作已取消",
            )
            log_gitlab_operation(
                "branch_delete",
                len(branches_to_delete),
                0,
                len(errors),
                started_at,
                instance_id=(
                    branches_to_delete[0].project.instance_id
                    if branches_to_delete
                    else None
                ),
            )
            return Response(
                {
                    "message": "部分分支删除失败，操作已取消",
                    "errors": errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Third pass: all GitLab deletions succeeded, now delete from DB
        deleted = []
        with transaction.atomic():
            for branch in branches_to_delete:
                branch.delete()
                deleted.append(branch.name)

        response_data = {
            "deleted": deleted,
            "errors": [],
        }
        create_operation_record(
            request=request,
            action=GitLabOperationRecord.ACTION_BRANCH_DELETE,
            instance=branches_to_delete[0].project.instance if branches_to_delete else None,
            target_summary=f"{len(branches_to_delete)} 个分支",
            request_data={"branch_ids": branch_ids},
            result_data=response_data,
            total_count=len(branches_to_delete),
            success_count=len(deleted),
            failed_count=0,
        )
        log_gitlab_operation(
            "branch_delete",
            len(branches_to_delete),
            len(deleted),
            0,
            started_at,
            instance_id=(
                branches_to_delete[0].project.instance_id
                if branches_to_delete
                else None
            ),
        )
        return Response(response_data)

    @action(detail=False, methods=["post"])
    def bulk_protect(self, request):
        """Bulk protect branches."""
        branch_ids = request.data.get("branch_ids", [])

        if not branch_ids:
            return Response(
                {"message": "branch_ids are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        protected = []
        errors = []
        started_at = time.monotonic()

        for branch_id in branch_ids:
            try:
                branch = GitLabBranch.objects.get(id=branch_id)
                client = get_gitlab_client(branch.project.instance)
                client.protect_branch(branch.project.gitlab_id, branch.name)
                branch.protected = True
                branch.save()
                protected.append(branch.name)
            except Exception as e:
                errors.append({"id": branch_id, "error": str(e)})

        response_data = {
            "protected": protected,
            "errors": errors,
        }
        create_operation_record(
            request=request,
            action=GitLabOperationRecord.ACTION_BRANCH_PROTECT,
            target_summary=f"{len(branch_ids)} 个分支",
            request_data={"branch_ids": branch_ids},
            result_data=response_data,
            total_count=len(branch_ids),
            success_count=len(protected),
            failed_count=len(errors),
        )
        log_gitlab_operation(
            "branch_protect",
            len(branch_ids),
            len(protected),
            len(errors),
            started_at,
        )
        return Response(response_data)

    @action(detail=False, methods=["post"])
    def bulk_unprotect(self, request):
        """Bulk unprotect branches."""
        branch_ids = request.data.get("branch_ids", [])

        if not branch_ids:
            return Response(
                {"message": "branch_ids are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        unprotected = []
        errors = []
        started_at = time.monotonic()

        for branch_id in branch_ids:
            try:
                branch = GitLabBranch.objects.get(id=branch_id)
                client = get_gitlab_client(branch.project.instance)
                client.unprotect_branch(branch.project.gitlab_id, branch.name)
                branch.protected = False
                branch.save()
                unprotected.append(branch.name)
            except Exception as e:
                errors.append({"id": branch_id, "error": str(e)})

        response_data = {
            "unprotected": unprotected,
            "errors": errors,
        }
        create_operation_record(
            request=request,
            action=GitLabOperationRecord.ACTION_BRANCH_UNPROTECT,
            target_summary=f"{len(branch_ids)} 个分支",
            request_data={"branch_ids": branch_ids},
            result_data=response_data,
            total_count=len(branch_ids),
            success_count=len(unprotected),
            failed_count=len(errors),
        )
        log_gitlab_operation(
            "branch_unprotect",
            len(branch_ids),
            len(unprotected),
            len(errors),
            started_at,
        )
        return Response(response_data)


class GitLabProjectLabelViewSet(viewsets.ModelViewSet):
    """ViewSet for GitLabProjectLabel."""

    queryset = GitLabProjectLabel.objects.all()
    serializer_class = ProjectLabelSerializer
    permission_classes = [HasRequiredFeature]
    required_feature = "admin_gitlab"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .annotate(project_count=Count("projects", distinct=True))
            .order_by("name")
        )


class GitLabCollectionRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only ViewSet for GitLab collection records."""

    queryset = GitLabCollectionRecord.objects.select_related("project").all()
    serializer_class = GitLabCollectionRecordSerializer
    permission_classes = [HasRequiredFeature]
    required_feature = "admin_gitlab"

    def get_queryset(self):
        queryset = super().get_queryset()
        project_id = self.request.query_params.get("project_id")
        status_value = self.request.query_params.get("status")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if status_value:
            queryset = queryset.filter(status=status_value)
        return queryset


class GitLabOperationRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only ViewSet for GitLab operation audit records."""

    queryset = (
        GitLabOperationRecord.objects.select_related(
            "actor",
            "instance",
            "group",
            "project",
        )
        .all()
    )
    serializer_class = GitLabOperationRecordSerializer
    permission_classes = [HasRequiredFeature]
    required_feature = "admin_gitlab"

    def get_queryset(self):
        queryset = super().get_queryset()
        action_value = self.request.query_params.get("action")
        status_value = self.request.query_params.get("status")
        project_id = self.request.query_params.get("project_id")
        if action_value:
            queryset = queryset.filter(action=action_value)
        if status_value:
            queryset = queryset.filter(status=status_value)
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset


class GitLabTagViewSet(viewsets.ModelViewSet):
    """ViewSet for GitLabTag."""

    queryset = GitLabTag.objects.all()
    serializer_class = None
    permission_classes = [HasRequiredFeature]
    required_feature = "admin_gitlab"

    def get_serializer_class(self):
        from .serializers import GitLabTagSerializer
        return GitLabTagSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        project_id = self.request.query_params.get("project_id")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        """Bulk create tags."""
        project_id = request.data.get("project_id")
        project_ids = request.data.get("project_ids")
        tag_names = request.data.get("tag_names", [])
        ref = request.data.get("ref", "main")
        message = (request.data.get("message") or "").strip()

        if project_ids:
            return self._bulk_create_for_projects(
                project_ids=project_ids,
                tag_names=tag_names,
                ref=ref,
                message=message,
            )

        if not project_id or not tag_names:
            return Response(
                {"message": "project_id and tag_names are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            project = RegisteredProject.objects.get(id=project_id)
        except RegisteredProject.DoesNotExist:
            return Response(
                {"message": "Project not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        client = get_gitlab_client(project.instance)
        created = []
        errors = []
        started_at = time.monotonic()

        for name in tag_names:
            try:
                tag = client.create_tag(project.gitlab_id, name, ref, message=message)
                GitLabTag.objects.update_or_create(
                    project=project,
                    name=tag.name,
                    defaults={
                        "commit_sha": tag.commit_sha,
                        "released_at": tag.released_at,
                    },
                )
                created.append(name)
            except Exception as e:
                errors.append({"name": name, "error": str(e)})

        response_data = {
            "created": created,
            "errors": errors,
            "success_count": len(created),
            "error_count": len(errors),
        }
        create_operation_record(
            request=request,
            action=GitLabOperationRecord.ACTION_TAG_CREATE,
            instance=project.instance,
            project=project,
            target_summary=f"1 个项目 / {len(tag_names)} 个标签",
            request_data={
                "project_id": project.id,
                "tag_names": tag_names,
                "ref": ref,
                "message": message,
            },
            result_data=response_data,
            total_count=len(tag_names),
            success_count=len(created),
            failed_count=len(errors),
        )
        log_gitlab_operation(
            "tag_create",
            len(tag_names),
            len(created),
            len(errors),
            started_at,
            instance_id=project.instance_id,
            project_id=project.id,
        )
        return Response(response_data)

    def _bulk_create_for_projects(self, project_ids, tag_names, ref="main", message=""):
        if not project_ids or not tag_names:
            return Response(
                {"message": "project_ids and tag_names are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        normalized_project_ids = []
        invalid_project_ids = []
        for project_id in project_ids:
            try:
                normalized_project_ids.append(int(project_id))
            except (TypeError, ValueError):
                invalid_project_ids.append(project_id)

        projects = list(
            RegisteredProject.objects
            .select_related("instance")
            .filter(id__in=normalized_project_ids)
        )
        found_project_ids = {project.id for project in projects}
        missing_project_ids = [
            project_id for project_id in normalized_project_ids
            if project_id not in found_project_ids
        ]

        created = []
        errors = []
        client_cache = {}
        started_at = time.monotonic()

        for missing_id in [*invalid_project_ids, *missing_project_ids]:
            errors.append({
                "project_id": missing_id,
                "tag": None,
                "error": "Project not found",
            })

        for project in projects:
            client = get_cached_gitlab_client(client_cache, project.instance)
            for name in tag_names:
                try:
                    tag = client.create_tag(project.gitlab_id, name, ref, message=message)
                    GitLabTag.objects.update_or_create(
                        project=project,
                        name=tag.name,
                        defaults={
                            "commit_sha": tag.commit_sha,
                            "released_at": tag.released_at,
                        },
                    )
                    created.append({
                        "project_id": project.id,
                        "project": project.path,
                        "tag": tag.name,
                    })
                except Exception as e:
                    errors.append({
                        "project_id": project.id,
                        "project": project.path,
                        "tag": name,
                        "error": str(e),
                    })

        response_data = {
            "created": created,
            "errors": errors,
            "success_count": len(created),
            "error_count": len(errors),
        }
        create_operation_record(
            request=self.request,
            action=GitLabOperationRecord.ACTION_TAG_CREATE,
            instance=projects[0].instance if projects else None,
            target_summary=f"{len(normalized_project_ids)} 个项目 / {len(tag_names)} 个标签",
            request_data={
                "project_ids": normalized_project_ids,
                "tag_names": tag_names,
                "ref": ref,
                "message": message,
            },
            result_data=response_data,
            total_count=len(normalized_project_ids) * len(tag_names),
            success_count=len(created),
            failed_count=len(errors),
        )
        log_gitlab_operation(
            "tag_create",
            len(normalized_project_ids) * len(tag_names),
            len(created),
            len(errors),
            started_at,
            instance_id=projects[0].instance_id if projects else None,
        )
        return Response(response_data)

    @action(detail=False, methods=["post"])
    def bulk_delete(self, request):
        """Bulk delete tags.

        Uses atomic transaction: GitLab deletion and DB deletion are atomic.
        If any GitLab deletion fails, the entire operation is rolled back.
        """
        tag_ids = request.data.get("tag_ids", [])

        if not tag_ids:
            return Response(
                {"message": "tag_ids are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # First pass: collect tags and validate they exist
        tags_to_delete = []
        for tag_id in tag_ids:
            try:
                tag = GitLabTag.objects.select_related('project', 'project__instance').get(id=tag_id)
                tags_to_delete.append(tag)
            except GitLabTag.DoesNotExist:
                return Response(
                    {"message": f"Tag with id {tag_id} not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        # Second pass: delete from GitLab first (if any fails, DB stays intact)
        errors = []
        started_at = time.monotonic()
        for tag in tags_to_delete:
            try:
                client = get_gitlab_client(tag.project.instance)
                client.delete_tag(tag.project.gitlab_id, tag.name)
            except Exception as e:
                errors.append({"id": tag.id, "name": tag.name, "error": str(e)})

        # If any GitLab deletions failed, abort entire operation
        if errors:
            create_operation_record(
                request=request,
                action=GitLabOperationRecord.ACTION_TAG_DELETE,
                instance=tags_to_delete[0].project.instance if tags_to_delete else None,
                target_summary=f"{len(tags_to_delete)} 个标签",
                request_data={"tag_ids": tag_ids},
                result_data={"deleted": [], "errors": errors},
                total_count=len(tags_to_delete),
                success_count=0,
                failed_count=len(errors),
                error="部分 Tag 删除失败，操作已取消",
            )
            log_gitlab_operation(
                "tag_delete",
                len(tags_to_delete),
                0,
                len(errors),
                started_at,
                instance_id=(
                    tags_to_delete[0].project.instance_id
                    if tags_to_delete
                    else None
                ),
            )
            return Response(
                {
                    "message": "部分 Tag 删除失败，操作已取消",
                    "errors": errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Third pass: all GitLab deletions succeeded, now delete from DB
        deleted = []
        with transaction.atomic():
            for tag in tags_to_delete:
                tag.delete()
                deleted.append(tag.name)

        response_data = {
            "deleted": deleted,
            "errors": [],
        }
        create_operation_record(
            request=request,
            action=GitLabOperationRecord.ACTION_TAG_DELETE,
            instance=tags_to_delete[0].project.instance if tags_to_delete else None,
            target_summary=f"{len(tags_to_delete)} 个标签",
            request_data={"tag_ids": tag_ids},
            result_data=response_data,
            total_count=len(tags_to_delete),
            success_count=len(deleted),
            failed_count=0,
        )
        log_gitlab_operation(
            "tag_delete",
            len(tags_to_delete),
            len(deleted),
            0,
            started_at,
            instance_id=(
                tags_to_delete[0].project.instance_id
                if tags_to_delete
                else None
            ),
        )
        return Response(response_data)


class GitLabWebhookViewSet(viewsets.ModelViewSet):
    """ViewSet for GitLabWebhook."""

    queryset = GitLabWebhook.objects.all()
    serializer_class = None
    permission_classes = [HasRequiredFeature]
    required_feature = "admin_gitlab"

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return GitLabWebhookCreateSerializer
        return GitLabWebhookSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        project_id = self.request.query_params.get("project_id")
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    def perform_create(self, serializer):
        """Create webhook in GitLab and save to DB."""
        project_id = serializer.validated_data.get("project").id
        project = RegisteredProject.objects.get(id=project_id)
        client = get_gitlab_client(project.instance)

        data = serializer.validated_data
        started_at = time.monotonic()
        try:
            webhook = client.create_webhook(
                project_id=project.gitlab_id,
                url=data["url"],
                push_events=data.get("push_events", True),
                tag_push_events=data.get("tag_push_events", False),
                merge_requests_events=data.get("merge_requests_events", False),
                enable_ssl_verification=data.get("enable_ssl_verification", True),
                push_events_branch_filter=data.get("push_events_branch_filter"),
                issues_events=data.get("issues_events", False),
                confidential_issues_events=data.get("confidential_issues_events", False),
                note_events=data.get("note_events", False),
                confidential_note_events=data.get("confidential_note_events", False),
                pipeline_events=data.get("pipeline_events", False),
                job_events=data.get("job_events", False),
                wiki_page_events=data.get("wiki_page_events", False),
                deployment_events=data.get("deployment_events", False),
                releases_events=data.get("releases_events", False),
                feature_flag_events=data.get("feature_flag_events", False),
                repository_update_events=data.get("repository_update_events", False),
                resource_access_token_events=data.get("resource_access_token_events", False),
                token=data.get("token"),
            )
        except Exception as exc:
            logger.error(
                "GitLab Webhook 创建失败 | integration=gitlab "
                "operation=webhook_create instance_id=%s project_id=%s "
                "error_type=%s duration_ms=%s",
                project.instance_id,
                project.id,
                type(exc).__name__,
                int((time.monotonic() - started_at) * 1000),
            )
            raise

        saved = serializer.save(webhook_id=webhook.id)
        create_operation_record(
            request=self.request,
            action=GitLabOperationRecord.ACTION_WEBHOOK_CREATE,
            instance=project.instance,
            group=project.group,
            project=project,
            target_summary=f"{project.path} / Webhook",
            request_data={
                "project": project.id,
                "url": data["url"],
                "push_events": data.get("push_events", True),
                "tag_push_events": data.get("tag_push_events", False),
                "merge_requests_events": data.get("merge_requests_events", False),
                "enable_ssl_verification": data.get("enable_ssl_verification", True),
            },
            result_data={"webhook_id": saved.webhook_id, "url": saved.url},
            total_count=1,
            success_count=1,
            failed_count=0,
        )
        log_gitlab_operation(
            "webhook_create",
            1,
            1,
            0,
            started_at,
            instance_id=project.instance_id,
            project_id=project.id,
        )

    def perform_update(self, serializer):
        """Update webhook in GitLab and save to DB."""
        instance = self.get_object()
        project = instance.project
        client = get_gitlab_client(project.instance)

        data = serializer.validated_data
        started_at = time.monotonic()
        try:
            webhook = client.update_webhook(
                project_id=project.gitlab_id,
                hook_id=instance.webhook_id,
                url=data.get("url"),
                push_events=data.get("push_events"),
                tag_push_events=data.get("tag_push_events"),
                merge_requests_events=data.get("merge_requests_events"),
                enable_ssl_verification=data.get("enable_ssl_verification"),
                push_events_branch_filter=data.get("push_events_branch_filter"),
                issues_events=data.get("issues_events"),
                confidential_issues_events=data.get("confidential_issues_events"),
                note_events=data.get("note_events"),
                confidential_note_events=data.get("confidential_note_events"),
                pipeline_events=data.get("pipeline_events"),
                job_events=data.get("job_events"),
                wiki_page_events=data.get("wiki_page_events"),
                deployment_events=data.get("deployment_events"),
                releases_events=data.get("releases_events"),
                feature_flag_events=data.get("feature_flag_events"),
                repository_update_events=data.get("repository_update_events"),
                resource_access_token_events=data.get("resource_access_token_events"),
                token=data.get("token"),
            )
        except Exception as exc:
            logger.error(
                "GitLab Webhook 更新失败 | integration=gitlab "
                "operation=webhook_update instance_id=%s project_id=%s "
                "webhook_id=%s error_type=%s duration_ms=%s",
                project.instance_id,
                project.id,
                instance.webhook_id,
                type(exc).__name__,
                int((time.monotonic() - started_at) * 1000),
            )
            raise

        saved = serializer.save()
        create_operation_record(
            request=self.request,
            action=GitLabOperationRecord.ACTION_WEBHOOK_UPDATE,
            instance=project.instance,
            group=project.group,
            project=project,
            target_summary=f"{project.path} / Webhook",
            request_data={
                "webhook_id": instance.webhook_id,
                "url": data.get("url"),
                "push_events": data.get("push_events"),
                "tag_push_events": data.get("tag_push_events"),
                "merge_requests_events": data.get("merge_requests_events"),
                "enable_ssl_verification": data.get("enable_ssl_verification"),
            },
            result_data={"webhook_id": saved.webhook_id, "url": saved.url},
            total_count=1,
            success_count=1,
            failed_count=0,
        )
        log_gitlab_operation(
            "webhook_update",
            1,
            1,
            0,
            started_at,
            instance_id=project.instance_id,
            project_id=project.id,
        )

    def perform_destroy(self, instance):
        """Delete webhook from GitLab and DB.

        Raises:
            Exception: If GitLab API call fails. DB record is NOT deleted
            to maintain consistency between local and remote state.
        """
        project = instance.project
        client = get_gitlab_client(project.instance)
        started_at = time.monotonic()
        try:
            if instance.webhook_id:
                # Try to delete from GitLab first. If this fails, keep the DB record.
                client.delete_webhook(project.gitlab_id, instance.webhook_id)
        except Exception as e:
            create_operation_record(
                request=self.request,
                action=GitLabOperationRecord.ACTION_WEBHOOK_DELETE,
                instance=project.instance,
                group=project.group,
                project=project,
                target_summary=f"{project.path} / Webhook",
                request_data={"webhook_id": instance.webhook_id, "url": instance.url},
                result_data={},
                total_count=1,
                success_count=0,
                failed_count=1,
                error=str(e),
            )
            logger.error(
                "GitLab Webhook 删除失败 | integration=gitlab "
                "operation=webhook_delete instance_id=%s project_id=%s "
                "webhook_id=%s error_type=%s duration_ms=%s",
                project.instance_id,
                project.id,
                instance.webhook_id,
                type(e).__name__,
                int((time.monotonic() - started_at) * 1000),
            )
            raise
        create_operation_record(
            request=self.request,
            action=GitLabOperationRecord.ACTION_WEBHOOK_DELETE,
            instance=project.instance,
            group=project.group,
            project=project,
            target_summary=f"{project.path} / Webhook",
            request_data={"webhook_id": instance.webhook_id, "url": instance.url},
            result_data={"webhook_id": instance.webhook_id, "url": instance.url},
            total_count=1,
            success_count=1,
            failed_count=0,
        )
        log_gitlab_operation(
            "webhook_delete",
            1,
            1,
            0,
            started_at,
            instance_id=project.instance_id,
            project_id=project.id,
        )
        # Only delete local record if GitLab deletion succeeded (or webhook_id was None)
        instance.delete()
