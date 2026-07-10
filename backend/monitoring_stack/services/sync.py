from urllib.parse import parse_qs, urlparse

import requests
from django.conf import settings
from django.utils import timezone
from monitoring_stack.models import (
    MonitoringSnapshotRun,
    N9eBusinessGroupSnapshot,
    N9eDatasourceSnapshot,
    N9eRuleSnapshot,
    N9eTargetSnapshot,
    PrometheusTargetSnapshot,
)
from monitoring_stack.services.core import (
    _fetch_n9e_collection,
    _n9e_payload_data,
    configured_value,
    integration_config,
    monitoring_config,
    n9e_target_connection_address,
)


def _string(value):
    return str(value or "").strip()


def _payload_items(payload):
    data = _n9e_payload_data(payload)
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ("list", "items", "data", "records"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def _n9e_session():
    config = monitoring_config()
    n9e_url = _string(config.get("n9e_url")).rstrip("/")
    runtime = integration_config()
    username = _string(
        configured_value(runtime, "n9e_username", "MONITORING_N9E_USERNAME", "")
    )
    password = _string(
        configured_value(runtime, "n9e_password", "MONITORING_N9E_PASSWORD", "")
    )
    if not n9e_url:
        raise ValueError("n9e url is not configured")
    if not username or not password:
        raise ValueError("n9e credentials are not configured")

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
        raise ValueError("n9e login failed")
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session, n9e_url


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


def _upsert_group(run, item, seen_at):
    external_id = _string(item.get("id") or item.get("ident") or item.get("uuid"))
    if not external_id:
        return False
    N9eBusinessGroupSnapshot.objects.update_or_create(
        external_id=external_id,
        defaults={
            "name": _string(item.get("name") or item.get("label")),
            "raw": item,
            "last_seen_run": run,
            "last_seen_at": seen_at,
        },
    )
    return True


def _upsert_datasource(run, item, seen_at):
    external_id = _string(item.get("id") or item.get("ident") or item.get("uuid"))
    if not external_id:
        return False
    N9eDatasourceSnapshot.objects.update_or_create(
        external_id=external_id,
        defaults={
            "name": _string(item.get("name") or item.get("label")),
            "type": _string(item.get("plugin_type") or item.get("type")),
            "raw": item,
            "last_seen_run": run,
            "last_seen_at": seen_at,
        },
    )
    return True


def _upsert_target(run, item, seen_at):
    hostname = _string(
        item.get("hostname")
        or item.get("host")
        or item.get("ident")
        or item.get("name")
    )
    address = n9e_target_connection_address(item)
    identity = _string(
        item.get("ident")
        or item.get("identity")
        or item.get("id")
        or hostname
        or address
    )
    if not identity:
        return False
    labels = item.get("labels") if isinstance(item.get("labels"), dict) else {}
    N9eTargetSnapshot.objects.update_or_create(
        identity=identity,
        defaults={
            "hostname": hostname,
            "address": address,
            "labels": labels,
            "raw": item,
            "last_seen_run": run,
            "last_seen_at": seen_at,
        },
    )
    return True


def _upsert_rule(run, group_id, item, seen_at):
    rule_id = _string(item.get("id") or item.get("ident") or item.get("uuid"))
    identity = f"{group_id}:{rule_id}" if rule_id else ""
    if not identity:
        return False
    N9eRuleSnapshot.objects.update_or_create(
        identity=identity,
        defaults={
            "group_id": _string(group_id),
            "name": _string(item.get("name") or item.get("title")),
            "enabled": _n9e_rule_enabled(item),
            "severity": _string(item.get("severity") or item.get("priority")),
            "raw": item,
            "last_seen_run": run,
            "last_seen_at": seen_at,
        },
    )
    return True


def sync_n9e_snapshot(run):
    session, n9e_url = _n9e_session()
    seen_at = timezone.now()
    summary = {
        "n9e_business_groups": 0,
        "n9e_datasources": 0,
        "n9e_targets": 0,
        "n9e_rules": 0,
    }

    groups_response = session.get(f"{n9e_url}/api/n9e/busi-groups", timeout=10)
    groups_response.raise_for_status()
    groups = _payload_items(groups_response.json())
    for item in groups:
        if isinstance(item, dict) and _upsert_group(run, item, seen_at):
            summary["n9e_business_groups"] += 1

    datasources_response = session.get(
        f"{n9e_url}/api/n9e/datasource/brief",
        timeout=10,
    )
    datasources_response.raise_for_status()
    for item in _payload_items(datasources_response.json()):
        if isinstance(item, dict) and _upsert_datasource(run, item, seen_at):
            summary["n9e_datasources"] += 1

    for path in (
        "/api/n9e/targets",
        "/api/n9e/target/list",
        "/api/n9e/objects",
        "/api/n9e/object/list",
    ):
        try:
            _count, targets = _fetch_n9e_collection(session, f"{n9e_url}{path}")
        except Exception:
            continue
        for item in targets:
            if isinstance(item, dict) and _upsert_target(run, item, seen_at):
                summary["n9e_targets"] += 1
        break

    for group in groups:
        if not isinstance(group, dict):
            continue
        group_id = group.get("id")
        if not group_id:
            continue
        try:
            _count, rules = _fetch_n9e_collection(
                session,
                f"{n9e_url}/api/n9e/busi-group/{group_id}/alert-rules",
            )
        except Exception:
            continue
        for item in rules:
            if isinstance(item, dict) and _upsert_rule(run, group_id, item, seen_at):
                summary["n9e_rules"] += 1

    return summary


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
        item = _string(value)
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
        item = _string(value).lower()
        if item in {"http", "tcp", "icmp"}:
            return item
    return ""


def sync_prometheus_snapshot(run):
    prometheus_url = _string(monitoring_config().get("prometheus_url")).rstrip("/")
    if not prometheus_url:
        raise ValueError("prometheus url is not configured")

    session = requests.Session()
    session.trust_env = False
    response = session.get(
        f"{prometheus_url}/api/v1/targets",
        params={"state": "active"},
        timeout=10,
    )
    response.raise_for_status()
    active_targets = response.json().get("data", {}).get("activeTargets", [])
    seen_at = timezone.now()
    summary = {
        "prometheus_targets": 0,
        "prometheus_down_targets": 0,
        "prometheus_blackbox_targets": 0,
    }

    for target in active_targets:
        if not isinstance(target, dict):
            continue
        labels = target.get("labels") or {}
        target_value = _prometheus_target_value(target)
        scrape_pool = _string(target.get("scrapePool"))
        identity = f"{scrape_pool}|{target_value or labels.get('instance') or ''}"
        identity = identity.strip("|")
        if not identity:
            continue
        health = _string(target.get("health") or "unknown").lower()
        probe_type = _prometheus_probe_type(target)
        is_blackbox = bool(
            probe_type
            or "blackbox" in _string(labels.get("job")).lower()
            or "blackbox" in scrape_pool.lower()
        )
        PrometheusTargetSnapshot.objects.update_or_create(
            identity=identity,
            defaults={
                "job": _string(labels.get("job")),
                "instance": _string(labels.get("instance")),
                "scrape_pool": scrape_pool,
                "health": health,
                "probe_type": probe_type,
                "probe_target": target_value,
                "last_error": _string(target.get("lastError")),
                "raw": target,
                "last_seen_run": run,
                "last_seen_at": seen_at,
            },
        )
        summary["prometheus_targets"] += 1
        if health == "down":
            summary["prometheus_down_targets"] += 1
        if is_blackbox:
            summary["prometheus_blackbox_targets"] += 1

    return summary


def sync_monitoring_snapshots(source=MonitoringSnapshotRun.SOURCE_ALL):
    source = _string(source or MonitoringSnapshotRun.SOURCE_ALL).lower()
    if source not in {
        MonitoringSnapshotRun.SOURCE_ALL,
        MonitoringSnapshotRun.SOURCE_N9E,
        MonitoringSnapshotRun.SOURCE_PROMETHEUS,
    }:
        raise ValueError("invalid monitoring snapshot source")

    run = MonitoringSnapshotRun.objects.create(
        source=source,
        status=MonitoringSnapshotRun.STATUS_RUNNING,
        started_at=timezone.now(),
    )
    summary = {}
    try:
        if source in {MonitoringSnapshotRun.SOURCE_ALL, MonitoringSnapshotRun.SOURCE_N9E}:
            summary.update(sync_n9e_snapshot(run))
        if source in {
            MonitoringSnapshotRun.SOURCE_ALL,
            MonitoringSnapshotRun.SOURCE_PROMETHEUS,
        }:
            summary.update(sync_prometheus_snapshot(run))
    except Exception as exc:
        run.status = MonitoringSnapshotRun.STATUS_FAILED
        run.error = str(exc)
        run.summary = summary
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error", "summary", "finished_at"])
        return run

    run.status = MonitoringSnapshotRun.STATUS_SUCCESS
    run.summary = summary
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "summary", "finished_at"])
    return run
