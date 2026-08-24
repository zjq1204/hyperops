"""Single logging configuration source for HyperOps services."""

import logging.config
from pathlib import Path


def build_logging_config(*, log_level="INFO", service="api", log_file=""):
    """Build a logging configuration for one HyperOps service process."""
    level = str(log_level or "INFO").upper()
    handler = {
        "level": level,
        "formatter": "hyperops",
        "filters": ["context"],
    }

    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(mode=0o640, exist_ok=True)
        path.chmod(0o640)
        handler.update(
            {
                "class": "logging.handlers.WatchedFileHandler",
                "filename": str(path),
                "encoding": "utf-8",
                "delay": True,
            }
        )
    else:
        handler.update(
            {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            }
        )

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "context": {
                "()": "core.logging.LogContextFilter",
                "service": service,
            }
        },
        "formatters": {
            "hyperops": {
                "()": "core.logging.HyperOpsFormatter",
            }
        },
        "handlers": {
            "application": handler,
            "null": {"class": "logging.NullHandler"},
        },
        "root": {
            "level": level,
            "handlers": ["application"],
        },
        "loggers": {
            "django.server": {
                "level": level,
                "handlers": ["null"],
                "propagate": False,
            },
            "django.request": {
                "level": "ERROR",
                "handlers": ["application"],
                "propagate": False,
            },
            "django.utils.autoreload": {
                "level": "WARNING",
                "handlers": ["application"],
                "propagate": False,
            },
            "celery": {
                "level": "WARNING",
                "handlers": ["application"],
                "propagate": False,
            },
            "flanker": {
                "level": "ERROR",
                "handlers": ["application"],
                "propagate": False,
            },
            "flanker.addresslib._parser.parser": {
                "level": "ERROR",
                "handlers": ["application"],
                "propagate": False,
            },
        },
    }


def configure_logging(log_level="INFO", service="api", log_file=""):
    """Configure logging once for the current Django or Celery process."""
    logging.config.dictConfig(
        build_logging_config(
            log_level=log_level,
            service=service,
            log_file=log_file,
        )
    )
