from django.utils import timezone

from monitoring_stack.models import AnsibleInstallJob
from monitoring_stack.services.ansible_progress import build_progress


class JobDispatchError(Exception):
    def __init__(self, job_id):
        super().__init__("installation task dispatch failed")
        self.job_id = job_id


def dispatch_install_job(job):
    try:
        from monitoring_stack.tasks import run_ansible_install_job

        run_ansible_install_job.delay(job.id)
    except Exception as exc:
        job.status = AnsibleInstallJob.STATUS_FAILED
        job.returncode = 1
        job.logs = ["installation task dispatch failed"]
        job.progress = build_progress("failed", message="dispatch_failed")
        job.finished_at = timezone.now()
        job.save(
            update_fields=[
                "status",
                "returncode",
                "logs",
                "progress",
                "finished_at",
            ]
        )
        raise JobDispatchError(job.id) from exc


def dispatch_error_response(error):
    return {
        "detail": "installation task dispatch failed",
        "code": "MONITORING_JOB_DISPATCH_FAILED",
        "job_id": error.job_id,
    }
