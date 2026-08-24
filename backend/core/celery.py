import logging
import os
import signal
import threading
import time

from celery import Celery
from celery.signals import (
    beat_init,
    before_task_publish,
    setup_logging,
    task_postrun,
    task_prerun,
    worker_process_init,
    worker_ready,
    worker_shutting_down,
)

from core.logging import (
    bind_log_context,
    get_log_context,
    reset_log_context,
)

logger = logging.getLogger(__name__)

# Set the Django project's settings module. This ensures Django can load
# the appropriate configuration. The 'DJANGO_SETTINGS_MODULE' environment
# variable specifies the configuration file. Here it is set to 'core.settings',
# indicating the Django configuration file is at 'core/settings.py'.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

# Create a Celery application instance. The name of the Celery application is
# 'core', which usually matches the Django project name for better association
# of tasks with the project.
logger.debug("Creating Celery application instance with name: core")
app = Celery("core")

# Load Celery configuration from Django's settings file.
# The 'namespace="CELERY"' option restricts loading to settings that
# start with 'CELERY_'. Therefore, all Celery-related settings in
# 'core/settings.py' must begin with 'CELERY_'.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Update the result backend to use Django database
# Explicitly set the beat scheduler to use database
app.conf.update(
    result_backend='django-db',
    beat_scheduler='django_celery_beat.schedulers:DatabaseScheduler',
    imports=tuple(app.conf.get("imports", ())),
)

# Automatically discover all task modules registered in the Django project.
# Celery will search for 'tasks.py' in each app and load any tasks
# defined there.
app.autodiscover_tasks()


@setup_logging.connect
def preserve_hyperops_logging(**kwargs):
    """Prevent Celery from replacing the Django logging configuration."""


@before_task_publish.connect
def propagate_request_id(headers=None, **kwargs):
    """Attach the originating HTTP request ID to a published task."""
    if headers is None:
        return
    request_id = get_log_context()["request_id"]
    if request_id != "-":
        headers.setdefault("hyperops_request_id", request_id)


@task_prerun.connect
def bind_task_log_context(task_id=None, task=None, **kwargs):
    """Bind task identifiers for all logs emitted while a task runs."""
    if task is None:
        return
    request = getattr(task, "request", None)
    headers = getattr(request, "headers", None) or {}
    request_id = headers.get("hyperops_request_id", "-")
    tokens = bind_log_context(
        request_id=request_id,
        task_id=task_id or "-",
    )
    setattr(request, "_hyperops_log_context_tokens", tokens)


@task_postrun.connect
def reset_task_log_context(task=None, **kwargs):
    """Reset contextvars so worker processes cannot leak task identifiers."""
    request = getattr(task, "request", None) if task is not None else None
    tokens = getattr(request, "_hyperops_log_context_tokens", None)
    if tokens:
        reset_log_context(tokens)
        delattr(request, "_hyperops_log_context_tokens")


def reap_zombies():
    """
    Reap zombie processes (non-blocking).

    Best practice: Call this periodically, not via signal handler.
    Signal handlers can interfere with Celery's own signal handling.
    """
    try:
        reaped_count = 0
        while True:
            try:
                # Wait for any child process to exit (non-blocking)
                pid, status = os.waitpid(-1, os.WNOHANG)
                if pid == 0:
                    # No more zombie processes
                    break
                reaped_count += 1
                logger.debug("已回收子进程 | pid=%s status=%s", pid, status)
            except ChildProcessError:
                # No child processes
                break
            except OSError:
                # No more processes to wait for
                break

        if reaped_count > 0:
            logger.debug("已回收僵尸进程 | count=%s", reaped_count)
    except Exception as e:
        logger.debug("回收僵尸进程失败 | error_type=%s", type(e).__name__)


def setup_periodic_zombie_reaper():
    """
    Setup periodic zombie process reaper.

    Best practice: Use a background thread instead of signal handler
    to avoid interfering with Celery's signal handling.
    """
    def periodic_reap():
        """
        Periodically reap zombie processes.

        Check every 30 seconds.
        """
        while True:
            time.sleep(30)
            reap_zombies()

    try:
        thread = threading.Thread(
            target=periodic_reap,
            daemon=True,
            name="zombie-reaper"
        )
        thread.start()
        logger.debug("周期性僵尸进程回收器已启动")
    except Exception as e:
        logger.warning(
            "无法启动僵尸进程回收器 | error_type=%s",
            type(e).__name__,
        )


@worker_ready.connect
def on_worker_ready(sender=None, **kwargs):
    logger.info("后台任务 Worker 已就绪")


@beat_init.connect
def on_beat_init(sender=None, **kwargs):
    logger.info("定时任务调度器已就绪")


@worker_process_init.connect
def on_worker_process_init(sender=None, **kwargs):
    """
    Called when each worker process is initialized.

    Best practice: Use worker_process_init instead of worker_ready
    to ensure each process sets up its own reaper.
    """
    logger.debug("Worker 子进程初始化 | pid=%s", os.getpid())

    # Worker startup cleanup can be added here if needed
    # Example: cleanup stale locks, reset states, etc.

    # Setup SIGCHLD handler for this process
    # Note: This only works in the worker process, not the main process
    def sigchld_handler(signum, frame):
        """
        Handle SIGCHLD signal to reap zombies.
        """
        reap_zombies()

    try:
        # Only set up signal handler if we're in a worker process
        # (not the main process)
        if hasattr(os, 'getpid'):
            signal.signal(signal.SIGCHLD, sigchld_handler)
            logger.debug("Worker 子进程信号处理器已配置 | pid=%s", os.getpid())
    except (ValueError, OSError, AttributeError) as e:
        # Signal handling may not be available in all environments
        # Fallback to periodic reaping
        logger.debug(
            "无法配置 Worker 子进程信号处理器 | error_type=%s",
            type(e).__name__,
        )
        setup_periodic_zombie_reaper()


@worker_shutting_down.connect
def on_worker_shutting_down(sender=None, **kwargs):
    """
    Called when worker is shutting down.
    """
    logger.info("后台任务 Worker 正在停止")
    reap_zombies()
