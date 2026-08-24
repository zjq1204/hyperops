import logging
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core.celery import (
    bind_task_log_context,
    propagate_request_id,
    reset_task_log_context,
)
from core.logging import (
    HyperOpsFormatter,
    LogContextFilter,
    bind_log_context,
    get_log_context,
    reset_log_context,
)
from core.settings.logging_config import build_logging_config
from platformkit.middleware import RequestIdMiddleware


def _record(message="operation completed"):
    return logging.LogRecord(
        name="monitoring_stack.services.core",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg=message,
        args=(),
        exc_info=None,
    )


class HyperOpsLoggingTests(unittest.TestCase):
    def test_formatter_renders_fixed_header_with_timezone_and_request_id(self):
        tokens = bind_log_context(request_id="request-12345678")
        try:
            record = _record("创建组件部署任务 | job_id=18")
            self.assertTrue(LogContextFilter("api").filter(record))

            output = HyperOpsFormatter().format(record)
        finally:
            reset_log_context(tokens)

        self.assertRegex(
            output,
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\+08:00 ",
        )
        self.assertIn("INFO     [api]", output)
        self.assertIn("[pid=", output)
        self.assertIn("[req=request-12345678]", output)
        self.assertIn(
            "monitoring_stack.services.core - 创建组件部署任务 | job_id=18",
            output,
        )

    def test_task_context_includes_originating_request_and_resets_cleanly(self):
        tokens = bind_log_context(
            request_id="request-12345678",
            task_id="task-12345678",
        )
        try:
            record = _record()
            LogContextFilter("worker").filter(record)
            self.assertEqual(
                record.correlation,
                "task=task-12345678 req=request-12345678",
            )
        finally:
            reset_log_context(tokens)

        self.assertEqual(
            get_log_context(),
            {"request_id": "-", "task_id": "-"},
        )

    def test_formatter_redacts_credentials_and_private_keys(self):
        message = (
            "upstream failed password=hunter2 token:abc123 "
            "Authorization=Bearer-secret "
            "client_secret=client-value access_token=access-value "
            "refresh_token=refresh-value private_token=private-value "
            "api_token=api-value secret_key=secret-key-value "
            "api_key=api-key-value ssh_password=ssh-password-value "
            "webhook_secret=webhook-secret-value cache_key=visible-cache-key "
            "url=https://service-user:service-password@example.internal/api "
            "email=user@example.com username=alice token_prefix=deadbeef "
            "registration token not found or already used: raw-token-value "
            "payload={'password': 'nested-secret'} "
            "-----BEGIN OPENSSH PRIVATE KEY-----\nsecret-material\n"
            "-----END OPENSSH PRIVATE KEY-----"
        )
        record = _record(message)
        LogContextFilter("api").filter(record)

        output = HyperOpsFormatter().format(record)

        self.assertNotIn("hunter2", output)
        self.assertNotIn("abc123", output)
        self.assertNotIn("Bearer-secret", output)
        self.assertNotIn("secret-material", output)
        self.assertNotIn("client-value", output)
        self.assertNotIn("access-value", output)
        self.assertNotIn("refresh-value", output)
        self.assertNotIn("private-value", output)
        self.assertNotIn("api-value", output)
        self.assertNotIn("secret-key-value", output)
        self.assertNotIn("api-key-value", output)
        self.assertNotIn("ssh-password-value", output)
        self.assertNotIn("webhook-secret-value", output)
        self.assertNotIn("service-user", output)
        self.assertNotIn("service-password", output)
        self.assertNotIn("user@example.com", output)
        self.assertNotIn("alice", output)
        self.assertNotIn("deadbeef", output)
        self.assertNotIn("raw-token-value", output)
        self.assertNotIn("nested-secret", output)
        self.assertIn("password=***", output)
        self.assertIn("token=***", output)
        self.assertIn("Authorization=***", output)
        self.assertIn("email=***", output)
        self.assertIn("username=***", output)
        self.assertIn("token_prefix=***", output)
        self.assertIn("https://***:***@example.internal/api", output)
        self.assertIn("api_key=***", output)
        self.assertIn("ssh_password=***", output)
        self.assertIn("webhook_secret=***", output)
        self.assertIn("cache_key=visible-cache-key", output)
        self.assertIn("[REDACTED PRIVATE KEY]", output)

    def test_file_logging_configuration_uses_watched_file_handler(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "api" / "application.log"

            config = build_logging_config(
                log_level="INFO",
                service="api",
                log_file=str(log_file),
            )

            self.assertTrue(log_file.parent.is_dir())
            self.assertTrue(log_file.is_file())
            self.assertEqual(os.stat(log_file).st_mode & 0o777, 0o640)
            self.assertEqual(
                config["handlers"]["application"]["class"],
                "logging.handlers.WatchedFileHandler",
            )
            self.assertEqual(
                config["handlers"]["application"]["filename"],
                str(log_file),
            )
            self.assertEqual(config["root"]["handlers"], ["application"])

    def test_console_logging_configuration_is_available_for_tests(self):
        config = build_logging_config(
            log_level="DEBUG",
            service="test",
            log_file="",
        )

        self.assertEqual(
            config["handlers"]["application"]["class"],
            "logging.StreamHandler",
        )
        self.assertNotIn("filename", config["handlers"]["application"])
        self.assertEqual(
            config["loggers"]["django.server"]["handlers"],
            ["null"],
        )
        self.assertEqual(config["loggers"]["django.request"]["level"], "ERROR")
        self.assertEqual(
            config["loggers"]["django.utils.autoreload"]["level"],
            "WARNING",
        )

    def test_formatter_keeps_regular_messages_on_one_line(self):
        record = _record("first line\nsecond line")
        LogContextFilter("api").filter(record)

        output = HyperOpsFormatter().format(record)

        self.assertNotIn("\n", output)
        self.assertIn(r"first line\nsecond line", output)

    def test_formatter_collapses_celery_unregistered_task_payload(self):
        record = logging.LogRecord(
            name="celery.worker.consumer.consumer",
            level=logging.ERROR,
            pathname=__file__,
            lineno=10,
            msg=(
                "Received unregistered task of type "
                "'example.tasks.unknown'.\n"
                "The full contents of the message body was:\n"
                "password=do-not-log\n"
                "The full contents of the message headers:\n"
                "{'token': 'do-not-log'}"
            ),
            args=(),
            exc_info=None,
        )
        LogContextFilter("worker").filter(record)

        output = HyperOpsFormatter().format(record)

        self.assertIn(
            "收到未注册 Celery 任务 | task_name=example.tasks.unknown",
            output,
        )
        self.assertNotIn("message body", output)
        self.assertNotIn("message headers", output)
        self.assertNotIn("do-not-log", output)

    def test_formatter_truncates_oversized_third_party_messages(self):
        record = _record("x" * 10000)
        LogContextFilter("api").filter(record)

        output = HyperOpsFormatter().format(record)

        self.assertLess(len(output), 5000)
        self.assertIn("[TRUNCATED]", output)

    def test_request_middleware_binds_and_resets_request_context(self):
        observed_context = {}

        def get_response(request):
            observed_context.update(get_log_context())
            return {}

        request = SimpleNamespace(
            META={"HTTP_X_REQUEST_ID": "request-12345678"}
        )

        response = RequestIdMiddleware(get_response)(request)

        self.assertEqual(observed_context["request_id"], "request-12345678")
        self.assertEqual(response["X-Request-ID"], "request-12345678")
        self.assertEqual(get_log_context()["request_id"], "-")

    def test_request_middleware_resets_context_when_view_raises(self):
        def get_response(request):
            raise RuntimeError("view failed")

        request = SimpleNamespace(
            META={"HTTP_X_REQUEST_ID": "request-12345678"}
        )

        with self.assertRaisesRegex(RuntimeError, "view failed"):
            RequestIdMiddleware(get_response)(request)

        self.assertEqual(get_log_context()["request_id"], "-")

    def test_celery_publish_and_execution_context_lifecycle(self):
        request_tokens = bind_log_context(request_id="request-12345678")
        headers = {}
        try:
            propagate_request_id(headers=headers)
        finally:
            reset_log_context(request_tokens)

        task = SimpleNamespace(
            request=SimpleNamespace(headers=headers),
        )
        bind_task_log_context(task_id="task-12345678", task=task)
        self.assertEqual(
            get_log_context(),
            {
                "request_id": "request-12345678",
                "task_id": "task-12345678",
            },
        )

        reset_task_log_context(task=task)

        self.assertEqual(
            get_log_context(),
            {"request_id": "-", "task_id": "-"},
        )
