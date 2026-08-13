import io
import json
import subprocess

import pytest
from accounts.access import (
    MONITORING_CREDENTIAL_PERMISSION_KEYS,
    get_access_profile,
    normalize_feature_keys,
)
from accounts.models import Role
from django.contrib.auth import get_user_model
from django.apps import apps
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from monitoring_stack.models import (
    AnsibleInstallJob,
    BlackboxProbeNode,
    MonitoringComponentStatus,
    MonitoringIntegrationConfig,
    MonitoringHost,
    MonitoringSshCredential,
    ProbeTarget,
    RuleImportRecord,
)
from monitoring_stack.services.asset_state import (
    choose_next_action,
    normalize_component_state,
)
from monitoring_stack.services.core import (
    MonitoringSshConnectionError,
    build_ansible_preview,
    check_monitoring_ssh_connection,
    execute_ansible_job,
    snapshot_hosts,
)
from monitoring_stack.services.credential_ingestion import create_credential_version
from monitoring_stack.tests.ssh_key_fixtures import generate_private_key
from rest_framework.test import APIClient

User = get_user_model()


def _payload(response):
    body = response.json()
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


@pytest.fixture
def monitoring_admin(db):
    user = User.objects.create_user(
        username="monitoring-admin",
        email="monitoring-admin@example.com",
        password="password123",
    )
    role = Role.objects.create(
        name="Monitoring Admin",
        visible_features=["admin_monitoring"],
        operation_permissions=list(MONITORING_CREDENTIAL_PERMISSION_KEYS),
        preferred_platform="admin_console",
    )
    user.platform_roles.add(role)
    return user


@pytest.fixture
def client(monitoring_admin):
    api_client = APIClient()
    api_client.force_authenticate(user=monitoring_admin)
    return api_client


@pytest.mark.django_db
def test_admin_monitoring_feature_is_available(monitoring_admin):
    assert normalize_feature_keys(["admin_monitoring"]) == ["admin_monitoring"]

    profile = get_access_profile(monitoring_admin)

    assert profile["visible_features"] == ["admin_monitoring"]
    assert profile["operation_permissions"] == list(
        MONITORING_CREDENTIAL_PERMISSION_KEYS
    )
    assert profile["landing_path"] == "/management/monitoring/overview"


@pytest.mark.django_db
def test_profiles_endpoint_initializes_default_profiles(client):
    response = client.get("/api/v1/monitoring/profiles/")

    assert response.status_code == 200
    profile_ids = {item["id"] for item in _payload(response)["results"]}
    assert {"linux-basic", "docker-host", "mysql-rds", "redis", "nginx"}.issubset(
        profile_ids
    )


@pytest.mark.django_db
def test_monitoring_config_exposes_installer_options(client):
    response = client.get("/api/v1/monitoring/config/")

    assert response.status_code == 200
    options = _payload(response)["installer"]["options"]
    assert "beijing-idc" in options["regions"]
    assert "prod" in options["envs"]
    assert "ops" in options["teams"]
    assert "docker-host" in options["roles"]
    assert "blackbox-beijing-idc" in options["probe_names"]


@pytest.mark.django_db
def test_monitoring_config_can_be_saved_and_preserves_masked_password(client):
    response = client.put(
        "/api/v1/monitoring/config/",
        {
            "n9e_url": "http://n9e.internal:17000",
            "n9e_username": "root",
            "n9e_password": "secret-1",
            "prometheus_url": "http://prometheus.internal:9090",
            "grafana_url": "http://grafana.internal:3000",
            "installer_base_url": "http://hyperops.local/api/v1/monitoring/installer",
            "categraf_install_dir": "/opt/categraf",
            "blackbox_install_dir": "/opt/blackbox-exporter",
            "blackbox_port": "9115",
            "blackbox_image": "prom/blackbox-exporter:v1",
        },
        format="json",
    )

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["n9e_url"] == "http://n9e.internal:17000"
    assert payload["prometheus_url"] == "http://prometheus.internal:9090"
    assert payload["grafana_url"] == "http://grafana.internal:3000"
    assert payload["n9e"]["username"] == "root"
    assert payload["n9e"]["has_password"] is True
    assert "password" not in payload["n9e"]
    assert payload["installer"]["base_url"] == (
        "http://hyperops.local/api/v1/monitoring/installer"
    )
    assert payload["installer"]["blackbox_image"] == "prom/blackbox-exporter:v1"

    preserve_response = client.put(
        "/api/v1/monitoring/config/",
        {
            "n9e_url": "http://n9e.internal:17000",
            "n9e_username": "root",
            "n9e_password": "",
            "prometheus_url": "http://prometheus.internal:9090",
            "grafana_url": "http://grafana.internal:3000",
            "installer_base_url": "http://hyperops.local/api/v1/monitoring/installer",
            "categraf_install_dir": "/srv/categraf",
            "blackbox_install_dir": "/srv/blackbox",
            "blackbox_port": "9116",
            "blackbox_image": "prom/blackbox-exporter:v2",
        },
        format="json",
    )

    assert preserve_response.status_code == 200
    preserved = _payload(preserve_response)
    assert preserved["n9e"]["has_password"] is True
    assert preserved["installer"]["install_dir"] == "/srv/categraf"
    assert preserved["installer"]["blackbox_dir"] == "/srv/blackbox"
    assert preserved["installer"]["blackbox_port"] == "9116"


@pytest.mark.django_db
def test_prometheus_http_sd_token_can_be_managed_from_config(client):
    response = client.post("/api/v1/monitoring/prometheus/http-sd/token/")

    assert response.status_code == 200
    payload = _payload(response)
    token = payload["token"]
    assert token.startswith("mon_")
    assert len(token) >= 32
    assert payload["http_sd"]["token_configured"] is True
    assert payload["http_sd"]["token_source"] == "database"
    assert token.endswith(payload["http_sd"]["token_preview"][-4:])

    config_response = client.get("/api/v1/monitoring/config/")
    config_payload = _payload(config_response)
    assert config_payload["http_sd"]["token_configured"] is True
    assert config_payload["http_sd"]["token_source"] == "database"
    assert config_payload["http_sd"]["token_preview"].endswith(token[-4:])
    assert token not in json.dumps(config_payload)


@pytest.mark.django_db
def test_prometheus_http_sd_uses_database_token_before_env_token(client):
    config = MonitoringIntegrationConfig.current()
    config.prometheus_http_sd_token = "database-token"
    config.save(update_fields=["prometheus_http_sd_token", "updated_at"])
    node_model = apps.get_model("monitoring_stack", "BlackboxProbeNode")
    node = node_model.objects.create(
        name="blackbox-token-test",
        address="10.0.0.12",
        enabled=True,
    )
    ProbeTarget.objects.create(
        type=ProbeTarget.TYPE_HTTP,
        target="https://database-token.example.com",
        enabled=True,
        probe_node=node,
        labels={"service": "website"},
    )

    public_client = APIClient()
    with override_settings(MONITORING_ADMIN_TOKEN="env-token"):
        env_denied = public_client.get(
            "/api/v1/monitoring/prometheus/http-sd/blackbox/http/",
            HTTP_AUTHORIZATION="Bearer env-token",
        )
        database_allowed = public_client.get(
            "/api/v1/monitoring/prometheus/http-sd/blackbox/http/",
            HTTP_AUTHORIZATION="Bearer database-token",
        )

    assert env_denied.status_code == 401
    assert database_allowed.status_code == 200
    assert _payload(database_allowed)[0]["targets"] == [
        "https://database-token.example.com"
    ]


@pytest.mark.django_db
def test_prometheus_http_sd_config_preview_returns_copyable_yaml(client):
    config = MonitoringIntegrationConfig.current()
    config.prometheus_http_sd_token = "database-token"
    config.save(update_fields=["prometheus_http_sd_token", "updated_at"])

    response = client.get(
        "/api/v1/monitoring/prometheus/http-sd/config/",
        HTTP_X_FORWARDED_HOST="192.168.7.168:18080",
        HTTP_X_FORWARDED_PROTO="http",
    )

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["token_configured"] is True
    assert payload["token_file_path"] == "/etc/prometheus/hyperops-http-sd.token"
    assert payload["urls"]["http"].endswith(
        "/api/v1/monitoring/prometheus/http-sd/blackbox/http/"
    )
    assert all(
        url.startswith("http://192.168.7.168:18080/api/v1/monitoring/")
        for url in payload["urls"].values()
    )
    assert "job_name: blackbox-http" in payload["yaml"]
    assert "job_name: blackbox-tcp" in payload["yaml"]
    assert "job_name: blackbox-icmp" in payload["yaml"]
    assert 'credentials: "database-token"' in payload["yaml"]
    assert "credentials_file:" not in payload["yaml"]


@pytest.mark.django_db
def test_probe_nodes_can_route_probe_targets_through_http_sd(client):
    from monitoring_stack.views import PrometheusHttpSdView
    from rest_framework.renderers import JSONRenderer

    assert PrometheusHttpSdView.__dict__.get("renderer_classes") == [JSONRenderer]

    node_response = client.post(
        "/api/v1/monitoring/probe-nodes/",
        {
            "name": "blackbox-beijing",
            "address": "192.168.7.159",
            "port": "9115",
            "enabled": True,
            "labels": {"region": "beijing", "env": "prod"},
        },
        format="json",
    )
    assert node_response.status_code == 201
    node = _payload(node_response)

    target_response = client.post(
        "/api/v1/monitoring/probe-targets/",
        {
            "type": "http",
            "target": "https://example.com",
            "enabled": True,
            "probe_node": node["id"],
            "labels": {"service": "website"},
        },
        format="json",
    )
    assert target_response.status_code == 201

    config = MonitoringIntegrationConfig.current()
    config.prometheus_http_sd_token = "database-token"
    config.save(update_fields=["prometheus_http_sd_token", "updated_at"])

    public_client = APIClient()
    sd_response = public_client.get(
        "/api/v1/monitoring/prometheus/http-sd/blackbox/http/",
        HTTP_AUTHORIZATION="Bearer database-token",
    )

    assert sd_response.status_code == 200
    assert isinstance(sd_response.json(), list)
    assert _payload(sd_response) == [
        {
            "targets": ["https://example.com"],
            "labels": {
                "service": "website",
                "probe_type": "http",
                "probe_node": "blackbox-beijing",
                "blackbox_address": "192.168.7.159:9115",
            },
        }
    ]


@pytest.mark.django_db
def test_http_sd_excludes_targets_without_enabled_probe_nodes(client):
    node_model = apps.get_model("monitoring_stack", "BlackboxProbeNode")
    enabled_node = node_model.objects.create(
        name="blackbox-enabled",
        address="10.0.0.10",
        enabled=True,
    )
    disabled_node = node_model.objects.create(
        name="blackbox-disabled",
        address="10.0.0.11",
        enabled=False,
    )
    ProbeTarget.objects.create(
        type=ProbeTarget.TYPE_HTTP,
        target="https://ready.example.com",
        probe_node=enabled_node,
    )
    ProbeTarget.objects.create(
        type=ProbeTarget.TYPE_HTTP,
        target="https://missing.example.com",
    )
    ProbeTarget.objects.create(
        type=ProbeTarget.TYPE_HTTP,
        target="https://disabled.example.com",
        probe_node=disabled_node,
    )
    config = MonitoringIntegrationConfig.current()
    config.prometheus_http_sd_token = "database-token"
    config.save(update_fields=["prometheus_http_sd_token", "updated_at"])

    response = APIClient().get(
        "/api/v1/monitoring/prometheus/http-sd/blackbox/http/",
        HTTP_AUTHORIZATION="Bearer database-token",
    )

    assert response.status_code == 200
    assert [group["targets"] for group in _payload(response)] == [
        ["https://ready.example.com"]
    ]


@pytest.mark.django_db
def test_prometheus_http_sd_config_uses_blackbox_address_label(client):
    response = client.get("/api/v1/monitoring/prometheus/http-sd/config/")

    assert response.status_code == 200
    payload = _payload(response)
    assert "source_labels: [blackbox_address]" in payload["yaml"]
    assert "target_label: __address__" in payload["yaml"]
    assert "<blackbox-exporter地址>:9115" not in payload["yaml"]


@pytest.mark.django_db
def test_successful_blackbox_install_registers_probe_node(client):
    node_model = apps.get_model("monitoring_stack", "BlackboxProbeNode")
    host = MonitoringHost.objects.create(
        hostname="bb-01",
        address="10.0.0.11",
        enabled=True,
    )
    job = AnsibleInstallJob.objects.create(
        component=AnsibleInstallJob.COMPONENT_BLACKBOX,
        status=AnsibleInstallJob.STATUS_SUCCESS,
        host_ids=[host.id],
        hosts_snapshot=[],
        base_url="http://installer",
        install_dir="/opt/blackbox-exporter",
        image="prom/blackbox-exporter:v1",
        probe_name="blackbox-beijing-idc",
        blackbox_port="9115",
        created_by=client.handler._force_user,
    )

    from monitoring_stack.services.core import mark_component_finished

    mark_component_finished(
        job,
        [host],
        MonitoringComponentStatus.STATUS_SUCCESS,
    )

    node = node_model.objects.get(name="blackbox-beijing-idc")
    assert node.host == host
    assert node.address == "10.0.0.11"
    assert node.port == "9115"
    assert node.enabled is True


@pytest.mark.django_db
def test_probe_targets_crud_and_prometheus_http_sd_token(client):
    with override_settings(MONITORING_ADMIN_TOKEN="monitor-secret"):
        node_model = apps.get_model("monitoring_stack", "BlackboxProbeNode")
        node = node_model.objects.create(
            name="blackbox-crud-test",
            address="10.0.0.13",
            enabled=True,
        )
        create_response = client.post(
            "/api/v1/monitoring/probe-targets/",
            {
                "type": "http",
                "target": "https://example.com",
                "enabled": True,
                "probe_node": node.id,
                "labels": {
                    "region": "center",
                    "env": "prod",
                    "team": "ops",
                    "service": "website",
                },
            },
            format="json",
        )
        assert create_response.status_code == 201

        client.post(
            "/api/v1/monitoring/probe-targets/",
            {
                "type": "http",
                "target": "https://disabled.example.com",
                "enabled": False,
                "labels": {"service": "disabled"},
            },
            format="json",
        )
        client.post(
            "/api/v1/monitoring/probe-targets/",
            {
                "type": "tcp",
                "target": "example.com:443",
                "enabled": True,
                "labels": {"service": "tcp"},
            },
            format="json",
        )

        unauthenticated = APIClient()
        denied = unauthenticated.get(
            "/api/v1/monitoring/prometheus/http-sd/blackbox/http/"
        )
        assert denied.status_code == 401

        sd_response = unauthenticated.get(
            "/api/v1/monitoring/prometheus/http-sd/blackbox/http/",
            HTTP_AUTHORIZATION="Bearer monitor-secret",
        )

        assert sd_response.status_code == 200
        assert _payload(sd_response) == [
            {
                "targets": ["https://example.com"],
                "labels": {
                    "region": "center",
                    "env": "prod",
                    "team": "ops",
                    "service": "website",
                    "probe_type": "http",
                    "probe_node": "blackbox-crud-test",
                    "blackbox_address": "10.0.0.13:9115",
                },
            }
        ]


@pytest.mark.django_db
def test_prometheus_targets_summary_matches_probe_targets(
    client, monkeypatch, settings
):
    settings.MONITORING_PROMETHEUS_URL = "http://prometheus"
    ProbeTarget.objects.create(
        type=ProbeTarget.TYPE_HTTP,
        target="https://example.com",
        enabled=True,
        labels={"service": "website"},
    )
    ProbeTarget.objects.create(
        type=ProbeTarget.TYPE_TCP,
        target="10.0.0.10:3306",
        enabled=True,
        labels={"service": "mysql"},
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "success",
                "data": {
                    "activeTargets": [
                        {
                            "health": "up",
                            "labels": {
                                "job": "blackbox",
                                "instance": "https://example.com",
                                "probe_type": "http",
                            },
                            "discoveredLabels": {
                                "__param_target__": "https://example.com"
                            },
                            "scrapePool": "blackbox/http",
                            "scrapeUrl": "http://blackbox/probe?target=https://example.com",
                            "lastError": "",
                            "lastScrape": "2026-06-23T06:00:00Z",
                        },
                        {
                            "health": "down",
                            "labels": {
                                "job": "blackbox",
                                "instance": "https://orphan.example.com",
                                "probe_type": "http",
                            },
                            "discoveredLabels": {
                                "__param_target__": "https://orphan.example.com"
                            },
                            "scrapePool": "blackbox/http",
                            "scrapeUrl": "http://blackbox/probe?target=https://orphan.example.com",
                            "lastError": "connection refused",
                            "lastScrape": "2026-06-23T06:00:00Z",
                        },
                    ]
                },
            }

    class FakeSession:
        trust_env = True

        def get(self, url, **kwargs):
            assert url == "http://prometheus/api/v1/targets"
            assert kwargs["params"] == {"state": "active"}
            return FakeResponse()

    monkeypatch.setattr("monitoring_stack.services.core.requests.Session", FakeSession)

    response = client.get("/api/v1/monitoring/prometheus/targets/summary/")

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["connected"] is True
    assert payload["active_targets"] == 2
    assert payload["down_targets"] == 1
    assert payload["blackbox_targets"] == 2
    assert payload["probe_statuses"]["http:https://example.com"]["health"] == "up"
    assert payload["reconciliation"]["configured_not_discovered"] == [
        {"type": "tcp", "target": "10.0.0.10:3306"}
    ]
    assert payload["reconciliation"]["discovered_not_configured"] == [
        {"type": "http", "target": "https://orphan.example.com", "health": "down"}
    ]
    assert payload["reconciliation"]["abnormal_targets"] == [
        {
            "type": "http",
            "target": "https://orphan.example.com",
            "health": "down",
            "last_error": "connection refused",
        }
    ]


@pytest.mark.django_db
def test_prometheus_probe_node_discovery_reports_unmanaged_exporters(
    client, monkeypatch, settings
):
    settings.MONITORING_PROMETHEUS_URL = "http://prometheus"
    ProbeTarget.objects.create(
        type=ProbeTarget.TYPE_HTTP,
        target="https://unbound.example.com",
        enabled=True,
    )

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class FakeSession:
        trust_env = True

        def get(self, url, **kwargs):
            if url == "http://prometheus/api/v1/targets":
                return FakeResponse(
                    {
                        "status": "success",
                        "data": {
                            "activeTargets": [
                                {
                                    "health": "up",
                                    "labels": {
                                        "job": "blackbox-exporter",
                                        "instance": "blackbox-exporter:9115",
                                    },
                                    "discoveredLabels": {
                                        "__address__": "blackbox-exporter:9115",
                                        "service": "blackbox-exporter",
                                    },
                                    "scrapePool": "blackbox-exporter",
                                    "scrapeUrl": (
                                        "http://blackbox-exporter:9115/metrics"
                                    ),
                                    "lastError": "",
                                    "lastScrape": "2026-07-29T09:00:00Z",
                                },
                                {
                                    "health": "up",
                                    "labels": {
                                        "job": "blackbox-http",
                                        "instance": "https://example.com",
                                        "probe_type": "http",
                                    },
                                    "discoveredLabels": {
                                        "__address__": "blackbox-exporter:9115",
                                        "__param_target__": "https://example.com",
                                    },
                                    "scrapePool": "blackbox-http",
                                    "scrapeUrl": (
                                        "http://blackbox-exporter:9115/probe"
                                        "?target=https://example.com"
                                    ),
                                },
                            ]
                        },
                    }
                )
            if url == "http://prometheus/api/v1/status/config":
                return FakeResponse(
                    {
                        "status": "success",
                        "data": {
                            "yaml": (
                                "http_sd_configs:\n"
                                "- url: http://host.docker.internal:18081/"
                                "api/prometheus/http-sd/blackbox/http\n"
                            )
                        },
                    }
                )
            raise AssertionError(url)

    monkeypatch.setattr("monitoring_stack.services.core.requests.Session", FakeSession)

    response = client.get(
        "/api/v1/monitoring/prometheus/probe-nodes/discoveries/"
    )

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["connected"] is True
    assert payload["unbound_target_count"] == 1
    assert payload["legacy_http_sd"]["detected"] is True
    assert payload["discoveries"] == [
        {
            "address": "blackbox-exporter",
            "port": "9115",
            "endpoint": "blackbox-exporter:9115",
            "health": "up",
            "job": "blackbox-exporter",
            "last_error": "",
            "last_scrape": "2026-07-29T09:00:00Z",
        }
    ]


@pytest.mark.django_db
def test_prometheus_probe_node_discovery_excludes_registered_endpoint(
    client, monkeypatch, settings
):
    settings.MONITORING_PROMETHEUS_URL = "http://prometheus"
    node_model = apps.get_model("monitoring_stack", "BlackboxProbeNode")
    node = node_model.objects.create(
        name="existing-blackbox",
        address="blackbox-exporter",
        port="9115",
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "success",
                "data": {
                    "activeTargets": [
                        {
                            "health": "up",
                            "labels": {
                                "job": "blackbox-http",
                                "instance": "https://example.com",
                                "blackbox_address": "blackbox-exporter:9115",
                            },
                            "discoveredLabels": {
                                "__address__": "https://example.com",
                                "__param_target__": "https://example.com",
                                "blackbox_address": "blackbox-exporter:9115",
                            },
                            "scrapePool": "blackbox-http",
                            "scrapeUrl": (
                                "http://blackbox-exporter:9115/probe"
                                "?target=https://example.com"
                            ),
                        }
                    ]
                },
            }

    class FakeSession:
        trust_env = True

        def get(self, url, **kwargs):
            if url.endswith("/api/v1/status/config"):
                return FakeResponseWithConfig()
            return FakeResponse()

    class FakeResponseWithConfig(FakeResponse):
        def json(self):
            return {"status": "success", "data": {"yaml": ""}}

    monkeypatch.setattr("monitoring_stack.services.core.requests.Session", FakeSession)

    response = client.get(
        "/api/v1/monitoring/prometheus/probe-nodes/discoveries/"
    )

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["discoveries"] == []
    assert payload["managed_nodes"] == [
        {
            "node_id": node.id,
            "endpoint": "blackbox-exporter:9115",
            "health": "up",
            "last_error": "",
            "last_scrape": "",
        }
    ]


@pytest.mark.django_db
def test_prometheus_probe_node_onboarding_can_bind_only_unbound_targets(client):
    node_model = apps.get_model("monitoring_stack", "BlackboxProbeNode")
    existing_node = node_model.objects.create(
        name="existing-blackbox",
        address="10.0.0.20",
        port="9115",
    )
    unbound_enabled = ProbeTarget.objects.create(
        type=ProbeTarget.TYPE_HTTP,
        target="https://unbound.example.com",
        enabled=True,
    )
    unbound_disabled = ProbeTarget.objects.create(
        type=ProbeTarget.TYPE_HTTP,
        target="https://disabled.example.com",
        enabled=False,
    )
    already_bound = ProbeTarget.objects.create(
        type=ProbeTarget.TYPE_TCP,
        target="db.example.com:3306",
        enabled=True,
        probe_node=existing_node,
    )

    response = client.post(
        "/api/v1/monitoring/prometheus/probe-nodes/onboard/",
        {
            "address": "blackbox-exporter",
            "port": "9115",
            "name": "blackbox-prometheus",
            "bind_unassigned_targets": True,
        },
        format="json",
    )

    assert response.status_code == 201
    payload = _payload(response)
    node = node_model.objects.get(pk=payload["node"]["id"])
    assert node.source == "prometheus"
    assert payload["bound_target_count"] == 1
    unbound_enabled.refresh_from_db()
    unbound_disabled.refresh_from_db()
    already_bound.refresh_from_db()
    assert unbound_enabled.probe_node == node
    assert unbound_disabled.probe_node is None
    assert already_bound.probe_node == existing_node


@pytest.mark.django_db
def test_prometheus_probe_node_onboarding_rejects_registered_endpoint(client):
    node_model = apps.get_model("monitoring_stack", "BlackboxProbeNode")
    node_model.objects.create(
        name="existing-blackbox",
        address="blackbox-exporter",
        port="9115",
    )

    response = client.post(
        "/api/v1/monitoring/prometheus/probe-nodes/onboard/",
        {
            "address": "blackbox-exporter",
            "port": "9115",
            "name": "duplicate-blackbox",
        },
        format="json",
    )

    assert response.status_code == 409


@pytest.mark.django_db
def test_n9e_summary_reports_groups_datasources_rules_and_hosts(
    client,
    monkeypatch,
    settings,
):
    settings.MONITORING_N9E_URL = "http://n9e"
    settings.MONITORING_N9E_USERNAME = "root"
    settings.MONITORING_N9E_PASSWORD = "pw"
    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeSession:
        trust_env = True
        headers = {}

        def post(self, url, **kwargs):
            calls.append(("post", url, kwargs))
            return FakeResponse({"dat": {"access_token": "token-1"}})

        def get(self, url, **kwargs):
            calls.append(("get", url, kwargs))
            if url.endswith("/api/n9e/busi-groups"):
                return FakeResponse({"dat": [{"id": 1}, {"id": 2}]})
            if url.endswith("/api/n9e/busi-group/1/alert-rules"):
                return FakeResponse(
                    {
                        "dat": {
                            "list": [
                                {"id": 101, "enable": True},
                                {"id": 102, "enable": False},
                            ]
                        }
                    }
                )
            if url.endswith("/api/n9e/busi-group/2/alert-rules"):
                return FakeResponse({"dat": [{"id": 201, "disabled": 0}]})
            if url.endswith("/api/n9e/targets"):
                return FakeResponse({"dat": {"list": [{"id": 1}, {"id": 2}, {"id": 3}]}})
            if url.endswith("/api/n9e/datasource/brief"):
                return FakeResponse(
                    {
                        "dat": [
                            {"id": 1, "plugin_type": "prometheus"},
                            {"id": 2, "plugin_type": "loki"},
                        ]
                    }
                )
            raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr("monitoring_stack.services.core.requests.Session", FakeSession)

    response = client.get("/api/v1/monitoring/n9e/summary/")

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["connected"] is True
    assert payload["business_groups"] == 2
    assert payload["datasources"] == 2
    assert payload["prometheus_datasources"] == 1
    assert payload["rules_available"] is True
    assert payload["rules"] == 3
    assert payload["enabled_rules"] == 2
    assert payload["hosts_available"] is True
    assert payload["hosts"] == 3
    assert any(call[1] == "http://n9e/api/n9e/auth/login" for call in calls)


@pytest.mark.django_db
def test_n9e_summary_explains_unsupported_rules_and_hosts(
    client,
    monkeypatch,
    settings,
):
    settings.MONITORING_N9E_URL = "http://n9e"
    settings.MONITORING_N9E_USERNAME = "root"
    settings.MONITORING_N9E_PASSWORD = "pw"

    class FakeResponse:
        def __init__(self, payload=None, status_code=200):
            self._payload = payload or {}
            self.status_code = status_code
            self.text = json.dumps(self._payload)

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"{self.status_code} response")

        def json(self):
            return self._payload

    class FakeSession:
        trust_env = True
        headers = {}

        def post(self, url, **kwargs):
            return FakeResponse({"dat": {"access_token": "token-1"}})

        def get(self, url, **kwargs):
            if url.endswith("/api/n9e/busi-groups"):
                return FakeResponse({"dat": [{"id": 1}]})
            if url.endswith("/api/n9e/datasource/brief"):
                return FakeResponse({"dat": []})
            return FakeResponse({"err": "not found"}, status_code=404)

    monkeypatch.setattr("monitoring_stack.services.core.requests.Session", FakeSession)

    response = client.get("/api/v1/monitoring/n9e/summary/")

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["connected"] is True
    assert payload["rules_available"] is False
    assert payload["rules_unavailable_reason"] == "当前 n9e 版本未暴露"
    assert payload["hosts_available"] is False
    assert payload["hosts_unavailable_reason"] == "当前 n9e 版本未暴露"


@pytest.mark.django_db
def test_governance_sync_persists_prometheus_target_snapshots(
    client,
    monkeypatch,
    settings,
):
    settings.MONITORING_PROMETHEUS_URL = "http://prometheus"

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "success",
                "data": {
                    "activeTargets": [
                        {
                            "health": "up",
                            "labels": {
                                "job": "blackbox",
                                "instance": "https://example.com",
                                "probe_type": "http",
                            },
                            "discoveredLabels": {
                                "__param_target__": "https://example.com"
                            },
                            "scrapePool": "blackbox/http",
                            "scrapeUrl": "http://blackbox/probe?target=https://example.com",
                            "lastError": "",
                        },
                        {
                            "health": "down",
                            "labels": {
                                "job": "node",
                                "instance": "10.0.0.10:9100",
                            },
                            "discoveredLabels": {},
                            "scrapePool": "node",
                            "scrapeUrl": "http://10.0.0.10:9100/metrics",
                            "lastError": "connection refused",
                        },
                    ]
                },
            }

    class FakeSession:
        trust_env = True

        def get(self, url, **kwargs):
            assert url == "http://prometheus/api/v1/targets"
            assert kwargs["params"] == {"state": "active"}
            return FakeResponse()

    monkeypatch.setattr("requests.Session", FakeSession)

    response = client.post(
        "/api/v1/monitoring/governance/sync/",
        {"source": "prometheus"},
        format="json",
    )

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["status"] == "success"
    assert payload["source"] == "prometheus"
    assert payload["summary"]["prometheus_targets"] == 2
    assert payload["summary"]["prometheus_down_targets"] == 1

    snapshot_model = apps.get_model("monitoring_stack", "PrometheusTargetSnapshot")
    rows = {row.identity: row for row in snapshot_model.objects.all()}
    assert set(rows) == {"blackbox/http|https://example.com", "node|10.0.0.10:9100"}
    assert rows["blackbox/http|https://example.com"].probe_type == "http"
    assert rows["blackbox/http|https://example.com"].probe_target == "https://example.com"
    assert rows["node|10.0.0.10:9100"].health == "down"
    assert rows["node|10.0.0.10:9100"].last_error == "connection refused"


@pytest.mark.django_db
def test_governance_sync_persists_n9e_snapshots(client, monkeypatch, settings):
    settings.MONITORING_N9E_URL = "http://n9e"
    settings.MONITORING_N9E_USERNAME = "root"
    settings.MONITORING_N9E_PASSWORD = "pw"

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeSession:
        trust_env = True
        headers = {}

        def post(self, url, **kwargs):
            assert url == "http://n9e/api/n9e/auth/login"
            return FakeResponse({"dat": {"access_token": "token-1"}})

        def get(self, url, **kwargs):
            if url.endswith("/api/n9e/busi-groups"):
                return FakeResponse({"dat": [{"id": 1, "name": "ops"}]})
            if url.endswith("/api/n9e/datasource/brief"):
                return FakeResponse(
                    {
                        "dat": [
                            {
                                "id": 10,
                                "name": "prom-main",
                                "plugin_type": "prometheus",
                            }
                        ]
                    }
                )
            if url.endswith("/api/n9e/busi-group/1/alert-rules"):
                return FakeResponse(
                    {
                        "dat": {
                            "list": [
                                {
                                    "id": 101,
                                    "name": "host down",
                                    "enable": True,
                                    "severity": 2,
                                }
                            ]
                        }
                    }
                )
            if url.endswith("/api/n9e/targets"):
                return FakeResponse(
                    {
                        "dat": {
                            "list": [
                                {
                                    "ident": "app-01",
                                    "hostname": "app-01",
                                    "ip": "10.0.0.11",
                                    "labels": {"region": "beijing"},
                                },
                                {
                                    "ident": "zjq-192-168-7-160",
                                    "hostname": "zjq-192-168-7-160",
                                    "host_ip": "172.50.1.2",
                                    "remote_addr": "192.168.7.160",
                                    "labels": {"region": "beijing"},
                                }
                            ]
                        }
                    }
                )
            return FakeResponse({"dat": []})

    monkeypatch.setattr("requests.Session", FakeSession)

    response = client.post(
        "/api/v1/monitoring/governance/sync/",
        {"source": "n9e"},
        format="json",
    )

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["status"] == "success"
    assert payload["source"] == "n9e"
    assert payload["summary"]["n9e_business_groups"] == 1
    assert payload["summary"]["n9e_datasources"] == 1
    assert payload["summary"]["n9e_targets"] == 2
    assert payload["summary"]["n9e_rules"] == 1

    group_model = apps.get_model("monitoring_stack", "N9eBusinessGroupSnapshot")
    datasource_model = apps.get_model("monitoring_stack", "N9eDatasourceSnapshot")
    target_model = apps.get_model("monitoring_stack", "N9eTargetSnapshot")
    rule_model = apps.get_model("monitoring_stack", "N9eRuleSnapshot")
    assert group_model.objects.get(external_id="1").name == "ops"
    assert datasource_model.objects.get(external_id="10").type == "prometheus"
    assert target_model.objects.get(identity="app-01").address == "10.0.0.11"
    assert (
        target_model.objects.get(identity="zjq-192-168-7-160").address
        == "192.168.7.160"
    )
    rule = rule_model.objects.get(identity="1:101")
    assert rule.name == "host down"
    assert rule.enabled is True
    assert rule.severity == "2"


@pytest.mark.django_db
def test_governance_overview_rebuilds_probe_and_component_findings(client, tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    run_model = apps.get_model("monitoring_stack", "MonitoringSnapshotRun")
    prometheus_model = apps.get_model("monitoring_stack", "PrometheusTargetSnapshot")
    finding_model = apps.get_model("monitoring_stack", "MonitoringGovernanceFinding")
    snapshot_run = run_model.objects.create(
        source="prometheus",
        status="success",
        started_at="2026-06-24T03:00:00Z",
        finished_at="2026-06-24T03:00:01Z",
        summary={"prometheus_targets": 2},
    )
    MonitoringHost.objects.create(
        hostname="app-01",
        address="10.0.0.11",
        enabled=True,
    )
    ProbeTarget.objects.create(
        type=ProbeTarget.TYPE_HTTP,
        target="https://configured.example.com",
        enabled=True,
        labels={"service": "web"},
    )
    prometheus_model.objects.create(
        identity="blackbox/http|https://orphan.example.com",
        job="blackbox",
        instance="https://orphan.example.com",
        scrape_pool="blackbox/http",
        health="down",
        probe_type="http",
        probe_target="https://orphan.example.com",
        last_error="connection refused",
        raw={"health": "down"},
        last_seen_run=snapshot_run,
        last_seen_at="2026-06-24T03:00:01Z",
    )

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        response = client.get("/api/v1/monitoring/governance/overview/")

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["finding_counts"]["open"] == 5
    assert payload["finding_counts"]["critical"] == 1
    assert payload["finding_counts"]["warning"] == 4
    categories = {
        item.category
        for item in finding_model.objects.filter(status="open").order_by("category")
    }
    assert categories == {
        "blackbox_not_installed",
        "categraf_not_installed",
        "probe_abnormal",
        "probe_configured_not_discovered",
        "probe_discovered_not_configured",
    }
    abnormal = finding_model.objects.get(category="probe_abnormal")
    assert abnormal.subject_type == "probe"
    assert abnormal.subject_key == "http:https://orphan.example.com"
    assert abnormal.recommended_action == "fix_probe_target"


@pytest.mark.django_db
def test_governance_overview_detects_host_not_visible_in_n9e(client, tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    run_model = apps.get_model("monitoring_stack", "MonitoringSnapshotRun")
    target_model = apps.get_model("monitoring_stack", "N9eTargetSnapshot")
    finding_model = apps.get_model("monitoring_stack", "MonitoringGovernanceFinding")
    snapshot_run = run_model.objects.create(
        source="n9e",
        status="success",
        started_at=timezone.now(),
        finished_at=timezone.now(),
        summary={"n9e_targets": 1},
    )
    visible_host = MonitoringHost.objects.create(
        hostname="visible-01",
        address="10.0.0.11",
        enabled=True,
    )
    missing_host = MonitoringHost.objects.create(
        hostname="missing-01",
        address="10.0.0.12",
        enabled=True,
    )
    for host in [visible_host, missing_host]:
        for component in [
            AnsibleInstallJob.COMPONENT_CATEGRAF,
            AnsibleInstallJob.COMPONENT_BLACKBOX,
        ]:
            MonitoringComponentStatus.objects.create(
                host=host,
                component=component,
                status=MonitoringComponentStatus.STATUS_SUCCESS,
            )
    target_model.objects.create(
        identity="visible-01",
        hostname="visible-01",
        address="10.0.0.11",
        labels={"region": "beijing"},
        raw={"ident": "visible-01"},
        last_seen_run=snapshot_run,
        last_seen_at=timezone.now(),
    )

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        response = client.get("/api/v1/monitoring/governance/overview/")

    assert response.status_code == 200
    finding = finding_model.objects.get(category="host_not_in_n9e")
    assert finding.subject_type == "host"
    assert finding.subject_key == "missing-01"
    assert finding.details["host_id"] == missing_host.id
    assert finding.recommended_action == "check_n9e_registration"
    assert not finding_model.objects.filter(
        category="host_not_in_n9e",
        subject_key="visible-01",
    ).exists()


@pytest.mark.django_db
def test_governance_overview_detects_categraf_host_not_scraped_by_prometheus(
    client,
    tmp_path,
):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    run_model = apps.get_model("monitoring_stack", "MonitoringSnapshotRun")
    prometheus_model = apps.get_model("monitoring_stack", "PrometheusTargetSnapshot")
    finding_model = apps.get_model("monitoring_stack", "MonitoringGovernanceFinding")
    snapshot_run = run_model.objects.create(
        source="prometheus",
        status="success",
        started_at=timezone.now(),
        finished_at=timezone.now(),
        summary={"prometheus_targets": 1},
    )
    scraped_host = MonitoringHost.objects.create(
        hostname="scraped-01",
        address="10.0.0.21",
        enabled=True,
    )
    missing_host = MonitoringHost.objects.create(
        hostname="missing-01",
        address="10.0.0.22",
        enabled=True,
    )
    for host in [scraped_host, missing_host]:
        MonitoringComponentStatus.objects.create(
            host=host,
            component=AnsibleInstallJob.COMPONENT_CATEGRAF,
            status=MonitoringComponentStatus.STATUS_SUCCESS,
        )
        MonitoringComponentStatus.objects.create(
            host=host,
            component=AnsibleInstallJob.COMPONENT_BLACKBOX,
            status=MonitoringComponentStatus.STATUS_SUCCESS,
        )
    prometheus_model.objects.create(
        identity="node|10.0.0.21:9100",
        job="node",
        instance="10.0.0.21:9100",
        scrape_pool="node",
        health="up",
        probe_type="",
        probe_target="",
        last_error="",
        raw={"labels": {"instance": "10.0.0.21:9100", "job": "node"}},
        last_seen_run=snapshot_run,
        last_seen_at=timezone.now(),
    )

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        response = client.get("/api/v1/monitoring/governance/overview/")

    assert response.status_code == 200
    finding = finding_model.objects.get(category="host_not_scraped_by_prometheus")
    assert finding.subject_type == "host"
    assert finding.subject_key == "missing-01"
    assert finding.details["host_id"] == missing_host.id
    assert finding.recommended_action == "check_prometheus_scrape"
    assert not finding_model.objects.filter(
        category="host_not_scraped_by_prometheus",
        subject_key="scraped-01",
    ).exists()


@pytest.mark.django_db
def test_governance_overview_uses_n9e_visibility_as_external_categraf_evidence(
    client,
    tmp_path,
):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    run_model = apps.get_model("monitoring_stack", "MonitoringSnapshotRun")
    target_model = apps.get_model("monitoring_stack", "N9eTargetSnapshot")
    snapshot_run = run_model.objects.create(
        source="n9e",
        status="success",
        started_at=timezone.now(),
        finished_at=timezone.now(),
        summary={"n9e_targets": 1},
    )
    host = MonitoringHost.objects.create(
        hostname="app-01",
        address="10.0.0.11",
        enabled=True,
    )
    target_model.objects.create(
        identity="app-01",
        hostname="app-01",
        address="10.0.0.11",
        raw={"ident": "app-01", "remote_addr": "10.0.0.11"},
        last_seen_run=snapshot_run,
        last_seen_at=timezone.now(),
    )

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        response = client.get("/api/v1/monitoring/governance/overview/")

    assert response.status_code == 200
    finding_model = apps.get_model("monitoring_stack", "MonitoringGovernanceFinding")
    assert not finding_model.objects.filter(
        category="categraf_not_installed",
        subject_key=host.hostname,
    ).exists()


@pytest.mark.django_db
def test_host_component_statuses_include_external_discovery(client, monkeypatch):
    run_model = apps.get_model("monitoring_stack", "MonitoringSnapshotRun")
    target_model = apps.get_model("monitoring_stack", "N9eTargetSnapshot")
    snapshot_run = run_model.objects.create(
        source="n9e",
        status="success",
        started_at=timezone.now(),
        finished_at=timezone.now(),
        summary={"n9e_targets": 1},
    )
    host = MonitoringHost.objects.create(
        hostname="app-01",
        address="10.0.0.11",
        enabled=True,
    )
    target_model.objects.create(
        identity="app-01",
        hostname="app-01",
        address="10.0.0.11",
        raw={"ident": "app-01", "remote_addr": "10.0.0.11"},
        last_seen_run=snapshot_run,
        last_seen_at=timezone.now(),
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

    class FakeSession:
        trust_env = True

        def get(self, url, **kwargs):
            assert url == "http://10.0.0.11:9115/-/healthy"
            assert self.trust_env is False
            return FakeResponse()

    monkeypatch.setattr("monitoring_stack.services.core.requests.Session", FakeSession)

    response = client.get(f"/api/v1/monitoring/hosts/{host.id}/")

    assert response.status_code == 200
    statuses = {
        item["component"]: item for item in _payload(response)["component_statuses"]
    }
    assert statuses["categraf"]["status"] == "external"
    assert statuses["categraf"]["runtime_status"] == "unknown"
    assert statuses["blackbox"]["status"] == "external"
    assert statuses["blackbox"]["runtime_status"] == "online"
    assert statuses["blackbox"]["runtime_endpoint"] == "http://10.0.0.11:9115/-/healthy"


@pytest.mark.django_db
def test_blackbox_instances_endpoint_aggregates_hosts_and_prometheus_targets(client):
    run_model = apps.get_model("monitoring_stack", "MonitoringSnapshotRun")
    prometheus_model = apps.get_model("monitoring_stack", "PrometheusTargetSnapshot")
    snapshot_run = run_model.objects.create(
        source="prometheus",
        status="success",
        started_at=timezone.now(),
        finished_at=timezone.now(),
        summary={"prometheus_targets": 1},
    )
    healthy_host = MonitoringHost.objects.create(
        hostname="bb-01",
        address="10.0.0.11",
        enabled=True,
    )
    failed_host = MonitoringHost.objects.create(
        hostname="bb-02",
        address="10.0.0.12",
        enabled=True,
    )
    job = AnsibleInstallJob.objects.create(
        component=AnsibleInstallJob.COMPONENT_BLACKBOX,
        status=AnsibleInstallJob.STATUS_SUCCESS,
        host_ids=[healthy_host.id],
        hosts_snapshot=[],
        base_url="http://installer",
        install_dir="/opt/blackbox-exporter",
        image="prom/blackbox-exporter:v1",
        probe_name="blackbox-beijing-idc",
        blackbox_port="9115",
        created_by=client.handler._force_user,
    )
    job.hosts_snapshot = [
        {
            "id": healthy_host.id,
            "hostname": healthy_host.hostname,
            "address": healthy_host.address,
        }
    ]
    job.save(update_fields=["hosts_snapshot"])
    MonitoringComponentStatus.objects.create(
        host=healthy_host,
        component=AnsibleInstallJob.COMPONENT_BLACKBOX,
        status=MonitoringComponentStatus.STATUS_SUCCESS,
        install_dir="/opt/blackbox-exporter",
        last_job=job,
    )
    MonitoringComponentStatus.objects.create(
        host=failed_host,
        component=AnsibleInstallJob.COMPONENT_BLACKBOX,
        status=MonitoringComponentStatus.STATUS_FAILED,
        last_error="ssh failed",
    )
    prometheus_model.objects.create(
        identity="blackbox/http|https://example.com",
        job="blackbox",
        instance="https://example.com",
        scrape_pool="blackbox/http",
        health="up",
        probe_type="http",
        probe_target="https://example.com",
        last_error="",
        raw={
            "scrapeUrl": "http://10.0.0.11:9115/probe?target=https://example.com",
            "labels": {"job": "blackbox"},
        },
        last_seen_run=snapshot_run,
        last_seen_at=timezone.now(),
    )

    response = client.get("/api/v1/monitoring/blackbox/instances/")

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["summary"] == {
        "total": 2,
        "installed": 1,
        "abnormal": 1,
        "prometheus_discovered": 1,
    }
    rows = {item["hostname"]: item for item in payload["results"]}
    assert rows["bb-01"]["port"] == "9115"
    assert rows["bb-01"]["probe_name"] == "blackbox-beijing-idc"
    assert rows["bb-01"]["prometheus_status"] == "up"
    assert rows["bb-01"]["probe_target_count"] == 1
    assert rows["bb-01"]["install_status"] == "success"
    assert rows["bb-02"]["prometheus_status"] == "not_discovered"
    assert rows["bb-02"]["install_status"] == "failed"
    assert rows["bb-02"]["last_error"] == "ssh failed"


@pytest.mark.django_db
def test_categraf_runtime_uses_n9e_offline_state(client, monkeypatch, settings):
    settings.MONITORING_N9E_URL = "http://n9e"
    settings.MONITORING_N9E_USERNAME = "root"
    settings.MONITORING_N9E_PASSWORD = "pw"
    host = MonitoringHost.objects.create(
        hostname="app-01",
        address="10.0.0.11",
        ssh_user="root",
    )
    job = AnsibleInstallJob.objects.create(
        component=AnsibleInstallJob.COMPONENT_CATEGRAF,
        status=AnsibleInstallJob.STATUS_SUCCESS,
        host_ids=[host.id],
        base_url="http://hyperops/api/v1/monitoring/installer",
        n9e_url="http://n9e",
        install_dir="/opt/categraf",
        image="flashcatcloud/categraf:v1",
    )
    MonitoringComponentStatus.objects.create(
        host=host,
        component=AnsibleInstallJob.COMPONENT_CATEGRAF,
        status=MonitoringComponentStatus.STATUS_SUCCESS,
        last_job=job,
    )

    class FakeResponse:
        def __init__(self, payload=None):
            self._payload = payload or {}

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeSession:
        trust_env = True
        headers = {}

        def post(self, url, **kwargs):
            return FakeResponse({"dat": {"access_token": "token-1"}})

        def get(self, url, **kwargs):
            if url.endswith("/api/n9e/targets"):
                return FakeResponse(
                    {
                        "dat": {
                            "list": [
                                {
                                    "ident": "app-01",
                                    "host": "10.0.0.11",
                                    "status": "offline",
                                }
                            ]
                        }
                    }
                )
            return FakeResponse({"dat": []})

    monkeypatch.setattr("monitoring_stack.services.core.requests.Session", FakeSession)

    response = client.get(f"/api/v1/monitoring/hosts/{host.id}/")

    assert response.status_code == 200
    statuses = {
        item["component"]: item for item in _payload(response)["component_statuses"]
    }
    assert statuses["categraf"]["runtime_status"] == "abnormal"
    assert "offline" in statuses["categraf"]["runtime_reason"]


@pytest.mark.django_db
def test_categraf_runtime_uses_n9e_target_up_snapshot(client, settings):
    settings.MONITORING_N9E_URL = ""
    settings.MONITORING_N9E_USERNAME = ""
    settings.MONITORING_N9E_PASSWORD = ""
    run_model = apps.get_model("monitoring_stack", "MonitoringSnapshotRun")
    n9e_model = apps.get_model("monitoring_stack", "N9eTargetSnapshot")
    snapshot_run = run_model.objects.create(
        source="n9e",
        status="success",
        started_at=timezone.now(),
        finished_at=timezone.now(),
        summary={"n9e_targets": 2},
    )
    online_host = MonitoringHost.objects.create(
        hostname="app-online",
        address="10.0.0.21",
        ssh_user="root",
    )
    offline_host = MonitoringHost.objects.create(
        hostname="app-offline",
        address="10.0.0.22",
        ssh_user="root",
    )
    job = AnsibleInstallJob.objects.create(
        component=AnsibleInstallJob.COMPONENT_CATEGRAF,
        status=AnsibleInstallJob.STATUS_SUCCESS,
        host_ids=[online_host.id, offline_host.id],
        base_url="http://hyperops/api/v1/monitoring/installer",
        n9e_url="http://n9e",
        install_dir="/opt/categraf",
        image="flashcatcloud/categraf:v1",
    )
    for host in (online_host, offline_host):
        MonitoringComponentStatus.objects.create(
            host=host,
            component=AnsibleInstallJob.COMPONENT_CATEGRAF,
            status=MonitoringComponentStatus.STATUS_SUCCESS,
            last_job=job,
        )
    n9e_model.objects.create(
        identity="app-online",
        hostname="app-online",
        address="10.0.0.21",
        raw={"ident": "app-online", "host_ip": "10.0.0.21", "target_up": 2},
        last_seen_run=snapshot_run,
        last_seen_at=timezone.now(),
    )
    n9e_model.objects.create(
        identity="app-offline",
        hostname="app-offline",
        address="10.0.0.22",
        raw={"ident": "app-offline", "host_ip": "10.0.0.22", "target_up": 0},
        last_seen_run=snapshot_run,
        last_seen_at=timezone.now(),
    )

    online_response = client.get(f"/api/v1/monitoring/hosts/{online_host.id}/")
    offline_response = client.get(f"/api/v1/monitoring/hosts/{offline_host.id}/")

    assert online_response.status_code == 200
    assert offline_response.status_code == 200
    online_statuses = {
        item["component"]: item
        for item in _payload(online_response)["component_statuses"]
    }
    offline_statuses = {
        item["component"]: item
        for item in _payload(offline_response)["component_statuses"]
    }
    assert online_statuses["categraf"]["runtime_status"] == "online"
    assert offline_statuses["categraf"]["runtime_status"] == "abnormal"
    assert "target_up=0" in offline_statuses["categraf"]["runtime_reason"]


@pytest.mark.django_db
def test_assets_reconciliation_returns_n9e_and_prometheus_unmanaged_hosts(client):
    run_model = apps.get_model("monitoring_stack", "MonitoringSnapshotRun")
    n9e_model = apps.get_model("monitoring_stack", "N9eTargetSnapshot")
    prometheus_model = apps.get_model("monitoring_stack", "PrometheusTargetSnapshot")
    snapshot_run = run_model.objects.create(
        source="all",
        status="success",
        started_at=timezone.now(),
        finished_at=timezone.now(),
        summary={"n9e_targets": 2, "prometheus_targets": 2},
    )
    MonitoringHost.objects.create(
        hostname="managed-01",
        address="10.0.0.31",
        enabled=True,
    )
    n9e_model.objects.create(
        identity="managed-01",
        hostname="managed-01",
        address="10.0.0.31",
        labels={"env": "prod"},
        raw={"ident": "managed-01"},
        last_seen_run=snapshot_run,
        last_seen_at=timezone.now(),
    )
    n9e_model.objects.create(
        identity="n9e-only-01",
        hostname="n9e-only-01",
        address="10.0.0.32",
        labels={"env": "prod"},
        raw={"ident": "n9e-only-01"},
        last_seen_run=snapshot_run,
        last_seen_at=timezone.now(),
    )
    prometheus_model.objects.create(
        identity="node|10.0.0.31:9100",
        job="node",
        instance="10.0.0.31:9100",
        scrape_pool="node",
        health="up",
        probe_type="",
        probe_target="",
        last_error="",
        raw={"labels": {"instance": "10.0.0.31:9100"}},
        last_seen_run=snapshot_run,
        last_seen_at=timezone.now(),
    )
    prometheus_model.objects.create(
        identity="node|10.0.0.33:9100",
        job="node",
        instance="10.0.0.33:9100",
        scrape_pool="node",
        health="up",
        probe_type="",
        probe_target="",
        last_error="",
        raw={"labels": {"instance": "10.0.0.33:9100"}},
        last_seen_run=snapshot_run,
        last_seen_at=timezone.now(),
    )

    response = client.get("/api/v1/monitoring/assets/reconciliation/")

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["summary"] == {
        "hyperops_hosts": 1,
        "n9e_only": 1,
        "prometheus_only": 1,
        "unmanaged": 2,
    }
    rows = {(item["source"], item["address"]): item for item in payload["results"]}
    assert rows[("n9e", "10.0.0.32")]["hostname"] == "n9e-only-01"
    assert rows[("n9e", "10.0.0.32")]["can_import"] is True
    assert rows[("prometheus", "10.0.0.33")]["hostname"] == "10.0.0.33"
    assert rows[("prometheus", "10.0.0.33")]["port"] == "9100"
    assert rows[("prometheus", "10.0.0.33")]["health"] == "up"


@pytest.mark.django_db
def test_assets_reconciliation_prefers_n9e_remote_addr_for_connection(client):
    run_model = apps.get_model("monitoring_stack", "MonitoringSnapshotRun")
    n9e_model = apps.get_model("monitoring_stack", "N9eTargetSnapshot")
    snapshot_run = run_model.objects.create(
        source="n9e",
        status="success",
        started_at=timezone.now(),
        finished_at=timezone.now(),
        summary={"n9e_targets": 1},
    )
    n9e_model.objects.create(
        identity="zjq-192-168-7-160",
        hostname="zjq-192-168-7-160",
        address="172.50.1.2",
        labels={"env": "dev"},
        raw={
            "ident": "zjq-192-168-7-160",
            "host_ip": "172.50.1.2",
            "remote_addr": "192.168.7.160",
        },
        last_seen_run=snapshot_run,
        last_seen_at=timezone.now(),
    )

    response = client.get("/api/v1/monitoring/assets/reconciliation/")

    assert response.status_code == 200
    payload = _payload(response)
    rows = {(item["source"], item["key"]): item for item in payload["results"]}
    assert rows[("n9e", "zjq-192-168-7-160")]["address"] == "192.168.7.160"


@pytest.mark.django_db
def test_governance_findings_filter_by_status_and_subject_type(client):
    finding_model = apps.get_model("monitoring_stack", "MonitoringGovernanceFinding")
    finding_model.objects.create(
        category="probe_abnormal",
        severity="critical",
        status="open",
        title="Probe abnormal",
        subject_type="probe",
        subject_key="http:https://example.com",
        source="prometheus",
        details={"health": "down"},
        recommended_action="fix_probe_target",
    )
    finding_model.objects.create(
        category="categraf_not_installed",
        severity="warning",
        status="ignored",
        title="Categraf not installed",
        subject_type="host",
        subject_key="app-01",
        source="hyperops",
        details={},
        recommended_action="install_categraf",
    )

    response = client.get(
        "/api/v1/monitoring/governance/findings/",
        {"status": "open", "subject_type": "probe"},
    )

    assert response.status_code == 200
    results = _payload(response)["results"]
    assert len(results) == 1
    assert results[0]["category"] == "probe_abnormal"
    assert results[0]["severity"] == "critical"
    assert results[0]["recommended_action"] == "fix_probe_target"


@pytest.mark.django_db
def test_governance_finding_can_create_probe_target(client):
    finding_model = apps.get_model("monitoring_stack", "MonitoringGovernanceFinding")
    finding = finding_model.objects.create(
        category="probe_discovered_not_configured",
        severity="warning",
        status="open",
        title="Probe not managed",
        subject_type="probe",
        subject_key="http:https://orphan.example.com",
        source="prometheus",
        details={
            "type": "http",
            "target": "https://orphan.example.com",
            "health": "up",
        },
        recommended_action="create_probe_target",
    )

    response = client.post(
        f"/api/v1/monitoring/governance/findings/{finding.id}/resolve/",
        {"action": "create_probe_target"},
        format="json",
    )

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["status"] == "resolved"
    target = ProbeTarget.objects.get(target="https://orphan.example.com")
    assert target.type == ProbeTarget.TYPE_HTTP
    assert target.enabled is True


@pytest.mark.django_db
def test_governance_finding_can_start_component_install(client, monkeypatch):
    finding_model = apps.get_model("monitoring_stack", "MonitoringGovernanceFinding")
    host = MonitoringHost.objects.create(
        hostname="app-01",
        address="10.0.0.11",
        enabled=True,
    )
    finding = finding_model.objects.create(
        category="categraf_not_installed",
        severity="warning",
        status="open",
        title="Categraf not installed",
        subject_type="host",
        subject_key="app-01",
        source="hyperops",
        details={"host_id": host.id, "address": host.address},
        recommended_action="install_categraf",
    )

    class FakeTask:
        @staticmethod
        def delay(job_id):
            return job_id

    monkeypatch.setattr("monitoring_stack.tasks.run_ansible_install_job", FakeTask)

    response = client.post(
        f"/api/v1/monitoring/governance/findings/{finding.id}/resolve/",
        {
            "action": "install_categraf",
            "payload": {
                "base_url": "http://hyperops.local/api/v1/monitoring/installer",
                "n9e_url": "http://n9e",
                "profiles": ["linux-basic"],
            },
        },
        format="json",
    )

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["status"] == "resolved"
    job = AnsibleInstallJob.objects.get()
    assert job.component == AnsibleInstallJob.COMPONENT_CATEGRAF
    assert job.host_ids == [host.id]
    status = MonitoringComponentStatus.objects.get(
        host=host,
        component=AnsibleInstallJob.COMPONENT_CATEGRAF,
    )
    assert status.status == MonitoringComponentStatus.STATUS_INSTALLING


@pytest.mark.django_db
def test_governance_finding_can_be_ignored(client):
    finding_model = apps.get_model("monitoring_stack", "MonitoringGovernanceFinding")
    finding = finding_model.objects.create(
        category="probe_abnormal",
        severity="critical",
        status="open",
        title="Probe abnormal",
        subject_type="probe",
        subject_key="http:https://example.com",
        source="prometheus",
        details={},
        recommended_action="fix_probe_target",
    )

    response = client.post(
        f"/api/v1/monitoring/governance/findings/{finding.id}/resolve/",
        {"action": "ignore"},
        format="json",
    )

    assert response.status_code == 200
    finding.refresh_from_db()
    assert finding.status == "ignored"
    assert _payload(response)["status"] == "ignored"


@pytest.mark.django_db
def test_governance_overview_detects_rule_template_not_imported(client, tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "linux-host.yml").write_text(
        "groups:\n- name: linux\n",
        encoding="utf-8",
    )

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        response = client.get("/api/v1/monitoring/governance/overview/")

    assert response.status_code == 200
    finding_model = apps.get_model("monitoring_stack", "MonitoringGovernanceFinding")
    finding = finding_model.objects.get(category="rule_template_not_imported")
    assert finding.subject_type == "rule"
    assert finding.subject_key == "linux-host.yml"
    assert finding.recommended_action == "import_rule_template"


@pytest.mark.django_db
def test_governance_overview_detects_untracked_n9e_rule(client, tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    rule_model = apps.get_model("monitoring_stack", "N9eRuleSnapshot")
    rule_model.objects.create(
        identity="manual-cpu-rule",
        group_id="10",
        name="Manual CPU rule",
        enabled=True,
        severity="warning",
        raw={"name": "Manual CPU rule"},
        last_seen_at=timezone.now(),
    )

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        response = client.get("/api/v1/monitoring/governance/overview/")

    assert response.status_code == 200
    finding_model = apps.get_model("monitoring_stack", "MonitoringGovernanceFinding")
    finding = finding_model.objects.get(category="n9e_rule_untracked")
    assert finding.subject_type == "rule"
    assert finding.subject_key == "manual-cpu-rule"
    assert finding.recommended_action == "review_n9e_rule"


@pytest.mark.django_db
def test_governance_overview_does_not_flag_n9e_rule_that_exists_in_template(
    client, tmp_path
):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "n9e-categraf-blackbox-rules.yml").write_text(
        "groups:\n"
        "  - name: categraf-host\n"
        "    rules:\n"
        "      - alert: 主机CPU使用率过高\n"
        "        expr: cpu_usage_active > 85\n",
        encoding="utf-8",
    )
    rule_model = apps.get_model("monitoring_stack", "N9eRuleSnapshot")
    rule_model.objects.create(
        identity="10:101",
        group_id="10",
        name="主机CPU使用率过高",
        enabled=True,
        severity="warning",
        raw={"name": "主机CPU使用率过高"},
        last_seen_at=timezone.now(),
    )

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        response = client.get("/api/v1/monitoring/governance/overview/")

    assert response.status_code == 200
    finding_model = apps.get_model("monitoring_stack", "MonitoringGovernanceFinding")
    assert not finding_model.objects.filter(
        category="n9e_rule_untracked",
        subject_key="10:101",
    ).exists()


@pytest.mark.django_db
def test_governance_overview_does_not_flag_template_import_when_alerts_exist_in_n9e(
    client, tmp_path
):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "n9e-categraf-blackbox-rules.yml").write_text(
        "groups:\n"
        "  - name: categraf-host\n"
        "    rules:\n"
        "      - alert: 主机CPU使用率过高\n"
        "        expr: cpu_usage_active > 85\n"
        "      - alert: 主机内存使用率过高\n"
        "        expr: mem_used_percent > 90\n",
        encoding="utf-8",
    )
    rule_model = apps.get_model("monitoring_stack", "N9eRuleSnapshot")
    for index, name in enumerate(["主机CPU使用率过高", "主机内存使用率过高"], start=1):
        rule_model.objects.create(
            identity=f"10:{index}",
            group_id="10",
            name=name,
            enabled=True,
            severity="warning",
            raw={"name": name},
            last_seen_at=timezone.now(),
        )

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        response = client.get("/api/v1/monitoring/governance/overview/")

    assert response.status_code == 200
    finding_model = apps.get_model("monitoring_stack", "MonitoringGovernanceFinding")
    assert not finding_model.objects.filter(
        category="rule_template_not_imported",
        subject_key="n9e-categraf-blackbox-rules.yml",
    ).exists()


@pytest.mark.django_db
def test_rule_detail_returns_structured_alert_rules(client, tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "n9e.yml").write_text(
        "groups:\n"
        "  - name: categraf-host\n"
        "    rules:\n"
        "      - alert: 主机CPU使用率过高\n"
        "        expr: cpu_usage_active > 85\n"
        "        for: 5m\n"
        "        labels:\n"
        "          severity: warning\n"
        "          category: host\n"
        "        annotations:\n"
        "          summary: 主机 CPU 使用率过高\n"
        "          description: CPU 使用率持续过高。\n",
        encoding="utf-8",
    )

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        response = client.get("/api/v1/monitoring/rules/n9e.yml/")

    assert response.status_code == 200
    data = _payload(response)
    assert data["name"] == "n9e.yml"
    assert data["rule_count"] == 1
    assert data["groups"][0]["name"] == "categraf-host"
    item = data["groups"][0]["rules"][0]
    assert item["alert"] == "主机CPU使用率过高"
    assert item["expr"] == "cpu_usage_active > 85"
    assert item["severity"] == "warning"
    assert item["category"] == "host"
    assert item["summary"] == "主机 CPU 使用率过高"


@pytest.mark.django_db
def test_rule_detail_patch_updates_single_alert_rule(client, tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    path = rules_dir / "n9e.yml"
    path.write_text(
        "groups:\n"
        "  - name: categraf-host\n"
        "    rules:\n"
        "      - alert: 主机CPU使用率过高\n"
        "        expr: cpu_usage_active > 85\n"
        "        for: 5m\n"
        "        labels:\n"
        "          severity: warning\n"
        "          category: host\n"
        "        annotations:\n"
        "          summary: 主机 CPU 使用率过高\n"
        "          description: CPU 使用率持续过高。\n",
        encoding="utf-8",
    )

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        response = client.patch(
            "/api/v1/monitoring/rules/n9e.yml/",
            {
                "group_index": 0,
                "rule_index": 0,
                "rule": {
                    "alert": "主机CPU使用率过高",
                    "expr": "cpu_usage_active > 90",
                    "for": "10m",
                    "severity": "critical",
                    "category": "host",
                    "summary": "CPU 已超过 90%",
                    "description": "CPU 使用率持续 10 分钟超过 90%。",
                },
            },
            format="json",
        )

    assert response.status_code == 200
    data = _payload(response)
    item = data["groups"][0]["rules"][0]
    assert item["expr"] == "cpu_usage_active > 90"
    assert item["for"] == "10m"
    assert item["severity"] == "critical"
    content = path.read_text(encoding="utf-8")
    assert "cpu_usage_active > 90" in content
    assert "CPU 已超过 90%" in content


@pytest.mark.django_db
def test_rule_detail_patch_updates_full_yaml_content(client, tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    path = rules_dir / "n9e.yml"
    path.write_text(
        "groups:\n"
        "  - name: categraf-host\n"
        "    rules:\n"
        "      - alert: 主机CPU使用率过高\n"
        "        expr: cpu_usage_active > 85\n",
        encoding="utf-8",
    )
    next_content = (
        "groups:\n"
        "  - name: categraf-host\n"
        "    rules:\n"
        "      - alert: 主机CPU使用率严重过高\n"
        "        expr: cpu_usage_active > 95\n"
        "        for: 3m\n"
        "        labels:\n"
        "          severity: critical\n"
        "          category: host\n"
    )

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        response = client.patch(
            "/api/v1/monitoring/rules/n9e.yml/",
            {"content": next_content},
            format="json",
        )

    assert response.status_code == 200
    data = _payload(response)
    assert data["rule_count"] == 1
    item = data["groups"][0]["rules"][0]
    assert item["alert"] == "主机CPU使用率严重过高"
    assert item["expr"] == "cpu_usage_active > 95"
    assert path.read_text(encoding="utf-8") == next_content


@pytest.mark.django_db
def test_rule_detail_patch_rejects_invalid_yaml_content(client, tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    path = rules_dir / "n9e.yml"
    original_content = (
        "groups:\n"
        "  - name: categraf-host\n"
        "    rules:\n"
        "      - alert: 主机CPU使用率过高\n"
        "        expr: cpu_usage_active > 85\n"
    )
    path.write_text(original_content, encoding="utf-8")

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        response = client.patch(
            "/api/v1/monitoring/rules/n9e.yml/",
            {"content": "groups: [\n"},
            format="json",
        )

    assert response.status_code == 400
    assert path.read_text(encoding="utf-8") == original_content


@pytest.mark.django_db
def test_rule_detail_post_appends_alert_rule(client, tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    path = rules_dir / "n9e.yml"
    path.write_text(
        "groups:\n"
        "  - name: categraf-host\n"
        "    rules:\n"
        "      - alert: 主机CPU使用率过高\n"
        "        expr: cpu_usage_active > 85\n"
        "        labels:\n"
        "          severity: warning\n",
        encoding="utf-8",
    )

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        response = client.post(
            "/api/v1/monitoring/rules/n9e.yml/",
            {
                "group_index": 0,
                "rule": {
                    "alert": "主机磁盘使用率过高",
                    "expr": "disk_used_percent > 85",
                    "for": "5m",
                    "severity": "warning",
                    "category": "host",
                    "summary": "磁盘使用率过高",
                    "description": "磁盘使用率持续超过 85%。",
                },
            },
            format="json",
        )

    assert response.status_code == 200
    data = _payload(response)
    assert data["rule_count"] == 2
    created = data["groups"][0]["rules"][1]
    assert created["alert"] == "主机磁盘使用率过高"
    assert created["expr"] == "disk_used_percent > 85"
    assert created["severity"] == "warning"
    assert created["category"] == "host"
    content = path.read_text(encoding="utf-8")
    assert "主机磁盘使用率过高" in content
    assert "磁盘使用率持续超过 85%。" in content


@pytest.mark.django_db
def test_rule_detail_delete_removes_single_alert_rule(client, tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    path = rules_dir / "n9e.yml"
    path.write_text(
        "groups:\n"
        "  - name: categraf-host\n"
        "    rules:\n"
        "      - alert: 主机CPU使用率过高\n"
        "        expr: cpu_usage_active > 85\n"
        "        labels:\n"
        "          severity: warning\n"
        "      - alert: 主机内存使用率过高\n"
        "        expr: mem_used_percent > 85\n"
        "        labels:\n"
        "          severity: warning\n",
        encoding="utf-8",
    )

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        response = client.delete(
            "/api/v1/monitoring/rules/n9e.yml/",
            {"group_index": 0, "rule_index": 0},
            format="json",
        )

    assert response.status_code == 200
    data = _payload(response)
    assert data["rule_count"] == 1
    remaining = data["groups"][0]["rules"][0]
    assert remaining["alert"] == "主机内存使用率过高"
    content = path.read_text(encoding="utf-8")
    assert "主机CPU使用率过高" not in content
    assert "主机内存使用率过高" in content


@pytest.mark.django_db
def test_rule_diff_compares_local_template_with_n9e_snapshots(client, tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "n9e.yml").write_text(
        "groups:\n"
        "  - name: categraf-host\n"
        "    rules:\n"
        "      - alert: 主机CPU使用率过高\n"
        "        expr: cpu_usage_active > 90\n"
        "        for: 10m\n"
        "        labels:\n"
        "          severity: critical\n"
        "          category: host\n"
        "        annotations:\n"
        "          summary: CPU 已超过 90%\n"
        "      - alert: 主机磁盘使用率过高\n"
        "        expr: disk_used_percent > 85\n"
        "        labels:\n"
        "          severity: warning\n"
        "          category: host\n"
        "      - alert: 主机内存使用率过高\n"
        "        expr: mem_used_percent > 85\n"
        "        labels:\n"
        "          severity: warning\n",
        encoding="utf-8",
    )
    rule_model = apps.get_model("monitoring_stack", "N9eRuleSnapshot")
    rule_model.objects.create(
        identity="10:101",
        group_id="10",
        name="主机CPU使用率过高",
        enabled=True,
        severity="warning",
        raw={
            "name": "主机CPU使用率过高",
            "expr": "cpu_usage_active > 85",
            "for": "5m",
            "severity": "warning",
            "labels": {"category": "host"},
            "annotations": {"summary": "CPU 使用率过高"},
        },
        last_seen_at=timezone.now(),
    )
    rule_model.objects.create(
        identity="10:102",
        group_id="10",
        name="主机内存使用率过高",
        enabled=True,
        severity="warning",
        raw={
            "name": "主机内存使用率过高",
            "expr": "mem_used_percent > 85",
            "severity": "warning",
        },
        last_seen_at=timezone.now(),
    )
    rule_model.objects.create(
        identity="10:103",
        group_id="10",
        name="主机网络连接数过高",
        enabled=True,
        severity="warning",
        raw={"name": "主机网络连接数过高", "expr": "tcp_connections > 10000"},
        last_seen_at=timezone.now(),
    )

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        response = client.get("/api/v1/monitoring/rules/n9e.yml/diff/")

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["has_baseline"] is True
    assert payload["summary"] == {
        "created": 1,
        "updated": 1,
        "n9e_only": 1,
        "unknown": 0,
        "unchanged": 1,
    }
    assert payload["baseline_source"] == "snapshot"
    by_name = {item["name"]: item for item in payload["items"]}
    assert by_name["主机磁盘使用率过高"]["status"] == "created"
    assert by_name["主机CPU使用率过高"]["status"] == "updated"
    assert by_name["主机CPU使用率过高"]["changes"]["expr"] == {
        "local": "cpu_usage_active > 90",
        "n9e": "cpu_usage_active > 85",
    }
    assert by_name["主机网络连接数过高"]["status"] == "n9e_only"
    assert by_name["主机网络连接数过高"]["reason"] == "n9e 中存在，本次模板同步不会删除"
    assert by_name["主机内存使用率过高"]["status"] == "unchanged"


@pytest.mark.django_db
def test_rule_diff_filters_n9e_snapshots_by_selected_group(client, tmp_path):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "n9e.yml").write_text(
        "groups:\n"
        "  - name: categraf-host\n"
        "    rules:\n"
        "      - alert: 主机CPU使用率过高\n"
        "        expr: cpu_usage_active > 90\n"
        "        for: 5m\n"
        "        labels:\n"
        "          severity: warning\n"
        "          category: host\n",
        encoding="utf-8",
    )
    rule_model = apps.get_model("monitoring_stack", "N9eRuleSnapshot")
    now = timezone.now()
    rule_model.objects.create(
        identity="10:101",
        group_id="10",
        name="主机CPU使用率过高",
        enabled=True,
        severity="2",
        raw={
            "name": "主机CPU使用率过高",
            "expr": "cpu_usage_active > 90",
            "for": "5m",
            "severity": 2,
            "labels": {"category": "host"},
        },
        last_seen_at=now,
    )
    rule_model.objects.create(
        identity="20:201",
        group_id="20",
        name="主机CPU使用率过高",
        enabled=True,
        severity="warning",
        raw={
            "name": "主机CPU使用率过高",
            "expr": "cpu_usage_active > 80",
            "for": "5m",
            "severity": "warning",
        },
        last_seen_at=now,
    )

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        response = client.get("/api/v1/monitoring/rules/n9e.yml/diff/?group_id=10")

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["filters"]["group_id"] == "10"
    assert payload["summary"] == {
        "created": 0,
        "updated": 0,
        "n9e_only": 0,
        "unknown": 0,
        "unchanged": 1,
    }
    assert payload["items"][0]["name"] == "主机CPU使用率过高"
    assert payload["items"][0]["status"] == "unchanged"


@pytest.mark.django_db
def test_rule_diff_prefers_live_n9e_rules_when_configured(client, tmp_path, monkeypatch):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "n9e.yml").write_text(
        "groups:\n"
        "  - name: categraf-host\n"
        "    rules:\n"
        "      - alert: 主机CPU使用率过高\n"
        "        expr: cpu_usage_active > 90\n"
        "        for: 5m\n"
        "        labels:\n"
        "          severity: warning\n"
        "          category: host\n",
        encoding="utf-8",
    )
    config = MonitoringIntegrationConfig.current()
    config.n9e_url = "http://n9e"
    config.n9e_username = "root"
    config.n9e_password = "pw"
    config.save()
    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class FakeSession:
        trust_env = True

        def __init__(self):
            self.headers = {}

        def post(self, url, **kwargs):
            calls.append(("post", url, kwargs))
            return FakeResponse({"dat": {"access_token": "token-1"}})

        def get(self, url, **kwargs):
            calls.append(("get", url, kwargs))
            if url.endswith("/api/n9e/busi-group/10/alert-rules"):
                return FakeResponse(
                    {
                        "dat": {
                            "list": [
                                {
                                    "id": 101,
                                    "name": "主机CPU使用率过高",
                                    "prom_ql": "",
                                    "prom_for_duration": 300,
                                    "severity": 2,
                                    "append_tags": ["category=host"],
                                    "rule_config": {
                                        "queries": [
                                            {
                                                "prom_ql": "cpu_usage_active > 90",
                                                "severity": 2,
                                            }
                                        ]
                                    },
                                },
                                {
                                    "id": 102,
                                    "name": "n9e 手工规则",
                                    "expr": "up == 0",
                                    "severity": 2,
                                },
                            ]
                        }
                    }
                )
            raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr("monitoring_stack.views.requests.Session", FakeSession)

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        response = client.get("/api/v1/monitoring/rules/n9e.yml/diff/?group_id=10")

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["baseline_source"] == "live"
    assert payload["baseline_message"] == "已读取 n9e 当前业务组规则"
    assert payload["summary"] == {
        "created": 0,
        "updated": 0,
        "n9e_only": 1,
        "unknown": 0,
        "unchanged": 1,
    }
    by_name = {item["name"]: item for item in payload["items"]}
    assert by_name["主机CPU使用率过高"]["status"] == "unchanged"
    assert by_name["n9e 手工规则"]["status"] == "n9e_only"
    assert any(
        call[1] == "http://n9e/api/n9e/busi-group/10/alert-rules" for call in calls
    )


@pytest.mark.django_db
def test_rule_import_resolves_rule_template_finding(client, tmp_path, monkeypatch):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "n9e.yml").write_text("groups:\n- name: test\n", encoding="utf-8")
    finding_model = apps.get_model("monitoring_stack", "MonitoringGovernanceFinding")
    finding = finding_model.objects.create(
        category="rule_template_not_imported",
        severity="warning",
        status="open",
        title="n9e.yml not imported to n9e",
        subject_type="rule",
        subject_key="n9e.yml",
        source="hyperops",
        details={"rule_file": "n9e.yml"},
        recommended_action="import_rule_template",
    )

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class FakeSession:
        trust_env = True

        def __init__(self):
            self.headers = {}

        def post(self, url, **kwargs):
            if url.endswith("/api/n9e/auth/login"):
                return FakeResponse({"dat": {"access_token": "token-1"}})
            return FakeResponse({"dat": {"imported": 1}})

    monkeypatch.setattr("monitoring_stack.views.requests.Session", FakeSession)

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        response = client.post(
            "/api/v1/monitoring/n9e/import-rules/",
            {
                "n9e_url": "http://n9e",
                "username": "root",
                "password": "pw",
                "group_id": 10,
                "datasource_id": 1,
                "rule_file": "n9e.yml",
                "enabled": True,
            },
            format="json",
        )

    assert response.status_code == 200
    finding.refresh_from_db()
    assert finding.status == "resolved"
    assert finding.details["resolution"]["record_id"] == _payload(response)["record_id"]


@pytest.mark.django_db
def test_failed_install_job_creates_retryable_finding(client, monkeypatch):
    host = MonitoringHost.objects.create(
        hostname="app-01",
        address="10.0.0.11",
        enabled=True,
    )
    job = AnsibleInstallJob.objects.create(
        component=AnsibleInstallJob.COMPONENT_CATEGRAF,
        status=AnsibleInstallJob.STATUS_FAILED,
        profiles=["linux-basic"],
        host_ids=[host.id],
        hosts_snapshot=[
            {
                "id": host.id,
                "hostname": host.hostname,
                "address": host.address,
                "ssh_user": "root",
                "ssh_port": 22,
            }
        ],
        base_url="http://hyperops.local/api/v1/monitoring/installer",
        n9e_url="http://n9e",
        install_dir="/opt/categraf",
        image="flashcatcloud/categraf:latest",
        results=[{"hostname": "app-01", "status": "failed"}],
    )

    response = client.get("/api/v1/monitoring/governance/overview/")

    assert response.status_code == 200
    finding_model = apps.get_model("monitoring_stack", "MonitoringGovernanceFinding")
    finding = finding_model.objects.get(category="install_job_failed")
    assert finding.subject_type == "job"
    assert finding.subject_key == str(job.id)
    assert finding.recommended_action == "retry_job"

    class FakeTask:
        @staticmethod
        def delay(job_id):
            return job_id

    monkeypatch.setattr("monitoring_stack.tasks.run_ansible_install_job", FakeTask)
    retry_response = client.post(
        f"/api/v1/monitoring/governance/findings/{finding.id}/resolve/",
        {"action": "retry_job"},
        format="json",
    )

    assert retry_response.status_code == 200
    finding.refresh_from_db()
    assert finding.status == "resolved"
    retry_job = AnsibleInstallJob.objects.exclude(id=job.id).get()
    assert retry_job.retry_of_id == job.id
    assert retry_job.host_ids == [host.id]
    assert _payload(retry_response)["details"]["resolution"]["job_id"] == retry_job.id


@pytest.mark.django_db
def test_host_asset_hides_legacy_ssh_key_and_preview_uses_all_hosts(client):
    create_response = client.post(
        "/api/v1/monitoring/hosts/",
        {
            "hostname": "app-01",
            "address": "10.0.0.11",
            "ssh_user": "root",
            "ssh_port": 22,
            "ssh_key": "../id_rsa_ops",
            "profiles": ["linux-basic", "docker-host"],
            "labels": {"region": "beijing", "env": "prod"},
            "params": {"mysql_address": "mysql.example.com:3306"},
            "enabled": True,
        },
        format="json",
    )
    assert create_response.status_code == 201
    host_payload = _payload(create_response)
    assert "ssh_key" not in host_payload
    assert host_payload["ssh_key_id"] is None
    assert host_payload["ssh_key_name"] == ""

    client.post(
        "/api/v1/monitoring/hosts/",
        {
            "hostname": "disabled-01",
            "address": "10.0.0.12",
            "enabled": False,
        },
        format="json",
    )

    preview_response = client.post(
        "/api/v1/monitoring/ansible/preview/",
        {"host_ids": [], "profiles": ["linux-basic"]},
        format="json",
    )

    assert preview_response.status_code == 200
    data = _payload(preview_response)
    assert "app-01 ansible_host=10.0.0.11" in data["inventory"]
    assert "disabled-01 ansible_host=10.0.0.12" in data["inventory"]
    assert "ansible_ssh_private_key_file" not in data["inventory"]
    assert data["vars"]["hosts"][0]["ssh_credential_id"] is None
    assert data["vars"]["hosts"][0]["ssh_key_name"] == ""
    assert (
        "--mysql-address mysql.example.com:3306"
        in data["vars"]["hosts"][0]["install_command"]
    )


@pytest.mark.django_db
def test_credential_upload_is_saved_as_encrypted_version(client, tmp_path):
    response = client.post(
        "/api/v1/monitoring/credentials/",
        {
            "name": "beijing-idc-key",
            "private_key": generate_private_key(tmp_path),
        },
        format="json",
    )

    assert response.status_code == 201
    data = _payload(response)
    assert data["name"] == "beijing-idc-key"
    assert data["status"] == MonitoringSshCredential.STATUS_ACTIVE
    assert data["active_version"] is None
    assert data["versions"][0]["algorithm"] == "ssh-ed25519"
    assert data["versions"][0]["public_key_fingerprint"].startswith("SHA256:")
    assert "file_name" not in data
    assert "private_key" not in data

    key = MonitoringSshCredential.objects.get(id=data["id"])
    assert key.name == "beijing-idc-key"
    assert key.storage_path is None
    assert key.versions.count() == 1


@pytest.mark.django_db
def test_ssh_key_compatibility_route_is_read_only(client, tmp_path):
    response = client.post(
        "/api/v1/monitoring/ssh-keys/",
        {"name": "legacy-write", "private_key": generate_private_key(tmp_path)},
        format="json",
    )

    assert response.status_code == 405
    assert response["Deprecation"] == "true"
    assert response["Link"] == (
        '</api/v1/monitoring/credentials/>; rel="successor-version"'
    )


@pytest.mark.django_db
def test_host_supports_password_or_saved_ssh_key_inventory(client, tmp_path):
    key_response = client.post(
        "/api/v1/monitoring/credentials/",
        {
            "name": "ops-key",
            "private_key": generate_private_key(tmp_path),
        },
        format="json",
    )
    ssh_key_id = _payload(key_response)["id"]
    credential = MonitoringSshCredential.objects.get(id=ssh_key_id)
    version = credential.versions.get()
    version.validation_status = version.VALIDATION_VALID
    version.save(update_fields=["validation_status"])
    activate_response = client.post(
        f"/api/v1/monitoring/credentials/{credential.id}/activate/",
        {"version_id": version.id},
        format="json",
    )
    assert activate_response.status_code == 200

    key_host_response = client.post(
        "/api/v1/monitoring/hosts/",
        {
            "hostname": "key-host",
            "address": "10.0.0.21",
            "ssh_user": "root",
            "ssh_port": 22,
            "ssh_auth_type": "key",
            "ssh_key_id": ssh_key_id,
        },
        format="json",
    )
    password_host_response = client.post(
        "/api/v1/monitoring/hosts/",
        {
            "hostname": "password-host",
            "address": "10.0.0.22",
            "ssh_user": "root",
            "ssh_port": 22,
            "ssh_auth_type": "password",
            "ssh_password": "secret123",
        },
        format="json",
    )

    assert key_host_response.status_code == 201
    assert password_host_response.status_code == 201
    key_host = _payload(key_host_response)
    password_host = _payload(password_host_response)
    assert key_host["ssh_auth_type"] == "key"
    assert key_host["ssh_key_name"] == "ops-key"
    assert password_host["ssh_auth_type"] == "password"
    assert password_host["has_ssh_password"] is True
    assert "ssh_password" not in password_host

    preview_response = client.post(
        "/api/v1/monitoring/ansible/preview/",
        {"host_ids": [key_host["id"], password_host["id"]], "profiles": []},
        format="json",
    )

    assert preview_response.status_code == 200
    preview = _payload(preview_response)
    inventory = preview["inventory"]
    assert "key-host ansible_host=10.0.0.21" in inventory
    assert "ansible_ssh_private_key_file=" not in inventory
    assert "password-host ansible_host=10.0.0.22" in inventory
    assert "ansible_password=secret123" in inventory
    preview_hosts = {item["hostname"]: item for item in preview["vars"]["hosts"]}
    assert preview_hosts["key-host"]["ssh_credential_id"] == credential.id
    assert preview_hosts["key-host"]["ssh_credential_version_id"] == version.id
    assert preview_hosts["key-host"]["ssh_public_key_fingerprint"].startswith(
        "SHA256:"
    )


@pytest.mark.django_db
def test_host_connection_test_uses_transient_password_without_saving(
    client, monkeypatch
):
    calls = []

    def fake_connection_test(**kwargs):
        calls.append(kwargs)
        return {"latency_ms": 12}

    import monitoring_stack.views as monitoring_views

    monkeypatch.setattr(
        monitoring_views,
        "check_monitoring_ssh_connection",
        fake_connection_test,
        raising=False,
    )
    before_count = MonitoringHost.objects.count()

    response = client.post(
        "/api/v1/monitoring/hosts/test-connection/",
        {
            "address": "192.168.7.159",
            "ssh_user": "root",
            "ssh_port": 22,
            "ssh_auth_type": "password",
            "ssh_password": "transient-secret",
        },
        format="json",
    )

    assert response.status_code == 200
    response_payload = _payload(response)
    assert response_payload["success"] is True
    assert response_payload["latency_ms"] == 12
    assert response_payload["verification_receipt"]
    assert MonitoringHost.objects.count() == before_count
    assert calls == [
        {
            "address": "192.168.7.159",
            "ssh_user": "root",
            "ssh_port": 22,
            "password": "transient-secret",
            "key_path": None,
        }
    ]


@pytest.mark.django_db
def test_host_connection_test_can_reuse_saved_password(client, monkeypatch):
    host = MonitoringHost.objects.create(
        hostname="password-host",
        address="192.168.7.160",
        ssh_user="ops",
        ssh_port=2222,
        ssh_auth_type=MonitoringHost.SSH_AUTH_PASSWORD,
        ssh_password="stored-secret",
    )
    calls = []

    def fake_connection_test(**kwargs):
        calls.append(kwargs)
        return {"latency_ms": 9}

    import monitoring_stack.views as monitoring_views

    monkeypatch.setattr(
        monitoring_views,
        "check_monitoring_ssh_connection",
        fake_connection_test,
        raising=False,
    )

    response = client.post(
        "/api/v1/monitoring/hosts/test-connection/",
        {
            "host_id": host.id,
            "address": host.address,
            "ssh_user": host.ssh_user,
            "ssh_port": host.ssh_port,
            "ssh_auth_type": "password",
            "ssh_password": "",
        },
        format="json",
    )

    assert response.status_code == 200
    assert calls[0]["password"] == "stored-secret"
    host.refresh_from_db()
    assert host.ssh_password == "stored-secret"


@pytest.mark.django_db
def test_host_connection_test_resolves_saved_ssh_key(
    client, monkeypatch, tmp_path
):
    credential = MonitoringSshCredential.objects.create(
        name="connection-test-key",
        legacy_file_name="connection-test-key.pem",
    )
    version = create_credential_version(
        credential=credential,
        private_key=generate_private_key(tmp_path),
        actor=None,
    )
    version.validation_status = version.VALIDATION_VALID
    version.save(update_fields=["validation_status"])
    credential.active_version = version
    credential.save(update_fields=["active_version", "updated_at"])
    calls = []

    def fake_connection_test(**kwargs):
        calls.append(kwargs)
        return {"latency_ms": 7}

    import monitoring_stack.views as monitoring_views

    monkeypatch.setattr(
        monitoring_views,
        "check_monitoring_ssh_connection",
        fake_connection_test,
        raising=False,
    )

    response = client.post(
        "/api/v1/monitoring/hosts/test-connection/",
        {
            "address": "192.168.7.161",
            "ssh_user": "root",
            "ssh_port": 22,
            "ssh_auth_type": "key",
            "ssh_key_id": credential.id,
        },
        format="json",
    )

    assert response.status_code == 200
    assert calls[0]["password"] is None
    assert calls[0]["key_path"].name == f"{version.id}.key"
    assert calls[0]["process_env"] == {}
    assert calls[0]["key_prevalidated"] is True
    assert not calls[0]["key_path"].exists()


def test_host_connection_test_classifies_refused_port_as_unreachable(monkeypatch):
    monkeypatch.setattr(
        "monitoring_stack.services.core.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            255,
            stdout="",
            stderr=(
                "ssh: connect to host 192.168.7.250 port 22: Connection refused"
            ),
        )
    )

    with pytest.raises(MonitoringSshConnectionError) as exc_info:
        check_monitoring_ssh_connection(
            address="192.168.7.250",
            ssh_user="root",
            ssh_port=22,
            password="secret",
        )

    assert exc_info.value.code == "SSH_UNREACHABLE"
    assert exc_info.value.status_code == 502


def test_host_connection_test_classifies_missing_key_as_key_error(monkeypatch):
    with pytest.raises(MonitoringSshConnectionError) as exc_info:
        check_monitoring_ssh_connection(
            address="192.168.7.251",
            ssh_user="root",
            ssh_port=22,
            key_path="/missing/monitoring-key.pem",
        )

    assert exc_info.value.code == "SSH_KEY_OR_PROTOCOL_FAILED"
    assert exc_info.value.status_code == 400


def test_host_connection_test_rejects_key_not_supported_by_openssh(
    monkeypatch, tmp_path
):
    key_path = tmp_path / "invalid.pem"
    key_path.write_text("not-an-openssh-key", encoding="utf-8")
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            255,
            stdout="",
            stderr="Load key invalid.pem: error in libcrypto",
        )

    monkeypatch.setattr(
        "monitoring_stack.services.core.subprocess.run",
        fake_run,
    )

    with pytest.raises(MonitoringSshConnectionError) as exc_info:
        check_monitoring_ssh_connection(
            address="192.168.7.251",
            ssh_user="root",
            ssh_port=22,
            key_path=key_path,
        )

    assert calls[0][:2] == ["ssh-keygen", "-y"]
    assert exc_info.value.code == "SSH_KEY_OR_PROTOCOL_FAILED"
    assert exc_info.value.status_code == 400


def test_host_connection_test_uses_sshpass_without_password_in_arguments(
    monkeypatch,
):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="hyperops-ssh-ok",
            stderr="",
        )

    monkeypatch.setattr(
        "monitoring_stack.services.core.subprocess.run",
        fake_run,
    )

    result = check_monitoring_ssh_connection(
        address="192.168.7.251",
        ssh_user="root",
        ssh_port=22,
        password="stored-secret",
    )

    command, kwargs = calls[0]
    assert command[:2] == ["sshpass", "-e"]
    assert "stored-secret" not in command
    assert kwargs["env"]["SSHPASS"] == "stored-secret"
    assert result["latency_ms"] >= 1


@pytest.mark.django_db
def test_host_list_exposes_unverified_ssh_snapshot_by_default(client):
    host = MonitoringHost.objects.create(
        hostname="asset-ssh-unverified",
        address="10.0.0.21",
        ssh_auth_type=MonitoringHost.SSH_AUTH_PASSWORD,
        ssh_password="secret",
    )

    response = client.get("/api/v1/monitoring/hosts/")
    payload = _payload(response)
    rows = payload.get("results", []) if isinstance(payload, dict) else payload
    row = next(item for item in rows if item["id"] == host.id)

    assert row["ssh_verification"] == {
        "status": "unverified",
        "checked_at": None,
        "latency_ms": None,
        "error_code": "",
        "matches_current_settings": False,
    }


@pytest.mark.django_db
def test_host_save_accepts_verification_receipt_for_exact_settings(
    client, monkeypatch
):
    import monitoring_stack.views as monitoring_views

    monkeypatch.setattr(
        monitoring_views,
        "check_monitoring_ssh_connection",
        lambda **kwargs: {"latency_ms": 12},
    )
    connection = {
        "address": "10.0.0.31",
        "ssh_user": "root",
        "ssh_port": 22,
        "ssh_auth_type": "password",
        "ssh_password": "secret",
    }
    test_response = client.post(
        "/api/v1/monitoring/hosts/test-connection/",
        connection,
        format="json",
    )

    assert test_response.status_code == 200
    receipt = _payload(test_response)["verification_receipt"]
    create_response = client.post(
        "/api/v1/monitoring/hosts/",
        {
            "hostname": "receipt-exact",
            **connection,
            "ssh_verification_receipt": receipt,
        },
        format="json",
    )

    assert create_response.status_code == 201
    host = MonitoringHost.objects.get(id=_payload(create_response)["id"])
    assert host.ssh_verification_status == MonitoringHost.SSH_VERIFICATION_VERIFIED
    assert host.ssh_verification_latency_ms == 12
    assert host.ssh_verification_signature


@pytest.mark.django_db
def test_host_save_rejects_verification_receipt_after_address_changes(
    client, monkeypatch
):
    import monitoring_stack.views as monitoring_views

    monkeypatch.setattr(
        monitoring_views,
        "check_monitoring_ssh_connection",
        lambda **kwargs: {"latency_ms": 8},
    )
    test_response = client.post(
        "/api/v1/monitoring/hosts/test-connection/",
        {
            "address": "10.0.0.41",
            "ssh_user": "root",
            "ssh_port": 22,
            "ssh_auth_type": "password",
            "ssh_password": "secret",
        },
        format="json",
    )

    create_response = client.post(
        "/api/v1/monitoring/hosts/",
        {
            "hostname": "receipt-mismatch",
            "address": "10.0.0.42",
            "ssh_user": "root",
            "ssh_port": 22,
            "ssh_auth_type": "password",
            "ssh_password": "secret",
            "ssh_verification_receipt": _payload(test_response)[
                "verification_receipt"
            ],
        },
        format="json",
    )

    assert create_response.status_code == 400
    payload = _payload(create_response)
    field_errors = payload.get("field_errors", payload)
    assert "ssh_verification_receipt" in field_errors


@pytest.mark.django_db
def test_failed_unsaved_settings_do_not_replace_saved_verification(
    client, monkeypatch
):
    host = MonitoringHost.objects.create(
        hostname="saved-verification",
        address="10.0.0.51",
        ssh_user="root",
        ssh_port=22,
        ssh_auth_type=MonitoringHost.SSH_AUTH_PASSWORD,
        ssh_password="saved-secret",
        ssh_verification_status=MonitoringHost.SSH_VERIFICATION_VERIFIED,
        ssh_verification_signature="saved-fingerprint",
    )
    import monitoring_stack.views as monitoring_views

    def fail_connection(**kwargs):
        raise MonitoringSshConnectionError("SSH_UNREACHABLE", 502)

    monkeypatch.setattr(
        monitoring_views,
        "check_monitoring_ssh_connection",
        fail_connection,
    )
    response = client.post(
        "/api/v1/monitoring/hosts/test-connection/",
        {
            "host_id": host.id,
            "address": "10.0.0.99",
            "ssh_user": "root",
            "ssh_port": 22,
            "ssh_auth_type": "password",
            "ssh_password": "new-secret",
        },
        format="json",
    )

    assert response.status_code == 502
    host.refresh_from_db()
    assert host.ssh_verification_status == MonitoringHost.SSH_VERIFICATION_VERIFIED
    assert host.ssh_verification_signature == "saved-fingerprint"


@pytest.mark.parametrize(
    ("categraf", "probe_required", "blackbox", "ssh", "expected"),
    [
        ("healthy", False, "not_applicable", "unverified", "running_normally"),
        ("pending_deployment", False, "not_applicable", "unverified", "verify_ssh"),
        ("pending_deployment", False, "not_applicable", "failed", "fix_ssh"),
        ("pending_deployment", False, "not_applicable", "verified", "deploy_categraf"),
        ("healthy", True, "pending_deployment", "verified", "deploy_blackbox"),
        ("abnormal", False, "not_applicable", "verified", "inspect_collection"),
    ],
)
def test_asset_next_action_priority(
    categraf, probe_required, blackbox, ssh, expected
):
    checked_at = timezone.now() if ssh == "verified" else None
    result = choose_next_action(
        collection_state={
            "code": categraf,
            "component": "categraf",
            "job_id": None,
        },
        probe_state={
            "code": blackbox if probe_required else "not_applicable",
            "component": "blackbox",
            "job_id": None,
        },
        ssh_state={
            "status": ssh,
            "checked_at": checked_at,
            "matches_current_settings": True,
        },
        now=timezone.now(),
    )

    assert result["code"] == expected


@pytest.mark.parametrize(
    ("rows", "expected_code", "expected_installation", "expected_runtime"),
    [
        (
            [
                {
                    "component": "categraf",
                    "status": "success",
                    "runtime_status": "online",
                }
            ],
            "healthy",
            "installed",
            "online",
        ),
        (
            [
                {
                    "component": "categraf",
                    "status": "external",
                    "runtime_status": "abnormal",
                }
            ],
            "abnormal",
            "installed",
            "abnormal",
        ),
        ([], "pending_deployment", "not_installed", "not_applicable"),
    ],
)
def test_component_state_preserves_installation_and_runtime_dimensions(
    rows,
    expected_code,
    expected_installation,
    expected_runtime,
):
    result = normalize_component_state(rows, "categraf")

    assert result["code"] == expected_code
    assert result["installation_status"] == expected_installation
    assert result["runtime_status"] == expected_runtime


def test_non_required_component_has_no_installation_or_runtime_state():
    result = normalize_component_state([], "blackbox", required=False)

    assert result["installation_status"] == "not_applicable"
    assert result["runtime_status"] == "not_applicable"


@pytest.mark.django_db
def test_host_roles_make_blackbox_not_applicable_for_ordinary_hosts(client):
    ordinary = MonitoringHost.objects.create(
        hostname="ordinary-collection-host",
        address="10.0.0.61",
    )
    probe = MonitoringHost.objects.create(
        hostname="probe-host",
        address="10.0.0.62",
    )
    BlackboxProbeNode.objects.create(
        name="probe-node-62",
        address=probe.address,
        host=probe,
        enabled=True,
    )

    response = client.get("/api/v1/monitoring/hosts/")
    payload = _payload(response)
    rows = payload.get("results", []) if isinstance(payload, dict) else payload
    by_id = {row["id"]: row for row in rows}

    assert by_id[ordinary.id]["roles"] == ["collection_host"]
    assert by_id[ordinary.id]["probe_state"]["code"] == "not_applicable"
    assert by_id[probe.id]["roles"] == ["collection_host", "probe_node"]
    assert by_id[probe.id]["probe_state"]["code"] != "not_applicable"


@pytest.mark.django_db
def test_blackbox_ansible_preview_uses_blackbox_installer(client):
    host_response = client.post(
        "/api/v1/monitoring/hosts/",
        {
            "hostname": "probe-01",
            "address": "10.0.0.21",
            "ssh_user": "root",
            "ssh_port": 22,
            "labels": {"region": "beijing-idc"},
            "enabled": True,
        },
        format="json",
    )
    assert host_response.status_code == 201
    host_id = _payload(host_response)["id"]

    preview = build_ansible_preview(
        [host_id],
        [],
        base_url="http://hyperops.local/api/v1/monitoring/installer",
        install_dir="/opt/blackbox-exporter",
        image="prom/blackbox-exporter:v1",
        component="blackbox",
        probe_name="blackbox-beijing-idc",
        blackbox_port="9115",
    )

    host_vars = preview["vars"]["hosts"][0]
    assert preview["vars"]["component"] == "blackbox"
    assert "/install-blackbox.sh" in host_vars["install_command"]
    assert "/install.sh" not in host_vars["install_command"]
    assert "--name blackbox-beijing-idc" in host_vars["install_command"]
    assert "--port 9115" in host_vars["install_command"]
    assert "--dir /opt/blackbox-exporter" in host_vars["install_command"]
    assert "--image prom/blackbox-exporter:v1" in host_vars["install_command"]


@pytest.mark.django_db
def test_install_job_creation_marks_component_status_installing(client, monkeypatch):
    host_response = client.post(
        "/api/v1/monitoring/hosts/",
        {
            "hostname": "app-install-01",
            "address": "10.0.0.41",
            "ssh_user": "root",
            "ssh_port": 22,
            "enabled": True,
        },
        format="json",
    )
    host_id = _payload(host_response)["id"]

    class FakeTask:
        @staticmethod
        def delay(job_id):
            return job_id

    monkeypatch.setattr("monitoring_stack.tasks.run_ansible_install_job", FakeTask)

    response = client.post(
        "/api/v1/monitoring/ansible/jobs/",
        {
            "component": "categraf",
            "host_ids": [host_id],
            "profiles": ["linux-basic"],
            "base_url": "http://hyperops.local/api/v1/monitoring/installer",
            "n9e_url": "http://n9e",
            "install_dir": "/opt/categraf",
            "image": "flashcatcloud/categraf:v1",
        },
        format="json",
    )

    assert response.status_code == 201
    status = MonitoringComponentStatus.objects.get(
        host_id=host_id,
        component=AnsibleInstallJob.COMPONENT_CATEGRAF,
    )
    assert status.status == MonitoringComponentStatus.STATUS_INSTALLING
    assert status.install_dir == "/opt/categraf"
    assert status.last_job_id == _payload(response)["id"]

    host_detail = _payload(client.get(f"/api/v1/monitoring/hosts/{host_id}/"))
    assert host_detail["component_statuses"][0]["status"] == "installing"


@pytest.mark.django_db
def test_retry_install_job_only_retries_failed_hosts(client, monkeypatch):
    success_host = MonitoringHost.objects.create(
        hostname="success-01",
        address="10.0.0.51",
        enabled=True,
    )
    failed_host = MonitoringHost.objects.create(
        hostname="failed-01",
        address="10.0.0.52",
        enabled=True,
    )
    payload = {
        "component": AnsibleInstallJob.COMPONENT_CATEGRAF,
        "profiles": ["linux-basic"],
        "labels": {},
        "params": {},
        "base_url": "http://hyperops.local/api/v1/monitoring/installer",
        "n9e_url": "http://n9e",
        "install_dir": "/opt/categraf",
        "image": "flashcatcloud/categraf:v1",
        "probe_name": "",
        "blackbox_port": "9115",
    }
    job = AnsibleInstallJob.objects.create(
        component=AnsibleInstallJob.COMPONENT_CATEGRAF,
        status=AnsibleInstallJob.STATUS_FAILED,
        host_ids=[success_host.id, failed_host.id],
        hosts_snapshot=snapshot_hosts([success_host, failed_host], payload),
        profiles=["linux-basic"],
        base_url=payload["base_url"],
        n9e_url=payload["n9e_url"],
        install_dir=payload["install_dir"],
        image=payload["image"],
        logs=["success-01 ok", "failed-01 connection refused"],
        results=[
            {"hostname": "success-01", "status": "success"},
            {"hostname": "failed-01", "status": "failed"},
        ],
    )

    class FakeTask:
        @staticmethod
        def delay(job_id):
            return job_id

    monkeypatch.setattr("monitoring_stack.tasks.run_ansible_install_job", FakeTask)

    response = client.post(f"/api/v1/monitoring/ansible/jobs/{job.id}/retry/")

    assert response.status_code == 201
    retry_job = AnsibleInstallJob.objects.get(id=_payload(response)["id"])
    assert retry_job.retry_of_id == job.id
    assert retry_job.host_ids == [failed_host.id]
    assert [item["hostname"] for item in retry_job.hosts_snapshot] == ["failed-01"]

    detail = _payload(client.get(f"/api/v1/monitoring/ansible/jobs/{job.id}/"))
    assert detail["total_hosts"] == 2
    assert detail["success_hosts"] == 1
    assert detail["failed_hosts"] == 1
    assert detail["failed_hostnames"] == ["failed-01"]
    assert "connection refused" in detail["last_error"]
    assert "# success-01" in detail["manual_command"]


@pytest.mark.django_db
def test_execute_ansible_job_marks_component_status_failed_when_ansible_missing(
    client,
    monkeypatch,
):
    host = MonitoringHost.objects.create(
        hostname="app-failed-01",
        address="10.0.0.42",
        ssh_user="root",
        enabled=True,
    )
    job = AnsibleInstallJob.objects.create(
        component=AnsibleInstallJob.COMPONENT_BLACKBOX,
        host_ids=[host.id],
        base_url="http://hyperops.local/api/v1/monitoring/installer",
        install_dir="/opt/blackbox-exporter",
        image="prom/blackbox-exporter:v1",
        probe_name="blackbox-test",
        blackbox_port="9115",
    )
    monkeypatch.setattr("monitoring_stack.services.core.shutil.which", lambda _: None)

    execute_ansible_job(job.id)

    status = MonitoringComponentStatus.objects.get(
        host=host,
        component=AnsibleInstallJob.COMPONENT_BLACKBOX,
    )
    assert status.status == MonitoringComponentStatus.STATUS_FAILED
    assert status.install_dir == "/opt/blackbox-exporter"
    assert status.last_job_id == job.id
    assert "ansible-playbook not found" in status.last_error


@pytest.mark.django_db
def test_execute_ansible_job_uses_recap_failure_when_process_returns_zero(
    monkeypatch,
):
    host = MonitoringHost.objects.create(
        hostname="nexus",
        address="10.0.0.43",
        ssh_user="root",
        enabled=True,
    )
    job = AnsibleInstallJob.objects.create(
        component=AnsibleInstallJob.COMPONENT_CATEGRAF,
        host_ids=[host.id],
        base_url="http://hyperops.local/api/v1/monitoring/installer",
        n9e_url="http://n9e",
        install_dir="/opt/categraf",
        image="flashcatcloud/categraf:v1",
    )
    stdout = """PLAY [Install Categraf by unified installer] *******************
[ERROR]: Task failed: the connection plugin 'paramiko' was not found
fatal: [nexus]: FAILED! => {\"changed\": false}
PLAY RECAP *******************************************************
nexus : ok=0 changed=0 unreachable=0 failed=1 skipped=0 rescued=0 ignored=0
"""
    monkeypatch.setattr(
        "monitoring_stack.services.core.shutil.which",
        lambda _: "/usr/bin/ansible-playbook",
    )

    class FakeProcess:
        def __init__(self):
            self.stdout = io.StringIO(stdout)
            self.returncode = 0

        def wait(self, timeout=None):
            return self.returncode

        def terminate(self):
            self.returncode = -15

        def kill(self):
            self.returncode = -9

    monkeypatch.setattr(
        "monitoring_stack.services.core.subprocess.Popen",
        lambda *args, **kwargs: FakeProcess(),
    )

    execute_ansible_job(job.id)

    job.refresh_from_db()
    component_status = MonitoringComponentStatus.objects.get(
        host=host,
        component=AnsibleInstallJob.COMPONENT_CATEGRAF,
    )
    assert job.status == AnsibleInstallJob.STATUS_FAILED
    assert job.returncode == 1
    assert job.results == [{"hostname": "nexus", "status": "failed"}]
    assert component_status.status == MonitoringComponentStatus.STATUS_FAILED
    assert "failed=1" in component_status.last_error


@pytest.mark.django_db
def test_host_component_statuses_include_runtime_health(
    client,
    monkeypatch,
    settings,
):
    settings.MONITORING_N9E_URL = "http://n9e"
    settings.MONITORING_N9E_USERNAME = "root"
    settings.MONITORING_N9E_PASSWORD = "pw"
    settings.MONITORING_BLACKBOX_PORT = "9115"
    host = MonitoringHost.objects.create(
        hostname="app-01",
        address="10.0.0.11",
        ssh_user="root",
    )
    categraf_job = AnsibleInstallJob.objects.create(
        component=AnsibleInstallJob.COMPONENT_CATEGRAF,
        status=AnsibleInstallJob.STATUS_SUCCESS,
        host_ids=[host.id],
        base_url="http://hyperops/api/v1/monitoring/installer",
        n9e_url="http://n9e",
        install_dir="/opt/categraf",
        image="flashcatcloud/categraf:v1",
    )
    blackbox_job = AnsibleInstallJob.objects.create(
        component=AnsibleInstallJob.COMPONENT_BLACKBOX,
        status=AnsibleInstallJob.STATUS_SUCCESS,
        host_ids=[host.id],
        base_url="http://hyperops/api/v1/monitoring/installer",
        n9e_url="",
        install_dir="/opt/blackbox-exporter",
        image="prom/blackbox-exporter:v1",
        blackbox_port="9115",
    )
    MonitoringComponentStatus.objects.create(
        host=host,
        component=AnsibleInstallJob.COMPONENT_CATEGRAF,
        status=MonitoringComponentStatus.STATUS_SUCCESS,
        last_job=categraf_job,
    )
    MonitoringComponentStatus.objects.create(
        host=host,
        component=AnsibleInstallJob.COMPONENT_BLACKBOX,
        status=MonitoringComponentStatus.STATUS_SUCCESS,
        last_job=blackbox_job,
    )

    class FakeResponse:
        def __init__(self, payload=None, status_code=200):
            self._payload = payload or {}
            self.status_code = status_code
            self.text = json.dumps(self._payload)

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"{self.status_code} response")

        def json(self):
            return self._payload

    class FakeSession:
        trust_env = True
        headers = {}

        def post(self, url, **kwargs):
            return FakeResponse({"dat": {"access_token": "token-1"}})

        def get(self, url, **kwargs):
            if url.endswith("/api/n9e/targets"):
                return FakeResponse(
                    {
                        "dat": {
                            "list": [
                                {
                                    "ident": "app-01",
                                    "host": "10.0.0.11",
                                    "status": "online",
                                }
                            ]
                        }
                    }
                )
            if url == "http://10.0.0.11:9115/-/healthy":
                assert self.trust_env is False
                return FakeResponse({"status": "ok"})
            return FakeResponse({"err": "not found"}, status_code=404)

    monkeypatch.setattr("monitoring_stack.services.core.requests.Session", FakeSession)

    response = client.get(f"/api/v1/monitoring/hosts/{host.id}/")

    assert response.status_code == 200
    statuses = {
        item["component"]: item for item in _payload(response)["component_statuses"]
    }
    assert statuses["categraf"]["runtime_status"] == "online"
    assert statuses["blackbox"]["runtime_status"] == "online"
    assert statuses["blackbox"]["runtime_endpoint"] == "http://10.0.0.11:9115/-/healthy"


@pytest.mark.django_db
def test_categraf_preview_uses_job_profiles_labels_and_params(client):
    host_response = client.post(
        "/api/v1/monitoring/hosts/",
        {
            "hostname": "bare-01",
            "address": "10.0.0.31",
            "ssh_user": "root",
            "ssh_port": 22,
            "enabled": True,
        },
        format="json",
    )
    assert host_response.status_code == 201
    host_id = _payload(host_response)["id"]

    preview = build_ansible_preview(
        [host_id],
        ["linux-basic", "mysql-rds", "redis"],
        base_url="http://127.0.0.1:18080/api/v1/monitoring/installer",
        n9e_url="http://n9e.example.com",
        install_dir="/opt/categraf",
        image="flashcatcloud/categraf:v1",
        component="categraf",
        labels={
            "region": "beijing-idc",
            "env": "prod",
            "team": "ops",
            "service": "mysql",
        },
        params={
            "mysql_address": "mysql.example.com:3306",
            "redis_address": "redis.example.com:6379",
        },
    )

    command = preview["vars"]["hosts"][0]["install_command"]
    assert "--profile linux-basic" in command
    assert "--profile mysql-rds" in command
    assert "--profile redis" in command
    assert "--region beijing-idc" in command
    assert "--team ops" in command
    assert "--service mysql" in command
    assert "--mysql-address mysql.example.com:3306" in command
    assert "--redis-address redis.example.com:6379" in command


@pytest.mark.django_db
def test_import_monitor_admin_json_command_imports_existing_state(tmp_path):
    data_dir = tmp_path / "monitor-admin-data"
    data_dir.mkdir()
    (data_dir / "probe-targets.json").write_text(
        json.dumps(
            [
                {
                    "id": "target-1",
                    "type": "icmp",
                    "target": "8.8.8.8",
                    "enabled": True,
                    "labels": {"service": "ping"},
                }
            ]
        ),
        encoding="utf-8",
    )
    (data_dir / "hosts.json").write_text(
        json.dumps(
            [
                {
                    "id": "host-1",
                    "hostname": "app-01",
                    "address": "10.0.0.11",
                    "ssh_key": "../id_rsa_ops",
                    "enabled": True,
                }
            ]
        ),
        encoding="utf-8",
    )
    (data_dir / "profiles.json").write_text("[]", encoding="utf-8")

    call_command("import_monitor_admin_json", str(data_dir))

    assert ProbeTarget.objects.get(external_id="target-1").target == "8.8.8.8"
    assert MonitoringHost.objects.get(external_id="host-1").ssh_key == "id_rsa_ops"


@pytest.mark.django_db
def test_installer_build_generates_archives_and_checksums(client, tmp_path):
    installer_dir = tmp_path / "installer"
    template_dir = tmp_path / "templates"
    categraf_template = template_dir / "categraf"
    blackbox_template = template_dir / "blackbox"
    (categraf_template / "conf").mkdir(parents=True)
    (blackbox_template / "config").mkdir(parents=True)
    (categraf_template / "docker-compose.yml").write_text(
        "services:\n  categraf:\n    image: categraf\n",
        encoding="utf-8",
    )
    (categraf_template / "conf" / "input.toml").write_text(
        "[[inputs.cpu]]\n",
        encoding="utf-8",
    )
    (blackbox_template / "docker-compose.yml").write_text(
        "services:\n  blackbox:\n    image: blackbox\n",
        encoding="utf-8",
    )
    (blackbox_template / "config" / "blackbox.yml").write_text(
        "modules: {}\n",
        encoding="utf-8",
    )
    (installer_dir).mkdir()
    (installer_dir / "install.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (installer_dir / "install-blackbox.sh").write_text(
        "#!/usr/bin/env bash\n",
        encoding="utf-8",
    )

    with override_settings(
        MONITORING_INSTALLER_DIR=str(installer_dir),
        MONITORING_TEMPLATE_DIR=str(template_dir),
    ):
        response = client.post("/api/v1/monitoring/installer/build/")

    assert response.status_code == 200
    payload = _payload(response)
    assert payload["status"] == "success"
    assert (installer_dir / "categraf-client.tar.gz").exists()
    assert (installer_dir / "blackbox-client.tar.gz").exists()
    assert "categraf-client.tar.gz" in (installer_dir / "SHA256SUMS").read_text(
        encoding="utf-8"
    )
    assert "blackbox-client.tar.gz" in (
        installer_dir / "BLACKBOX_SHA256SUMS"
    ).read_text(encoding="utf-8")
    assert payload["assets"]["categraf-client.tar.gz"]["sha256"]


@pytest.mark.django_db
def test_installer_download_returns_file_response(tmp_path):
    installer_dir = tmp_path / "installer"
    installer_dir.mkdir()
    (installer_dir / "install.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (installer_dir / "blackbox-client.tar.gz").write_bytes(b"archive")

    public_client = APIClient()

    with override_settings(MONITORING_INSTALLER_DIR=str(installer_dir)):
        script_response = public_client.get("/api/v1/monitoring/installer/install.sh")
        archive_response = public_client.get(
            "/api/v1/monitoring/installer/blackbox-client.tar.gz"
        )

    assert script_response.status_code == 200
    assert script_response.headers["Content-Type"] == "text/plain"
    assert b"bash" in b"".join(script_response.streaming_content)
    assert archive_response.status_code == 200
    assert archive_response.headers["Content-Type"] == "application/gzip"
    assert b"".join(archive_response.streaming_content) == b"archive"


@pytest.mark.django_db
def test_import_monitor_admin_assets_copies_file_resources(tmp_path, settings):
    legacy_root = tmp_path / "monitor-admin"
    storage_root = tmp_path / "storage" / "monitoring_stack"
    (legacy_root / "installer").mkdir(parents=True)
    (legacy_root / "templates" / "categraf").mkdir(parents=True)
    (legacy_root / "rules").mkdir(parents=True)
    (legacy_root / "ssh").mkdir(parents=True)
    (legacy_root / "installer" / "install.sh").write_text("install", encoding="utf-8")
    (legacy_root / "templates" / "categraf" / "docker-compose.yml").write_text(
        "compose",
        encoding="utf-8",
    )
    (legacy_root / "rules" / "rules.yml").write_text("groups: []", encoding="utf-8")
    (legacy_root / "ssh" / "id_rsa_ops").write_text("secret", encoding="utf-8")

    with override_settings(
        MONITORING_STACK_ROOT=str(storage_root),
        MONITORING_INSTALLER_DIR=str(storage_root / "installer"),
        MONITORING_TEMPLATE_DIR=str(storage_root / "templates"),
        MONITORING_RULES_DIR=str(storage_root / "rules"),
        MONITORING_SSH_DIR=str(storage_root / "ssh"),
    ):
        call_command("import_monitor_admin_assets", str(legacy_root))

    assert (storage_root / "installer" / "install.sh").read_text(
        encoding="utf-8"
    ) == "install"
    assert (storage_root / "templates" / "categraf" / "docker-compose.yml").exists()
    assert (storage_root / "rules" / "rules.yml").exists()
    assert (storage_root / "ssh" / "id_rsa_ops").exists()


@pytest.mark.django_db
def test_n9e_discover_and_import_use_legacy_nightingale_api(
    client, tmp_path, monkeypatch
):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "n9e.yml").write_text("groups:\n- name: test\n", encoding="utf-8")
    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload
            self.status_code = 200
            self.text = json.dumps(payload)

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class FakeSession:
        trust_env = True

        def __init__(self):
            self.headers = {}

        def post(self, url, **kwargs):
            calls.append(("post", url, kwargs))
            if url.endswith("/api/n9e/auth/login"):
                return FakeResponse({"dat": {"access_token": "token-1"}})
            return FakeResponse({"dat": {"imported": 1}})

        def get(self, url, **kwargs):
            calls.append(("get", url, kwargs))
            if url.endswith("/api/n9e/busi-groups"):
                return FakeResponse({"dat": [{"id": 10, "name": "ops"}]})
            if url.endswith("/api/n9e/datasource/brief"):
                return FakeResponse(
                    {
                        "dat": [
                            {"id": 1, "name": "prom", "plugin_type": "prometheus"},
                            {"id": 2, "name": "other", "plugin_type": "loki"},
                        ]
                    }
                )
            raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr("monitoring_stack.views.requests.Session", FakeSession)

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        discover = client.post(
            "/api/v1/monitoring/n9e/discover/",
            {"n9e_url": "http://n9e", "username": "root", "password": "pw"},
            format="json",
        )
        imported = client.post(
            "/api/v1/monitoring/n9e/import-rules/",
            {
                "n9e_url": "http://n9e",
                "username": "root",
                "password": "pw",
                "group_id": 10,
                "datasource_id": 1,
                "rule_file": "n9e.yml",
                "enabled": True,
            },
            format="json",
        )

    assert discover.status_code == 200
    assert _payload(discover)["groups"] == [{"id": 10, "name": "ops"}]
    assert _payload(discover)["datasources"] == [
        {"id": 1, "name": "prom", "plugin_type": "prometheus"}
    ]
    assert imported.status_code == 200
    assert _payload(imported)["summary"] == {
        "success": 1,
        "skipped": 0,
        "failed": 0,
        "message": "",
    }
    record = RuleImportRecord.objects.get(rule_file="n9e.yml")
    assert record.status == RuleImportRecord.STATUS_SUCCESS
    assert record.template_category == "categraf"
    assert record.summary["success"] == 1
    assert record.group_id == 10
    assert any(
        call[1] == "http://n9e/api/n9e/busi-group/10/alert-rules/import-prom-rule"
        for call in calls
    )


@pytest.mark.django_db
def test_n9e_discover_and_import_use_saved_integration_credentials(
    client, tmp_path, monkeypatch
):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "n9e.yml").write_text("groups:\n- name: test\n", encoding="utf-8")
    config = MonitoringIntegrationConfig.current()
    config.n9e_url = "http://saved-n9e"
    config.n9e_username = "saved-user"
    config.n9e_password = "saved-password"
    config.save()
    login_payloads = []

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class FakeSession:
        trust_env = True

        def __init__(self):
            self.headers = {}

        def post(self, url, **kwargs):
            if url.endswith("/api/n9e/auth/login"):
                login_payloads.append((url, kwargs["json"]))
                return FakeResponse({"dat": {"access_token": "token-1"}})
            return FakeResponse({"dat": {"imported": 1}})

        def get(self, url, **kwargs):
            if url.endswith("/api/n9e/busi-groups"):
                return FakeResponse({"dat": [{"id": 10, "name": "ops"}]})
            if url.endswith("/api/n9e/datasource/brief"):
                return FakeResponse(
                    {"dat": [{"id": 1, "name": "prom", "plugin_type": "prometheus"}]}
                )
            raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr("monitoring_stack.views.requests.Session", FakeSession)

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        discover = client.post("/api/v1/monitoring/n9e/discover/", {}, format="json")
        imported = client.post(
            "/api/v1/monitoring/n9e/import-rules/",
            {
                "group_id": 10,
                "datasource_id": 1,
                "rule_file": "n9e.yml",
                "enabled": True,
            },
            format="json",
        )

    assert discover.status_code == 200
    assert imported.status_code == 200
    assert login_payloads == [
        (
            "http://saved-n9e/api/n9e/auth/login",
            {"username": "saved-user", "password": "saved-password"},
        ),
        (
            "http://saved-n9e/api/n9e/auth/login",
            {"username": "saved-user", "password": "saved-password"},
        ),
    ]


@pytest.mark.django_db
def test_n9e_import_without_count_fields_reports_unknown_counts(
    client, tmp_path, monkeypatch
):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "n9e.yml").write_text("groups:\n- name: test\n", encoding="utf-8")

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            return None

    class FakeSession:
        trust_env = True

        def __init__(self):
            self.headers = {}

        def post(self, url, **kwargs):
            if url.endswith("/api/n9e/auth/login"):
                return FakeResponse({"dat": {"access_token": "token-1"}})
            return FakeResponse({"dat": {}})

    monkeypatch.setattr("monitoring_stack.views.requests.Session", FakeSession)

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        imported = client.post(
            "/api/v1/monitoring/n9e/import-rules/",
            {
                "n9e_url": "http://n9e",
                "username": "root",
                "password": "pw",
                "group_id": 10,
                "datasource_id": 1,
                "rule_file": "n9e.yml",
                "enabled": True,
            },
            format="json",
        )

    assert imported.status_code == 200
    summary = _payload(imported)["summary"]
    assert summary["count_available"] is False
    assert summary["submitted"] == 1
    assert summary["success"] is None
    assert summary["skipped"] is None
    assert summary["failed"] is None
    assert "未返回成功/跳过/失败数量" in summary["message"]
    record = RuleImportRecord.objects.get(rule_file="n9e.yml")
    assert record.status == RuleImportRecord.STATUS_SUCCESS


@pytest.mark.django_db
def test_n9e_import_failure_is_recorded(client, tmp_path, monkeypatch):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "linux-host.yml").write_text(
        "groups:\n- name: linux\n",
        encoding="utf-8",
    )

    class FakeLoginResponse:
        def json(self):
            return {"dat": {"access_token": "token-1"}}

        def raise_for_status(self):
            return None

    class FakeFailedImportResponse:
        def json(self):
            return {"err": "import failed"}

        def raise_for_status(self):
            raise RuntimeError("n9e import failed")

    class FakeSession:
        trust_env = True

        def __init__(self):
            self.headers = {}

        def post(self, url, **kwargs):
            if url.endswith("/api/n9e/auth/login"):
                return FakeLoginResponse()
            return FakeFailedImportResponse()

    monkeypatch.setattr("monitoring_stack.views.requests.Session", FakeSession)

    with override_settings(MONITORING_RULES_DIR=str(rules_dir)):
        imported = client.post(
            "/api/v1/monitoring/n9e/import-rules/",
            {
                "n9e_url": "http://n9e",
                "username": "root",
                "password": "pw",
                "group_id": 10,
                "datasource_id": 1,
                "rule_file": "linux-host.yml",
                "enabled": True,
            },
            format="json",
        )

    assert imported.status_code == 502
    payload = _payload(imported)
    assert payload["summary"]["failed"] == 1
    record = RuleImportRecord.objects.get(rule_file="linux-host.yml")
    assert record.status == RuleImportRecord.STATUS_FAILED
    assert record.template_category == "host"
    assert record.summary["message"] == "n9e import failed"
