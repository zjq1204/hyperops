import logging

from celery import shared_task
from django.utils import timezone

from monitoring_stack.models import AnsibleInstallJob
from monitoring_stack.services.ansible_progress import build_progress
from monitoring_stack.services.core import execute_ansible_job

logger = logging.getLogger(__name__)


@shared_task
def run_ansible_install_job(job_id):
    try:
        execute_ansible_job(job_id)
    except Exception:
        logger.exception("monitoring install job %s failed unexpectedly", job_id)
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
        raise
