import logging
import time

from celery import shared_task
from django.utils import timezone

from monitoring_stack.models import AnsibleInstallJob
from monitoring_stack.services.ansible_progress import build_progress
from monitoring_stack.services.core import execute_ansible_job

logger = logging.getLogger(__name__)


@shared_task
def run_ansible_install_job(job_id):
    started_at = time.monotonic()
    logger.info("组件部署开始执行 | job_id=%s", job_id)
    try:
        job = execute_ansible_job(job_id)
    except Exception as exc:
        job = AnsibleInstallJob.objects.filter(pk=job_id).first()
        if job:
            job.status = AnsibleInstallJob.STATUS_FAILED
            job.returncode = 1
            job.logs = [*(job.logs or []), "worker execution failed"]
            job.progress = build_progress("failed", message="worker_failed")
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
            "组件部署执行异常 | job_id=%s error_type=%s duration_ms=%s",
            job_id,
            type(exc).__name__,
            int((time.monotonic() - started_at) * 1000),
        )
        raise
    reason_code = (job.progress or {}).get("reason_code", "")
    log_method = (
        logger.error
        if job.status == AnsibleInstallJob.STATUS_FAILED
        else logger.info
    )
    log_method(
        "组件部署执行完成 | job_id=%s component=%s host_count=%s status=%s "
        "returncode=%s reason_code=%s duration_ms=%s",
        job.id,
        job.component,
        len(job.host_ids or []),
        job.status,
        job.returncode,
        reason_code,
        int((time.monotonic() - started_at) * 1000),
    )
    return job.id
