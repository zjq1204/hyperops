import ast
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
FIRST_PARTY_PACKAGES = (
    "core",
    "platformkit",
    "accounts",
    "gitlab_resource",
    "jenkins_trigger",
    "monitoring_stack",
    "action_orchestration",
)
LOGGER_METHODS = {
    "debug",
    "info",
    "warning",
    "error",
    "exception",
    "critical",
}
SENSITIVE_LOG_ARGUMENTS = {
    "client_ip",
    "e",
    "email",
    "error_message",
    "exc",
    "exception_msg",
    "queue_url",
    "request_data",
    "safe_request_data",
    "tag_name",
    "token",
    "token_prefix",
    "url",
    "username",
}
SENSITIVE_LOG_ATTRIBUTES = {
    "response.text",
    "serializer.errors",
}


def _iter_runtime_sources():
    for package in FIRST_PARTY_PACKAGES:
        for path in (BACKEND_ROOT / package).rglob("*.py"):
            relative_parts = path.relative_to(BACKEND_ROOT).parts
            if "migrations" in relative_parts or "tests" in relative_parts:
                continue
            if path.name.startswith("test_") or path.name.startswith("tests_"):
                continue
            yield path


def _is_logger_call(node):
    if not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr not in LOGGER_METHODS:
        return False
    receiver = node.func.value
    return isinstance(receiver, ast.Name) and receiver.id in {"logger", "logging"}


def _expression_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _expression_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


class LoggingSourcePolicyTests(unittest.TestCase):
    def test_runtime_code_avoids_print_and_logging_fstrings(self):
        violations = []
        for path in _iter_runtime_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id == "print":
                        violations.append(f"{path}:{node.lineno} print()")
                if (
                    isinstance(node, ast.Call)
                    and _is_logger_call(node)
                    and node.args
                    and isinstance(node.args[0], ast.JoinedStr)
                ):
                    violations.append(
                        f"{path}:{node.lineno} logging f-string"
                    )

        self.assertEqual([], violations, "\n" + "\n".join(violations))

    def test_logging_calls_do_not_receive_sensitive_or_raw_values(self):
        violations = []
        for path in _iter_runtime_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not _is_logger_call(node):
                    continue
                values = list(node.args[1:])
                values.extend(keyword.value for keyword in node.keywords)
                for value in values:
                    expression = _expression_name(value)
                    if (
                        expression in SENSITIVE_LOG_ARGUMENTS
                        or expression in SENSITIVE_LOG_ATTRIBUTES
                    ):
                        violations.append(
                            f"{path}:{node.lineno} sensitive log argument {expression}"
                        )
                    if isinstance(value, ast.Dict):
                        for key in value.keys:
                            if (
                                isinstance(key, ast.Constant)
                                and key.value in SENSITIVE_LOG_ARGUMENTS
                            ):
                                violations.append(
                                    f"{path}:{node.lineno} sensitive log field {key.value}"
                                )

        self.assertEqual([], violations, "\n" + "\n".join(violations))

    def test_critical_business_flows_define_lifecycle_events(self):
        expected_events = {
            "action_orchestration/tasks.py": (
                "动作编排开始执行",
                "动作编排执行完成",
            ),
            "action_orchestration/services.py": (
                "动作步骤开始执行",
                "动作步骤执行完成",
                "动作步骤执行失败",
                "嵌套动作步骤执行失败",
            ),
            "monitoring_stack/services/job_dispatch.py": (
                "已发布组件部署任务",
                "组件部署任务发布失败",
            ),
            "monitoring_stack/tasks.py": (
                "组件部署开始执行",
                "组件部署执行完成",
            ),
            "monitoring_stack/services/sync.py": (
                "监控快照同步开始",
                "监控快照同步完成",
                "监控快照同步失败",
            ),
        }
        missing = []
        for relative_path, messages in expected_events.items():
            source = (BACKEND_ROOT / relative_path).read_text(encoding="utf-8")
            for message in messages:
                if message not in source:
                    missing.append(f"{relative_path}: missing {message}")

        self.assertEqual([], missing, "\n" + "\n".join(missing))

    def test_external_clients_do_not_log_and_rethrow(self):
        violations = []
        for relative_path in (
            "gitlab_resource/services/gitlab_client.py",
            "jenkins_trigger/services/jenkins_client.py",
        ):
            path = BACKEND_ROOT / relative_path
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _is_logger_call(node):
                    violations.append(f"{relative_path}:{node.lineno} client logging")

        self.assertEqual([], violations, "\n" + "\n".join(violations))

    def test_integration_views_define_terminal_outcome_events(self):
        expected_events = {
            "jenkins_trigger/views.py": (
                "Jenkins 构建触发成功",
                "Jenkins 构建状态已更新",
            ),
            "gitlab_resource/views.py": (
                "GitLab 资源采集完成",
                "GitLab 批量采集完成",
            ),
            "accounts/views/registration.py": ("注册完成",),
            "accounts/views/password.py": ("密码已重置",),
            "accounts/auth_backends.py": ("LDAP 认证服务不可用",),
        }
        missing = []
        for relative_path, messages in expected_events.items():
            source = (BACKEND_ROOT / relative_path).read_text(encoding="utf-8")
            for message in messages:
                if message not in source:
                    missing.append(f"{relative_path}: missing {message}")

        self.assertEqual([], missing, "\n" + "\n".join(missing))

    def test_supporting_services_keep_logs_aggregate_and_structured(self):
        periodic_source = (
            BACKEND_ROOT / "core/management/commands/register_periodic_tasks.py"
        ).read_text(encoding="utf-8")
        content_filter_source = (
            BACKEND_ROOT / "core/utils/content_filter.py"
        ).read_text(encoding="utf-8")

        self.assertIn("定时任务注册完成", periodic_source)
        self.assertIn("定时任务注册失败", periodic_source)
        self.assertNotIn("logger.", content_filter_source)
