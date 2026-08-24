from pathlib import Path

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from monitoring_stack.models import (
    AnsibleInstallJob,
    BlackboxProbeNode,
    MonitoringComponentStatus,
    MonitoringHost,
)
from monitoring_stack.serializers import (
    AnsibleInstallJobSerializer,
    AnsiblePreviewSerializer,
    BlackboxProbeNodeSerializer,
)
from monitoring_stack.services.core import mark_component_finished
from monitoring_stack.views import resolved_install_job_payload


class CapabilityUpdateSafetyTests(TestCase):
    def setUp(self):
        self.host = MonitoringHost.objects.create(
            hostname="capability-update-01",
            address="10.0.0.61",
            enabled=True,
        )
        self.baseline = AnsibleInstallJob.objects.create(
            status=AnsibleInstallJob.STATUS_SUCCESS,
            component=AnsibleInstallJob.COMPONENT_CATEGRAF,
            profiles=["linux-basic", "mysql-rds"],
            labels={"region": "beijing", "service": "mysql"},
            params={
                "mysql_address": "mysql.internal:3306",
                "mysql_user": "monitor",
                "mysql_password": "secret",
            },
            host_ids=[self.host.id],
            base_url="http://old.example/api/v1/monitoring/installer",
            n9e_url="http://old-n9e",
            install_dir="/srv/categraf",
            image="flashcatcloud/categraf:stable",
        )

    def test_update_payload_inherits_last_successful_job_config(self):
        serializer = AnsiblePreviewSerializer(
            data={
                "component": "categraf",
                "host_ids": [self.host.id],
                "profiles": ["redis"],
                "labels": {"env": "prod"},
                "params": {"redis_address": "redis.internal:6379"},
                "base_job_id": self.baseline.id,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        payload = resolved_install_job_payload(serializer.validated_data)

        self.assertEqual(payload["base_job"], self.baseline)
        self.assertEqual(
            payload["profiles"], ["linux-basic", "mysql-rds", "redis"]
        )
        self.assertEqual(
            payload["labels"],
            {"region": "beijing", "service": "mysql", "env": "prod"},
        )
        self.assertEqual(
            payload["params"],
            {
                "mysql_address": "mysql.internal:3306",
                "mysql_user": "monitor",
                "mysql_password": "secret",
                "redis_address": "redis.internal:6379",
            },
        )
        self.assertEqual(payload["base_url"], self.baseline.base_url)
        self.assertEqual(payload["n9e_url"], self.baseline.n9e_url)
        self.assertEqual(payload["install_dir"], self.baseline.install_dir)
        self.assertEqual(payload["image"], self.baseline.image)

    def test_update_payload_accepts_explicit_deployment_setting_changes(self):
        serializer = AnsibleInstallJobSerializer(
            data={
                "component": "categraf",
                "host_ids": [self.host.id],
                "profiles": ["redis"],
                "base_job_id": self.baseline.id,
                "base_url": "http://new.example/installer",
                "n9e_url": "http://new-n9e",
                "install_dir": "/srv/categraf-next",
                "image": "flashcatcloud/categraf:next",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        payload = resolved_install_job_payload(serializer.validated_data)

        self.assertEqual(payload["base_url"], "http://new.example/installer")
        self.assertEqual(payload["n9e_url"], "http://new-n9e")
        self.assertEqual(payload["install_dir"], "/srv/categraf-next")
        self.assertEqual(payload["image"], "flashcatcloud/categraf:next")

    def test_failed_update_keeps_last_successful_job_active(self):
        component_status = MonitoringComponentStatus.objects.create(
            host=self.host,
            component=AnsibleInstallJob.COMPONENT_CATEGRAF,
            status=MonitoringComponentStatus.STATUS_SUCCESS,
            install_dir=self.baseline.install_dir,
            last_job=self.baseline,
            active_job=self.baseline,
        )
        failed_update = AnsibleInstallJob.objects.create(
            status=AnsibleInstallJob.STATUS_FAILED,
            component=AnsibleInstallJob.COMPONENT_CATEGRAF,
            profiles=["linux-basic", "mysql-rds", "redis"],
            host_ids=[self.host.id],
            base_url=self.baseline.base_url,
            n9e_url=self.baseline.n9e_url,
            install_dir=self.baseline.install_dir,
            base_job=self.baseline,
        )

        mark_component_finished(
            failed_update,
            [self.host],
            MonitoringComponentStatus.STATUS_FAILED,
            ["redis validation failed"],
        )

        component_status.refresh_from_db()
        self.assertEqual(
            component_status.status, MonitoringComponentStatus.STATUS_SUCCESS
        )
        self.assertEqual(component_status.active_job_id, self.baseline.id)
        self.assertEqual(component_status.last_job_id, failed_update.id)
        self.assertIn("redis validation failed", component_status.last_error)

    def test_installer_is_transactional(self):
        script = (
            Path(__file__).resolve().parents[1] / "installer" / "install.sh"
        ).read_text(encoding="utf-8")

        self.assertIn('mktemp -d "${install_parent}/.${install_name}.staging.', script)
        self.assertIn('"${COMPOSE[@]}" config -q', script)
        self.assertIn('backup_dir="${INSTALL_DIR}.backup.', script)
        self.assertIn("rollback_install", script)
        self.assertIn('"${COMPOSE[@]}" up -d', script)

    def test_blackbox_install_rejects_installed_and_installing_hosts(self):
        component_status = MonitoringComponentStatus.objects.create(
            host=self.host,
            component=AnsibleInstallJob.COMPONENT_BLACKBOX,
            status=MonitoringComponentStatus.STATUS_SUCCESS,
        )

        for blocked_status in (
            MonitoringComponentStatus.STATUS_SUCCESS,
            MonitoringComponentStatus.STATUS_INSTALLING,
        ):
            component_status.status = blocked_status
            component_status.save(update_fields=["status"])
            with self.assertRaises(ValidationError):
                resolved_install_job_payload(
                    {
                        "component": AnsibleInstallJob.COMPONENT_BLACKBOX,
                        "host_ids": [self.host.id],
                    }
                )

    def test_blackbox_install_allows_host_after_failed_attempt(self):
        MonitoringComponentStatus.objects.create(
            host=self.host,
            component=AnsibleInstallJob.COMPONENT_BLACKBOX,
            status=MonitoringComponentStatus.STATUS_FAILED,
        )

        payload = resolved_install_job_payload(
            {
                "component": AnsibleInstallJob.COMPONENT_BLACKBOX,
                "host_ids": [self.host.id],
            }
        )

        self.assertEqual(payload["component"], AnsibleInstallJob.COMPONENT_BLACKBOX)

    def test_blackbox_install_rejects_host_bound_to_probe_node(self):
        BlackboxProbeNode.objects.create(
            name="existing-probe-node",
            address=self.host.address,
            port="9115",
            host=self.host,
        )

        with self.assertRaises(ValidationError):
            resolved_install_job_payload(
                {
                    "component": AnsibleInstallJob.COMPONENT_BLACKBOX,
                    "host_ids": [self.host.id],
                }
            )

    def test_managed_probe_node_identity_cannot_be_edited(self):
        for source in (
            BlackboxProbeNode.SOURCE_INSTALL,
            BlackboxProbeNode.SOURCE_PROMETHEUS,
        ):
            node = BlackboxProbeNode.objects.create(
                name=f"managed-{source}",
                address="10.0.0.80",
                port="9115",
                host=self.host,
                source=source,
            )
            serializer = BlackboxProbeNodeSerializer(
                node,
                data={
                    "address": "10.0.0.81",
                    "port": "9116",
                    "host": None,
                },
                partial=True,
            )

            self.assertFalse(serializer.is_valid())
            self.assertIn("address", serializer.errors)
            self.assertIn("port", serializer.errors)
            self.assertIn("host", serializer.errors)

    def test_managed_probe_node_allows_name_and_enabled_changes(self):
        node = BlackboxProbeNode.objects.create(
            name="managed-install",
            address="10.0.0.80",
            port="9115",
            host=self.host,
            source=BlackboxProbeNode.SOURCE_INSTALL,
        )
        serializer = BlackboxProbeNodeSerializer(
            node,
            data={"name": "managed-install-renamed", "enabled": False},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        node.refresh_from_db()
        self.assertEqual(node.name, "managed-install-renamed")
        self.assertFalse(node.enabled)
        self.assertEqual(node.address, "10.0.0.80")
        self.assertEqual(node.host_id, self.host.id)

    def test_manual_probe_node_identity_remains_editable(self):
        node = BlackboxProbeNode.objects.create(
            name="manual-probe",
            address="10.0.0.80",
            port="9115",
            source=BlackboxProbeNode.SOURCE_MANUAL,
        )
        serializer = BlackboxProbeNodeSerializer(
            node,
            data={"address": "10.0.0.81", "port": "9116", "host": self.host.id},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
