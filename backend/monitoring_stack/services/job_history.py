from monitoring_stack.models import AnsibleInstallJob
from monitoring_stack.services.ansible_progress import normalize_progress


FAILED_STATUSES = {"failed", "error", "timeout"}
SUCCESS_STATUSES = {"success", "succeeded", "completed", "done"}


def _duration_seconds(job):
    if not job.started_at or not job.finished_at:
        return None
    return int((job.finished_at - job.started_at).total_seconds())


def _result_status(job, host):
    hostname = str(host.get("hostname") or "")
    for result in job.results or []:
        if str(result.get("hostname") or "") == hostname:
            return str(result.get("status") or job.status).lower()
    return str(job.status or AnsibleInstallJob.STATUS_QUEUED).lower()


def _history_item(job, host):
    progress = normalize_progress(job.progress, job.status)
    return {
        "job_id": job.id,
        "retry_of": job.retry_of_id,
        "component": job.component,
        "job_status": job.status,
        "host_status": _result_status(job, host),
        "duration_seconds": _duration_seconds(job),
        "returncode": job.returncode,
        "reason_code": progress.get("reason_code") or progress.get("message") or "",
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def build_host_job_summaries(jobs):
    summaries = {}
    ordered_jobs = sorted(
        jobs,
        key=lambda job: (job.created_at, job.id),
        reverse=True,
    )
    for job in ordered_jobs:
        seen_host_ids = set()
        for snapshot in job.hosts_snapshot or []:
            host_id = snapshot.get("id")
            if not host_id or host_id in seen_host_ids:
                continue
            seen_host_ids.add(host_id)
            summary = summaries.setdefault(
                host_id,
                {
                    "host_id": host_id,
                    "hostname": snapshot.get("hostname") or f"host-{host_id}",
                    "address": snapshot.get("address") or "",
                    "components": {
                        AnsibleInstallJob.COMPONENT_CATEGRAF: {
                            "latest": None,
                            "attempt_count": 0,
                            "history": [],
                        },
                        AnsibleInstallJob.COMPONENT_BLACKBOX: {
                            "latest": None,
                            "attempt_count": 0,
                            "history": [],
                        },
                    },
                },
            )
            component = summary["components"].setdefault(
                job.component,
                {"latest": None, "attempt_count": 0, "history": []},
            )
            item = _history_item(job, snapshot)
            component["history"].append(item)
            component["attempt_count"] += 1
            if component["latest"] is None:
                component["latest"] = item
    return list(summaries.values())
