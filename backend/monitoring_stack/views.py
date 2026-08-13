from pathlib import Path
from types import SimpleNamespace

import requests
import yaml
from accounts.permissions import HasRequiredFeature
from django.conf import settings
from django.http import FileResponse
from django.db import transaction
from django.db.models import Count, Prefetch
from django.utils import timezone
from monitoring_stack.models import (
    AnsibleInstallJob,
    BlackboxProbeNode,
    MonitoringGovernanceFinding,
    MonitoringHost,
    MonitoringIntegrationConfig,
    MonitoringProfile,
    MonitoringSshCredential,
    MonitoringSshCredentialVersion,
    N9eRuleSnapshot,
    ProbeTarget,
    RuleImportRecord,
)
from monitoring_stack.serializers import (
    AnsibleInstallJobSerializer,
    AnsiblePreviewSerializer,
    BlackboxProbeNodeSerializer,
    MonitoringGovernanceFindingSerializer,
    MonitoringHostSerializer,
    MonitoringHostConnectionTestSerializer,
    MonitoringIntegrationConfigSerializer,
    MonitoringProfileSerializer,
    MonitoringSnapshotRunSerializer,
    CredentialCreateSerializer,
    CredentialDetailSerializer,
    CredentialListSerializer,
    CredentialRotateSerializer,
    PrometheusProbeNodeOnboardSerializer,
    ProbeTargetSerializer,
)
from monitoring_stack.services.core import (
    _fetch_n9e_collection,
    atomic_write,
    assets_reconciliation_summary,
    active_prometheus_http_sd_token,
    build_ansible_preview,
    blackbox_instances_summary,
    build_installer_archives,
    clean_labels,
    clean_string_list,
    ensure_default_profiles,
    installer_assets,
    installer_file_path,
    mark_component_installing,
    check_monitoring_ssh_connection,
    MonitoringSshConnectionError,
    monitoring_config,
    n9e_platform_summary,
    generate_prometheus_http_sd_token,
    prometheus_http_sd_config,
    prometheus_http_sd_state,
    prometheus_probe_node_discoveries,
    prometheus_targets_summary,
    onboard_prometheus_probe_node,
    ProbeNodeAlreadyManaged,
    render_http_sd_targets,
    rules_dir,
    selected_hosts,
    snapshot_hosts,
)
from monitoring_stack.services.job_dispatch import (
    JobDispatchError,
    dispatch_error_response,
    dispatch_install_job,
)
from monitoring_stack.permissions import (
    CredentialOperationPermission,
    has_credential_permission,
)
from monitoring_stack.services.credential_ingestion import (
    DuplicateCredentialFingerprint,
    PrivateKeyValidationError,
    create_credential_version,
)
from monitoring_stack.services.credential_lifecycle import (
    CredentialActivationError,
    CredentialLifecycleError,
    CredentialReferenceConflict,
    activate_version,
    archive_credential,
    delete_credential,
    record_credential_audit,
    request_context_from_request,
    validate_version_on_hosts,
)
from monitoring_stack.services.credential_runtime import (
    CredentialRuntimeError,
    DatabaseSshCredentialProvider,
    materialize_legacy_credential,
)
from monitoring_stack.services.reconcile import governance_overview
from monitoring_stack.services.ssh_verification import (
    connection_fingerprint,
    connection_fingerprint_for_host,
    failed_verification_defaults,
    issue_verification_receipt,
)
from monitoring_stack.services.sync import sync_monitoring_snapshots
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView


class MonitoringPermissionMixin:
    permission_classes = [HasRequiredFeature]
    required_feature = "admin_monitoring"


def rule_template_metadata(path):
    name = path.name
    value = name.lower()
    category = "categraf"
    if any(item in value for item in ["mysql", "redis", "nginx"]):
        category = next(item for item in ["mysql", "redis", "nginx"] if item in value)
    elif any(item in value for item in ["http", "tcp", "ssl", "blackbox"]):
        category = "probe"
    elif any(item in value for item in ["linux", "host", "node"]):
        category = "host"
    title = path.stem.replace("_", " ").replace("-", " ").strip().title()
    return {
        "name": name,
        "title": title or name,
        "category": category,
        "size": path.stat().st_size,
    }


def parse_rule_template(path):
    content = path.read_text(encoding="utf-8")
    data = yaml.safe_load(content) or {}
    groups = []
    for group_index, group in enumerate(data.get("groups", []) if isinstance(data, dict) else []):
        if not isinstance(group, dict):
            continue
        rules = []
        for rule_index, rule in enumerate(group.get("rules", []) or []):
            if not isinstance(rule, dict):
                continue
            labels = rule.get("labels") if isinstance(rule.get("labels"), dict) else {}
            annotations = (
                rule.get("annotations") if isinstance(rule.get("annotations"), dict) else {}
            )
            rules.append(
                {
                    "group_index": group_index,
                    "rule_index": rule_index,
                    "alert": str(rule.get("alert") or ""),
                    "expr": str(rule.get("expr") or ""),
                    "for": str(rule.get("for") or ""),
                    "severity": str(labels.get("severity") or ""),
                    "category": str(labels.get("category") or ""),
                    "summary": str(annotations.get("summary") or ""),
                    "description": str(annotations.get("description") or ""),
                    "labels": labels,
                    "annotations": annotations,
                }
            )
        groups.append(
            {
                "index": group_index,
                "name": str(group.get("name") or ""),
                "rules": rules,
            }
        )
    return {
        "name": path.name,
        "content": content,
        "groups": groups,
        "rule_count": sum(len(group["rules"]) for group in groups),
    }


def normalize_local_rule(rule, group_name=""):
    return {
        "name": str(rule.get("alert") or "").strip(),
        "group": str(group_name or "").strip(),
        "expr": str(rule.get("expr") or "").strip(),
        "for": str(rule.get("for") or "").strip(),
        "severity": str(rule.get("severity") or "").strip(),
        "category": str(rule.get("category") or "").strip(),
        "summary": str(rule.get("summary") or "").strip(),
        "description": str(rule.get("description") or "").strip(),
    }


def _raw_first(raw, *keys):
    for key in keys:
        value = raw.get(key) if isinstance(raw, dict) else None
        if value not in (None, ""):
            return value
    return ""


def normalize_rule_severity(value):
    text = str(value or "").strip().lower()
    return {
        "1": "critical",
        "critical": "critical",
        "crit": "critical",
        "严重": "critical",
        "2": "warning",
        "warning": "warning",
        "warn": "warning",
        "警告": "warning",
        "3": "info",
        "info": "info",
        "notice": "info",
        "提示": "info",
    }.get(text, text)


def _raw_datasource_values(raw):
    values = set()
    if not isinstance(raw, dict):
        return values
    for key in ("datasource_id", "datasourceId", "data_source_id", "datasource"):
        value = raw.get(key)
        if value not in (None, ""):
            values.add(str(value).strip())
    for key in ("datasource_ids", "datasourceIds"):
        value = raw.get(key)
        if isinstance(value, list):
            values.update(str(item).strip() for item in value if item not in (None, ""))
    queries = raw.get("datasource_queries")
    if isinstance(queries, list):
        for query in queries:
            if not isinstance(query, dict):
                continue
            for value in query.get("values") or []:
                if value not in (None, ""):
                    values.add(str(value).strip())
            value = query.get("datasource_id") or query.get("datasourceId")
            if value not in (None, ""):
                values.add(str(value).strip())
    return values


def _first_rule_query(rule_config):
    queries = rule_config.get("queries") if isinstance(rule_config, dict) else None
    if not isinstance(queries, list):
        return {}
    for query in queries:
        if isinstance(query, dict):
            return query
    return {}


def normalize_prom_duration(value):
    if value in (None, ""):
        return ""
    text = str(value).strip()
    try:
        seconds = int(float(text))
    except (TypeError, ValueError):
        return text
    if seconds <= 0:
        return ""
    if seconds % 86400 == 0:
        return f"{seconds // 86400}d"
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def append_tag_value(raw, key):
    tags = raw.get("append_tags") if isinstance(raw, dict) else None
    if not isinstance(tags, list):
        return ""
    prefix = f"{key}="
    for tag in tags:
        text = str(tag or "").strip()
        if text.startswith(prefix):
            return text[len(prefix) :].strip()
    return ""


def n9e_snapshot_matches_filters(snapshot, group_id="", datasource_id=""):
    if group_id and str(snapshot.group_id) != str(group_id):
        return False
    if datasource_id:
        values = _raw_datasource_values(snapshot.raw)
        if values and str(datasource_id) not in values:
            return False
    return True


def normalize_n9e_rule_from_raw(raw, group_id="", fallback_name="", fallback_severity=""):
    raw = raw if isinstance(raw, dict) else {}
    rule_config = raw.get("rule_config") if isinstance(raw.get("rule_config"), dict) else {}
    first_query = _first_rule_query(rule_config)
    labels = raw.get("labels") if isinstance(raw.get("labels"), dict) else {}
    if not labels and isinstance(rule_config.get("labels"), dict):
        labels = rule_config.get("labels")
    annotations = (
        raw.get("annotations") if isinstance(raw.get("annotations"), dict) else {}
    )
    if not annotations and isinstance(rule_config.get("annotations"), dict):
        annotations = rule_config.get("annotations")
    return {
        "name": str(
            _raw_first(raw, "name", "title", "alert")
            or _raw_first(rule_config, "name", "title", "alert")
            or fallback_name
        ).strip(),
        "group": str(group_id or "").strip(),
        "expr": str(
            _raw_first(raw, "expr", "prom_ql", "promql", "query")
            or _raw_first(rule_config, "expr", "prom_ql", "promql", "query")
            or _raw_first(first_query, "expr", "prom_ql", "promql", "query")
        ).strip(),
        "for": normalize_prom_duration(
            _raw_first(raw, "for", "duration")
            or _raw_first(rule_config, "for", "duration")
            or _raw_first(raw, "prom_for_duration")
            or _raw_first(rule_config, "prom_for_duration")
        ).strip(),
        "severity": normalize_rule_severity(
            _raw_first(raw, "severity", "priority")
            or _raw_first(rule_config, "severity", "priority")
            or _raw_first(first_query, "severity", "priority")
            or fallback_severity
        ),
        "category": str(
            _raw_first(labels, "category") or append_tag_value(raw, "category")
        ).strip(),
        "summary": str(_raw_first(annotations, "summary")).strip(),
        "description": str(_raw_first(annotations, "description")).strip(),
    }


def normalize_n9e_rule(snapshot):
    return normalize_n9e_rule_from_raw(
        snapshot.raw,
        group_id=snapshot.group_id,
        fallback_name=snapshot.name,
        fallback_severity=snapshot.severity,
    )


def build_rule_diff(
    path,
    group_id="",
    datasource_id="",
    live_rules=None,
    baseline_source="snapshot",
    baseline_message="使用最近一次 n9e 快照对比",
):
    detail = parse_rule_template(path)
    local_rules = {}
    for group in detail["groups"]:
        for rule in group["rules"]:
            normalized = normalize_local_rule(rule, group.get("name", ""))
            if normalized["name"]:
                local_rules[normalized["name"]] = normalized

    snapshots = []
    if live_rules is None:
        snapshots = [
            snapshot
            for snapshot in N9eRuleSnapshot.objects.all()
            if n9e_snapshot_matches_filters(snapshot, group_id, datasource_id)
        ]
        normalized_n9e_rules = [normalize_n9e_rule(snapshot) for snapshot in snapshots]
    else:
        normalized_n9e_rules = [
            normalize_n9e_rule_from_raw(raw, group_id=group_id) for raw in live_rules
        ]
    n9e_rules = {
        normalized["name"]: normalized
        for normalized in normalized_n9e_rules
        if normalized["name"]
    }
    fields = ["expr", "for", "severity", "category", "summary", "description"]
    items = []
    summary = {"created": 0, "updated": 0, "n9e_only": 0, "unknown": 0, "unchanged": 0}

    for name in sorted(local_rules):
        local = local_rules[name]
        remote = n9e_rules.get(name)
        if not remote:
            status_value = "created"
            changes = {}
            confidence = "high"
            reason = "本地模板中存在，n9e 中不存在"
        else:
            changes = {
                field: {"local": local.get(field, ""), "n9e": remote.get(field, "")}
                for field in fields
                if local.get(field, "") != remote.get(field, "")
            }
            confidence = "high"
            status_value = "updated" if changes else "unchanged"
            reason = "字段有变化" if changes else "本地模板与 n9e 一致"
        summary[status_value] += 1
        items.append(
            {
                "name": name,
                "status": status_value,
                "local": local,
                "n9e": remote,
                "changes": changes,
                "confidence": confidence,
                "reason": reason,
            }
        )

    for name in sorted(set(n9e_rules) - set(local_rules)):
        summary["n9e_only"] += 1
        items.append(
            {
                "name": name,
                "status": "n9e_only",
                "local": None,
                "n9e": n9e_rules[name],
                "changes": {},
                "confidence": "high",
                "reason": "n9e 中存在，本次模板同步不会删除",
            }
        )

    return {
        "rule_file": path.name,
        "has_baseline": bool(snapshots or live_rules),
        "baseline_source": baseline_source,
        "baseline_message": baseline_message,
        "filters": {
            "group_id": str(group_id or ""),
            "datasource_id": str(datasource_id or ""),
        },
        "summary": summary,
        "items": items,
    }


def update_rule_template(path, group_index, rule_index, payload):
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    groups = data.get("groups") if isinstance(data, dict) else None
    if not isinstance(groups, list):
        raise ValueError("invalid rule template")
    try:
        rule = groups[int(group_index)]["rules"][int(rule_index)]
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("rule not found") from exc
    if not isinstance(rule, dict):
        raise ValueError("rule not found")

    for field in ["alert", "expr", "for"]:
        if field in payload:
            rule[field] = str(payload.get(field) or "").strip()

    labels = rule.setdefault("labels", {})
    if not isinstance(labels, dict):
        labels = {}
        rule["labels"] = labels
    for field in ["severity", "category"]:
        if field in payload:
            labels[field] = str(payload.get(field) or "").strip()

    annotations = rule.setdefault("annotations", {})
    if not isinstance(annotations, dict):
        annotations = {}
        rule["annotations"] = annotations
    for field in ["summary", "description"]:
        if field in payload:
            annotations[field] = str(payload.get(field) or "").strip()

    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return parse_rule_template(path)


def update_rule_template_content(path, content):
    if not isinstance(content, str):
        raise ValueError("invalid rule template content")
    try:
        data = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid yaml: {exc}") from exc
    groups = data.get("groups") if isinstance(data, dict) else None
    if not isinstance(groups, list):
        raise ValueError("invalid rule template content")

    atomic_write(path, content)
    return parse_rule_template(path)


def build_rule_template_item(payload):
    rule = {
        "alert": str(payload.get("alert") or "").strip(),
        "expr": str(payload.get("expr") or "").strip(),
    }
    rule_for = str(payload.get("for") or "").strip()
    if rule_for:
        rule["for"] = rule_for

    labels = {}
    for field in ["severity", "category"]:
        value = str(payload.get(field) or "").strip()
        if value:
            labels[field] = value
    if labels:
        rule["labels"] = labels

    annotations = {}
    for field in ["summary", "description"]:
        value = str(payload.get(field) or "").strip()
        if value:
            annotations[field] = value
    if annotations:
        rule["annotations"] = annotations

    if not rule["alert"] or not rule["expr"]:
        raise ValueError("alert and expr are required")
    return rule


def create_rule_template(path, group_index, payload):
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    groups = data.get("groups") if isinstance(data, dict) else None
    if not isinstance(groups, list):
        raise ValueError("invalid rule template")
    try:
        group = groups[int(group_index)]
    except (IndexError, TypeError, ValueError) as exc:
        raise ValueError("rule group not found") from exc
    if not isinstance(group, dict):
        raise ValueError("rule group not found")

    rules = group.setdefault("rules", [])
    if not isinstance(rules, list):
        raise ValueError("invalid rule group")
    rules.append(build_rule_template_item(payload))
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return parse_rule_template(path)


def delete_rule_template(path, group_index, rule_index):
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    groups = data.get("groups") if isinstance(data, dict) else None
    if not isinstance(groups, list):
        raise ValueError("invalid rule template")
    try:
        rules = groups[int(group_index)]["rules"]
        rule = rules[int(rule_index)]
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("rule not found") from exc
    if not isinstance(rules, list) or not isinstance(rule, dict):
        raise ValueError("rule not found")

    rules.pop(int(rule_index))
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return parse_rule_template(path)


class MonitoringProfileViewSet(
    MonitoringPermissionMixin, viewsets.ReadOnlyModelViewSet
):
    serializer_class = MonitoringProfileSerializer
    queryset = MonitoringProfile.objects.all()
    pagination_class = None

    def list(self, request, *args, **kwargs):
        ensure_default_profiles()
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response({"results": serializer.data})


class ProbeTargetViewSet(MonitoringPermissionMixin, viewsets.ModelViewSet):
    serializer_class = ProbeTargetSerializer
    queryset = ProbeTarget.objects.select_related("probe_node").all()

    def get_queryset(self):
        queryset = super().get_queryset()
        target_type = self.request.query_params.get("type")
        if target_type:
            queryset = queryset.filter(type=target_type)
        enabled = self.request.query_params.get("enabled")
        if enabled in {"true", "false"}:
            queryset = queryset.filter(enabled=enabled == "true")
        return queryset


class BlackboxProbeNodeViewSet(MonitoringPermissionMixin, viewsets.ModelViewSet):
    serializer_class = BlackboxProbeNodeSerializer
    queryset = BlackboxProbeNode.objects.select_related("host", "last_job").all()

    def get_queryset(self):
        queryset = super().get_queryset()
        enabled = self.request.query_params.get("enabled")
        if enabled in {"true", "false"}:
            queryset = queryset.filter(enabled=enabled == "true")
        return queryset


class MonitoringHostViewSet(MonitoringPermissionMixin, viewsets.ModelViewSet):
    serializer_class = MonitoringHostSerializer
    queryset = MonitoringHost.objects.select_related("ssh_key_credential").prefetch_related(
        "component_statuses__last_job",
        "blackbox_probe_nodes",
    )

    def get_queryset(self):
        queryset = super().get_queryset()
        enabled = self.request.query_params.get("enabled")
        if enabled in {"true", "false"}:
            queryset = queryset.filter(enabled=enabled == "true")
        return queryset

    def _require_credential_use(self, serializer):
        explicit_assignment = (
            "ssh_key_credential" in serializer.validated_data
            or serializer.validated_data.get("ssh_auth_type")
            == MonitoringHost.SSH_AUTH_KEY
        )
        if not explicit_assignment:
            return
        credential = serializer.validated_data.get(
            "ssh_key_credential",
            getattr(serializer.instance, "ssh_key_credential", None),
        )
        auth_type = serializer.validated_data.get(
            "ssh_auth_type",
            getattr(serializer.instance, "ssh_auth_type", None),
        )
        if (
            auth_type == MonitoringHost.SSH_AUTH_KEY
            and credential
            and not has_credential_permission(
                self.request.user, "monitoring_credentials_use"
            )
        ):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("credential use permission required")

    def perform_create(self, serializer):
        self._require_credential_use(serializer)
        host = serializer.save()
        if host.ssh_key_credential_id:
            record_credential_audit(
                action="assign", status="success",
                credential=host.ssh_key_credential, actor=self.request.user,
                affected_host_ids=[host.id],
                request_context=request_context_from_request(self.request),
            )

    def perform_update(self, serializer):
        old_credential = getattr(serializer.instance, "ssh_key_credential", None)
        self._require_credential_use(serializer)
        host = serializer.save()
        new_credential = host.ssh_key_credential
        if getattr(old_credential, "id", None) == getattr(new_credential, "id", None):
            return
        context = request_context_from_request(self.request)
        if old_credential:
            record_credential_audit(
                action="unassign", status="success", credential=old_credential,
                actor=self.request.user, affected_host_ids=[host.id],
                request_context=context,
            )
        if new_credential:
            record_credential_audit(
                action="assign", status="success", credential=new_credential,
                actor=self.request.user, affected_host_ids=[host.id],
                request_context=context,
            )

    @action(detail=False, methods=["post"], url_path="test-connection")
    def test_connection(self, request):
        serializer = MonitoringHostConnectionTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        credential = data.get("ssh_key_credential")
        if credential and not has_credential_permission(
            request.user, "monitoring_credentials_use"
        ):
            return Response({"detail": "credential use permission required"}, status=403)
        version = getattr(credential, "active_version", None)
        fingerprint = connection_fingerprint(
            address=data["address"],
            ssh_user=data.get("ssh_user") or "root",
            ssh_port=data.get("ssh_port") or 22,
            ssh_auth_type=data["ssh_auth_type"],
            password=data.get("resolved_password") or "",
            ssh_key_id=getattr(credential, "id", None),
            ssh_key_name="",
            ssh_credential_id=getattr(credential, "id", None),
            ssh_credential_version_id=getattr(version, "id", None),
            ssh_public_key_fingerprint=getattr(version, "public_key_fingerprint", ""),
        )
        try:
            if credential:
                provider_context = (
                    DatabaseSshCredentialProvider().materialize([version])
                    if version
                    else materialize_legacy_credential(credential)
                )
                with provider_context as bundle:
                    key_path = (
                        bundle.key_paths[version.id]
                        if version else bundle.key_paths[credential.id]
                    )
                    result = check_monitoring_ssh_connection(
                        address=data["address"], ssh_user=data.get("ssh_user") or "root",
                        ssh_port=data.get("ssh_port") or 22,
                        password=None, key_path=key_path,
                        process_env=bundle.process_env, key_prevalidated=True,
                    )
            else:
                result = check_monitoring_ssh_connection(
                    address=data["address"], ssh_user=data.get("ssh_user") or "root",
                    ssh_port=data.get("ssh_port") or 22,
                    password=data.get("resolved_password"),
                    key_path=None,
                )
        except CredentialRuntimeError as exc:
            return Response({"detail": "credential unavailable", "error_code": exc.code}, status=400)
        except MonitoringSshConnectionError as exc:
            saved_host = data.get("saved_host")
            if (
                saved_host
                and fingerprint == connection_fingerprint_for_host(saved_host)
            ):
                MonitoringHost.objects.filter(id=saved_host.id).update(
                    **failed_verification_defaults(
                        fingerprint=fingerprint,
                        error_code=exc.code,
                    )
                )
            return Response(
                {
                    "detail": "SSH connection test failed",
                    "error_code": exc.code,
                },
                status=exc.status_code,
            )
        checked_at = timezone.now()
        receipt = issue_verification_receipt(
            user_id=request.user.id,
            host_id=getattr(data.get("saved_host"), "id", None),
            fingerprint=fingerprint,
            checked_at=checked_at,
            latency_ms=result["latency_ms"],
        )
        return Response(
            {
                "success": True,
                **result,
                "verified_at": checked_at.isoformat(),
                "verification_receipt": receipt,
            }
        )


class MonitoringCredentialViewSet(viewsets.ModelViewSet):
    permission_classes = [CredentialOperationPermission]
    pagination_class = None

    def get_queryset(self):
        queryset = MonitoringSshCredential.objects.select_related("active_version").prefetch_related(
            "versions__validations", "hosts", "audit_records"
        ).annotate(usage_count=Count("hosts", distinct=True))
        status_value = self.request.query_params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value)
        elif self.action == "list":
            queryset = queryset.exclude(status=MonitoringSshCredential.STATUS_ARCHIVED)
        if self.request.query_params.get("assignable") == "true":
            queryset = queryset.filter(
                status=MonitoringSshCredential.STATUS_ACTIVE,
                active_version__validation_status=MonitoringSshCredentialVersion.VALIDATION_VALID,
            )
        return queryset.order_by("name", "id")

    def get_serializer_class(self):
        if self.action == "create":
            return CredentialCreateSerializer
        if self.action == "rotate":
            return CredentialRotateSerializer
        if self.action == "retrieve":
            return CredentialDetailSerializer
        return CredentialListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        context = request_context_from_request(request)
        try:
            with transaction.atomic():
                credential = MonitoringSshCredential.objects.create(
                    name=data["name"], created_by=request.user, updated_by=request.user
                )
                version = create_credential_version(
                    credential=credential, private_key=data["private_key"],
                    passphrase=data.get("passphrase", ""), actor=request.user,
                )
                record_credential_audit(
                    action="create", status="success", credential=credential,
                    version=version, actor=request.user,
                    metadata={"public_key_fingerprint": version.public_key_fingerprint, "algorithm": version.algorithm, "key_size": version.key_size, "curve": version.curve},
                    request_context=context,
                )
        except PrivateKeyValidationError as exc:
            return Response({exc.field: [exc.code]}, status=400)
        except DuplicateCredentialFingerprint as exc:
            return Response({"private_key": [exc.code], "credential_id": exc.credential_id}, status=409)
        credential.usage_count = 0
        return Response(CredentialDetailSerializer(credential).data, status=201)

    @action(detail=True, methods=["post"])
    def rotate(self, request, pk=None):
        credential = self.get_object()
        if credential.status == credential.STATUS_ARCHIVED:
            return Response({"code": "CREDENTIAL_ARCHIVED"}, status=409)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            version = create_credential_version(
                credential=credential, actor=request.user, **serializer.validated_data
            )
        except PrivateKeyValidationError as exc:
            return Response({exc.field: [exc.code]}, status=400)
        except DuplicateCredentialFingerprint as exc:
            return Response({"private_key": [exc.code], "credential_id": exc.credential_id}, status=409)
        record_credential_audit(action="rotate_start", status="success", credential=credential, version=version, actor=request.user, request_context=request_context_from_request(request))
        return Response(CredentialDetailSerializer(self.get_object()).data, status=201)

    @action(detail=True, methods=["post"])
    def validate(self, request, pk=None):
        credential = self.get_object()
        version_id = request.data.get("version_id") or credential.active_version_id
        try:
            version = credential.versions.get(pk=version_id)
        except MonitoringSshCredentialVersion.DoesNotExist:
            return Response({"version_id": ["invalid version"]}, status=400)
        host_ids = request.data.get("host_ids") or list(
            credential.hosts.filter(enabled=True).values_list("id", flat=True)
        )
        hosts = list(MonitoringHost.objects.filter(id__in=host_ids, enabled=True))
        for candidate in request.data.get("candidate_hosts") or []:
            if not isinstance(candidate, dict) or not candidate.get("address"):
                continue
            hosts.append(SimpleNamespace(
                id=None,
                pk=None,
                hostname=str(candidate.get("hostname") or candidate["address"]),
                address=str(candidate["address"]),
                ssh_user=str(candidate.get("ssh_user") or "root"),
                ssh_port=int(candidate.get("ssh_port") or 22),
            ))
        if not hosts:
            return Response({"host_ids": ["at least one host is required"]}, status=400)
        try:
            results = validate_version_on_hosts(
                version=version, hosts=hosts, actor=request.user,
                request_context=request_context_from_request(request),
            )
        except CredentialRuntimeError as exc:
            return Response({"code": exc.code, "detail": "credential unavailable"}, status=400)
        from monitoring_stack.serializers import CredentialValidationSerializer
        return Response({"results": CredentialValidationSerializer(results, many=True).data})

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        try:
            credential = activate_version(
                credential_id=self.get_object().id,
                version_id=request.data.get("version_id"), actor=request.user,
                request_context=request_context_from_request(request),
            )
        except (CredentialActivationError, CredentialLifecycleError) as exc:
            return Response({"code": exc.code, "detail": exc.code}, status=409)
        credential.usage_count = credential.hosts.count()
        return Response(CredentialDetailSerializer(credential).data)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        try:
            credential = archive_credential(
                credential_id=self.get_object().id, actor=request.user,
                request_context=request_context_from_request(request),
            )
        except CredentialReferenceConflict as exc:
            return Response({"code": exc.code, "hosts": exc.hosts}, status=409)
        credential.usage_count = 0
        return Response(CredentialDetailSerializer(credential).data)

    def destroy(self, request, *args, **kwargs):
        try:
            delete_credential(
                credential_id=self.get_object().id, actor=request.user,
                request_context=request_context_from_request(request),
            )
        except CredentialReferenceConflict as exc:
            return Response({"code": exc.code, "hosts": exc.hosts}, status=409)
        except CredentialLifecycleError as exc:
            return Response({"code": exc.code, "detail": exc.code}, status=409)
        return Response(status=204)


class MonitoringSshKeyCompatibilityViewSet(MonitoringCredentialViewSet):
    http_method_names = ["get", "head", "options"]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Deprecation"] = "true"
        response["Link"] = '</api/v1/monitoring/credentials/>; rel="successor-version"'
        return response


class PrometheusHttpSdView(APIView):
    authentication_classes = []
    permission_classes = []
    renderer_classes = [JSONRenderer]

    def get(self, request, target_type):
        token, _source = active_prometheus_http_sd_token()
        expected = f"Bearer {token}" if token else ""
        if not expected or request.headers.get("Authorization") != expected:
            return Response(
                {"detail": "invalid bearer token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if target_type not in {
            ProbeTarget.TYPE_HTTP,
            ProbeTarget.TYPE_TCP,
            ProbeTarget.TYPE_ICMP,
        }:
            return Response(
                {"detail": "target type not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(render_http_sd_targets(target_type))


class PrometheusHttpSdTokenView(MonitoringPermissionMixin, APIView):
    def post(self, request):
        token = generate_prometheus_http_sd_token()
        return Response({"token": token, "http_sd": prometheus_http_sd_state()})


class PrometheusHttpSdConfigView(MonitoringPermissionMixin, APIView):
    def get(self, request):
        return Response(prometheus_http_sd_config(request.build_absolute_uri("/")))


class PrometheusTargetsSummaryView(MonitoringPermissionMixin, APIView):
    def get(self, request):
        return Response(prometheus_targets_summary())


class PrometheusProbeNodeDiscoveryView(MonitoringPermissionMixin, APIView):
    def get(self, request):
        return Response(prometheus_probe_node_discoveries())


class PrometheusProbeNodeOnboardView(MonitoringPermissionMixin, APIView):
    def post(self, request):
        serializer = PrometheusProbeNodeOnboardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            node, bound_target_count = onboard_prometheus_probe_node(
                **serializer.validated_data
            )
        except ProbeNodeAlreadyManaged:
            return Response(
                {"detail": "probe node endpoint is already managed"},
                status=status.HTTP_409_CONFLICT,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "node": BlackboxProbeNodeSerializer(node).data,
                "bound_target_count": bound_target_count,
            },
            status=status.HTTP_201_CREATED,
        )


class BlackboxInstancesView(MonitoringPermissionMixin, APIView):
    def get(self, request):
        return Response(blackbox_instances_summary())


class AssetsReconciliationView(MonitoringPermissionMixin, APIView):
    def get(self, request):
        return Response(assets_reconciliation_summary())


class MonitoringConfigView(MonitoringPermissionMixin, APIView):
    def get(self, request):
        return Response(monitoring_config())

    def put(self, request):
        instance = MonitoringIntegrationConfig.current()
        serializer = MonitoringIntegrationConfigSerializer(
            instance,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(monitoring_config())


class N9ePlatformSummaryView(MonitoringPermissionMixin, APIView):
    def get(self, request):
        return Response(n9e_platform_summary())


class MonitoringGovernanceSyncView(MonitoringPermissionMixin, APIView):
    def post(self, request):
        try:
            run = sync_monitoring_snapshots(request.data.get("source", "all"))
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(MonitoringSnapshotRunSerializer(run).data)


class MonitoringGovernanceOverviewView(MonitoringPermissionMixin, APIView):
    def get(self, request):
        data = governance_overview()
        data["top_findings"] = MonitoringGovernanceFindingSerializer(
            data["top_findings"],
            many=True,
        ).data
        return Response(data)


class MonitoringGovernanceFindingView(MonitoringPermissionMixin, APIView):
    def get(self, request):
        queryset = MonitoringGovernanceFinding.objects.all()
        for key in ("category", "severity", "status", "subject_type"):
            value = request.query_params.get(key)
            if value:
                queryset = queryset.filter(**{key: value})
        serializer = MonitoringGovernanceFindingSerializer(queryset, many=True)
        return Response({"results": serializer.data})


class MonitoringGovernanceFindingResolveView(MonitoringPermissionMixin, APIView):
    def post(self, request, finding_id):
        try:
            finding = MonitoringGovernanceFinding.objects.get(pk=finding_id)
        except MonitoringGovernanceFinding.DoesNotExist:
            return Response(
                {"detail": "finding not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        action_name = request.data.get("action") or finding.recommended_action
        payload = request.data.get("payload") or {}
        if not isinstance(payload, dict):
            return Response(
                {"detail": "payload must be an object"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if action_name == "ignore":
            self._finish_finding(
                finding,
                MonitoringGovernanceFinding.STATUS_IGNORED,
                {"action": action_name},
            )
            return Response(MonitoringGovernanceFindingSerializer(finding).data)
        if action_name == "create_probe_target":
            return self._create_probe_target(finding, payload)
        if action_name in {"install_categraf", "install_blackbox"}:
            component = (
                AnsibleInstallJob.COMPONENT_BLACKBOX
                if action_name == "install_blackbox"
                else AnsibleInstallJob.COMPONENT_CATEGRAF
            )
            return self._start_install_job(request, finding, payload, component)
        if action_name == "retry_job":
            return self._retry_install_job(request, finding, payload)

        return Response(
            {"detail": "unsupported finding action"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def _create_probe_target(self, finding, payload):
        details = finding.details or {}
        target_type = payload.get("type") or details.get("type") or ""
        target = payload.get("target") or details.get("target") or ""
        if target_type not in {
            ProbeTarget.TYPE_HTTP,
            ProbeTarget.TYPE_TCP,
            ProbeTarget.TYPE_ICMP,
        }:
            return Response(
                {"detail": "invalid probe target type"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not target:
            return Response(
                {"detail": "probe target is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        labels = clean_labels({**details.get("labels", {}), **payload.get("labels", {})})
        probe, created = ProbeTarget.objects.get_or_create(
            type=target_type,
            target=target,
            defaults={
                "enabled": True,
                "labels": labels,
            },
        )
        if not created:
            probe.enabled = True
            if labels:
                probe.labels = {**(probe.labels or {}), **labels}
            probe.save(update_fields=["enabled", "labels", "updated_at"])

        self._finish_finding(
            finding,
            MonitoringGovernanceFinding.STATUS_RESOLVED,
            {
                "action": "create_probe_target",
                "probe_target_id": probe.id,
                "created": created,
            },
        )
        return Response(MonitoringGovernanceFindingSerializer(finding).data)

    def _start_install_job(self, request, finding, payload, component):
        host_ids = self._resolve_host_ids(finding, payload)
        hosts = selected_hosts(host_ids)
        if not host_ids or len(hosts) != len(set(host_ids)):
            return Response(
                {"detail": "valid host_ids are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        config = MonitoringIntegrationConfig.current()
        is_blackbox = component == AnsibleInstallJob.COMPONENT_BLACKBOX
        base_url = (
            payload.get("base_url")
            or config.installer_base_url
            or request.build_absolute_uri("/api/v1/monitoring/installer")
        )
        job_payload = {
            "component": component,
            "profiles": clean_string_list(payload.get("profiles") or []),
            "labels": clean_labels(payload.get("labels") or {}),
            "params": clean_labels(payload.get("params") or {}),
            "base_url": base_url,
            "n9e_url": "" if is_blackbox else payload.get("n9e_url") or config.n9e_url,
            "install_dir": payload.get("install_dir")
            or (
                config.blackbox_install_dir
                if is_blackbox
                else config.categraf_install_dir
            )
            or ("/opt/blackbox-exporter" if is_blackbox else "/opt/categraf"),
            "image": payload.get("image")
            or (
                config.blackbox_image
                if is_blackbox and config.blackbox_image
                else ""
            )
            or (
                "prom/blackbox-exporter:latest"
                if is_blackbox
                else "flashcatcloud/categraf:latest"
            ),
            "probe_name": payload.get("probe_name") or "",
            "blackbox_port": payload.get("blackbox_port")
            or config.blackbox_port
            or "9115",
        }
        job = AnsibleInstallJob.objects.create(
            component=component,
            profiles=job_payload["profiles"],
            labels=job_payload["labels"],
            params=job_payload["params"],
            host_ids=host_ids,
            hosts_snapshot=snapshot_hosts(hosts, job_payload),
            base_url=job_payload["base_url"],
            n9e_url=job_payload["n9e_url"],
            install_dir=job_payload["install_dir"],
            image=job_payload["image"],
            probe_name=job_payload["probe_name"],
            blackbox_port=job_payload["blackbox_port"],
            created_by=request.user,
        )
        mark_component_installing(job, hosts)
        try:
            dispatch_install_job(job)
        except JobDispatchError as exc:
            return Response(
                dispatch_error_response(exc),
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        self._finish_finding(
            finding,
            MonitoringGovernanceFinding.STATUS_RESOLVED,
            {
                "action": f"install_{component}",
                "job_id": job.id,
                "host_ids": host_ids,
            },
        )
        return Response(MonitoringGovernanceFindingSerializer(finding).data)

    def _retry_install_job(self, request, finding, payload):
        job_id = payload.get("job_id") or (finding.details or {}).get("job_id")
        try:
            job = AnsibleInstallJob.objects.get(pk=job_id)
        except (AnsibleInstallJob.DoesNotExist, TypeError, ValueError):
            return Response(
                {"detail": "install job not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        host_ids = self._failed_host_ids(job)
        if not host_ids:
            return Response(
                {"detail": "no failed hosts to retry"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        retry_job = AnsibleInstallJob.objects.create(
            component=job.component,
            profiles=job.profiles,
            labels=job.labels,
            params=job.params,
            host_ids=host_ids,
            hosts_snapshot=snapshot_hosts(
                selected_hosts(host_ids), self._job_payload(job)
            ),
            base_url=job.base_url,
            n9e_url=job.n9e_url,
            install_dir=job.install_dir,
            image=job.image,
            probe_name=job.probe_name,
            blackbox_port=job.blackbox_port,
            retry_of=job,
            created_by=request.user,
        )
        try:
            dispatch_install_job(retry_job)
        except JobDispatchError as exc:
            return Response(
                dispatch_error_response(exc),
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        self._finish_finding(
            finding,
            MonitoringGovernanceFinding.STATUS_RESOLVED,
            {
                "action": "retry_job",
                "job_id": retry_job.id,
                "retry_of": job.id,
                "host_ids": host_ids,
            },
        )
        return Response(MonitoringGovernanceFindingSerializer(finding).data)

    def _failed_host_ids(self, job):
        failed_names = {
            str(item.get("hostname") or "")
            for item in job.results or []
            if str(item.get("status") or "").lower() in {"failed", "error", "timeout"}
        }
        snapshot = job.hosts_snapshot or []
        if failed_names:
            return [
                item.get("id")
                for item in snapshot
                if item.get("hostname") in failed_names and item.get("id")
            ]
        if job.status == AnsibleInstallJob.STATUS_FAILED:
            return [item.get("id") for item in snapshot if item.get("id")]
        return []

    def _job_payload(self, job):
        return {
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

    def _resolve_host_ids(self, finding, payload):
        raw_ids = payload.get("host_ids") or []
        if not raw_ids:
            host_id = (finding.details or {}).get("host_id")
            raw_ids = [host_id] if host_id else []
        cleaned = []
        for item in raw_ids:
            try:
                cleaned.append(int(item))
            except (TypeError, ValueError):
                continue
        return cleaned

    def _finish_finding(self, finding, status_value, resolution):
        details = dict(finding.details or {})
        details["resolution"] = {
            **resolution,
            "resolved_at": timezone.now().isoformat(),
        }
        finding.details = details
        finding.status = status_value
        finding.resolved_at = timezone.now()
        finding.save(update_fields=["details", "status", "resolved_at", "updated_at"])


class InstallerAssetsView(MonitoringPermissionMixin, APIView):
    def get(self, request):
        return Response(installer_assets())


class InstallerBuildView(MonitoringPermissionMixin, APIView):
    def post(self, request):
        try:
            payload = build_installer_archives()
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        payload["status"] = "success"
        payload["generated_at"] = timezone.now().isoformat()
        return Response(payload)


class InstallerDownloadView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, file_name):
        path = installer_file_path(file_name)
        if not path:
            return Response(
                {"detail": "installer asset not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        media_type = (
            "application/gzip" if str(path).endswith(".tar.gz") else "text/plain"
        )
        if str(path).endswith(".json"):
            media_type = "application/json"
        return FileResponse(
            path.open("rb"), content_type=media_type, filename=path.name
        )


class AnsiblePreviewView(MonitoringPermissionMixin, APIView):
    def post(self, request):
        serializer = AnsiblePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        preview = build_ansible_preview(
            data.get("host_ids", []),
            data.get("profiles", []),
            data.get("base_url", ""),
            data.get("n9e_url", ""),
            data.get("install_dir", ""),
            data.get("image", ""),
            data.get("component", "categraf"),
            data.get("probe_name", ""),
            data.get("blackbox_port", ""),
            data.get("labels", {}),
            data.get("params", {}),
        )
        return Response(preview)


class AnsibleInstallJobViewSet(MonitoringPermissionMixin, viewsets.ModelViewSet):
    serializer_class = AnsibleInstallJobSerializer
    queryset = AnsibleInstallJob.objects.select_related("created_by").all()
    http_method_names = ["get", "post", "head", "options"]

    def perform_create(self, serializer):
        data = serializer.validated_data
        host_ids = data.get("host_ids") or []
        component = data.get("component") or AnsibleInstallJob.COMPONENT_CATEGRAF
        profiles = clean_string_list(data.get("profiles") or [])
        labels = clean_labels(data.get("labels") or {})
        params = clean_labels(data.get("params") or {})
        hosts = selected_hosts(host_ids)
        is_blackbox = component == AnsibleInstallJob.COMPONENT_BLACKBOX
        job_payload = {
            "component": component,
            "profiles": profiles,
            "labels": labels,
            "params": params,
            "base_url": data["base_url"],
            "n9e_url": "" if is_blackbox else data.get("n9e_url", ""),
            "install_dir": data.get("install_dir")
            or ("/opt/blackbox-exporter" if is_blackbox else "/opt/categraf"),
            "image": data.get("image")
            or (
                "prom/blackbox-exporter:latest"
                if is_blackbox
                else "flashcatcloud/categraf:latest"
            ),
            "probe_name": data.get("probe_name", ""),
            "blackbox_port": data.get("blackbox_port", "") or "9115",
        }
        job = serializer.save(
            created_by=self.request.user,
            component=component,
            profiles=profiles,
            labels=labels,
            params=params,
            hosts_snapshot=snapshot_hosts(hosts, job_payload),
            n9e_url=job_payload["n9e_url"],
            install_dir=job_payload["install_dir"],
            image=job_payload["image"],
            probe_name=job_payload["probe_name"],
            blackbox_port=job_payload["blackbox_port"],
        )
        mark_component_installing(job, hosts)

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        job_id = response.data.get("id")
        if job_id:
            try:
                dispatch_install_job(self.get_queryset().get(pk=job_id))
            except JobDispatchError as exc:
                return Response(
                    dispatch_error_response(exc),
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
        return response

    @action(detail=True, methods=["post"], url_path="retry")
    def retry(self, request, pk=None):
        job = self.get_object()
        host_ids = self._failed_host_ids(job)
        if not host_ids:
            return Response(
                {"detail": "no failed hosts to retry"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        retry_job = AnsibleInstallJob.objects.create(
            component=job.component,
            profiles=job.profiles,
            labels=job.labels,
            params=job.params,
            host_ids=host_ids,
            hosts_snapshot=snapshot_hosts(
                selected_hosts(host_ids), self._job_payload(job)
            ),
            base_url=job.base_url,
            n9e_url=job.n9e_url,
            install_dir=job.install_dir,
            image=job.image,
            probe_name=job.probe_name,
            blackbox_port=job.blackbox_port,
            retry_of=job,
            created_by=request.user,
        )
        try:
            dispatch_install_job(retry_job)
        except JobDispatchError as exc:
            return Response(
                dispatch_error_response(exc),
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(
            self.get_serializer(retry_job).data,
            status=status.HTTP_201_CREATED,
        )

    def _failed_host_ids(self, job):
        failed_names = {
            str(item.get("hostname") or "")
            for item in job.results or []
            if str(item.get("status") or "").lower() in {"failed", "error", "timeout"}
        }
        snapshot = job.hosts_snapshot or []
        if failed_names:
            return [
                item.get("id")
                for item in snapshot
                if item.get("hostname") in failed_names and item.get("id")
            ]
        if job.status == AnsibleInstallJob.STATUS_FAILED:
            return [item.get("id") for item in snapshot if item.get("id")]
        return []

    def _job_payload(self, job):
        return {
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


class RulesView(MonitoringPermissionMixin, APIView):
    def _rule_path(self, rule_file):
        base = rules_dir()
        path = (base / rule_file).resolve()
        if base.resolve() not in path.parents and path != base.resolve():
            return None, Response(
                {"detail": "invalid rule file"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not path.exists() or path.suffix not in {".yml", ".yaml"}:
            return None, Response(
                {"detail": "rule file not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return path, None

    def get(self, request, rule_file=None):
        base = rules_dir()
        if not rule_file:
            files = []
            if base.exists():
                files = [
                    rule_template_metadata(path)
                    for path in sorted(base.glob("*.y*ml"))
                    if path.is_file()
                ]
            return Response({"results": files})

        path, error = self._rule_path(rule_file)
        if error:
            return error
        return Response(parse_rule_template(path))

    def post(self, request, rule_file=None):
        if not rule_file:
            return Response(
                {"detail": "invalid rule file"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        path, error = self._rule_path(rule_file)
        if error:
            return error
        try:
            return Response(
                create_rule_template(
                    path,
                    request.data.get("group_index"),
                    request.data.get("rule") or {},
                )
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def patch(self, request, rule_file=None):
        if not rule_file:
            return Response(
                {"detail": "invalid rule file"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        path, error = self._rule_path(rule_file)
        if error:
            return error
        try:
            if "content" in request.data:
                return Response(
                    update_rule_template_content(
                        path,
                        request.data.get("content"),
                    )
                )
            return Response(
                update_rule_template(
                    path,
                    request.data.get("group_index"),
                    request.data.get("rule_index"),
                    request.data.get("rule") or {},
                )
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def delete(self, request, rule_file=None):
        if not rule_file:
            return Response(
                {"detail": "invalid rule file"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        path, error = self._rule_path(rule_file)
        if error:
            return error
        try:
            return Response(
                delete_rule_template(
                    path,
                    request.data.get("group_index"),
                    request.data.get("rule_index"),
                )
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class RuleDiffView(MonitoringPermissionMixin, APIView):
    def get(self, request, rule_file):
        path, error = RulesView()._rule_path(rule_file)
        if error:
            return error
        group_id = request.query_params.get("group_id", "")
        datasource_id = request.query_params.get("datasource_id", "")
        live_rules = None
        baseline_source = "snapshot"
        baseline_message = "使用最近一次 n9e 快照对比"
        if group_id:
            try:
                live_rules = self._fetch_live_rules(request, group_id)
                baseline_source = "live"
                baseline_message = "已读取 n9e 当前业务组规则"
            except Exception as exc:
                baseline_message = f"读取 n9e 实时规则失败，已回退最近快照：{exc}"
        return Response(
            build_rule_diff(
                path,
                group_id=group_id,
                datasource_id=datasource_id,
                live_rules=live_rules,
                baseline_source=baseline_source,
                baseline_message=baseline_message,
            )
        )

    def _fetch_live_rules(self, request, group_id):
        config = MonitoringIntegrationConfig.current()
        if not config.n9e_url:
            raise ValueError("未配置 n9e 地址")
        session = requests.Session()
        session.trust_env = False
        token = N9eDiscoverView()._login({}, session)
        session.headers.update({"Authorization": f"Bearer {token}"})
        _count, rules = _fetch_n9e_collection(
            session,
            f"{config.n9e_url.rstrip('/')}/api/n9e/busi-group/{group_id}/alert-rules",
        )
        return [item for item in rules if isinstance(item, dict)]


class N9eDiscoverView(MonitoringPermissionMixin, APIView):
    def post(self, request):
        session = self._session()
        token = self._login(request.data, session)
        n9e_url = self._n9e_url(request.data)
        session.headers.update({"Authorization": f"Bearer {token}"})
        groups = session.get(
            f"{n9e_url}/api/n9e/busi-groups",
            timeout=15,
        )
        datasources = session.get(
            f"{n9e_url}/api/n9e/datasource/brief",
            timeout=15,
        )
        groups.raise_for_status()
        datasources.raise_for_status()
        datasource_items = [
            item
            for item in datasources.json().get("dat", [])
            if item.get("plugin_type") == "prometheus"
        ]
        return Response(
            {
                "groups": groups.json().get("dat", []),
                "datasources": datasource_items,
            }
        )

    def _session(self):
        session = requests.Session()
        session.trust_env = False
        return session

    def _login(self, data, session=None):
        session = session or self._session()
        n9e_url = self._n9e_url(data)
        config = MonitoringIntegrationConfig.current()
        response = session.post(
            f"{n9e_url}/api/n9e/auth/login",
            json={
                "username": data.get("username")
                or config.n9e_username
                or getattr(settings, "MONITORING_N9E_USERNAME", "root"),
                "password": data.get("password")
                or config.n9e_password
                or getattr(settings, "MONITORING_N9E_PASSWORD", ""),
            },
            timeout=15,
        )
        response.raise_for_status()
        token = response.json().get("dat", {}).get("access_token")
        if not token:
            raise ValueError("n9e login failed")
        return token

    def _n9e_url(self, data):
        config = MonitoringIntegrationConfig.current()
        return str(
            data.get("n9e_url")
            or config.n9e_url
            or getattr(settings, "MONITORING_N9E_URL", "")
        ).rstrip("/")


class N9eImportRulesView(N9eDiscoverView):
    def post(self, request):
        rule_file = request.data.get("rule_file", "")
        path = (rules_dir() / rule_file).resolve()
        if rules_dir().resolve() not in path.parents and path != rules_dir().resolve():
            return Response(
                {"detail": "invalid rule file"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not path.exists() or path.suffix not in {".yml", ".yaml"}:
            return Response(
                {"detail": "rule file not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        metadata = rule_template_metadata(path)
        group_id = int(request.data.get("group_id") or 0)
        datasource_id = int(request.data.get("datasource_id") or 0)
        enabled = bool(request.data.get("enabled", False))
        session = self._session()
        try:
            token = self._login(request.data, session)
            n9e_url = self._n9e_url(request.data)
            payload = {
                "payload": path.read_text(encoding="utf-8"),
                "datasource_queries": [
                    {
                        "match_type": 0,
                        "op": "in",
                        "values": [datasource_id],
                    }
                ],
                "disabled": 0 if enabled else 1,
            }
            session.headers.update({"Authorization": f"Bearer {token}"})
            response = session.post(
                f"{n9e_url}/api/n9e/busi-group/{group_id}/alert-rules/import-prom-rule",
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            summary = self._import_summary(result)
            import_status = self._record_status(summary)
            record = self._record_import(
                request,
                rule_file,
                metadata["category"],
                group_id,
                datasource_id,
                enabled,
                import_status,
                summary,
                result,
            )
            if import_status == RuleImportRecord.STATUS_SUCCESS:
                self._resolve_rule_findings(rule_file, record)
            return Response(
                {"summary": summary, "result": result, "record_id": record.id}
            )
        except Exception as exc:
            summary = {
                "success": 0,
                "skipped": 0,
                "failed": 1,
                "message": str(exc),
            }
            result = {"detail": str(exc)}
            record = self._record_import(
                request,
                rule_file,
                metadata["category"],
                group_id,
                datasource_id,
                enabled,
                RuleImportRecord.STATUS_FAILED,
                summary,
                result,
            )
            return Response(
                {"summary": summary, "result": result, "record_id": record.id},
                status=status.HTTP_502_BAD_GATEWAY,
            )

    def _record_import(
        self,
        request,
        rule_file,
        template_category,
        group_id,
        datasource_id,
        enabled,
        import_status,
        summary,
        result,
    ):
        return RuleImportRecord.objects.create(
            rule_file=rule_file,
            template_category=template_category,
            group_id=group_id,
            datasource_id=datasource_id,
            enabled=enabled,
            status=import_status,
            summary=summary,
            result=result,
            created_by=request.user,
        )

    def _resolve_rule_findings(self, rule_file, record):
        now = timezone.now()
        findings = MonitoringGovernanceFinding.objects.filter(
            category="rule_template_not_imported",
            status=MonitoringGovernanceFinding.STATUS_OPEN,
            subject_key=rule_file,
        )
        for finding in findings:
            details = dict(finding.details or {})
            details["resolution"] = {
                "action": "import_rule_template",
                "record_id": record.id,
                "resolved_at": now.isoformat(),
            }
            finding.details = details
            finding.status = MonitoringGovernanceFinding.STATUS_RESOLVED
            finding.resolved_at = now
            finding.save(
                update_fields=["details", "status", "resolved_at", "updated_at"]
            )

    def _record_status(self, summary):
        failed = int(summary.get("failed") or 0)
        success = int(summary.get("success") or 0)
        if failed and success:
            return RuleImportRecord.STATUS_PARTIAL
        if failed:
            return RuleImportRecord.STATUS_FAILED
        return RuleImportRecord.STATUS_SUCCESS

    def _import_summary(self, result):
        data = result.get("dat") if isinstance(result, dict) else {}
        if not isinstance(data, dict):
            data = {}
        imported_raw = self._first_present(data, "imported", "success", "created")
        skipped_raw = self._first_present(data, "skipped", "ignored")
        failed_raw = self._first_present(data, "failed", "errors")
        count_available = any(
            value is not None for value in [imported_raw, skipped_raw, failed_raw]
        )
        if not count_available:
            return {
                "success": None,
                "skipped": None,
                "failed": None,
                "submitted": 1,
                "count_available": False,
                "message": (
                    result.get("err")
                    if isinstance(result, dict) and result.get("err")
                    else "n9e 已接收导入请求，但未返回成功/跳过/失败数量"
                ),
            }
        return {
            "success": self._summary_count(imported_raw),
            "skipped": self._summary_count(skipped_raw),
            "failed": self._summary_count(failed_raw),
            "message": result.get("err", "") if isinstance(result, dict) else "",
        }

    def _first_present(self, data, *keys):
        for key in keys:
            if key in data:
                return data.get(key)
        return None

    def _summary_count(self, value):
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            return len(value)
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
