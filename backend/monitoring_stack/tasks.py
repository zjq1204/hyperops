from celery import shared_task
from monitoring_stack.services.core import execute_ansible_job


@shared_task
def run_ansible_install_job(job_id):
    execute_ansible_job(job_id)
