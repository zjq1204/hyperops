import logging
import time

from django.utils import timezone

from monitoring_stack.models import AnsibleInstallJob
from monitoring_stack.services.ansible_progress import build_progress

logger = logging.getLogger(__name__)


class JobDispatchError(Exception):
    def __init__(self, job_id):
        super().__init__("installation task dispatch failed")
        self.job_id = job_id


def dispatch_install_job(job):
    started_at = time.monotonic()
    try:
        from monitoring_stack.tasks import run_ansible_install_job

        task = run_ansible_install_job.delay(job.id)
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
        logger.error(
            "组件部署任务发布失败 | job_id=%s component=%s host_count=%s "
            "retry_of=%s user_id=%s error_type=%s duration_ms=%s",
            job.id,
            job.component,
            len(job.host_ids or []),
            job.retry_of_id,
            job.created_by_id,
            type(exc).__name__,
            int((time.monotonic() - started_at) * 1000),
        )
        raise JobDispatchError(job.id) from exc
    logger.info(
        "已发布组件部署任务 | job_id=%s component=%s host_count=%s "
        "retry_of=%s user_id=%s celery_task_id=%s duration_ms=%s",
        job.id,
        job.component,
        len(job.host_ids or []),
        job.retry_of_id,
        job.created_by_id,
        task.id,
        int((time.monotonic() - started_at) * 1000),
    )
    return task


def dispatch_error_response(error):
    return {
        "detail": "installation task dispatch failed",
        "code": "MONITORING_JOB_DISPATCH_FAILED",
        "job_id": error.job_id,
    }
