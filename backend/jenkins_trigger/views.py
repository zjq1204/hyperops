"""
Jenkins Trigger views.
"""

import logging
from datetime import datetime, timezone as dt_timezone

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import HasRequiredFeature

from .models import (
    JenkinsInstance,
    TriggerEntry,
    TriggerRecord,
    UserEntryNotificationPreference,
)
from .notification_service import (
    build_notification_result,
    deliver_build_notifications,
)
from .serializers import (
    JenkinsInstanceConnectionTestSerializer,
    JenkinsInstanceCreateSerializer,
    JenkinsInstanceSerializer,
    TriggerEntryCreateSerializer,
    TriggerEntrySerializer,
    TriggerParamsSerializer,
    TriggerRecordSerializer,
)
from .services.jenkins_client import JenkinsClient, JenkinsJobNode, JenkinsParamDefinition


logger = logging.getLogger(__name__)

TERMINAL_RECORD_STATUSES = {"success", "failure", "aborted"}
QUEUED_STAGE_NAME = "排队中"
DEFAULT_PARAM_MODE = "hidden"


def build_job_catalog_cache_key(instance_id: int) -> str:
    return f"jenkins:job_catalog:v1:{instance_id}"


def get_job_catalog_cache_ttl(instance: JenkinsInstance) -> int:
    days = getattr(instance, "job_catalog_cache_ttl_days", 1) or 1
    return max(1, days) * 24 * 60 * 60


def get_jenkins_client(instance: JenkinsInstance) -> JenkinsClient:
    """Create Jenkins client from instance."""
    return JenkinsClient(
        url=instance.url,
        username=instance.username,
        token=instance.token,
    )


def build_jenkins_client(url: str, username: str, token: str) -> JenkinsClient:
    """Create Jenkins client from raw credentials."""
    return JenkinsClient(
        url=url,
        username=username,
        token=token,
    )


def apply_build_result_to_record(record: TriggerRecord, result) -> None:
    """Apply Jenkins build result fields to a trigger record."""
    record.build_number = result.build_number

    if result.result is None:
        record.status = "running"
    elif result.result == "SUCCESS":
        record.status = "success"
    elif result.result == "FAILURE":
        record.status = "failure"
    elif result.result == "ABORTED":
        record.status = "aborted"
    else:
        record.status = "failure"

    record.artifacts = [
        {"path": artifact.get("relativePath"), "name": artifact.get("fileName")}
        for artifact in result.artifacts
    ]

    if record.status in ["success", "failure", "aborted"] and not record.finished_at:
        finished_timestamp_ms = (result.timestamp or 0) + max(result.duration or 0, 0)
        if finished_timestamp_ms > 0:
            record.finished_at = datetime.fromtimestamp(
                finished_timestamp_ms / 1000,
                tz=dt_timezone.utc,
            )
        else:
            record.finished_at = timezone.now()


def notify_record_if_terminal(record: TriggerRecord, previous_status: str) -> None:
    if previous_status in TERMINAL_RECORD_STATUSES or record.status not in TERMINAL_RECORD_STATUSES:
        return
    status_text = {
        "success": "成功",
        "failure": "失败",
        "aborted": "已取消",
    }.get(record.status, record.status)
    record.notification_result = build_notification_result(
        record.user,
        record.entry,
        (record.finished_at or timezone.now()).isoformat(),
    ) if record.user else {}
    deliver_build_notifications(record, status_text)


def apply_queued_progress_to_record(record: TriggerRecord) -> None:
    """Store an explicit queue progress snapshot before Jenkins assigns a build."""
    record.progress_percent = 0
    record.current_stage = QUEUED_STAGE_NAME
    record.stage_summary = None
    record.pipeline_supported = False


def apply_terminal_progress_to_record(record: TriggerRecord) -> None:
    """Terminal Jenkins records always expose a completed progress snapshot."""
    record.progress_percent = 100
    record.current_stage = ""
    record.stage_summary = None
    record.pipeline_supported = False


def apply_pipeline_progress_to_record(record: TriggerRecord, progress) -> None:
    """Copy parsed Pipeline progress onto the trigger record snapshot fields."""
    if getattr(progress, "pipeline_supported", False) is not True:
        record.pipeline_supported = False
        record.progress_percent = 100 if record.status in TERMINAL_RECORD_STATUSES else None
        record.current_stage = ""
        record.stage_summary = None
        return

    progress_percent = getattr(progress, "progress_percent", None)
    if record.status in TERMINAL_RECORD_STATUSES:
        progress_percent = 100
    elif not isinstance(progress_percent, int):
        progress_percent = None

    record.pipeline_supported = True
    record.progress_percent = progress_percent
    current_stage = getattr(progress, "current_stage", "") or ""
    record.current_stage = current_stage[:255] if isinstance(current_stage, str) else ""
    stage_summary = getattr(progress, "stage_summary", None)
    if isinstance(stage_summary, dict):
        if record.status in TERMINAL_RECORD_STATUSES and stage_summary.get("total"):
            stage_summary = {
                **stage_summary,
                "completed": stage_summary["total"],
            }
        record.stage_summary = stage_summary
    else:
        record.stage_summary = None


def refresh_record_pipeline_progress(record: TriggerRecord, client: JenkinsClient) -> None:
    """Refresh Pipeline progress best-effort without breaking status refresh."""
    if not record.build_number:
        apply_queued_progress_to_record(record)
        return

    try:
        progress = client.get_pipeline_progress(record.entry.job_name, record.build_number)
    except Exception as exc:
        logger.warning(
            "Failed to refresh Pipeline progress for record %s: %s",
            record.pk,
            exc,
        )
        progress = None

    apply_pipeline_progress_to_record(record, progress)


def is_http_404(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None) == 404


def refresh_trigger_record_status(record: TriggerRecord) -> TriggerRecord:
    """Refresh one Jenkins trigger record using queue/build fallback logic."""
    if record.status in TERMINAL_RECORD_STATUSES:
        if record.progress_percent != 100:
            apply_terminal_progress_to_record(record)
            record.save(
                update_fields=[
                    "progress_percent",
                    "current_stage",
                    "stage_summary",
                    "pipeline_supported",
                ]
            )
        return record

    if not record.build_number and not record.queue_url:
        raise ValueError("No build number or Jenkins queue URL")

    client = get_jenkins_client(record.entry.instance)

    if not record.build_number and record.queue_url:
        queue_id = JenkinsClient._parse_queue_id(record.queue_url)
        try:
            queue_item = client.get_queue_item(record.queue_url)
        except Exception as queue_exc:
            if not is_http_404(queue_exc) or not queue_id:
                raise
            resolved_build_number = client.find_build_number_by_queue_id(
                record.entry.job_name,
                queue_id,
            )
            if resolved_build_number is None:
                record.status = "pending"
                apply_queued_progress_to_record(record)
                record.save(
                    update_fields=[
                        "status",
                        "progress_percent",
                        "current_stage",
                        "stage_summary",
                        "pipeline_supported",
                    ]
                )
                return record
            record.build_number = resolved_build_number
            queue_item = None

        if queue_item is None:
            result = client.get_build_result(record.entry.job_name, record.build_number)
            previous_status = record.status
            apply_build_result_to_record(record, result)
            refresh_record_pipeline_progress(record, client)
            notify_record_if_terminal(record, previous_status)
            record.save()
            return record

        if queue_item.cancelled:
            record.status = "aborted"
            record.finished_at = record.finished_at or timezone.now()
            apply_terminal_progress_to_record(record)
            record.save()
            return record

        if not queue_item.executable_number:
            record.status = "pending"
            apply_queued_progress_to_record(record)
            record.save(
                update_fields=[
                    "status",
                    "progress_percent",
                    "current_stage",
                    "stage_summary",
                    "pipeline_supported",
                ]
            )
            return record

        record.build_number = queue_item.executable_number

    try:
        result = client.get_build_result(record.entry.job_name, record.build_number)
    except Exception as build_exc:
        if not is_http_404(build_exc):
            raise

        queue_id = record.build_number
        if not queue_id:
            raise
        try:
            queue_item = client.get_queue_item_by_id(queue_id)
        except Exception as queue_exc:
            if not is_http_404(queue_exc):
                raise
            resolved_build_number = client.find_build_number_by_queue_id(
                record.entry.job_name,
                queue_id,
            )
            if resolved_build_number is None:
                record.status = "pending"
                record.queue_url = record.queue_url or f"{client.url}/queue/item/{queue_id}/"
                record.build_number = None
                apply_queued_progress_to_record(record)
                record.save(
                    update_fields=[
                        "status",
                        "queue_url",
                        "build_number",
                        "progress_percent",
                        "current_stage",
                        "stage_summary",
                        "pipeline_supported",
                    ]
                )
                return record

            record.queue_url = record.queue_url or f"{client.url}/queue/item/{queue_id}/"
            record.build_number = resolved_build_number
            result = client.get_build_result(record.entry.job_name, record.build_number)
            previous_status = record.status
            apply_build_result_to_record(record, result)
            refresh_record_pipeline_progress(record, client)
            notify_record_if_terminal(record, previous_status)
            record.save()
            return record

        if queue_item.cancelled:
            record.status = "aborted"
            record.finished_at = record.finished_at or timezone.now()
            apply_terminal_progress_to_record(record)
            record.save()
            return record
        if not queue_item.executable_number:
            record.status = "pending"
            record.queue_url = record.queue_url or f"{client.url}/queue/item/{queue_id}/"
            record.build_number = None
            apply_queued_progress_to_record(record)
            record.save(
                update_fields=[
                    "status",
                    "queue_url",
                    "build_number",
                    "progress_percent",
                    "current_stage",
                    "stage_summary",
                    "pipeline_supported",
                ]
            )
            return record

        record.queue_url = record.queue_url or f"{client.url}/queue/item/{queue_id}/"
        record.build_number = queue_item.executable_number
        result = client.get_build_result(record.entry.job_name, record.build_number)

    previous_status = record.status
    apply_build_result_to_record(record, result)
    refresh_record_pipeline_progress(record, client)
    notify_record_if_terminal(record, previous_status)
    record.save()
    return record


def normalize_job_enabled(node: JenkinsJobNode) -> bool | None:
    """Normalize whether a Jenkins job is enabled."""
    if node.type != "job":
        return None
    if node.buildable is not None:
        return bool(node.buildable)
    if (node.color or "").lower() == "disabled":
        return False
    return None


def serialize_job_node(node: JenkinsJobNode) -> dict:
    return {
        "full_name": node.full_name,
        "display_name": node.display_name,
        "url": node.url,
        "type": node.type,
        "has_children": node.has_children,
        "buildable": node.buildable,
        "color": node.color,
        "enabled": normalize_job_enabled(node),
        "children": [serialize_job_node(child) for child in node.children],
    }


def resolve_param_default_values(
    client: JenkinsClient, job_name: str, params: list[JenkinsParamDefinition]
) -> list[dict]:
    """Resolve parameter values preferring the last successful build."""
    try:
        latest_build_params = client.get_last_successful_build_params(job_name)
    except Exception as exc:
        logger.warning(
            "Failed to resolve last successful build params for %s: %s",
            job_name,
            exc,
        )
        latest_build_params = {}

    resolved_params = []
    for param in params:
        if param.name in latest_build_params:
            default_value = latest_build_params[param.name]
            value_source = "latest_success_build"
        elif param.default_value not in (None, ""):
            default_value = param.default_value
            value_source = "job_default"
        else:
            default_value = ""
            value_source = "empty"

        resolved_params.append(
            {
                "name": param.name,
                "type": param.type,
                "default_value": default_value,
                "choices": param.choices,
                "description": param.description,
                "value_source": value_source,
            }
        )

    return resolved_params


def build_entry_param_payload(
    jenkins_params: list[JenkinsParamDefinition],
    params_config: dict,
    include_hidden: bool = False,
) -> list[dict]:
    """Merge Jenkins parameter definitions with saved trigger-entry config."""
    merged_params = []
    seen_names = set()
    normalized_config = {
        str(param_name).lower(): config
        for param_name, config in params_config.items()
    }

    for param in jenkins_params:
        normalized_name = str(param.name).lower()
        config = params_config.get(param.name) or normalized_config.get(normalized_name, {})
        mode = config.get("mode", DEFAULT_PARAM_MODE)

        if mode == "hidden" and not include_hidden:
            continue

        seen_names.add(normalized_name)
        merged_params.append(
            {
                "name": param.name,
                "type": param.type,
                "default_value": config.get("default_value", param.default_value),
                "choices": param.choices,
                "description": param.description,
                "mode": mode,
            }
        )

    if include_hidden:
        for param_name, config in params_config.items():
            if str(param_name).lower() in seen_names:
                continue

            merged_params.append(
                {
                    "name": param_name,
                    "type": config.get("type", "StringParameterDefinition"),
                    "default_value": config.get("default_value", ""),
                    "choices": config.get("choices"),
                    "description": config.get("description"),
                    "mode": config.get("mode", DEFAULT_PARAM_MODE),
                }
            )

    return merged_params


def build_trigger_params(
    user_params: dict,
    params_config: dict,
    jenkins_params: list[JenkinsParamDefinition],
) -> dict:
    """Build Jenkins trigger params using Jenkins' canonical parameter names."""
    normalized_config = {
        str(param_name).lower(): config
        for param_name, config in params_config.items()
    }
    canonical_param_names = {
        str(param.name).lower(): param.name
        for param in jenkins_params
    }

    final_params = {}
    for param_name, param_value in user_params.items():
        normalized_name = str(param_name).lower()
        config = params_config.get(param_name) or normalized_config.get(
            normalized_name,
            {},
        )
        mode = config.get("mode", "editable")
        if mode == "hidden":
            continue

        canonical_name = canonical_param_names.get(normalized_name, param_name)
        final_params[canonical_name] = param_value

    for param_name, config in params_config.items():
        if config.get("mode") != "hidden":
            continue

        normalized_name = str(param_name).lower()
        canonical_name = canonical_param_names.get(normalized_name, param_name)
        final_params[canonical_name] = config.get("default_value", "")

    return final_params


def build_job_catalog_payload(instance: JenkinsInstance, jobs: list[JenkinsJobNode]) -> dict:
    return {
        "instance": {
            "id": instance.id,
            "name": instance.name,
            "url": instance.url,
        },
        "jobs": [serialize_job_node(job) for job in jobs],
        "fetched_at": timezone.now().isoformat(),
    }


class JenkinsInstanceViewSet(viewsets.ModelViewSet):
    """ViewSet for JenkinsInstance."""

    queryset = JenkinsInstance.objects.all()
    permission_classes = [HasRequiredFeature]
    required_feature = "admin_jenkins"

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return JenkinsInstanceCreateSerializer
        return JenkinsInstanceSerializer

    @action(detail=False, methods=["post"])
    def validate_connection(self, request):
        """Test Jenkins connection with draft form values before saving."""
        serializer = JenkinsInstanceConnectionTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        token = validated.get("token", "")
        instance_id = validated.get("instance_id")

        if not token and instance_id:
            try:
                existing_instance = JenkinsInstance.objects.get(id=instance_id)
                token = existing_instance.token
            except JenkinsInstance.DoesNotExist:
                return Response(
                    {"message": "Jenkins instance not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        if not token:
            return Response(
                {"message": "token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = build_jenkins_client(
            url=validated["url"],
            username=validated["username"],
            token=token,
        )
        success, message = client.test_connection()

        if success:
            return Response({"message": message})

        return Response(
            {"message": message},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=True, methods=["post"])
    def test_connection(self, request, pk=None):
        """Test Jenkins connection."""
        instance = self.get_object()
        client = get_jenkins_client(instance)
        success, message = client.test_connection()

        if success:
            return Response({"message": message})

        return Response(
            {"message": message},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=True, methods=["get"])
    def jobs(self, request, pk=None):
        """List Jenkins jobs recursively with long-lived cache."""
        instance = self.get_object()
        force_refresh = (
            str(request.query_params.get("force_refresh", "")).lower() == "true"
        )
        cache_key = build_job_catalog_cache_key(instance.id)

        cached_payload = cache.get(cache_key)
        if cached_payload and not force_refresh:
            return Response(
                {
                    **cached_payload,
                    "cached": True,
                    "stale": False,
                }
            )

        client = get_jenkins_client(instance)
        try:
            jobs = client.list_jobs()
            payload = build_job_catalog_payload(instance, jobs)
            cache.set(cache_key, payload, timeout=get_job_catalog_cache_ttl(instance))
            return Response(
                {
                    **payload,
                    "cached": False,
                    "stale": False,
                }
            )
        except Exception as exc:
            logger.error("Failed to list Jenkins jobs: %s", exc)
            if cached_payload:
                return Response(
                    {
                        **cached_payload,
                        "cached": True,
                        "stale": True,
                        "warning": f"刷新 Jenkins Job 列表失败，已返回缓存数据: {exc}",
                    }
                )

            return Response(
                {"message": f"获取 Job 列表失败: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=["post"])
    def fetch_params(self, request, pk=None):
        """Fetch job parameters from Jenkins."""
        instance = self.get_object()
        job_name = request.data.get("job_name")

        if not job_name:
            return Response(
                {"message": "job_name is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = get_jenkins_client(instance)
        try:
            params = client.get_job_params(job_name)
            resolved_params = resolve_param_default_values(client, job_name, params)
            return Response({"params": resolved_params})
        except Exception as exc:
            logger.error("Failed to fetch params: %s", exc)
            return Response(
                {"message": f"获取参数失败: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class TriggerEntryViewSet(viewsets.ModelViewSet):
    """ViewSet for TriggerEntry."""

    queryset = TriggerEntry.objects.all()
    permission_classes = [HasRequiredFeature]
    required_feature = "admin_jenkins"

    def get_permissions(self):
        if self.action == "params":
            self.required_feature = "workspace_jenkins"
        else:
            self.required_feature = "admin_jenkins"
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return TriggerEntryCreateSerializer
        return TriggerEntrySerializer

    @action(detail=True, methods=["get"])
    def params(self, request, pk=None):
        """Get user-visible merged params config for a trigger entry."""
        entry = self.get_object()

        client = get_jenkins_client(entry.instance)
        try:
            jenkins_params = client.get_job_params(entry.job_name)
        except Exception as exc:
            logger.error("Failed to fetch params from Jenkins: %s", exc)
            return Response(
                {"message": f"获取 Jenkins 参数失败: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        params_config = entry.params_config or {}
        merged_params = build_entry_param_payload(
            jenkins_params,
            params_config,
            include_hidden=False,
        )

        return Response(
            {
                "params": merged_params,
            }
        )

    @action(detail=True, methods=["get"])
    def admin_params(self, request, pk=None):
        """Get full merged params config for admin editing, including hidden."""
        entry = self.get_object()

        client = get_jenkins_client(entry.instance)
        try:
            jenkins_params = client.get_job_params(entry.job_name)
        except Exception as exc:
            logger.error("Failed to fetch params from Jenkins: %s", exc)
            return Response(
                {"message": f"获取 Jenkins 参数失败: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        params_config = entry.params_config or {}
        merged_params = build_entry_param_payload(
            jenkins_params,
            params_config,
            include_hidden=True,
        )

        return Response(
            {
                "params": merged_params,
                "config": params_config,
            }
        )


class TriggerRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for TriggerRecord (read-only)."""

    queryset = TriggerRecord.objects.all()
    serializer_class = TriggerRecordSerializer
    permission_classes = [HasRequiredFeature]
    required_feature = "workspace_jenkins"

    def get_queryset(self):
        queryset = super().get_queryset()
        entry_id = self.request.query_params.get("entry_id")
        record_status = self.request.query_params.get("status")
        if entry_id:
            queryset = queryset.filter(entry_id=entry_id)
        if record_status:
            queryset = queryset.filter(status=record_status)
        return queryset

    @action(detail=False, methods=["post"])
    def trigger(self, request):
        """Trigger a build."""
        serializer = TriggerParamsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        entry_id = request.data.get("entry_id")
        if not entry_id:
            return Response(
                {"message": "entry_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            entry = TriggerEntry.objects.get(id=entry_id, is_active=True)
        except TriggerEntry.DoesNotExist:
            return Response(
                {"message": "Trigger entry not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        user_params = serializer.validated_data.get("params", {})
        params_config = entry.params_config or {}
        client = get_jenkins_client(entry.instance)
        try:
            jenkins_params = client.get_job_params(entry.job_name)
            final_params = build_trigger_params(
                user_params=user_params,
                params_config=params_config,
                jenkins_params=jenkins_params,
            )
            trigger_result = client.trigger_build(entry.job_name, final_params)
        except Exception as exc:
            logger.error("Failed to trigger build: %s", exc)
            return Response(
                {"message": f"触发构建失败: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        record = TriggerRecord.objects.create(
            entry=entry,
            user=request.user,
            params=final_params,
            status="pending",
            build_number=trigger_result.build_number,
            queue_url=trigger_result.queue_url,
        )
        if record.build_number:
            record.progress_percent = 0
            record.current_stage = ""
        else:
            apply_queued_progress_to_record(record)
        record.save(
            update_fields=[
                "progress_percent",
                "current_stage",
                "stage_summary",
                "pipeline_supported",
            ]
        )

        return Response(
            {
                "record_id": record.id,
                "build_number": record.build_number,
                "queue_url": record.queue_url,
                "status": record.status,
                "progress_percent": record.progress_percent,
                "current_stage": record.current_stage,
                "stage_summary": record.stage_summary,
                "pipeline_supported": record.pipeline_supported,
                "message": "构建已触发",
            }
        )

    @action(detail=True, methods=["post"])
    def refresh_status(self, request, pk=None):
        """Refresh build status."""
        record = self.get_object()

        if record.status in TERMINAL_RECORD_STATUSES:
            if record.progress_percent != 100:
                apply_terminal_progress_to_record(record)
                record.save(
                    update_fields=[
                        "progress_percent",
                        "current_stage",
                        "stage_summary",
                        "pipeline_supported",
                    ]
                )
            return Response(
                TriggerRecordSerializer(
                    record, context={"request": request}
                ).data
            )

        if not record.build_number and not record.queue_url:
            return Response(
                {"message": "No build number or Jenkins queue URL"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            record = refresh_trigger_record_status(record)
            return Response(
                TriggerRecordSerializer(
                    record, context={"request": request}
                ).data
            )
        except Exception as exc:
            logger.error("Failed to refresh status: %s", exc)
            return Response(
                {"message": f"刷新状态失败: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class UserTriggerEntriesView(APIView):
    """View for users to list their trigger entries."""

    permission_classes = [HasRequiredFeature]
    required_feature = "workspace_jenkins"

    def get(self, request):
        """List active trigger entries for current user."""
        entries = TriggerEntry.objects.filter(is_active=True).select_related("instance")
        return Response(
            [
                {
                    "id": entry.id,
                    "instance": entry.instance_id,
                    "instance_name": entry.instance.name,
                    "name": entry.name,
                    "job_name": entry.job_name,
                    "description": entry.description,
                    "is_active": entry.is_active,
                    "created_at": entry.created_at,
                    "updated_at": entry.updated_at,
                }
                for entry in entries
            ]
        )


class UserNotificationPreferencesView(APIView):
    """Manage per-entry notification channels for the current user."""

    permission_classes = [HasRequiredFeature]
    required_feature = "workspace_jenkins"

    def get(self, request):
        entries = TriggerEntry.objects.filter(is_active=True).select_related("instance")
        preferences = {
            pref.entry_id: pref
            for pref in UserEntryNotificationPreference.objects.filter(user=request.user)
        }
        return Response(
            [
                {
                    "entry_id": entry.id,
                    "entry_name": entry.name,
                    "instance_name": entry.instance.name,
                    "job_name": entry.job_name,
                    "description": entry.description,
                    "notification_channels": {
                        "personal_email": bool(
                            preferences.get(entry.id)
                            and preferences[entry.id].notify_personal_email
                        ),
                        "personal_webhook": bool(
                            preferences.get(entry.id)
                            and preferences[entry.id].notify_personal_webhook
                        ),
                        "group_email": bool(
                            preferences.get(entry.id)
                            and preferences[entry.id].notify_group_email
                        ),
                        "group_webhook": bool(
                            preferences.get(entry.id)
                            and preferences[entry.id].notify_group_webhook
                        ),
                    },
                }
                for entry in entries
            ]
        )

    def put(self, request):
        items = request.data.get("preferences")
        if not isinstance(items, list):
            return Response(
                {"message": "preferences must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_entry_ids = set(
            TriggerEntry.objects.filter(is_active=True).values_list("id", flat=True)
        )
        for item in items:
            entry_id = item.get("entry_id")
            if entry_id not in valid_entry_ids:
                continue
            channels = item.get("notification_channels") or {}
            preference, _ = UserEntryNotificationPreference.objects.get_or_create(
                user=request.user,
                entry_id=entry_id,
            )
            preference.notify_personal_email = bool(channels.get("personal_email"))
            preference.notify_personal_webhook = bool(channels.get("personal_webhook"))
            preference.notify_group_email = bool(channels.get("group_email"))
            preference.notify_group_webhook = bool(channels.get("group_webhook"))
            preference.save()

        return self.get(request)
