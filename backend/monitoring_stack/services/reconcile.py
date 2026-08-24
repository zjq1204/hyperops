import json

import yaml
from monitoring_stack.models import (
    AnsibleInstallJob,
    MonitoringComponentStatus,
    MonitoringGovernanceFinding,
    MonitoringHost,
    MonitoringSnapshotRun,
    N9eTargetSnapshot,
    N9eRuleSnapshot,
    ProbeTarget,
    PrometheusTargetSnapshot,
    RuleImportRecord,
)
from monitoring_stack.services.core import (
    blackbox_health_for_host,
    host_visible_in_n9e,
    rules_dir,
)
from monitoring_stack.services.job_history import (
    FAILED_STATUSES,
    build_host_job_summaries,
)

MANAGED_CATEGORIES = {
    "host_not_in_n9e",
    "host_not_scraped_by_prometheus",
    "categraf_not_installed",
    "blackbox_not_installed",
    "probe_configured_not_discovered",
    "probe_discovered_not_configured",
    "probe_abnormal",
    "rule_template_not_imported",
    "n9e_rule_untracked",
    "install_job_failed",
}


def _probe_key(target_type, target):
    return f"{target_type}:{target}"


def _finding(category, severity, title, subject_type, subject_key, **kwargs):
    return MonitoringGovernanceFinding(
        category=category,
        severity=severity,
        status=MonitoringGovernanceFinding.STATUS_OPEN,
        title=title,
        subject_type=subject_type,
        subject_key=subject_key,
        source=kwargs.get("source", ""),
        details=kwargs.get("details", {}),
        recommended_action=kwargs.get("recommended_action", ""),
    )


def _component_installed(host, component, cache=None):
    status = next(
        (
            item
            for item in host.component_statuses.all()
            if item.component == component
        ),
        None,
    )
    if status and status.status == MonitoringComponentStatus.STATUS_SUCCESS:
        return True
    if component == AnsibleInstallJob.COMPONENT_CATEGRAF:
        return host_visible_in_n9e(host, cache=cache)
    if component == AnsibleInstallJob.COMPONENT_BLACKBOX:
        return (
            blackbox_health_for_host(host, cache=cache).get("runtime_status")
            == "online"
        )
    return False


def reconcile_hosts():
    findings = []
    n9e_targets = N9eTargetSnapshot.objects.all()
    if not n9e_targets.exists():
        return findings

    visible_keys = set()
    for target in n9e_targets:
        for value in [target.identity, target.hostname, target.address]:
            if value:
                visible_keys.add(str(value).strip().lower())

    for host in MonitoringHost.objects.filter(enabled=True):
        subject_key = host.hostname or host.address or str(host.id)
        host_keys = {
            str(value).strip().lower()
            for value in [host.hostname, host.address]
            if value
        }
        if host_keys & visible_keys:
            continue
        findings.append(
            _finding(
                "host_not_in_n9e",
                MonitoringGovernanceFinding.SEVERITY_WARNING,
                f"{subject_key} not visible in n9e",
                "host",
                subject_key,
                source="n9e",
                details={
                    "host_id": host.id,
                    "hostname": host.hostname,
                    "address": host.address,
                },
                recommended_action="check_n9e_registration",
            )
        )
    return findings


def _snapshot_is_blackbox(snapshot):
    marker = " ".join(
        [
            snapshot.job or "",
            snapshot.scrape_pool or "",
            snapshot.probe_type or "",
            snapshot.probe_target or "",
        ]
    ).lower()
    return "blackbox" in marker or bool(snapshot.probe_type or snapshot.probe_target)


def _snapshot_matches_host(snapshot, host):
    values = []
    raw = snapshot.raw if isinstance(snapshot.raw, dict) else {}
    values.extend([snapshot.identity, snapshot.instance])
    values.extend(_flatten_raw_strings(raw))
    needles = {
        str(host.hostname or "").strip().lower(),
        str(host.address or "").strip().lower(),
    }
    needles.discard("")
    for value in values:
        item = str(value or "").strip().lower()
        if not item:
            continue
        for needle in needles:
            if item == needle or item.startswith(f"{needle}:") or needle in item:
                return True
    return False


def _current_prometheus_snapshots():
    latest_run = (
        MonitoringSnapshotRun.objects.filter(
            source__in=[
                MonitoringSnapshotRun.SOURCE_ALL,
                MonitoringSnapshotRun.SOURCE_PROMETHEUS,
            ],
            status=MonitoringSnapshotRun.STATUS_SUCCESS,
        )
        .order_by("-started_at", "-id")
        .first()
    )
    if not latest_run:
        return PrometheusTargetSnapshot.objects.none()
    return PrometheusTargetSnapshot.objects.filter(last_seen_run=latest_run)


def _flatten_raw_strings(value):
    if isinstance(value, dict):
        rows = []
        for item in value.values():
            rows.extend(_flatten_raw_strings(item))
        return rows
    if isinstance(value, list):
        rows = []
        for item in value:
            rows.extend(_flatten_raw_strings(item))
        return rows
    if value is None:
        return []
    return [str(value)]


def reconcile_host_prometheus_scrapes():
    findings = []
    snapshots = [
        item
        for item in _current_prometheus_snapshots()
        if not _snapshot_is_blackbox(item)
    ]
    if not snapshots:
        return findings
    hosts = MonitoringHost.objects.filter(enabled=True).prefetch_related(
        "component_statuses"
    )
    cache = {}
    for host in hosts:
        if not _component_installed(
            host,
            AnsibleInstallJob.COMPONENT_CATEGRAF,
            cache=cache,
        ):
            continue
        if any(_snapshot_matches_host(item, host) for item in snapshots):
            continue
        subject_key = host.hostname or host.address or str(host.id)
        findings.append(
            _finding(
                "host_not_scraped_by_prometheus",
                MonitoringGovernanceFinding.SEVERITY_WARNING,
                f"{subject_key} not scraped by Prometheus",
                "host",
                subject_key,
                source="prometheus",
                details={
                    "host_id": host.id,
                    "hostname": host.hostname,
                    "address": host.address,
                },
                recommended_action="check_prometheus_scrape",
            )
        )
    return findings


def _configured_probe_keys():
    rows = {}
    for item in ProbeTarget.objects.filter(enabled=True):
        key = _probe_key(item.type, item.target)
        rows[key] = item
    return rows


def _discovered_probe_keys():
    rows = {}
    for item in _current_prometheus_snapshots().exclude(probe_target=""):
        if not item.probe_type:
            continue
        key = _probe_key(item.probe_type, item.probe_target)
        rows[key] = item
    return rows


def reconcile_probes():
    findings = []
    configured = _configured_probe_keys()
    discovered = _discovered_probe_keys()

    for key, item in configured.items():
        if key in discovered:
            continue
        findings.append(
            _finding(
                "probe_configured_not_discovered",
                MonitoringGovernanceFinding.SEVERITY_WARNING,
                f"{item.target} not discovered by Prometheus",
                "probe",
                key,
                source="hyperops",
                details={"type": item.type, "target": item.target},
                recommended_action="check_prometheus_sd",
            )
        )

    for key, item in discovered.items():
        if key not in configured:
            findings.append(
                _finding(
                    "probe_discovered_not_configured",
                    MonitoringGovernanceFinding.SEVERITY_WARNING,
                    f"{item.probe_target} not managed in HyperOps",
                    "probe",
                    key,
                    source="prometheus",
                    details={
                        "type": item.probe_type,
                        "target": item.probe_target,
                        "health": item.health,
                    },
                    recommended_action="create_probe_target",
                )
            )
        if item.health != "up":
            findings.append(
                _finding(
                    "probe_abnormal",
                    MonitoringGovernanceFinding.SEVERITY_CRITICAL,
                    f"{item.probe_target} probe abnormal",
                    "probe",
                    key,
                    source="prometheus",
                    details={
                        "type": item.probe_type,
                        "target": item.probe_target,
                        "health": item.health,
                        "last_error": item.last_error,
                    },
                    recommended_action="fix_probe_target",
                )
            )
    return findings


def _rule_template_files():
    base = rules_dir()
    if not base.exists():
        return []
    return sorted(
        path
        for path in base.iterdir()
        if path.is_file() and path.suffix.lower() in {".yml", ".yaml", ".json"}
    )


def _rule_template_alert_names(path=None):
    names = set()
    paths = [path] if path else _rule_template_files()
    for item in paths:
        try:
            if item.suffix.lower() == ".json":
                data = json.loads(item.read_text(encoding="utf-8"))
            else:
                data = yaml.safe_load(item.read_text(encoding="utf-8"))
        except Exception:
            continue
        for group in data.get("groups", []) if isinstance(data, dict) else []:
            if not isinstance(group, dict):
                continue
            for rule in group.get("rules", []) or []:
                if not isinstance(rule, dict):
                    continue
                alert = str(rule.get("alert") or "").strip()
                if alert:
                    names.add(alert)
    return names


def _n9e_rule_names():
    return {
        str(value).strip()
        for value in N9eRuleSnapshot.objects.values_list("name", flat=True)
        if str(value or "").strip()
    }


def _rule_template_alerts_exist_in_n9e(path, n9e_rule_names):
    alert_names = _rule_template_alert_names(path)
    return bool(alert_names) and alert_names.issubset(n9e_rule_names)


def _successful_imported_rule_files():
    return set(
        RuleImportRecord.objects.filter(
            status=RuleImportRecord.STATUS_SUCCESS
        ).values_list("rule_file", flat=True)
    )


def _imported_rule_names():
    names = _rule_template_alert_names()
    for rule_file in _successful_imported_rule_files():
        names.add(rule_file)
        names.add(rule_file.rsplit(".", 1)[0])
    return names


def reconcile_rules():
    findings = []
    imported_files = _successful_imported_rule_files()
    n9e_rule_names = _n9e_rule_names()
    for path in _rule_template_files():
        if path.name in imported_files:
            continue
        if _rule_template_alerts_exist_in_n9e(path, n9e_rule_names):
            continue
        findings.append(
            _finding(
                "rule_template_not_imported",
                MonitoringGovernanceFinding.SEVERITY_WARNING,
                f"{path.name} 尚未导入 n9e",
                "rule",
                path.name,
                source="hyperops",
                details={"rule_file": path.name},
                recommended_action="import_rule_template",
            )
        )

    imported_names = _imported_rule_names()
    for rule in N9eRuleSnapshot.objects.all():
        rule_name = rule.name or rule.identity
        if rule.identity in imported_names or rule_name in imported_names:
            continue
        findings.append(
            _finding(
                "n9e_rule_untracked",
                MonitoringGovernanceFinding.SEVERITY_INFO,
                f"{rule_name} 仅存在于 n9e",
                "rule",
                rule.identity,
                source="n9e",
                details={
                    "identity": rule.identity,
                    "name": rule.name,
                    "group_id": rule.group_id,
                    "enabled": rule.enabled,
                    "severity": rule.severity,
                },
                recommended_action="review_n9e_rule",
            )
        )
    return findings


def reconcile_failed_jobs():
    findings = []
    summaries = build_host_job_summaries(AnsibleInstallJob.objects.all())
    for host in summaries:
        for component, summary in host.get("components", {}).items():
            latest = summary.get("latest") or {}
            if str(latest.get("host_status") or "").lower() not in FAILED_STATUSES:
                continue
            job_id = latest.get("job_id")
            host_id = host.get("host_id")
            if not job_id or not host_id:
                continue
            findings.append(
                _finding(
                    "install_job_failed",
                    MonitoringGovernanceFinding.SEVERITY_WARNING,
                    f"{host.get('hostname')} {component} deployment failed",
                    "job",
                    f"{host_id}:{component}",
                    source="hyperops",
                    details={
                        "job_id": job_id,
                        "host_id": host_id,
                        "hostname": host.get("hostname"),
                        "component": component,
                        "failed_host_ids": [host_id],
                    },
                    recommended_action="retry_job",
                )
            )
    return findings


def rebuild_governance_findings():
    MonitoringGovernanceFinding.objects.filter(
        status=MonitoringGovernanceFinding.STATUS_OPEN,
        category__in=MANAGED_CATEGORIES,
    ).delete()
    findings = [
        *reconcile_hosts(),
        *reconcile_host_prometheus_scrapes(),
        *reconcile_probes(),
        *reconcile_rules(),
        *reconcile_failed_jobs(),
    ]
    if findings:
        MonitoringGovernanceFinding.objects.bulk_create(findings)
    return findings


def governance_overview():
    rebuild_governance_findings()
    prometheus_targets = _current_prometheus_snapshots()
    open_findings = MonitoringGovernanceFinding.objects.filter(
        status=MonitoringGovernanceFinding.STATUS_OPEN
    )
    return {
        "config_counts": {
            "hosts": MonitoringHost.objects.count(),
            "probe_targets": ProbeTarget.objects.count(),
            "rule_templates": len(_rule_template_files()),
        },
        "real_counts": {
            "prometheus_targets": prometheus_targets.count(),
            "prometheus_down_targets": prometheus_targets.filter(
                health="down"
            ).count(),
            "n9e_targets": N9eTargetSnapshot.objects.count(),
            "n9e_rules": N9eRuleSnapshot.objects.count(),
        },
        "finding_counts": {
            "open": open_findings.count(),
            "critical": open_findings.filter(
                severity=MonitoringGovernanceFinding.SEVERITY_CRITICAL
            ).count(),
            "warning": open_findings.filter(
                severity=MonitoringGovernanceFinding.SEVERITY_WARNING
            ).count(),
            "info": open_findings.filter(
                severity=MonitoringGovernanceFinding.SEVERITY_INFO
            ).count(),
        },
        "top_findings": open_findings[:8],
    }
