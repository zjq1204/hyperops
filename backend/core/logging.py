"""Shared logging primitives for HyperOps services."""

from __future__ import annotations

import copy
import logging
import os
import re
from contextvars import ContextVar
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


_request_id = ContextVar("hyperops_log_request_id", default="-")
_task_id = ContextVar("hyperops_log_task_id", default="-")
MAX_LOG_MESSAGE_LENGTH = 4096

_CELERY_UNREGISTERED_TASK_PATTERN = re.compile(
    r"^Received unregistered task of type ['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)

_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN [^-\r\n]*PRIVATE KEY-----.*?"
    r"-----END [^-\r\n]*PRIVATE KEY-----",
    re.IGNORECASE | re.DOTALL,
)
_SENSITIVE_VALUE_PATTERN = re.compile(
    r"[\"']?\b("
    r"(?:[a-z0-9]+[_-])*(?:password|passwd|secret|token|private[_-]?key)|"
    r"(?:[a-z0-9]+[_-])*(?:api|secret|encryption|signing)[_-]?key|"
    r"authorization|cookie|email|username"
    r")\b[\"']?\s*[:=]\s*"
    r"(?:Bearer\s+)?(?:\"[^\"]*\"|'[^']*'|[^\s|,;]+)",
    re.IGNORECASE,
)
_TOKEN_PREFIX_PATTERN = re.compile(
    r"\btoken(?:[_\s-]+prefix)\b\s*[:=]\s*[^\s|,;]+",
    re.IGNORECASE,
)
_TOKEN_CONTEXT_PATTERN = re.compile(
    r"\b(?:registration\s+)?token\b(?![_\s-]*prefix)"
    r"[^|:\r\n]{0,48}[:=]\s*[^\s|,;]+",
    re.IGNORECASE,
)
_EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",
    re.IGNORECASE,
)
_URL_SECRET_PATTERN = re.compile(
    r"([?&](?:access_token|refresh_token|private_token|api_token|token|"
    r"api_key|client_secret|secret_key|secret|password)=)[^&#\s]+",
    re.IGNORECASE,
)
_URL_CREDENTIAL_PATTERN = re.compile(
    r"([a-z][a-z0-9+.-]*://)[^:/@\s]+:[^@\s]+@",
    re.IGNORECASE,
)


def get_log_context():
    """Return the identifiers currently bound to this execution context."""
    return {
        "request_id": _request_id.get(),
        "task_id": _task_id.get(),
    }


def bind_log_context(*, request_id=None, task_id=None):
    """Bind supplied identifiers and return tokens that can restore the context."""
    tokens = {}
    if request_id is not None:
        tokens["request_id"] = _request_id.set(str(request_id or "-"))
    if task_id is not None:
        tokens["task_id"] = _task_id.set(str(task_id or "-"))
    return tokens


def reset_log_context(tokens):
    """Restore a context previously changed by :func:`bind_log_context`."""
    if "task_id" in tokens:
        _task_id.reset(tokens["task_id"])
    if "request_id" in tokens:
        _request_id.reset(tokens["request_id"])


def redact_log_text(value):
    """Mask common credential material before a record reaches a log file."""
    text = str(value)
    text = _PRIVATE_KEY_PATTERN.sub("[REDACTED PRIVATE KEY]", text)
    text = _TOKEN_PREFIX_PATTERN.sub("token_prefix=***", text)
    text = _TOKEN_CONTEXT_PATTERN.sub("token=***", text)
    text = _SENSITIVE_VALUE_PATTERN.sub(
        lambda match: f"{match.group(1)}=***",
        text,
    )
    text = _URL_SECRET_PATTERN.sub(r"\1***", text)
    text = _URL_CREDENTIAL_PATTERN.sub(r"\1***:***@", text)
    return _EMAIL_PATTERN.sub("[REDACTED EMAIL]", text)


def normalize_log_message(logger_name, message):
    """Collapse unsafe third-party payloads and bound regular message size."""
    text = str(message)
    if logger_name == "celery.worker.consumer.consumer":
        match = _CELERY_UNREGISTERED_TASK_PATTERN.match(text)
        if match:
            text = f"收到未注册 Celery 任务 | task_name={match.group(1)}"
    if len(text) > MAX_LOG_MESSAGE_LENGTH:
        text = f"{text[:MAX_LOG_MESSAGE_LENGTH]} [TRUNCATED]"
    return text


class LogContextFilter(logging.Filter):
    """Inject service and correlation fields into every service log record."""

    def __init__(self, service="application"):
        super().__init__()
        self.service = str(service or "application")

    def filter(self, record):
        context = get_log_context()
        request_id = context["request_id"]
        task_id = context["task_id"]
        correlation = []
        if task_id != "-":
            correlation.append(f"task={task_id}")
        if request_id != "-":
            correlation.append(f"req={request_id}")

        record.service = self.service
        record.correlation = " ".join(correlation) or "-"
        return True


class HyperOpsFormatter(logging.Formatter):
    """Render the stable human-readable HyperOps service-log format."""

    DEFAULT_FORMAT = (
        "%(asctime)s %(levelname)-8s [%(service)s] [pid=%(process)d] "
        "[%(correlation)s] %(name)s - %(message)s"
    )

    def __init__(
        self,
        fmt=None,
        datefmt=None,
        style="%",
        validate=True,
        timezone_name=None,
    ):
        super().__init__(
            fmt=fmt or self.DEFAULT_FORMAT,
            datefmt=datefmt,
            style=style,
            validate=validate,
        )
        configured_timezone = timezone_name or os.getenv(
            "HYPEROPS_LOG_TIMEZONE",
            "Asia/Shanghai",
        )
        try:
            self.timezone = ZoneInfo(configured_timezone)
        except ZoneInfoNotFoundError:
            self.timezone = ZoneInfo("UTC")

    def formatTime(self, record, datefmt=None):
        timestamp = datetime.fromtimestamp(record.created, tz=self.timezone)
        if datefmt:
            return timestamp.strftime(datefmt)
        return timestamp.isoformat(sep=" ", timespec="milliseconds")

    def format(self, record):
        normalized_record = copy.copy(record)
        normalized_record.msg = normalize_log_message(
            record.name,
            record.getMessage(),
        ).replace(
            "\r",
            r"\r",
        ).replace("\n", r"\n")
        normalized_record.args = ()
        return redact_log_text(super().format(normalized_record))
