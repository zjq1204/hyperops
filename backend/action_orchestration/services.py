from __future__ import annotations

import re
import time
from types import SimpleNamespace
from typing import Any

from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone

from action_orchestration.models import ActionRun, ActionStep, ActionStepRun, ActionTemplate
from gitlab_resource.models import GitLabBranch, GitLabTag, GitLabWebhook, RegisteredProject
from gitlab_resource.views import get_gitlab_client
from jenkins_trigger.models import TriggerEntry, TriggerRecord
from jenkins_trigger.views import (
    build_trigger_params,
    get_jenkins_client,
    refresh_trigger_record_status,
)

PARAM_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
TERMINAL_JENKINS_STATUSES = {"success", "failure", "aborted"}
DEFAULT_JENKINS_POLL_INTERVAL_SECONDS = 15
DEFAULT_JENKINS_TIMEOUT_SECONDS = 120 * 60
CONDITION_OPERATORS = {"equals", "not_equals", "contains", "is_empty", "is_not_empty"}


class ActionExecutionError(Exception):
    """Raised when an action step fails."""


def render_template_value(value: Any, params: dict[str, Any]):
    """Render ${param_name} placeholders in strings, lists and dicts."""
    if isinstance(value, str):
        def replace(match):
            replacement = params.get(match.group(1), "")
            return "" if replacement is None else str(replacement)

        return PARAM_PATTERN.sub(replace, value)
    if isinstance(value, list):
        return [render_template_value(item, params) for item in value]
    if isinstance(value, dict):
        return {
            key: render_template_value(item, params)
            for key, item in value.items()
        }
    return value


def can_user_access_template(user, template: ActionTemplate) -> bool:
    """Return whether user may execute or view a workspace template."""
    if not user or not user.is_authenticated or not template.is_active:
        return False
    if getattr(user, "is_staff", False):
        return True
    if template.scope == ActionTemplate.SCOPE_PERSONAL:
        return template.owner_id == user.id
    if template.visible_users.filter(id=user.id).exists():
        return True
    user_group_ids = list(user.groups.values_list("id", flat=True))
    return template.visible_groups.filter(id__in=user_group_ids).exists()


def can_user_approve_step(user, step_run: ActionStepRun) -> bool:
    """Return whether user may approve or reject a manual approval step."""
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_staff", False):
        return True
    config = _active_nested_approval_config(step_run)
    if config is None:
        config = step_run.resolved_config or step_run.step.config or {}
    approver_user_ids = {int(item) for item in config.get("approver_user_ids", [])}
    if user.id in approver_user_ids:
        return True
    approver_group_ids = {int(item) for item in config.get("approver_group_ids", [])}
    if not approver_group_ids:
        return False
    return user.groups.filter(id__in=approver_group_ids).exists()


@transaction.atomic
def create_action_run(template: ActionTemplate, user, input_params: dict[str, Any]):
    """Create a queued action run."""
    run = ActionRun.objects.create(
        template=template,
        triggered_by=user,
        input_params=input_params or {},
        status=ActionRun.STATUS_QUEUED,
    )
    _snapshot_run_steps(run)
    return run


def _snapshot_run_steps(run: ActionRun):
    """Freeze the template steps that this run should execute."""
    steps = (
        run.template.steps
        .filter(is_archived=False)
        .order_by("order", "id")
    )
    for step in steps:
        ActionStepRun.objects.get_or_create(run=run, step=step)


def _create_step_run(run: ActionRun, step: ActionStep):
    step_run, _ = ActionStepRun.objects.get_or_create(run=run, step=step)
    return step_run


def _finish_run(run: ActionRun, status: str, error_message: str = ""):
    run.status = status
    run.error_message = error_message or run.error_message
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "error_message", "finished_at", "updated_at"])


def _mark_step_success(step_run: ActionStepRun, output: dict[str, Any] | None = None):
    step_run.status = ActionStepRun.STATUS_SUCCESS
    step_run.output = output or step_run.output or {}
    step_run.finished_at = timezone.now()
    step_run.save(update_fields=["status", "output", "finished_at", "updated_at"])


def _mark_step_failed(step_run: ActionStepRun, error: Exception):
    step_run.status = ActionStepRun.STATUS_FAILED
    step_run.error_message = str(error)
    step_run.finished_at = timezone.now()
    step_run.save(update_fields=["status", "error_message", "finished_at", "updated_at"])


def _mark_step_skipped(step_run: ActionStepRun, output: dict[str, Any] | None = None):
    step_run.status = ActionStepRun.STATUS_SKIPPED
    step_run.output = output or {}
    step_run.finished_at = timezone.now()
    step_run.save(update_fields=["status", "output", "finished_at", "updated_at"])


def _execute_jenkins_step(run: ActionRun, step: ActionStep, step_run: ActionStepRun):
    config = step_run.resolved_config
    entry_id = config.get("entry_id")
    if not entry_id:
        raise ActionExecutionError("Jenkins entry_id is required")
    try:
        entry = TriggerEntry.objects.select_related("instance").get(id=entry_id, is_active=True)
    except TriggerEntry.DoesNotExist as exc:
        raise ActionExecutionError("Jenkins trigger entry not found") from exc

    client = get_jenkins_client(entry.instance)
    record = step_run.jenkins_record
    if not record:
        user_params = config.get("params") or {}
        jenkins_params = client.get_job_params(entry.job_name)
        final_params = build_trigger_params(
            user_params=user_params,
            params_config=entry.params_config or {},
            jenkins_params=jenkins_params,
        )
        trigger_result = client.trigger_build(entry.job_name, final_params)
        record = TriggerRecord.objects.create(
            entry=entry,
            user=run.triggered_by,
            params=final_params,
            status="pending",
            build_number=trigger_result.build_number,
            queue_url=trigger_result.queue_url,
        )
        step_run.jenkins_record = record
        step_run.save(update_fields=["jenkins_record", "updated_at"])

    if not bool(config.get("wait_for_completion", False)):
        return {
            "record_id": record.id,
            "build_number": record.build_number,
            "queue_url": record.queue_url,
            "waited": False,
        }

    poll_interval = int(config.get("poll_interval_seconds") or DEFAULT_JENKINS_POLL_INTERVAL_SECONDS)
    timeout_seconds = int(config.get("timeout_seconds") or DEFAULT_JENKINS_TIMEOUT_SECONDS)
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        record.refresh_from_db()
        record = refresh_trigger_record_status(record)
        if record.status in TERMINAL_JENKINS_STATUSES:
            break
        time.sleep(poll_interval)

    record.refresh_from_db()
    if record.status != "success":
        raise ActionExecutionError(f"Jenkins build ended with status {record.status}")
    return {
        "record_id": record.id,
        "build_number": record.build_number,
        "status": record.status,
        "waited": True,
    }


def _resolve_project_ids(config: dict[str, Any], input_params: dict[str, Any]):
    project_ids = list(config.get("project_ids") or [])
    if config.get("allow_runtime_project_selection"):
        project_ids.extend(input_params.get("project_ids") or [])
    return list(dict.fromkeys(int(item) for item in project_ids if str(item).strip()))


def _get_gitlab_projects(project_ids: list[int], target_key: str, target_value: str):
    projects = list(
        RegisteredProject.objects
        .select_related("instance")
        .filter(id__in=project_ids)
    )
    found_ids = {project.id for project in projects}
    errors = [
        {
            "project_id": project_id,
            target_key: target_value,
            "error": "Project not found",
        }
        for project_id in project_ids
        if project_id not in found_ids
    ]
    return projects, errors


def _build_gitlab_output(results: list[dict[str, Any]], errors: list[dict[str, Any]], label: str):
    if errors and not results:
        raise ActionExecutionError(f"GitLab {label} failed: {errors[0]['error']}")
    return {
        "succeeded": results,
        "errors": errors,
        "success_count": len(results),
        "error_count": len(errors),
    }


def _execute_gitlab_branch_operation_step(run: ActionRun, step_run: ActionStepRun):
    config = step_run.resolved_config
    operation = config.get("operation") or "create"
    if operation not in {"create", "protect", "unprotect"}:
        raise ActionExecutionError("GitLab branch operation must be create, protect or unprotect")

    project_ids = _resolve_project_ids(config, run.input_params or {})
    branch_name = (config.get("branch_name") or "").strip()
    ref = (config.get("ref") or "main").strip() or "main"
    if not project_ids or not branch_name:
        raise ActionExecutionError("project_ids and branch_name are required")

    projects, errors = _get_gitlab_projects(project_ids, "branch", branch_name)
    results = []
    for project in projects:
        try:
            client = get_gitlab_client(project.instance)
            if operation == "create":
                branch = client.create_branch(project.gitlab_id, branch_name, ref)
                GitLabBranch.objects.update_or_create(
                    project=project,
                    name=branch.name,
                    defaults={
                        "protected": branch.protected,
                        "last_commit_sha": branch.commit_sha,
                        "last_commit_date": branch.commit_date,
                    },
                )
                result_branch_name = branch.name
            elif operation == "protect":
                client.protect_branch(project.gitlab_id, branch_name)
                GitLabBranch.objects.filter(project=project, name=branch_name).update(protected=True)
                result_branch_name = branch_name
            else:
                client.unprotect_branch(project.gitlab_id, branch_name)
                GitLabBranch.objects.filter(project=project, name=branch_name).update(protected=False)
                result_branch_name = branch_name

            results.append({
                "project_id": project.id,
                "project": project.path,
                "branch": result_branch_name,
                "operation": operation,
            })
        except Exception as exc:
            errors.append({
                "project_id": project.id,
                "project": project.path,
                "branch": branch_name,
                "operation": operation,
                "error": str(exc),
            })

    return _build_gitlab_output(results, errors, f"branch {operation}")


def _execute_gitlab_branch_create_step(run: ActionRun, step_run: ActionStepRun):
    step_run.resolved_config = {
        **(step_run.resolved_config or {}),
        "operation": "create",
    }
    return _execute_gitlab_branch_operation_step(run, step_run)


def _execute_gitlab_tag_operation_step(run: ActionRun, step_run: ActionStepRun):
    config = step_run.resolved_config
    operation = config.get("operation") or "create"
    if operation != "create":
        raise ActionExecutionError("GitLab tag operation must be create")

    project_ids = _resolve_project_ids(config, run.input_params or {})
    tag_name = (config.get("tag_name") or "").strip()
    ref = (config.get("ref") or "main").strip() or "main"
    if not project_ids or not tag_name:
        raise ActionExecutionError("project_ids and tag_name are required")

    projects, errors = _get_gitlab_projects(project_ids, "tag", tag_name)
    results = []
    for project in projects:
        try:
            client = get_gitlab_client(project.instance)
            tag = client.create_tag(project.gitlab_id, tag_name, ref)
            GitLabTag.objects.update_or_create(
                project=project,
                name=tag.name,
                defaults={
                    "commit_sha": tag.commit_sha,
                    "released_at": tag.released_at,
                },
            )
            results.append({
                "project_id": project.id,
                "project": project.path,
                "tag": tag.name,
                "operation": operation,
            })
        except Exception as exc:
            errors.append({
                "project_id": project.id,
                "project": project.path,
                "tag": tag_name,
                "operation": operation,
                "error": str(exc),
            })

    return _build_gitlab_output(results, errors, "tag create")


def _execute_gitlab_webhook_operation_step(run: ActionRun, step_run: ActionStepRun):
    config = step_run.resolved_config
    operation = config.get("operation") or "create"
    if operation != "create":
        raise ActionExecutionError("GitLab webhook operation must be create")

    project_ids = _resolve_project_ids(config, run.input_params or {})
    url = (config.get("url") or "").strip()
    if not project_ids or not url:
        raise ActionExecutionError("project_ids and url are required")

    projects, errors = _get_gitlab_projects(project_ids, "webhook", url)
    results = []
    for project in projects:
        try:
            client = get_gitlab_client(project.instance)
            webhook = client.create_webhook(
                project_id=project.gitlab_id,
                url=url,
                push_events=bool(config.get("push_events", True)),
                tag_push_events=bool(config.get("tag_push_events", False)),
                merge_requests_events=bool(config.get("merge_requests_events", False)),
                enable_ssl_verification=bool(config.get("enable_ssl_verification", True)),
                push_events_branch_filter=(config.get("push_events_branch_filter") or None),
            )
            GitLabWebhook.objects.create(
                project=project,
                webhook_id=webhook.id,
                url=webhook.url,
                push_events=webhook.push_events,
                tag_push_events=webhook.tag_push_events,
                merge_requests_events=webhook.merge_requests_events,
                enable_ssl_verification=webhook.enable_ssl_verification,
            )
            results.append({
                "project_id": project.id,
                "project": project.path,
                "webhook_id": webhook.id,
                "url": webhook.url,
                "operation": operation,
            })
        except Exception as exc:
            errors.append({
                "project_id": project.id,
                "project": project.path,
                "webhook": url,
                "operation": operation,
                "error": str(exc),
            })

    return _build_gitlab_output(results, errors, "webhook create")


def _execute_manual_approval_step(run: ActionRun, step: ActionStep, step_run: ActionStepRun):
    step_run.status = ActionStepRun.STATUS_WAITING_APPROVAL
    step_run.output = {
        "message": step_run.resolved_config.get("message", ""),
        "approver_user_ids": step_run.resolved_config.get("approver_user_ids", []),
        "approver_group_ids": step_run.resolved_config.get("approver_group_ids", []),
    }
    step_run.save(update_fields=["status", "output", "updated_at"])
    run.status = ActionRun.STATUS_WAITING_APPROVAL
    run.current_step = step
    run.save(update_fields=["status", "current_step", "updated_at"])


def _normalize_condition_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _condition_matches(condition: dict[str, Any], input_params: dict[str, Any]) -> bool:
    param = condition.get("param")
    operator = condition.get("operator") or "equals"
    if operator not in CONDITION_OPERATORS:
        raise ActionExecutionError(f"Unsupported branch condition operator {operator}")

    actual = _normalize_condition_value(input_params.get(param))
    expected = _normalize_condition_value(condition.get("value"))

    if operator == "equals":
        return actual == expected
    if operator == "not_equals":
        return actual != expected
    if operator == "contains":
        return expected in actual
    if operator == "is_empty":
        return actual == ""
    if operator == "is_not_empty":
        return actual != ""
    return False


def _select_branch(config: dict[str, Any], input_params: dict[str, Any]):
    for branch in config.get("branches") or []:
        if _condition_matches(branch.get("condition") or {}, input_params):
            return branch
    return None


def _initial_nested_step_state(index: int, nested_step: dict[str, Any]):
    return {
        "index": index,
        "name": nested_step.get("name") or f"Branch step {index}",
        "action_type": nested_step.get("action_type"),
        "failure_policy": nested_step.get("failure_policy") or ActionStep.FAILURE_STOP,
        "status": ActionStepRun.STATUS_PENDING,
        "resolved_config": nested_step.get("config") or {},
        "output": {},
        "error_message": "",
    }


def _initialize_branch_output(branch: dict[str, Any]):
    return {
        "matched": True,
        "branch_id": branch.get("id") or "",
        "branch_label": branch.get("label") or "",
        "nested_steps": [
            _initial_nested_step_state(index, nested_step)
            for index, nested_step in enumerate(branch.get("steps") or [], start=1)
        ],
    }


def _active_nested_approval_config(step_run: ActionStepRun):
    if step_run.step.action_type != ActionStep.TYPE_CONDITIONAL_BRANCH:
        return None
    output = step_run.output or {}
    for nested_step in output.get("nested_steps") or []:
        if (
            nested_step.get("action_type") == ActionStep.TYPE_MANUAL_APPROVAL
            and nested_step.get("status") == ActionStepRun.STATUS_WAITING_APPROVAL
        ):
            return nested_step.get("resolved_config") or {}
    return None


def _run_jenkins_config(run: ActionRun, config: dict[str, Any]):
    entry_id = config.get("entry_id")
    if not entry_id:
        raise ActionExecutionError("Jenkins entry_id is required")
    try:
        entry = TriggerEntry.objects.select_related("instance").get(id=entry_id, is_active=True)
    except TriggerEntry.DoesNotExist as exc:
        raise ActionExecutionError("Jenkins trigger entry not found") from exc

    client = get_jenkins_client(entry.instance)
    user_params = config.get("params") or {}
    jenkins_params = client.get_job_params(entry.job_name)
    final_params = build_trigger_params(
        user_params=user_params,
        params_config=entry.params_config or {},
        jenkins_params=jenkins_params,
    )
    trigger_result = client.trigger_build(entry.job_name, final_params)
    record = TriggerRecord.objects.create(
        entry=entry,
        user=run.triggered_by,
        params=final_params,
        status="pending",
        build_number=trigger_result.build_number,
        queue_url=trigger_result.queue_url,
    )

    if not bool(config.get("wait_for_completion", False)):
        return {
            "record_id": record.id,
            "build_number": record.build_number,
            "queue_url": record.queue_url,
            "waited": False,
        }

    poll_interval = int(config.get("poll_interval_seconds") or DEFAULT_JENKINS_POLL_INTERVAL_SECONDS)
    timeout_seconds = int(config.get("timeout_seconds") or DEFAULT_JENKINS_TIMEOUT_SECONDS)
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        record.refresh_from_db()
        record = refresh_trigger_record_status(record)
        if record.status in TERMINAL_JENKINS_STATUSES:
            break
        time.sleep(poll_interval)

    record.refresh_from_db()
    if record.status != "success":
        raise ActionExecutionError(f"Jenkins build ended with status {record.status}")
    return {
        "record_id": record.id,
        "build_number": record.build_number,
        "status": record.status,
        "waited": True,
    }


def _execute_nested_action(run: ActionRun, parent_step: ActionStep, parent_run: ActionStepRun, nested_step: dict[str, Any]):
    nested_step["status"] = ActionStepRun.STATUS_RUNNING
    nested_step["error_message"] = ""
    parent_run.output = parent_run.output or {}
    parent_run.save(update_fields=["output", "updated_at"])

    action_type = nested_step.get("action_type")
    config = nested_step.get("resolved_config") or {}
    if action_type == ActionStep.TYPE_MANUAL_APPROVAL:
        nested_step["status"] = ActionStepRun.STATUS_WAITING_APPROVAL
        nested_step["output"] = {
            "message": config.get("message", ""),
            "approver_user_ids": config.get("approver_user_ids", []),
            "approver_group_ids": config.get("approver_group_ids", []),
        }
        parent_run.status = ActionStepRun.STATUS_WAITING_APPROVAL
        parent_run.output = parent_run.output
        parent_run.save(update_fields=["status", "output", "updated_at"])
        run.status = ActionRun.STATUS_WAITING_APPROVAL
        run.current_step = parent_step
        run.save(update_fields=["status", "current_step", "updated_at"])
        return "paused"

    if action_type == ActionStep.TYPE_JENKINS_TRIGGER:
        output = _run_jenkins_config(run, config)
    elif action_type == ActionStep.TYPE_GITLAB_BRANCH_CREATE:
        output = _execute_gitlab_branch_create_step(
            run,
            SimpleNamespace(resolved_config=config),
        )
    elif action_type == ActionStep.TYPE_GITLAB_BRANCH_OPERATION:
        output = _execute_gitlab_branch_operation_step(
            run,
            SimpleNamespace(resolved_config=config),
        )
    elif action_type == ActionStep.TYPE_GITLAB_TAG_OPERATION:
        output = _execute_gitlab_tag_operation_step(
            run,
            SimpleNamespace(resolved_config=config),
        )
    elif action_type == ActionStep.TYPE_GITLAB_WEBHOOK_OPERATION:
        output = _execute_gitlab_webhook_operation_step(
            run,
            SimpleNamespace(resolved_config=config),
        )
    else:
        raise ActionExecutionError(f"Unsupported nested action type {action_type}")

    nested_step["status"] = ActionStepRun.STATUS_SUCCESS
    nested_step["output"] = output or {}
    parent_run.output = parent_run.output
    parent_run.save(update_fields=["output", "updated_at"])
    return "completed"


def _execute_conditional_branch_step(run: ActionRun, step: ActionStep, step_run: ActionStepRun):
    config = step_run.resolved_config or {}
    output = step_run.output or {}
    if not output.get("matched"):
        branch = _select_branch(config, run.input_params or {})
        if not branch:
            _mark_step_skipped(
                step_run,
                {"matched": False, "reason": "no_condition_matched"},
            )
            return "completed"
        output = _initialize_branch_output(branch)
        step_run.output = output
        step_run.save(update_fields=["output", "updated_at"])

    for nested_step in output.get("nested_steps") or []:
        if nested_step.get("status") in {
            ActionStepRun.STATUS_SUCCESS,
            ActionStepRun.STATUS_SKIPPED,
        }:
            continue
        if nested_step.get("status") == ActionStepRun.STATUS_WAITING_APPROVAL:
            return "paused"

        try:
            result = _execute_nested_action(run, step, step_run, nested_step)
            step_run.output = output
            step_run.save(update_fields=["output", "updated_at"])
            if result == "paused":
                return "paused"
        except Exception as exc:
            nested_step["status"] = ActionStepRun.STATUS_FAILED
            nested_step["error_message"] = str(exc)
            step_run.output = output
            step_run.save(update_fields=["output", "updated_at"])
            if nested_step.get("failure_policy") != ActionStep.FAILURE_CONTINUE:
                raise

    return output


def _execute_step(run: ActionRun, step: ActionStep):
    step_run = _create_step_run(run, step)
    step_run.status = ActionStepRun.STATUS_RUNNING
    step_run.resolved_config = render_template_value(step.config or {}, run.input_params or {})
    step_run.error_message = ""
    step_run.started_at = step_run.started_at or timezone.now()
    step_run.save(update_fields=[
        "status",
        "resolved_config",
        "error_message",
        "started_at",
        "updated_at",
    ])

    if step.action_type == ActionStep.TYPE_MANUAL_APPROVAL:
        _execute_manual_approval_step(run, step, step_run)
        return "paused"
    if step.action_type == ActionStep.TYPE_JENKINS_TRIGGER:
        output = _execute_jenkins_step(run, step, step_run)
    elif step.action_type == ActionStep.TYPE_CONDITIONAL_BRANCH:
        output = _execute_conditional_branch_step(run, step, step_run)
        if output == "paused":
            return "paused"
        if output == "completed" and step_run.status == ActionStepRun.STATUS_SKIPPED:
            return "completed"
    elif step.action_type == ActionStep.TYPE_GITLAB_BRANCH_CREATE:
        output = _execute_gitlab_branch_create_step(run, step_run)
    elif step.action_type == ActionStep.TYPE_GITLAB_BRANCH_OPERATION:
        output = _execute_gitlab_branch_operation_step(run, step_run)
    elif step.action_type == ActionStep.TYPE_GITLAB_TAG_OPERATION:
        output = _execute_gitlab_tag_operation_step(run, step_run)
    elif step.action_type == ActionStep.TYPE_GITLAB_WEBHOOK_OPERATION:
        output = _execute_gitlab_webhook_operation_step(run, step_run)
    else:
        raise ActionExecutionError(f"Unsupported action type {step.action_type}")

    _mark_step_success(step_run, output)
    return "completed"


@transaction.atomic
def _start_run_if_needed(run: ActionRun):
    if run.status == ActionRun.STATUS_QUEUED:
        run.status = ActionRun.STATUS_RUNNING
        run.started_at = timezone.now()
        run.save(update_fields=["status", "started_at", "updated_at"])


def execute_action_run(run_id: int):
    """Execute a run until complete, failed, or waiting for approval."""
    run = (
        ActionRun.objects
        .select_related("template", "triggered_by")
        .get(id=run_id)
    )
    if run.status in {
        ActionRun.STATUS_SUCCESS,
        ActionRun.STATUS_FAILED,
        ActionRun.STATUS_REJECTED,
        ActionRun.STATUS_WAITING_APPROVAL,
    }:
        return run

    _start_run_if_needed(run)
    if not run.step_runs.exists():
        _snapshot_run_steps(run)
    step_runs = list(
        run.step_runs
        .select_related("step")
        .order_by("step__order", "id")
    )

    for existing in step_runs:
        step = existing.step
        if existing.status in {
            ActionStepRun.STATUS_SUCCESS,
            ActionStepRun.STATUS_SKIPPED,
        }:
            continue
        if existing.status == ActionStepRun.STATUS_REJECTED:
            _finish_run(run, ActionRun.STATUS_REJECTED, existing.error_message)
            return run

        run.current_step = step
        run.status = ActionRun.STATUS_RUNNING
        run.save(update_fields=["current_step", "status", "updated_at"])

        try:
            result = _execute_step(run, step)
            if result == "paused":
                return run
        except Exception as exc:
            step_run = _create_step_run(run, step)
            _mark_step_failed(step_run, exc)
            if step.failure_policy != ActionStep.FAILURE_CONTINUE:
                _finish_run(run, ActionRun.STATUS_FAILED, str(exc))
                return run

    run.current_step = None
    run.status = ActionRun.STATUS_SUCCESS
    run.finished_at = timezone.now()
    run.save(update_fields=["current_step", "status", "finished_at", "updated_at"])
    return run


def _approve_nested_action_step(step_run: ActionStepRun, user, comment: str = ""):
    output = step_run.output or {}
    for nested_step in output.get("nested_steps") or []:
        if nested_step.get("status") != ActionStepRun.STATUS_WAITING_APPROVAL:
            continue
        nested_step["status"] = ActionStepRun.STATUS_SUCCESS
        nested_step["output"] = {
            "approved": True,
            "comment": comment or "",
        }
        nested_step["approved_by"] = user.id
        nested_step["approved_by_name"] = getattr(user, "username", "")
        nested_step["approval_comment"] = comment or ""
        step_run.status = ActionStepRun.STATUS_RUNNING
        step_run.output = output
        step_run.save(update_fields=["status", "output", "updated_at"])
        return
    raise ActionExecutionError("Conditional branch is not waiting for approval")


def _reject_nested_action_step(step_run: ActionStepRun, user, comment: str = ""):
    output = step_run.output or {}
    for nested_step in output.get("nested_steps") or []:
        if nested_step.get("status") != ActionStepRun.STATUS_WAITING_APPROVAL:
            continue
        nested_step["status"] = ActionStepRun.STATUS_REJECTED
        nested_step["approved_by"] = user.id
        nested_step["approved_by_name"] = getattr(user, "username", "")
        nested_step["approval_comment"] = comment or ""
        nested_step["error_message"] = comment or "Rejected"
        step_run.status = ActionStepRun.STATUS_REJECTED
        step_run.error_message = nested_step["error_message"]
        step_run.output = output
        step_run.finished_at = timezone.now()
        step_run.save(update_fields=[
            "status",
            "error_message",
            "output",
            "finished_at",
            "updated_at",
        ])
        return
    raise ActionExecutionError("Conditional branch is not waiting for approval")


def approve_action_run(run: ActionRun, user, comment: str = ""):
    """Approve the current manual step and queue the run for execution."""
    if run.status != ActionRun.STATUS_WAITING_APPROVAL or not run.current_step_id:
        raise ActionExecutionError("Run is not waiting for approval")
    step_run = run.step_runs.get(step=run.current_step)
    if not can_user_approve_step(user, step_run):
        raise PermissionError("You are not allowed to approve this step")
    if run.current_step.action_type == ActionStep.TYPE_CONDITIONAL_BRANCH:
        _approve_nested_action_step(step_run, user, comment)
        run.status = ActionRun.STATUS_QUEUED
        run.save(update_fields=["status", "updated_at"])
        return run
    _mark_step_success(step_run, {"approved": True, "comment": comment or ""})
    step_run.approved_by = user
    step_run.approval_comment = comment or ""
    step_run.save(update_fields=["approved_by", "approval_comment", "updated_at"])
    run.status = ActionRun.STATUS_QUEUED
    run.save(update_fields=["status", "updated_at"])
    return run


def reject_action_run(run: ActionRun, user, comment: str = ""):
    """Reject the current manual step and finish the run as rejected."""
    if run.status != ActionRun.STATUS_WAITING_APPROVAL or not run.current_step_id:
        raise ActionExecutionError("Run is not waiting for approval")
    step_run = run.step_runs.get(step=run.current_step)
    if not can_user_approve_step(user, step_run):
        raise PermissionError("You are not allowed to reject this step")
    if run.current_step.action_type == ActionStep.TYPE_CONDITIONAL_BRANCH:
        _reject_nested_action_step(step_run, user, comment)
        _finish_run(run, ActionRun.STATUS_REJECTED, comment or "Rejected")
        return run
    step_run.status = ActionStepRun.STATUS_REJECTED
    step_run.approved_by = user
    step_run.approval_comment = comment or ""
    step_run.error_message = comment or "Rejected"
    step_run.finished_at = timezone.now()
    step_run.save(update_fields=[
        "status",
        "approved_by",
        "approval_comment",
        "error_message",
        "finished_at",
        "updated_at",
    ])
    _finish_run(run, ActionRun.STATUS_REJECTED, step_run.error_message)
    return run
