import logging
import time

from celery import shared_task

from action_orchestration.services import execute_action_run

logger = logging.getLogger(__name__)


@shared_task(name="action_orchestration.execute_action_run")
def execute_action_run_task(run_id: int):
    started_at = time.monotonic()
    logger.info("动作编排开始执行 | run_id=%s", run_id)
    try:
        run = execute_action_run(run_id)
    except Exception as exc:
        logger.error(
            "动作编排执行异常 | run_id=%s error_type=%s duration_ms=%s",
            run_id,
            type(exc).__name__,
            int((time.monotonic() - started_at) * 1000),
        )
        raise
    logger.info(
        "动作编排执行完成 | run_id=%s status=%s duration_ms=%s",
        run_id,
        run.status,
        int((time.monotonic() - started_at) * 1000),
    )
    return run.id
