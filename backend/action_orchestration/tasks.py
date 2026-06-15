from celery import shared_task

from action_orchestration.services import execute_action_run


@shared_task(name="action_orchestration.execute_action_run")
def execute_action_run_task(run_id: int):
    execute_action_run(run_id)
