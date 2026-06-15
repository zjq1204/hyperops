"""
GitLab Resource views.
"""

import logging

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
    actor = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
    return GitLabOperationRecord.objects.create(
        actor=actor,
        action=action,
        status=get_operation_status(success_count, failed_count),
        instance=instance,
        group=group,
        project=project,
        target_summary=target_summary,
        request_data=request_data or {},
        result_data=result_data or {},
        total_count=total_count,
        success_count=success_count,
        failed_count=failed_count,
        error=error,
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
            logger.error(f"Failed to list groups: {e}")
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
            logger.error(f"Failed to list projects: {e}")
            return Response(
                {"message": f"获取项目列表失败: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"])
    def collect_projects(self, request, pk=None):
        """Collect projects from GitLab and register them."""
        group = self.get_object()
        client = get_gitlab_client(group.instance)
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
            return Response(response_data)
        except Exception as e:
            logger.error(f"Failed to collect projects: {e}")
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
        for w in webhooks:
            GitLabWebhook.objects.update_or_create(
                project=project,
                webhook_id=w.id,
                defaults={
                    "url": w.url,
                    "push_events": w.push_events,
                    "tag_push_events": w.tag_push_events,
                    "merge_requests_events": w.merge_requests_events,
                    "enable_ssl_verification": w.enable_ssl_verification,
                },
            )

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
            return Response(response_data)
        except Exception as e:
            logger.error(f"Failed to collect: {e}")
            self._create_collection_record(
                project,
                GitLabCollectionRecord.STATUS_FAILED,
                error=str(e),
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
                logger.error(f"Failed to bulk collect project {project.id}: {e}")
                self._create_collection_record(
                    project,
                    GitLabCollectionRecord.STATUS_FAILED,
                    error=str(e),
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
        webhook = client.create_webhook(
            project_id=project.gitlab_id,
            url=data["url"],
            push_events=data.get("push_events", True),
            tag_push_events=data.get("tag_push_events", False),
            merge_requests_events=data.get("merge_requests_events", False),
            enable_ssl_verification=data.get("enable_ssl_verification", True),
        )

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

    def perform_update(self, serializer):
        """Update webhook in GitLab and save to DB."""
        instance = self.get_object()
        project = instance.project
        client = get_gitlab_client(project.instance)

        data = serializer.validated_data
        webhook = client.update_webhook(
            project_id=project.gitlab_id,
            hook_id=instance.webhook_id,
            url=data.get("url"),
            push_events=data.get("push_events"),
            tag_push_events=data.get("tag_push_events"),
            merge_requests_events=data.get("merge_requests_events"),
            enable_ssl_verification=data.get("enable_ssl_verification"),
        )

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

    def perform_destroy(self, instance):
        """Delete webhook from GitLab and DB.

        Raises:
            Exception: If GitLab API call fails. DB record is NOT deleted
            to maintain consistency between local and remote state.
        """
        project = instance.project
        client = get_gitlab_client(project.instance)
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
        # Only delete local record if GitLab deletion succeeded (or webhook_id was None)
        instance.delete()
