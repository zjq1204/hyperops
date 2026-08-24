"""
Discover all installed apps' periodic_tasks and register to Celery Beat.

Run at startup (e.g. in entrypoint after migrate) so that each app's
register_periodic_tasks() is called and tasks are written to
django_celery_beat. No Django signals; keeps the flow explicit and portable.
"""
import importlib
import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from core.periodic_registry import (
    TASK_REGISTRY,
    apply_registry,
)

logger = logging.getLogger(__name__)


def discover_and_register():
    """
    Clear registry, discover each app's periodic_tasks, call
    register_periodic_tasks, then apply registry to django_celery_beat.
    """
    TASK_REGISTRY.clear()
    discovered_apps = 0

    for app in settings.INSTALLED_APPS:
        module_name = f"{app}.periodic_tasks"
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name == module_name:
                continue
            logger.error(
                "定时任务注册失败 | stage=discovery app=%s error_type=%s",
                app,
                type(exc).__name__,
            )
            raise

        if hasattr(module, "register_periodic_tasks"):
            discovered_apps += 1
            try:
                module.register_periodic_tasks()
            except Exception as exc:
                logger.error(
                    "定时任务注册失败 | stage=registration app=%s error_type=%s",
                    app,
                    type(exc).__name__,
                )
                raise

    try:
        result = apply_registry()
    except Exception as exc:
        logger.error(
            "定时任务注册失败 | stage=apply task_count=%s error_type=%s",
            len(TASK_REGISTRY),
            type(exc).__name__,
        )
        raise
    logger.info(
        "定时任务注册完成 | app_count=%s task_count=%s created_count=%s "
        "skipped_count=%s",
        discovered_apps,
        len(TASK_REGISTRY),
        result["created_count"],
        result["skipped_count"],
    )
    return result


class Command(BaseCommand):
    help = (
        "Discover all apps' periodic_tasks.register_periodic_tasks() and "
        "register entries to django_celery_beat without updating existing "
        "rows."
    )

    def handle(self, *args, **options):
        discover_and_register()
        count = len(TASK_REGISTRY)
        self.stdout.write(
            self.style.SUCCESS(
                f"Registered {count} periodic task(s) to django_celery_beat; "
            )
        )
