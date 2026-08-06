import hashlib
import json
import os
import re
import secrets
import shlex
import shutil
import socket
import subprocess
import tarfile
import tempfile
import textwrap
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import paramiko
import requests
import yaml
from django.conf import settings
from django.db import OperationalError, ProgrammingError, transaction
from django.utils import timezone
from monitoring_stack.defaults import DEFAULT_INSTALLER_OPTIONS, DEFAULT_PROFILES
from monitoring_stack.models import (
    AnsibleInstallJob,
    BlackboxProbeNode,
    MonitoringComponentStatus,
    MonitoringHost,
    MonitoringIntegrationConfig,
    MonitoringProfile,
    N9eTargetSnapshot,
    ProbeTarget,
    PrometheusTargetSnapshot,
)
from monitoring_stack.services.ansible_progress import (
    build_progress,
    current_host_for_line,
    failure_reason_code,
    stream_process_output,
)
from monitoring_stack.services.ssh_verification import (
    connection_fingerprint_for_host,
    failed_verification_defaults,
)

INSTALLER_DOWNLOAD_FILES = {
    "install.sh",
    "install-blackbox.sh",
    "categraf-client.tar.gz",
    "blackbox-client.tar.gz",
    "SHA256SUMS",
    "BLACKBOX_SHA256SUMS",
    "VERSION",
    "installer-config.json",
}

N9E_VERSION_NOT_EXPOSED = "当前 n9e 版本未暴露"
EXTERNAL_COMPONENT_STATUS = "external"
N9E_ONLINE_VALUES = {
    "up",
    "online",
    "alive",
    "ok",
    "normal",
    "running",
    "active",
    "healthy",
    "true",
    "1",
}
N9E_OFFLINE_VALUES = {
    "down",
    "offline",
    "dead",
    "lost",
    "unreachable",
    "abnormal",
    "critical",
    "error",
    "failed",
    "inactive",
    "stopped",
    "false",
    "0",
}


def monitoring_root() -> Path:
    configured = getattr(settings, "MONITORING_STACK_ROOT", "")
    if configured:
        return Path(configured)
    return Path(getattr(settings, "STORAGE_ROOT", "/opt/storage")) / "monitoring_stack"


def installer_dir() -> Path:
    return Path(
        getattr(settings, "MONITORING_INSTALLER_DIR", monitoring_root() / "installer")
    )


def template_dir() -> Path:
    return Path(
        getattr(settings, "MONITORING_TEMPLATE_DIR", monitoring_root() / "templates")
    )


def rules_dir() -> Path:
    return Path(getattr(settings, "MONITORING_RULES_DIR", monitoring_root() / "rules"))


def ssh_dir() -> Path:
    return Path(getattr(settings, "MONITORING_SSH_DIR", monitoring_root() / "ssh"))


def integration_config():
    try:
        return MonitoringIntegrationConfig.current()
    except (OperationalError, ProgrammingError):
        return None


def configured_value(config, field_name, setting_name, default=""):
    value = getattr(config, field_name, "") if config else ""
    if value:
        return value
    return getattr(settings, setting_name, default)


def _n9e_payload_data(payload):
    if isinstance(payload, dict) and "dat" in payload:
        return payload.get("dat")
    return payload


def _n9e_collection_count(data):
    if isinstance(data, list):
        return len(data), data
    if not isinstance(data, dict):
        return 0, []
    for total_key in ("total", "count", "total_count"):
        value = data.get(total_key)
        if isinstance(value, int):
            items = data.get("list") or data.get("items") or data.get("data") or []
            return value, items if isinstance(items, list) else []
    for list_key in ("list", "items", "data", "records"):
        value = data.get(list_key)
        if isinstance(value, list):
            return len(value), value
    return 0, []


def _n9e_rule_enabled(rule):
    if not isinstance(rule, dict):
        return True
    if "enable" in rule:
        return bool(rule.get("enable"))
    if "enabled" in rule:
        return bool(rule.get("enabled"))
    if "disabled" in rule:
        return str(rule.get("disabled")).lower() not in {"1", "true", "yes"}
    return True


def _fetch_n9e_collection(session, url):
    response = session.get(url, timeout=10)
    response.raise_for_status()
    return _n9e_collection_count(_n9e_payload_data(response.json()))


def _n9e_rules_summary(session, n9e_url, groups):
    total = 0
    enabled = 0
    matched = False
    for group in groups:
        group_id = group.get("id") if isinstance(group, dict) else None
        if not group_id:
            continue
        try:
            count, items = _fetch_n9e_collection(
                session,
                f"{n9e_url}/api/n9e/busi-group/{group_id}/alert-rules",
            )
        except Exception:
            continue
        matched = True
        total += count
        enabled += sum(1 for item in items if _n9e_rule_enabled(item))
    if matched:
        return {
            "rules_available": True,
            "rules": total,
            "enabled_rules": enabled,
            "rules_unavailable_reason": "",
        }

    for path in ("/api/n9e/alert-rules", "/api/n9e/alert-rules/list"):
        try:
            count, items = _fetch_n9e_collection(session, f"{n9e_url}{path}")
        except Exception:
            continue
        return {
            "rules_available": True,
            "rules": count,
            "enabled_rules": sum(1 for item in items if _n9e_rule_enabled(item)),
            "rules_unavailable_reason": "",
        }
    return {
        "rules_available": False,
        "rules": None,
        "enabled_rules": None,
        "rules_unavailable_reason": N9E_VERSION_NOT_EXPOSED,
    }


def _n9e_hosts_summary(session, n9e_url):
    for path in (
        "/api/n9e/targets",
        "/api/n9e/target/list",
        "/api/n9e/objects",
        "/api/n9e/object/list",
    ):
        try:
            count, _items = _fetch_n9e_collection(session, f"{n9e_url}{path}")
        except Exception:
            continue
        return {
            "hosts_available": True,
            "hosts": count,
            "hosts_unavailable_reason": "",
        }
    return {
        "hosts_available": False,
        "hosts": None,
        "hosts_unavailable_reason": N9E_VERSION_NOT_EXPOSED,
    }


def _load_n9e_visible_hosts():
    config = monitoring_config()
    n9e_url = str(config.get("n9e_url") or "").rstrip("/")
    runtime = integration_config()
    username = str(
        configured_value(runtime, "n9e_username", "MONITORING_N9E_USERNAME", "") or ""
    ).strip()
    password = str(
        configured_value(runtime, "n9e_password", "MONITORING_N9E_PASSWORD", "") or ""
    )
    if not n9e_url or not username or not password:
        return None

    session = requests.Session()
    session.trust_env = False
    login = session.post(
        f"{n9e_url}/api/n9e/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )
    login.raise_for_status()
    token = (login.json().get("dat") or {}).get("access_token")
    if not token:
        return None
    session.headers.update({"Authorization": f"Bearer {token}"})

    for path in (
        "/api/n9e/targets",
        "/api/n9e/target/list",
        "/api/n9e/objects",
        "/api/n9e/object/list",
    ):
        try:
            _count, items = _fetch_n9e_collection(session, f"{n9e_url}{path}")
        except Exception:
            continue
        return items
    return None


def _flatten_strings(value):
    if isinstance(value, dict):
        result = []
        for item in value.values():
            result.extend(_flatten_strings(item))
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(_flatten_strings(item))
        return result
    if value is None:
        return []
    return [str(value).strip().lower()]


def _n9e_host_matches(candidate, host):
    values = [item for item in _flatten_strings(candidate) if item]
    targets = {
        str(host.hostname or "").strip().lower(),
        str(host.address or "").strip().lower(),
    }
    targets.discard("")
    return any(
        value == target or target in value
        for value in values
        for target in targets
    )


def _normalize_n9e_runtime_value(value):
    if isinstance(value, bool):
        return "online" if value else "abnormal", str(value).lower()
    if isinstance(value, (int, float)):
        text = str(int(value))
    else:
        text = str(value or "").strip().lower()
    if not text:
        return "", ""
    if text in N9E_ONLINE_VALUES:
        return "online", text
    if text in N9E_OFFLINE_VALUES:
        return "abnormal", text
    return "", text


def _normalize_n9e_target_up_value(value):
    if isinstance(value, bool):
        return "online" if value else "abnormal", str(value).lower()
    if isinstance(value, (int, float)):
        text = str(int(value))
    else:
        text = str(value or "").strip().lower()
    if not text:
        return "", ""
    if text == "0":
        return "abnormal", text
    if text in {"1", "2"}:
        return "online", text
    return _normalize_n9e_runtime_value(value)


def _n9e_candidate_runtime_status(candidate):
    if not isinstance(candidate, dict):
        return "", ""
    matched = []
    keys = {
        "health",
        "status",
        "state",
        "target_status",
        "host_status",
        "target_up",
        "up",
        "is_up",
        "online",
        "is_online",
        "alive",
        "reachable",
    }
    disabled_keys = {"disabled", "is_disabled"}

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                key_name = str(key or "").strip().lower()
                if key_name in keys:
                    normalizer = (
                        _normalize_n9e_target_up_value
                        if key_name == "target_up"
                        else _normalize_n9e_runtime_value
                    )
                    status, raw = normalizer(item)
                    if status:
                        matched.append((status, key_name, raw))
                elif key_name in disabled_keys:
                    status, raw = _normalize_n9e_runtime_value(item)
                    if raw in {"true", "1"}:
                        matched.append(("abnormal", key_name, raw))
                if isinstance(item, (dict, list)):
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(candidate)
    offline = next((item for item in matched if item[0] == "abnormal"), None)
    if offline:
        return "abnormal", f"n9e 返回 {offline[1]}={offline[2]}"
    online = next((item for item in matched if item[0] == "online"), None)
    if online:
        return "online", ""
    return "", ""


def n9e_snapshot_matches_host(snapshot, host):
    candidate = {
        "identity": snapshot.identity,
        "hostname": snapshot.hostname,
        "address": snapshot.address,
        "connection_address": n9e_target_connection_address(
            snapshot.raw,
            snapshot.address,
        ),
        "raw": snapshot.raw,
    }
    return _n9e_host_matches(candidate, host)


def n9e_runtime_for_host(host, candidates=None, cache=None):
    checked_at = timezone.now().isoformat()
    base = {
        "runtime_status": "unknown",
        "runtime_reason": "",
        "runtime_endpoint": "n9e",
        "runtime_checked_at": checked_at,
    }
    cache = cache if cache is not None else {}
    matched_candidates = []
    if candidates is None:
        if "n9e_target_snapshots" not in cache:
            cache["n9e_target_snapshots"] = list(N9eTargetSnapshot.objects.all())
        for snapshot in cache["n9e_target_snapshots"]:
            if not n9e_snapshot_matches_host(snapshot, host):
                continue
            matched_candidates.append(
                {
                    "identity": snapshot.identity,
                    "hostname": snapshot.hostname,
                    "address": snapshot.address,
                    "raw": snapshot.raw,
                }
            )
    else:
        matched_candidates = [
            item for item in candidates if _n9e_host_matches(item, host)
        ]

    if not matched_candidates:
        return {
            **base,
            "runtime_status": "abnormal",
            "runtime_reason": "n9e 当前未发现该主机对象",
        }

    for candidate in matched_candidates:
        runtime_status, reason = _n9e_candidate_runtime_status(candidate)
        if runtime_status == "abnormal":
            return {
                **base,
                "runtime_status": "abnormal",
                "runtime_reason": reason,
            }
        if runtime_status == "online":
            return {**base, "runtime_status": "online"}

    return {
        **base,
        "runtime_reason": "n9e 已发现该主机，但未返回在线状态",
    }


def host_visible_in_n9e(host, cache=None):
    cache = cache if cache is not None else {}
    if "n9e_target_snapshots" not in cache:
        cache["n9e_target_snapshots"] = list(N9eTargetSnapshot.objects.all())
    return any(
        n9e_snapshot_matches_host(snapshot, host)
        for snapshot in cache["n9e_target_snapshots"]
    )


def _get_without_proxy(url, timeout=2):
    session = requests.Session()
    session.trust_env = False
    return session.get(url, timeout=timeout)


def blackbox_health_for_host(host, cache=None):
    cache = cache if cache is not None else {}
    port = str(
        monitoring_config().get("installer", {}).get("blackbox_port") or "9115"
    )
    endpoint = f"http://{host.address}:{port}/-/healthy"
    cache_key = ("blackbox_health", host.id, endpoint)
    if cache_key in cache:
        return cache[cache_key]
    try:
        response = _get_without_proxy(endpoint, timeout=1)
        response.raise_for_status()
    except Exception as exc:
        result = {
            "runtime_status": "unknown",
            "runtime_reason": str(exc),
            "runtime_endpoint": endpoint,
        }
    else:
        result = {
            "runtime_status": "online",
            "runtime_reason": "",
            "runtime_endpoint": endpoint,
        }
    cache[cache_key] = result
    return result


def component_runtime_health(component_status, cache=None):
    checked_at = timezone.now().isoformat()
    base = {
        "runtime_status": "unknown",
        "runtime_reason": "",
        "runtime_endpoint": "",
        "runtime_checked_at": checked_at,
    }
    if component_status.status != MonitoringComponentStatus.STATUS_SUCCESS:
        return {**base, "runtime_reason": "组件尚未安装成功"}

    host = component_status.host
    if component_status.component == AnsibleInstallJob.COMPONENT_BLACKBOX:
        port = (
            getattr(component_status.last_job, "blackbox_port", "")
            or monitoring_config().get("installer", {}).get("blackbox_port")
            or "9115"
        )
        endpoint = f"http://{host.address}:{port}/-/healthy"
        try:
            response = _get_without_proxy(endpoint, timeout=3)
            response.raise_for_status()
        except Exception as exc:
            return {
                **base,
                "runtime_status": "abnormal",
                "runtime_reason": str(exc),
                "runtime_endpoint": endpoint,
            }
        return {
            **base,
            "runtime_status": "online",
            "runtime_endpoint": endpoint,
        }

    if component_status.component == AnsibleInstallJob.COMPONENT_CATEGRAF:
        cache = cache if cache is not None else {}
        if "n9e_visible_hosts" not in cache:
            try:
                cache["n9e_visible_hosts"] = _load_n9e_visible_hosts()
            except Exception:
                cache["n9e_visible_hosts"] = None
        candidates = cache.get("n9e_visible_hosts")
        if candidates is None:
            return {**base, **n9e_runtime_for_host(host, cache=cache)}
        return {**base, **n9e_runtime_for_host(host, candidates=candidates, cache=cache)}

    return base


def clean_labels(labels):
    if not isinstance(labels, dict):
        return {}
    return {
        str(key).strip(): str(value).strip()
        for key, value in labels.items()
        if str(key).strip() and str(value).strip()
    }


def clean_string_list(values):
    if not isinstance(values, list):
        return []
    seen = set()
    cleaned = []
    for value in values:
        item = str(value).strip()
        if item and item not in seen:
            seen.add(item)
            cleaned.append(item)
    return cleaned


def clean_ssh_key(value):
    return Path(str(value or "").strip()).name


def host_ssh_key_path(host):
    if host.ssh_auth_type != MonitoringHost.SSH_AUTH_KEY:
        return None
    credential = getattr(host, "ssh_key_credential", None)
    if credential and credential.file_name:
        return credential.storage_path
    ssh_key = clean_ssh_key(host.ssh_key)
    return ssh_dir() / ssh_key if ssh_key else None


class MonitoringSshConnectionError(Exception):
    def __init__(self, code, status_code):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def check_monitoring_ssh_connection(
    *, address, ssh_user, ssh_port, password=None, key_path=None
):
    started_at = time.monotonic()
    key_file = Path(key_path) if key_path else None
    if key_file and not key_file.is_file():
        raise MonitoringSshConnectionError("SSH_KEY_OR_PROTOCOL_FAILED", 400)

    env = dict(os.environ)
    ssh_command = [
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "ConnectTimeout=8",
        "-p",
        str(int(ssh_port or 22)),
    ]
    if key_file:
        try:
            validation = subprocess.run(
                ["ssh-keygen", "-y", "-f", str(key_file)],
                capture_output=True,
                text=True,
                timeout=8,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise MonitoringSshConnectionError(
                "SSH_KEY_OR_PROTOCOL_FAILED", 400
            ) from exc
        if validation.returncode != 0:
            raise MonitoringSshConnectionError("SSH_KEY_OR_PROTOCOL_FAILED", 400)
        ssh_command.extend(
            [
                "-o",
                "BatchMode=yes",
                "-o",
                "IdentitiesOnly=yes",
                "-i",
                str(key_file),
            ]
        )
    elif password:
        env["SSHPASS"] = str(password)
        ssh_command = [
            "sshpass",
            "-e",
            *ssh_command,
            "-o",
            "BatchMode=no",
            "-o",
            "PreferredAuthentications=password",
            "-o",
            "PubkeyAuthentication=no",
        ]
    else:
        ssh_command.extend(["-o", "BatchMode=yes"])

    ssh_command.extend(
        [
            f"{ssh_user or 'root'}@{address}",
            "printf hyperops-ssh-ok",
        ]
    )
    try:
        result = subprocess.run(
            ssh_command,
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise MonitoringSshConnectionError("SSH_TIMEOUT", 504) from exc
    except FileNotFoundError as exc:
        raise MonitoringSshConnectionError("SSH_COMMAND_FAILED", 502) from exc

    if result.returncode != 0 or result.stdout != "hyperops-ssh-ok":
        output = f"{result.stderr}\n{result.stdout}".lower()
        if "error in libcrypto" in output or "invalid format" in output:
            raise MonitoringSshConnectionError("SSH_KEY_OR_PROTOCOL_FAILED", 400)
        if "permission denied" in output or "authentication failed" in output:
            raise MonitoringSshConnectionError("SSH_AUTH_FAILED", 400)
        if "timed out" in output or "timeout" in output:
            raise MonitoringSshConnectionError("SSH_TIMEOUT", 504)
        if any(
            marker in output
            for marker in (
                "connection refused",
                "no route to host",
                "could not resolve hostname",
                "name or service not known",
                "network is unreachable",
            )
        ):
            raise MonitoringSshConnectionError("SSH_UNREACHABLE", 502)
        raise MonitoringSshConnectionError("SSH_COMMAND_FAILED", 502)
    return {"latency_ms": max(1, round((time.monotonic() - started_at) * 1000))}


def ensure_default_profiles():
    for item in DEFAULT_PROFILES:
        MonitoringProfile.objects.update_or_create(
            id=item["id"],
            defaults={
                "name": item["name"],
                "category": item.get("category", ""),
                "description": item.get("description", ""),
                "plugins": item.get("plugins", []),
                "is_builtin": True,
            },
        )


def render_http_sd_targets(target_type):
    groups = []
    for item in (
        ProbeTarget.objects.filter(
            type=target_type,
            enabled=True,
            probe_node__isnull=False,
            probe_node__enabled=True,
        )
        .select_related("probe_node")
        .order_by("id")
    ):
        labels = clean_labels(item.labels)
        labels["probe_type"] = target_type
        labels["probe_node"] = item.probe_node.name
        labels["blackbox_address"] = item.probe_node.endpoint
        groups.append({"targets": [item.target], "labels": labels})
    return groups


def active_prometheus_http_sd_token():
    config = integration_config()
    database_token = str(
        getattr(config, "prometheus_http_sd_token", "") if config else ""
    ).strip()
    if database_token:
        return database_token, "database"
    env_token = str(getattr(settings, "MONITORING_ADMIN_TOKEN", "") or "").strip()
    if env_token:
        return env_token, "env"
    return "", ""


def mask_token(token):
    token = str(token or "").strip()
    if not token:
        return ""
    if len(token) <= 8:
        return "*" * len(token)
    return f"{token[:4]}******{token[-4:]}"


def prometheus_http_sd_state():
    token, source = active_prometheus_http_sd_token()
    return {
        "token_configured": bool(token),
        "token_source": source,
        "token_preview": mask_token(token),
        "token_file_path": "/etc/prometheus/hyperops-http-sd.token",
    }


def generate_prometheus_http_sd_token():
    token = f"mon_{secrets.token_urlsafe(32)}"
    config = MonitoringIntegrationConfig.current()
    config.prometheus_http_sd_token = token
    config.save(update_fields=["prometheus_http_sd_token", "updated_at"])
    return token


def prometheus_http_sd_urls(base_url):
    base = str(base_url or "").rstrip("/")
    return {
        target_type: (
            f"{base}/api/v1/monitoring/prometheus/http-sd/blackbox/{target_type}/"
        )
        for target_type in (
            ProbeTarget.TYPE_HTTP,
            ProbeTarget.TYPE_TCP,
            ProbeTarget.TYPE_ICMP,
        )
    }


def prometheus_http_sd_config(base_url):
    urls = prometheus_http_sd_urls(base_url)
    token, _source = active_prometheus_http_sd_token()
    token_literal = json.dumps(token)
    yaml_content = textwrap.dedent(
        f"""
        global:
          scrape_interval: 30s
          scrape_timeout: 10s
          evaluation_interval: 30s

        scrape_configs:
          - job_name: blackbox-http
            metrics_path: /probe
            params:
              module: [http_2xx]
            http_sd_configs:
              - url: {urls[ProbeTarget.TYPE_HTTP]}
                refresh_interval: 30s
                authorization:
                  type: Bearer
                  credentials: {token_literal}
            relabel_configs:
              - source_labels: [__address__]
                target_label: __param_target
              - source_labels: [__param_target]
                target_label: instance
              - target_label: probe_type
                replacement: http
              - source_labels: [blackbox_address]
                target_label: __address__

          - job_name: blackbox-tcp
            metrics_path: /probe
            params:
              module: [tcp_connect]
            http_sd_configs:
              - url: {urls[ProbeTarget.TYPE_TCP]}
                refresh_interval: 30s
                authorization:
                  type: Bearer
                  credentials: {token_literal}
            relabel_configs:
              - source_labels: [__address__]
                target_label: __param_target
              - source_labels: [__param_target]
                target_label: instance
              - target_label: probe_type
                replacement: tcp
              - source_labels: [blackbox_address]
                target_label: __address__

          - job_name: blackbox-icmp
            metrics_path: /probe
            params:
              module: [icmp]
            http_sd_configs:
              - url: {urls[ProbeTarget.TYPE_ICMP]}
                refresh_interval: 30s
                authorization:
                  type: Bearer
                  credentials: {token_literal}
            relabel_configs:
              - source_labels: [__address__]
                target_label: __param_target
              - source_labels: [__param_target]
                target_label: instance
              - target_label: probe_type
                replacement: icmp
              - source_labels: [blackbox_address]
                target_label: __address__
        """
    ).strip()
    return {
        **prometheus_http_sd_state(),
        "urls": urls,
        "yaml": yaml_content,
    }


def monitoring_config():
    root = monitoring_root()
    config = integration_config()
    n9e_url = configured_value(config, "n9e_url", "MONITORING_N9E_URL", "")
    n9e_username = configured_value(
        config,
        "n9e_username",
        "MONITORING_N9E_USERNAME",
        "",
    )
    n9e_password = configured_value(
        config,
        "n9e_password",
        "MONITORING_N9E_PASSWORD",
        "",
    )
    prometheus_url = configured_value(
        config,
        "prometheus_url",
        "MONITORING_PROMETHEUS_URL",
        "",
    )
    grafana_url = configured_value(config, "grafana_url", "MONITORING_GRAFANA_URL", "")
    installer_base_url = configured_value(
        config,
        "installer_base_url",
        "MONITORING_INSTALLER_BASE_URL",
        "",
    )
    categraf_install_dir = configured_value(
        config,
        "categraf_install_dir",
        "MONITORING_CATEGRAF_INSTALL_DIR",
        "/opt/categraf",
    )
    blackbox_install_dir = configured_value(
        config,
        "blackbox_install_dir",
        "MONITORING_BLACKBOX_INSTALL_DIR",
        "/opt/blackbox-exporter",
    )
    blackbox_port = configured_value(
        config,
        "blackbox_port",
        "MONITORING_BLACKBOX_PORT",
        "9115",
    )
    blackbox_image = configured_value(
        config,
        "blackbox_image",
        "MONITORING_BLACKBOX_IMAGE",
        "prom/blackbox-exporter:latest",
    )
    return {
        "stack_root": str(root),
        "prometheus_url": prometheus_url,
        "n9e_url": n9e_url,
        "grafana_url": grafana_url,
        "n9e": {
            "url": n9e_url,
            "username": n9e_username,
            "has_password": bool(n9e_password),
        },
        "http_sd": prometheus_http_sd_state(),
        "installer": {
            "base_url": installer_base_url,
            "install_dir": categraf_install_dir,
            "blackbox_dir": blackbox_install_dir,
            "blackbox_port": blackbox_port,
            "blackbox_image": blackbox_image,
            "n9e_url": n9e_url,
            "options": DEFAULT_INSTALLER_OPTIONS,
        },
    }


def n9e_platform_summary():
    config = monitoring_config()
    n9e_url = str(config.get("n9e_url") or "").rstrip("/")
    runtime = integration_config()
    username = str(
        configured_value(runtime, "n9e_username", "MONITORING_N9E_USERNAME", "") or ""
    ).strip()
    password = str(
        configured_value(runtime, "n9e_password", "MONITORING_N9E_PASSWORD", "") or ""
    )
    synced_at = timezone.now().isoformat()
    empty = {
        "configured": bool(n9e_url),
        "connected": False,
        "auth_configured": bool(username and password),
        "n9e_url": n9e_url,
        "synced_at": synced_at,
        "error": "",
        "business_groups": None,
        "datasources": None,
        "prometheus_datasources": None,
        "rules": None,
        "enabled_rules": None,
        "hosts": None,
        "hosts_available": False,
        "hosts_unavailable_reason": "",
        "rules_available": False,
        "rules_unavailable_reason": "",
    }
    if not n9e_url:
        return {**empty, "error": "n9e url is not configured"}
    if not username or not password:
        return {
            **empty,
            "error": "n9e credentials are not configured",
        }

    session = requests.Session()
    session.trust_env = False
    try:
        login = session.post(
            f"{n9e_url}/api/n9e/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
        login.raise_for_status()
        token = (login.json().get("dat") or {}).get("access_token")
        if not token:
            return {**empty, "error": "n9e login failed"}
        session.headers.update({"Authorization": f"Bearer {token}"})
        groups_response = session.get(f"{n9e_url}/api/n9e/busi-groups", timeout=10)
        datasources_response = session.get(
            f"{n9e_url}/api/n9e/datasource/brief",
            timeout=10,
        )
        groups_response.raise_for_status()
        datasources_response.raise_for_status()
        groups = groups_response.json().get("dat", [])
        datasources = datasources_response.json().get("dat", [])
        prometheus_datasources = [
            item for item in datasources if item.get("plugin_type") == "prometheus"
        ]
        rules_summary = _n9e_rules_summary(session, n9e_url, groups)
        hosts_summary = _n9e_hosts_summary(session, n9e_url)
        return {
            **empty,
            "connected": True,
            "error": "",
            "business_groups": len(groups),
            "datasources": len(datasources),
            "prometheus_datasources": len(prometheus_datasources),
            **rules_summary,
            **hosts_summary,
        }
    except Exception as exc:
        return {**empty, "error": str(exc)}


def _prometheus_target_value(target):
    labels = target.get("labels") or {}
    discovered = target.get("discoveredLabels") or {}
    scrape_url = target.get("scrapeUrl") or ""
    parsed_query = parse_qs(urlparse(scrape_url).query)
    candidates = [
        labels.get("__param_target__"),
        labels.get("target"),
        labels.get("instance"),
        discovered.get("__param_target__"),
        discovered.get("target"),
        discovered.get("__address__"),
        parsed_query.get("target", [""])[0],
    ]
    for value in candidates:
        item = str(value or "").strip()
        if item:
            return item
    return ""


def _prometheus_probe_type(target):
    labels = target.get("labels") or {}
    discovered = target.get("discoveredLabels") or {}
    for value in [
        labels.get("probe_type"),
        labels.get("module"),
        discovered.get("probe_type"),
        discovered.get("__param_module__"),
    ]:
        item = str(value or "").strip().lower()
        if item in {ProbeTarget.TYPE_HTTP, ProbeTarget.TYPE_TCP, ProbeTarget.TYPE_ICMP}:
            return item
    return ""


def _empty_prometheus_reconciliation():
    return {
        "configured_not_discovered": [],
        "discovered_not_configured": [],
        "abnormal_targets": [],
    }


def prometheus_targets_summary():
    prometheus_url = str(monitoring_config().get("prometheus_url") or "").rstrip("/")
    synced_at = timezone.now().isoformat()
    if not prometheus_url:
        return {
            "configured": False,
            "connected": False,
            "prometheus_url": "",
            "synced_at": synced_at,
            "error": "prometheus url is not configured",
            "active_targets": 0,
            "down_targets": 0,
            "blackbox_targets": 0,
            "targets": [],
            "probe_statuses": {},
            "reconciliation": _empty_prometheus_reconciliation(),
        }

    try:
        session = requests.Session()
        session.trust_env = False
        response = session.get(
            f"{prometheus_url}/api/v1/targets",
            params={"state": "active"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return {
            "configured": True,
            "connected": False,
            "prometheus_url": prometheus_url,
            "synced_at": synced_at,
            "error": str(exc),
            "active_targets": 0,
            "down_targets": 0,
            "blackbox_targets": 0,
            "targets": [],
            "probe_statuses": {},
            "reconciliation": _empty_prometheus_reconciliation(),
        }

    active_targets = payload.get("data", {}).get("activeTargets", [])
    rows = []
    probe_statuses = {}
    for target in active_targets:
        health = str(target.get("health") or "unknown").lower()
        probe_type = _prometheus_probe_type(target)
        target_value = _prometheus_target_value(target)
        labels = target.get("labels") or {}
        discovered = target.get("discoveredLabels") or {}
        is_blackbox = bool(
            probe_type
            or "blackbox" in str(labels.get("job") or "").lower()
            or "blackbox" in str(target.get("scrapePool") or "").lower()
        )
        row = {
            "health": health,
            "target": target_value,
            "probe_type": probe_type,
            "job": labels.get("job", ""),
            "scrape_url": target.get("scrapeUrl", ""),
            "scrape_pool": target.get("scrapePool", ""),
            "last_error": target.get("lastError", ""),
            "last_scrape": target.get("lastScrape", ""),
            "is_blackbox": is_blackbox,
        }
        rows.append(row)
        if probe_type and target_value:
            probe_statuses[f"{probe_type}:{target_value}"] = row
        discovered_probe_type = str(discovered.get("probe_type") or "").lower()
        if discovered_probe_type and target_value:
            probe_statuses[f"{discovered_probe_type}:{target_value}"] = row

    blackbox_targets = [item for item in rows if item["is_blackbox"]]
    configured_probes = list(ProbeTarget.objects.filter(enabled=True).order_by("type", "target", "id"))
    configured_keys = {f"{item.type}:{item.target}" for item in configured_probes}
    configured_not_discovered = [
        {"type": item.type, "target": item.target}
        for item in configured_probes
        if f"{item.type}:{item.target}" not in probe_statuses
    ]
    discovered_not_configured = [
        {
            "type": item["probe_type"],
            "target": item["target"],
            "health": item["health"],
        }
        for item in blackbox_targets
        if item["probe_type"]
        and item["target"]
        and f"{item['probe_type']}:{item['target']}" not in configured_keys
    ]
    abnormal_targets = [
        {
            "type": item["probe_type"],
            "target": item["target"],
            "health": item["health"],
            "last_error": item["last_error"],
        }
        for item in blackbox_targets
        if item["target"] and item["health"] != "up"
    ]
    return {
        "configured": True,
        "connected": True,
        "prometheus_url": prometheus_url,
        "synced_at": synced_at,
        "error": "",
        "active_targets": len(active_targets),
        "down_targets": sum(
            1 for item in active_targets if str(item.get("health", "")).lower() != "up"
        ),
        "blackbox_targets": len(blackbox_targets),
        "targets": blackbox_targets,
        "probe_statuses": probe_statuses,
        "reconciliation": {
            "configured_not_discovered": configured_not_discovered,
            "discovered_not_configured": discovered_not_configured,
            "abnormal_targets": abnormal_targets,
        },
    }


def _probe_node_endpoint_key(address, port):
    return str(address or "").strip().lower(), str(port or "9115").strip() or "9115"


def _blackbox_exporter_target(target):
    labels = target.get("labels") or {}
    discovered = target.get("discoveredLabels") or {}
    scrape_url = str(target.get("scrapeUrl") or "")
    parsed_scrape = urlparse(scrape_url)
    is_probe_request = bool(
        _prometheus_probe_type(target)
        or discovered.get("__param_target__")
        or parsed_scrape.path.rstrip("/").endswith("/probe")
    )
    if is_probe_request:
        return None

    identity = " ".join(
        str(value or "").lower()
        for value in [
            labels.get("job"),
            labels.get("service"),
            discovered.get("job"),
            discovered.get("service"),
            target.get("scrapePool"),
        ]
    )
    candidates = [
        discovered.get("__address__"),
        labels.get("instance"),
        scrape_url,
    ]
    address = ""
    port = ""
    for candidate in candidates:
        address, port = _host_port_from_value(candidate)
        if address:
            break
    port = port or "9115"
    metrics_endpoint = parsed_scrape.path.rstrip("/") in {"", "/metrics"}
    if not address or not (
        "blackbox-exporter" in identity
        or ("blackbox" in identity and metrics_endpoint)
        or (port == "9115" and metrics_endpoint)
    ):
        return None
    return {
        "address": address,
        "port": port,
        "endpoint": f"{address}:{port}",
        "health": str(target.get("health") or "unknown").lower(),
        "job": str(labels.get("job") or target.get("scrapePool") or ""),
        "last_error": str(target.get("lastError") or ""),
        "last_scrape": str(target.get("lastScrape") or ""),
    }


def _managed_probe_node_runtime_target(target):
    labels = target.get("labels") or {}
    discovered = target.get("discoveredLabels") or {}
    scrape_url = str(target.get("scrapeUrl") or "")
    parsed_scrape = urlparse(scrape_url)
    if not (
        _prometheus_probe_type(target)
        or discovered.get("__param_target__")
        or parsed_scrape.path.rstrip("/").endswith("/probe")
    ):
        return None

    candidates = [
        labels.get("blackbox_address"),
        discovered.get("blackbox_address"),
        parsed_scrape.netloc,
    ]
    for candidate in candidates:
        address, port = _host_port_from_value(candidate)
        if address:
            return {
                "address": address,
                "port": port or "9115",
                "health": str(target.get("health") or "unknown").lower(),
                "last_error": str(target.get("lastError") or ""),
                "last_scrape": str(target.get("lastScrape") or ""),
            }
    return None


def _legacy_http_sd_state(session, prometheus_url):
    state = {"checked": False, "detected": False, "endpoints": [], "error": ""}
    try:
        response = session.get(
            f"{prometheus_url}/api/v1/status/config",
            timeout=10,
        )
        response.raise_for_status()
        config_yaml = str(response.json().get("data", {}).get("yaml") or "")
        endpoints = []
        for line in config_yaml.splitlines():
            value = line.strip().strip("'\"")
            if "18081" in value or "/api/prometheus/http-sd/" in value:
                endpoints.append(value.removeprefix("- url:").strip())
        state.update(
            checked=True,
            detected=bool(endpoints),
            endpoints=list(dict.fromkeys(endpoints)),
        )
    except Exception as exc:
        state["error"] = str(exc)
    return state


def prometheus_probe_node_discoveries():
    prometheus_url = str(monitoring_config().get("prometheus_url") or "").rstrip("/")
    managed_node_records = list(
        BlackboxProbeNode.objects.all().only("id", "address", "port")
    )
    managed_nodes = {
        _probe_node_endpoint_key(node.address, node.port): {
            "node_id": node.id,
            "endpoint": f"{node.address}:{node.port}",
            "health": "unknown",
            "last_error": "",
            "last_scrape": "",
        }
        for node in managed_node_records
    }
    result = {
        "configured": bool(prometheus_url),
        "connected": False,
        "prometheus_url": prometheus_url,
        "error": "",
        "discoveries": [],
        "managed_nodes": list(managed_nodes.values()),
        "unbound_target_count": ProbeTarget.objects.filter(
            enabled=True,
            probe_node__isnull=True,
        ).count(),
        "legacy_http_sd": {
            "checked": False,
            "detected": False,
            "endpoints": [],
            "error": "",
        },
    }
    if not prometheus_url:
        result["error"] = "prometheus url is not configured"
        return result

    session = requests.Session()
    session.trust_env = False
    try:
        response = session.get(
            f"{prometheus_url}/api/v1/targets",
            params={"state": "active"},
            timeout=10,
        )
        response.raise_for_status()
        active_targets = response.json().get("data", {}).get("activeTargets", [])
    except Exception as exc:
        result["error"] = str(exc)
        return result

    discoveries = {}
    for target in active_targets:
        runtime_item = _managed_probe_node_runtime_target(target)
        if runtime_item:
            runtime_key = _probe_node_endpoint_key(
                runtime_item["address"], runtime_item["port"]
            )
            current_runtime = managed_nodes.get(runtime_key)
            if current_runtime and (
                current_runtime["health"] != "up"
                or runtime_item["health"] == "up"
            ):
                current_runtime.update(
                    health=runtime_item["health"],
                    last_error=runtime_item["last_error"],
                    last_scrape=runtime_item["last_scrape"],
                )

        item = _blackbox_exporter_target(target)
        if not item:
            continue
        key = _probe_node_endpoint_key(item["address"], item["port"])
        if key in managed_nodes:
            managed_nodes[key].update(
                health=item["health"],
                last_error=item["last_error"],
                last_scrape=item["last_scrape"],
            )
            continue
        current = discoveries.get(key)
        if not current or (current["health"] != "up" and item["health"] == "up"):
            discoveries[key] = item

    result.update(
        connected=True,
        managed_nodes=sorted(
            managed_nodes.values(),
            key=lambda item: item["node_id"],
        ),
        discoveries=sorted(
            discoveries.values(),
            key=lambda item: (item["address"].lower(), item["port"]),
        ),
        legacy_http_sd=_legacy_http_sd_state(session, prometheus_url),
    )
    return result


class ProbeNodeAlreadyManaged(Exception):
    pass


@transaction.atomic
def onboard_prometheus_probe_node(
    *, address, port="9115", name="", bind_unassigned_targets=False
):
    address = str(address or "").strip()
    port = str(port or "9115").strip() or "9115"
    if BlackboxProbeNode.objects.filter(address__iexact=address, port=port).exists():
        raise ProbeNodeAlreadyManaged(f"{address}:{port}")

    requested_name = str(name or "").strip()
    if not requested_name:
        safe_endpoint = "".join(
            character if character.isalnum() else "-"
            for character in f"{address}-{port}".lower()
        ).strip("-")
        requested_name = f"blackbox-{safe_endpoint}"[:120]
    if BlackboxProbeNode.objects.filter(name=requested_name).exists():
        raise ValueError("probe node name already exists")

    node = BlackboxProbeNode.objects.create(
        name=requested_name,
        address=address,
        port=port,
        source=BlackboxProbeNode.SOURCE_PROMETHEUS,
        enabled=True,
        labels={"discovered_from": "prometheus"},
    )
    bound_target_count = 0
    if bind_unassigned_targets:
        bound_target_count = ProbeTarget.objects.filter(
            enabled=True,
            probe_node__isnull=True,
        ).update(probe_node=node)
    return node, bound_target_count


def _snapshot_scrape_endpoint(snapshot):
    raw = snapshot.raw if isinstance(snapshot.raw, dict) else {}
    scrape_url = raw.get("scrapeUrl") or raw.get("scrape_url") or ""
    parsed = urlparse(str(scrape_url or ""))
    if parsed.hostname:
        return parsed.hostname.lower(), str(parsed.port or "")

    parsed_instance = urlparse(str(snapshot.instance or ""))
    if parsed_instance.hostname:
        return parsed_instance.hostname.lower(), str(parsed_instance.port or "")
    return "", ""


def _host_port_from_value(value):
    item = str(value or "").strip()
    if not item:
        return "", ""
    parsed = urlparse(item if "://" in item else f"//{item}")
    if parsed.hostname:
        return parsed.hostname, str(parsed.port or "")
    if ":" in item:
        host, port = item.rsplit(":", 1)
        return host.strip(), port.strip()
    return item, ""


def _managed_host_keys():
    keys = set()
    for host in MonitoringHost.objects.all():
        for value in [host.hostname, host.address]:
            item = str(value or "").strip().lower()
            if item:
                keys.add(item)
    return keys


def _is_managed_asset(hostname, address, managed_keys):
    for value in [hostname, address]:
        item = str(value or "").strip().lower()
        if item and item in managed_keys:
            return True
    return False


def n9e_target_connection_address(raw, fallback=""):
    if not isinstance(raw, dict):
        return str(fallback or "").strip()
    for key in (
        "remote_addr",
        "connect_addr",
        "connection_address",
        "management_ip",
        "mgmt_ip",
        "ssh_ip",
        "ssh_host",
        "ip",
        "address",
        "addr",
        "host_ip",
    ):
        value = str(raw.get(key) or "").strip()
        if value:
            return value
    return str(fallback or "").strip()


def assets_reconciliation_summary():
    managed_keys = _managed_host_keys()
    results = []

    for target in N9eTargetSnapshot.objects.all().order_by("hostname", "identity"):
        hostname = target.hostname or target.identity
        address = n9e_target_connection_address(target.raw, target.address)
        if _is_managed_asset(hostname, address, managed_keys):
            continue
        results.append(
            {
                "source": "n9e",
                "key": target.identity,
                "hostname": hostname,
                "address": address,
                "port": "",
                "health": "",
                "labels": target.labels or {},
                "last_seen_at": target.last_seen_at.isoformat()
                if target.last_seen_at
                else "",
                "can_import": bool(hostname or address),
            }
        )

    for target in PrometheusTargetSnapshot.objects.all().order_by("job", "instance"):
        if target.probe_type or target.probe_target:
            continue
        host_value, port = _host_port_from_value(target.instance or target.identity)
        hostname = host_value
        address = host_value
        if _is_managed_asset(hostname, address, managed_keys):
            continue
        results.append(
            {
                "source": "prometheus",
                "key": target.identity,
                "hostname": hostname,
                "address": address,
                "port": port,
                "health": target.health,
                "labels": (target.raw or {}).get("labels", {})
                if isinstance(target.raw, dict)
                else {},
                "last_seen_at": target.last_seen_at.isoformat()
                if target.last_seen_at
                else "",
                "can_import": bool(address),
            }
        )

    summary = {
        "hyperops_hosts": MonitoringHost.objects.count(),
        "n9e_only": sum(1 for item in results if item["source"] == "n9e"),
        "prometheus_only": sum(
            1 for item in results if item["source"] == "prometheus"
        ),
    }
    summary["unmanaged"] = summary["n9e_only"] + summary["prometheus_only"]
    return {"summary": summary, "results": results}


def _blackbox_prometheus_targets_by_endpoint():
    rows = {}
    snapshots = PrometheusTargetSnapshot.objects.all()
    for snapshot in snapshots:
        marker = " ".join(
            [
                snapshot.job or "",
                snapshot.scrape_pool or "",
                snapshot.probe_type or "",
                str((snapshot.raw or {}).get("scrapeUrl") or ""),
            ]
        ).lower()
        if "blackbox" not in marker and not snapshot.probe_type:
            continue
        host, port = _snapshot_scrape_endpoint(snapshot)
        if not host:
            continue
        rows.setdefault((host, port), []).append(snapshot)
    return rows


def blackbox_instances_summary():
    config = monitoring_config()
    default_port = str(config.get("installer", {}).get("blackbox_port") or "9115")
    statuses = (
        MonitoringComponentStatus.objects.filter(
            component=AnsibleInstallJob.COMPONENT_BLACKBOX
        )
        .select_related("host", "last_job")
        .order_by("host__hostname", "host__id")
    )
    targets_by_endpoint = _blackbox_prometheus_targets_by_endpoint()
    results = []
    for status in statuses:
        host = status.host
        last_job = status.last_job
        port = str(getattr(last_job, "blackbox_port", "") or default_port)
        endpoint_keys = {
            (str(host.address or "").strip().lower(), port),
            (str(host.hostname or "").strip().lower(), port),
            (str(host.address or "").strip().lower(), ""),
            (str(host.hostname or "").strip().lower(), ""),
        }
        endpoint_keys.discard(("", port))
        endpoint_keys.discard(("", ""))
        matched_targets = []
        for key in endpoint_keys:
            matched_targets.extend(targets_by_endpoint.get(key, []))
        seen = set()
        unique_targets = []
        for item in matched_targets:
            if item.id in seen:
                continue
            seen.add(item.id)
            unique_targets.append(item)

        if not unique_targets:
            prometheus_status = "not_discovered"
        elif any(str(item.health or "").lower() != "up" for item in unique_targets):
            prometheus_status = "down"
        else:
            prometheus_status = "up"

        target_summaries = [
            {
                "type": item.probe_type,
                "target": item.probe_target or item.instance,
                "health": item.health,
                "last_error": item.last_error,
                "scrape_pool": item.scrape_pool,
            }
            for item in unique_targets
        ]
        results.append(
            {
                "host_id": host.id,
                "hostname": host.hostname,
                "address": host.address,
                "port": port,
                "probe_name": getattr(last_job, "probe_name", "") or "",
                "install_dir": status.install_dir
                or getattr(last_job, "install_dir", "")
                or config.get("installer", {}).get("blackbox_dir", ""),
                "image": getattr(last_job, "image", "")
                or config.get("installer", {}).get("blackbox_image", ""),
                "install_status": status.status,
                "last_error": status.last_error,
                "last_job_id": getattr(last_job, "id", None),
                "prometheus_status": prometheus_status,
                "probe_target_count": len(unique_targets),
                "probe_targets": target_summaries,
            }
        )

    summary = {
        "total": len(results),
        "installed": sum(
            1
            for item in results
            if item["install_status"] == MonitoringComponentStatus.STATUS_SUCCESS
        ),
        "abnormal": sum(
            1
            for item in results
            if item["install_status"] != MonitoringComponentStatus.STATUS_SUCCESS
            or item["prometheus_status"] == "down"
        ),
        "prometheus_discovered": sum(
            1 for item in results if item["prometheus_status"] != "not_discovered"
        ),
    }
    return {"summary": summary, "results": results}


def installer_asset_info(name):
    path = installer_dir() / name
    if not path.exists() or not path.is_file():
        return {"name": name, "exists": False, "size": 0, "sha256": ""}
    return {
        "name": name,
        "exists": True,
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def installer_assets():
    return {
        "installer_dir": str(installer_dir()),
        "template_dir": str(template_dir()),
        "assets": {
            name: installer_asset_info(name)
            for name in sorted(INSTALLER_DOWNLOAD_FILES)
        },
    }


def installer_file_path(file_name):
    if file_name not in INSTALLER_DOWNLOAD_FILES:
        return None
    path = installer_dir() / file_name
    if not path.exists() or not path.is_file():
        return None
    return path


def atomic_write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    os.chmod(tmp_path, 0o644)
    tmp_path.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_template_path(path: Path, description: str):
    if not path.exists():
        raise ValueError(f"{description} 不存在: {path}")


def create_tar_gz(output_path: Path, entries: list[tuple[Path, str]]):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=output_path.parent, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with tarfile.open(tmp_path, "w:gz") as archive:
            for source, arcname in entries:
                archive.add(source, arcname=arcname)
        os.chmod(tmp_path, 0o644)
        tmp_path.replace(output_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def write_checksum(checksum_path: Path, archive_path: Path):
    atomic_write(checksum_path, f"{sha256_file(archive_path)}  {archive_path.name}\n")


def build_installer_archives():
    base_template_dir = template_dir()
    categraf_template = base_template_dir / "categraf"
    blackbox_template = base_template_dir / "blackbox"
    ensure_template_path(
        categraf_template / "docker-compose.yml",
        "Categraf docker-compose 模板",
    )
    ensure_template_path(categraf_template / "conf", "Categraf conf 模板目录")
    ensure_template_path(
        blackbox_template / "docker-compose.yml",
        "blackbox docker-compose 模板",
    )
    ensure_template_path(blackbox_template / "config", "blackbox config 模板目录")

    base_installer_dir = installer_dir()
    base_installer_dir.mkdir(parents=True, exist_ok=True)
    categraf_archive = base_installer_dir / "categraf-client.tar.gz"
    blackbox_archive = base_installer_dir / "blackbox-client.tar.gz"

    create_tar_gz(
        categraf_archive,
        [
            (categraf_template / "docker-compose.yml", "docker-compose.yml"),
            (categraf_template / "conf", "conf"),
        ],
    )
    write_checksum(base_installer_dir / "SHA256SUMS", categraf_archive)

    create_tar_gz(
        blackbox_archive,
        [
            (blackbox_template / "docker-compose.yml", "docker-compose.yml"),
            (blackbox_template / "config", "config"),
        ],
    )
    write_checksum(base_installer_dir / "BLACKBOX_SHA256SUMS", blackbox_archive)
    for script in ["install.sh", "install-blackbox.sh"]:
        path = base_installer_dir / script
        if path.exists():
            os.chmod(path, 0o755)
    return installer_assets()


def selected_hosts(host_ids):
    qs = MonitoringHost.objects.select_related("ssh_key_credential")
    if host_ids:
        qs = qs.filter(id__in=host_ids)
    return list(qs.order_by("hostname", "id"))


def merged_profiles(host, job_profiles):
    return clean_string_list([*(host.profiles or []), *(job_profiles or [])])


def categraf_install_args(host, job):
    labels = {**clean_labels(host.labels), **clean_labels(job.get("labels"))}
    profiles = merged_profiles(host, job.get("profiles") or [])
    role = "docker-host" if "docker-host" in profiles else "linux-host"
    args = [
        "--base-url",
        str(job["base_url"]).rstrip("/"),
        "--n9e",
        str(job["n9e_url"]).rstrip("/"),
        "--region",
        labels.get("region", "center"),
        "--env",
        labels.get("env", "prod"),
        "--team",
        labels.get("team", "ops"),
        "--service",
        labels.get("service", "infra"),
        "--role",
        role,
        "--hostname",
        host.hostname,
        "--dir",
        job.get("install_dir") or "/opt/categraf",
        "--image",
        job.get("image") or "flashcatcloud/categraf:latest",
    ]
    if "docker-host" not in profiles:
        args.append("--no-docker")
    for profile in profiles:
        args.extend(["--profile", profile])

    params = {**clean_labels(host.params), **clean_labels(job.get("params"))}
    option_map = {
        "mysql_address": "--mysql-address",
        "mysql_user": "--mysql-user",
        "mysql_password": "--mysql-password",
        "mysql_parameters": "--mysql-parameters",
        "redis_address": "--redis-address",
        "redis_username": "--redis-username",
        "redis_password": "--redis-password",
        "nginx_status_url": "--nginx-status-url",
    }
    for key, option in option_map.items():
        if params.get(key):
            args.extend([option, params[key]])
    return args


def blackbox_install_args(host, job):
    labels = {**clean_labels(host.labels), **clean_labels(job.get("labels"))}
    probe_name = (
        job.get("probe_name") or labels.get("probe_name") or f"blackbox-{host.hostname}"
    )
    return [
        "--base-url",
        str(job["base_url"]).rstrip("/"),
        "--region",
        labels.get("region", "center"),
        "--name",
        probe_name,
        "--port",
        job.get("blackbox_port") or "9115",
        "--dir",
        job.get("install_dir") or "/opt/blackbox-exporter",
        "--image",
        job.get("image") or "prom/blackbox-exporter:latest",
    ]


def host_install_args(host, job):
    if job.get("component") == AnsibleInstallJob.COMPONENT_BLACKBOX:
        return blackbox_install_args(host, job)
    return categraf_install_args(host, job)


def install_command_for_host(host, job):
    base_url = str(job["base_url"]).rstrip("/")
    args = " ".join(shlex.quote(str(arg)) for arg in host_install_args(host, job))
    script = (
        "install-blackbox.sh"
        if job.get("component") == AnsibleInstallJob.COMPONENT_BLACKBOX
        else "install.sh"
    )
    script_url = shlex.quote(base_url + "/" + script)
    return f"curl -fsSL {script_url} | sudo bash -s -- {args}"


def render_inventory(hosts):
    lines = ["[categraf_targets]"]
    for host in hosts:
        key_path = (
            host_ssh_key_path(host)
            if host.ssh_auth_type == MonitoringHost.SSH_AUTH_KEY
            else None
        )
        key_arg = (
            f" ansible_ssh_private_key_file={shlex.quote(str(key_path))}"
            if key_path
            else ""
        )
        password_arg = (
            f" ansible_password={shlex.quote(str(host.ssh_password))}"
            if host.ssh_auth_type == MonitoringHost.SSH_AUTH_PASSWORD
            and host.ssh_password
            else ""
        )
        lines.append(
            f"{host.hostname} ansible_host={host.address} "
            f"ansible_user={host.ssh_user or 'root'} "
            f"ansible_port={host.ssh_port or 22} "
            f"ansible_connection=ssh{key_arg}{password_arg}"
        )
    return "\n".join(lines) + "\n"


def job_vars(job, hosts):
    return {
        "component": job.get("component") or AnsibleInstallJob.COMPONENT_CATEGRAF,
        "profiles": clean_string_list(job.get("profiles") or []),
        "labels": clean_labels(job.get("labels")),
        "params": clean_labels(job.get("params")),
        "hosts": [
            {
                "id": host.id,
                "hostname": host.hostname,
                "address": host.address,
                "ssh_user": host.ssh_user or "root",
                "ssh_port": host.ssh_port or 22,
                "ssh_auth_type": host.ssh_auth_type,
                "ssh_key": clean_ssh_key(
                    host.ssh_key_credential.file_name
                    if host.ssh_key_credential_id
                    else host.ssh_key
                ),
                "ssh_key_name": (
                    host.ssh_key_credential.name if host.ssh_key_credential_id else ""
                ),
                "has_ssh_password": bool(host.ssh_password),
                "labels": clean_labels(host.labels),
                "params": clean_labels(host.params),
                "profiles": merged_profiles(host, job.get("profiles") or []),
                "install_command": install_command_for_host(host, job),
            }
            for host in hosts
        ],
    }


def build_ansible_preview(
    host_ids,
    profiles,
    base_url="",
    n9e_url="",
    install_dir="",
    image="",
    component=AnsibleInstallJob.COMPONENT_CATEGRAF,
    probe_name="",
    blackbox_port="",
    labels=None,
    params=None,
):
    config = monitoring_config()["installer"]
    is_blackbox = component == AnsibleInstallJob.COMPONENT_BLACKBOX
    job = {
        "component": component,
        "profiles": clean_string_list(profiles),
        "labels": clean_labels(labels),
        "params": clean_labels(params),
        "base_url": base_url
        or config.get("base_url")
        or "http://localhost:18080/api/v1/monitoring/installer",
        "n9e_url": (
            ""
            if is_blackbox
            else n9e_url or config.get("n9e_url") or "http://localhost:17000"
        ),
        "install_dir": install_dir
        or (config.get("blackbox_dir") if is_blackbox else config.get("install_dir"))
        or ("/opt/blackbox-exporter" if is_blackbox else "/opt/categraf"),
        "image": image
        or (
            config.get("blackbox_image")
            if is_blackbox
            else "flashcatcloud/categraf:latest"
        ),
        "probe_name": probe_name,
        "blackbox_port": blackbox_port or config.get("blackbox_port") or "9115",
    }
    hosts = selected_hosts(host_ids)
    return {
        "inventory": render_inventory(hosts),
        "vars": job_vars(job, hosts),
    }


def snapshot_hosts(hosts, job):
    return job_vars(job, hosts)["hosts"]


def update_component_statuses(job, hosts, status, last_error=""):
    component = job.component or AnsibleInstallJob.COMPONENT_CATEGRAF
    for host in hosts:
        MonitoringComponentStatus.objects.update_or_create(
            host=host,
            component=component,
            defaults={
                "status": status,
                "install_dir": job.install_dir or "",
                "last_job": job,
                "last_error": last_error or "",
            },
        )


def _blackbox_probe_node_name(host, job, host_count):
    base = str(job.probe_name or "").strip()
    if not base:
        base = f"blackbox-{host.hostname}"
    if host_count <= 1:
        return base
    return f"{base}-{host.hostname}"


def register_blackbox_probe_nodes(job, hosts):
    labels = clean_labels(job.labels)
    for host in hosts:
        name = _blackbox_probe_node_name(host, job, len(hosts))
        BlackboxProbeNode.objects.update_or_create(
            name=name,
            defaults={
                "address": host.address or host.hostname,
                "port": job.blackbox_port or "9115",
                "source": BlackboxProbeNode.SOURCE_INSTALL,
                "host": host,
                "install_dir": job.install_dir or "",
                "labels": {**clean_labels(host.labels), **labels},
                "enabled": True,
                "last_job": job,
            },
        )


def mark_component_installing(job, hosts):
    update_component_statuses(
        job,
        hosts,
        MonitoringComponentStatus.STATUS_INSTALLING,
    )


def mark_component_finished(job, hosts, status, logs=None):
    last_error = ""
    if status == MonitoringComponentStatus.STATUS_FAILED:
        last_error = "\n".join((logs or [])[-8:])
    update_component_statuses(job, hosts, status, last_error=last_error)
    if (
        job.component == AnsibleInstallJob.COMPONENT_BLACKBOX
        and status == MonitoringComponentStatus.STATUS_SUCCESS
    ):
        register_blackbox_probe_nodes(job, hosts)


def build_playbook(hosts, job):
    commands = {host.hostname: install_command_for_host(host, job) for host in hosts}
    is_blackbox = job.get("component") == AnsibleInstallJob.COMPONENT_BLACKBOX
    play_name = (
        "Install blackbox-exporter by unified installer"
        if is_blackbox
        else "Install Categraf by unified installer"
    )
    task_name = (
        "Run unified blackbox-exporter installer"
        if is_blackbox
        else "Run unified Categraf installer"
    )
    return [
        {
            "name": play_name,
            "hosts": "categraf_targets",
            "become": False,
            "gather_facts": False,
            "tasks": [
                {
                    "name": task_name,
                    "shell": "{{ install_commands[inventory_hostname] }}",
                    "args": {"executable": "/bin/bash"},
                    "vars": {"install_commands": commands},
                }
            ],
        }
    ]


def _parse_ansible_recap(logs):
    recap = {}
    in_recap = False
    for line in logs:
        stripped = line.strip()
        if stripped.startswith("PLAY RECAP"):
            in_recap = True
            continue
        if not in_recap:
            continue

        match = re.match(r"^(?P<hostname>\S+)\s*:\s*(?P<stats>.+)$", stripped)
        if not match:
            continue
        stats = {
            key: int(value)
            for key, value in re.findall(r"([a-z_]+)=(\d+)", match.group("stats"))
        }
        if "failed" not in stats and "unreachable" not in stats:
            continue
        recap[match.group("hostname")] = stats
    return recap


def _ansible_output_has_failure(logs):
    for line in logs:
        stripped = line.strip()
        if stripped.startswith("[ERROR]:"):
            return True
        if re.match(
            r"^fatal:\s*\[[^]]+\]:\s*(?:FAILED|UNREACHABLE)!",
            stripped,
            re.IGNORECASE,
        ):
            return True
    return False


def _ansible_execution_result(hosts, logs, process_returncode):
    recap = _parse_ansible_recap(logs)
    recap_failed = {
        hostname
        for hostname, stats in recap.items()
        if stats.get("failed", 0) > 0 or stats.get("unreachable", 0) > 0
    }
    output_failed = _ansible_output_has_failure(logs)
    execution_failed = process_returncode != 0 or output_failed or bool(recap_failed)
    unattributed_failure = (process_returncode != 0 or output_failed) and not recap_failed

    results = []
    for host in hosts:
        stats = recap.get(host.hostname)
        host_failed = host.hostname in recap_failed
        if stats is None and execution_failed:
            host_failed = True
        elif unattributed_failure:
            host_failed = True
        results.append(
            {
                "hostname": host.hostname,
                "status": (
                    AnsibleInstallJob.STATUS_FAILED
                    if host_failed
                    else AnsibleInstallJob.STATUS_SUCCESS
                ),
            }
        )

    status = (
        AnsibleInstallJob.STATUS_FAILED
        if execution_failed
        else AnsibleInstallJob.STATUS_SUCCESS
    )
    effective_returncode = process_returncode or (1 if execution_failed else 0)
    return status, effective_returncode, results


def mark_unreachable_host_verification_failed(hosts, logs):
    unreachable = {}
    for line in logs:
        match = re.match(
            r"^fatal:\s*\[([^]]+)]\s*:\s*UNREACHABLE!",
            str(line or "").strip(),
            re.IGNORECASE,
        )
        if not match:
            continue
        lowered = str(line or "").lower()
        if "error in libcrypto" in lowered or "invalid format" in lowered:
            code = "SSH_KEY_OR_PROTOCOL_FAILED"
        elif "permission denied" in lowered or "authentication failed" in lowered:
            code = "SSH_AUTH_FAILED"
        elif "timed out" in lowered or "timeout" in lowered:
            code = "SSH_TIMEOUT"
        else:
            code = "SSH_UNREACHABLE"
        unreachable[match.group(1)] = code

    update_fields = list(
        failed_verification_defaults(
            fingerprint="",
            error_code="SSH_UNREACHABLE",
        ).keys()
    )
    for host in hosts:
        code = unreachable.get(host.hostname)
        if not code:
            continue
        defaults = failed_verification_defaults(
            fingerprint=connection_fingerprint_for_host(host),
            error_code=code,
        )
        for field, value in defaults.items():
            setattr(host, field, value)
        host.save(update_fields=update_fields)


def execute_ansible_job(job_id):
    job = AnsibleInstallJob.objects.get(pk=job_id)
    hosts = selected_hosts(job.host_ids)
    job.status = AnsibleInstallJob.STATUS_RUNNING
    job.started_at = timezone.now()
    job.progress = build_progress("preparing")
    job.save(update_fields=["status", "started_at", "progress"])
    mark_component_installing(job, hosts)

    if not hosts:
        job.status = AnsibleInstallJob.STATUS_FAILED
        job.returncode = 1
        job.logs = ["no enabled hosts selected"]
        job.results = []
        job.progress = build_progress("failed", message="no_hosts")
        job.finished_at = timezone.now()
        job.save(
            update_fields=[
                "status",
                "returncode",
                "logs",
                "results",
                "progress",
                "finished_at",
            ]
        )
        return job

    if not shutil.which("ansible-playbook"):
        job.status = AnsibleInstallJob.STATUS_FAILED
        job.returncode = 127
        job.logs = ["ansible-playbook not found"]
        job.results = [
            {"hostname": host.hostname, "status": "failed"} for host in hosts
        ]
        job.progress = build_progress("failed", message="ansible_missing")
        job.finished_at = timezone.now()
        job.save(
            update_fields=[
                "status",
                "returncode",
                "logs",
                "results",
                "progress",
                "finished_at",
            ]
        )
        mark_component_finished(
            job,
            hosts,
            MonitoringComponentStatus.STATUS_FAILED,
            job.logs,
        )
        return job

    payload = {
        "component": job.component,
        "profiles": job.profiles,
        "labels": job.labels,
        "params": job.params,
        "base_url": job.base_url,
        "n9e_url": job.n9e_url,
        "install_dir": job.install_dir,
        "image": job.image,
        "probe_name": job.probe_name,
        "blackbox_port": job.blackbox_port,
    }
    logs = []
    current_stage = "connecting"
    current_host = ""
    with tempfile.TemporaryDirectory(prefix="hyperops-monitoring-ansible-") as tmp:
        tmp_path = Path(tmp)
        inventory_path = tmp_path / "inventory.ini"
        playbook_path = tmp_path / "playbook.yml"
        inventory_path.write_text(render_inventory(hosts), encoding="utf-8")
        playbook_path.write_text(
            yaml.safe_dump(
                build_playbook(hosts, payload), allow_unicode=True, sort_keys=False
            ),
            encoding="utf-8",
        )
        proc = subprocess.Popen(
            ["ansible-playbook", "-i", str(inventory_path), str(playbook_path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            env={
                **os.environ,
                "ANSIBLE_HOST_KEY_CHECKING": "False",
                "ANSIBLE_FORCE_COLOR": "0",
                "PYTHONUNBUFFERED": "1",
            },
        )
        job.progress = build_progress("connecting")
        job.save(update_fields=["progress"])

        def persist_output(lines, stage):
            nonlocal current_stage, current_host
            logs.extend(lines)
            if stage:
                current_stage = stage
            for line in reversed(lines):
                line_host = current_host_for_line(line)
                if line_host:
                    current_host = line_host
                    break
            job.logs = list(logs)
            job.progress = build_progress(
                current_stage,
                current_host=current_host,
            )
            job.save(update_fields=["logs", "progress"])

        stream_result = stream_process_output(
            proc,
            timeout_seconds=1800,
            on_flush=persist_output,
        )

    status, effective_returncode, results = _ansible_execution_result(
        hosts,
        logs,
        stream_result.returncode,
    )
    job.status = status
    job.returncode = effective_returncode
    job.logs = logs
    job.results = results
    job.progress = build_progress(
        "completed" if status == AnsibleInstallJob.STATUS_SUCCESS else "failed",
        current_host=current_host,
        reason_code=(
            failure_reason_code(logs, timed_out=stream_result.timed_out)
            if status == AnsibleInstallJob.STATUS_FAILED
            else "completed"
        ),
    )
    job.finished_at = timezone.now()
    job.save(
        update_fields=[
            "status",
            "returncode",
            "logs",
            "results",
            "progress",
            "finished_at",
        ]
    )
    if status == AnsibleInstallJob.STATUS_FAILED:
        mark_unreachable_host_verification_failed(hosts, logs)
    mark_component_finished(
        job,
        hosts,
        (
            MonitoringComponentStatus.STATUS_SUCCESS
            if status == AnsibleInstallJob.STATUS_SUCCESS
            else MonitoringComponentStatus.STATUS_FAILED
        ),
        logs,
    )
    return job
