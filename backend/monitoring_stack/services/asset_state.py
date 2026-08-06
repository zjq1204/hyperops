from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime


SSH_VERIFICATION_MAX_AGE = timedelta(hours=24)
COMPONENT_WORK_STATES = {
    "pending_deployment",
    "deployment_failed",
    "abnormal",
    "unknown",
}


def host_roles(host):
    roles = ["collection_host"]
    if any(node.enabled for node in host.blackbox_probe_nodes.all()):
        roles.append("probe_node")
    return roles


def normalize_component_state(rows, component, *, required=True):
    if not required:
        return {
            "code": "not_applicable",
            "component": component,
            "job_id": None,
            "reason": "",
            "installation_status": "not_applicable",
            "runtime_status": "not_applicable",
        }
    row = next((item for item in rows if item.get("component") == component), None)
    if not row:
        return {
            "code": "pending_deployment",
            "component": component,
            "job_id": None,
            "reason": "",
            "installation_status": "not_installed",
            "runtime_status": "not_applicable",
        }

    install_status = str(row.get("status") or "unknown").lower()
    runtime_status = str(row.get("runtime_status") or "unknown").lower()
    common = {
        "component": component,
        "job_id": row.get("last_job_id"),
        "reason": row.get("runtime_reason") or row.get("last_error") or "",
    }
    if install_status == "installing":
        return {
            **common,
            "code": "deploying",
            "installation_status": "installing",
            "runtime_status": "not_applicable",
        }
    if install_status == "failed":
        return {
            **common,
            "code": "deployment_failed",
            "installation_status": "failed",
            "runtime_status": "not_applicable",
        }
    if install_status == "unknown":
        return {
            **common,
            "code": "pending_deployment",
            "installation_status": "unknown",
            "runtime_status": "not_applicable",
        }
    if install_status not in {"success", "external"}:
        return {
            **common,
            "code": "unknown",
            "installation_status": "unknown",
            "runtime_status": "not_applicable",
        }
    if runtime_status == "online":
        return {
            **common,
            "code": "healthy",
            "installation_status": "installed",
            "runtime_status": "online",
        }
    if runtime_status == "abnormal":
        return {
            **common,
            "code": "abnormal",
            "installation_status": "installed",
            "runtime_status": "abnormal",
        }
    return {
        **common,
        "code": "unknown",
        "installation_status": "installed",
        "runtime_status": "unknown",
    }


def _checked_at(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = parse_datetime(value)
    if value and timezone.is_naive(value):
        value = timezone.make_aware(value)
    return value


def ssh_verification_required(ssh_state, *, now=None):
    if not ssh_state.get("matches_current_settings", False):
        return True
    if ssh_state.get("status") != "verified":
        return True
    checked_at = _checked_at(ssh_state.get("checked_at"))
    if checked_at is None:
        return True
    return (now or timezone.now()) - checked_at > SSH_VERIFICATION_MAX_AGE


def choose_next_action(
    *, collection_state, probe_state, ssh_state, now=None
):
    expected = [collection_state]
    if probe_state.get("code") != "not_applicable":
        expected.append(probe_state)

    deploying = next(
        (item for item in expected if item.get("code") == "deploying"), None
    )
    if deploying:
        return {
            "code": "deployment_in_progress",
            "component": deploying.get("component", ""),
            "job_id": deploying.get("job_id"),
        }

    blocked_component = next(
        (item for item in expected if item.get("code") in COMPONENT_WORK_STATES),
        None,
    )
    effective_ssh_status = (
        ssh_state.get("status")
        if ssh_state.get("matches_current_settings", False)
        else "unverified"
    )
    if blocked_component and effective_ssh_status == "failed":
        return {
            "code": "fix_ssh",
            "component": blocked_component.get("component", ""),
            "job_id": None,
        }
    if blocked_component and ssh_verification_required(ssh_state, now=now):
        return {
            "code": "verify_ssh",
            "component": blocked_component.get("component", ""),
            "job_id": None,
        }

    deployment_failure = next(
        (item for item in expected if item.get("code") == "deployment_failed"),
        None,
    )
    if deployment_failure:
        return {
            "code": "review_deployment_failure",
            "component": deployment_failure.get("component", ""),
            "job_id": deployment_failure.get("job_id"),
        }
    if collection_state.get("code") == "pending_deployment":
        return {"code": "deploy_categraf", "component": "categraf", "job_id": None}
    if probe_state.get("code") == "pending_deployment":
        return {"code": "deploy_blackbox", "component": "blackbox", "job_id": None}
    if collection_state.get("code") == "abnormal":
        return {
            "code": "inspect_collection",
            "component": "categraf",
            "job_id": collection_state.get("job_id"),
        }
    if probe_state.get("code") == "abnormal":
        return {
            "code": "inspect_probe",
            "component": "blackbox",
            "job_id": probe_state.get("job_id"),
        }
    if any(item.get("code") == "unknown" for item in expected):
        return {"code": "status_unconfirmed", "component": "", "job_id": None}
    return {"code": "running_normally", "component": "", "job_id": None}
