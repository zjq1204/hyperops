import io
import time
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model

from monitoring_stack.models import AnsibleInstallJob, MonitoringHost
from monitoring_stack.serializers import AnsibleInstallJobSerializer
from monitoring_stack.services import ansible_progress
from monitoring_stack.services import core as core_service
from monitoring_stack.services.ansible_progress import (
    build_progress,
    current_host_for_line,
    progress_stage_for_line,
    stream_process_output,
)
from monitoring_stack.services.core import render_inventory
from rest_framework.test import APIClient


@pytest.fixture
def api_client(db):
    user = get_user_model().objects.create_superuser(
        username="monitoring-progress-admin",
        email="monitoring-progress@example.com",
        password="password123",
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def job_payload(db):
    host = MonitoringHost.objects.create(
        hostname="dispatch-node-01",
        address="10.0.0.20",
        ssh_user="root",
        enabled=True,
    )
    return {
        "component": "categraf",
        "host_ids": [host.id],
        "profiles": ["linux-basic"],
        "labels": {},
        "params": {},
        "base_url": "http://hyperops.local/api/v1/monitoring/installer",
        "n9e_url": "http://n9e.local:17000",
        "install_dir": "/opt/categraf",
        "image": "flashcatcloud/categraf:latest",
    }


@pytest.mark.django_db
def test_inventory_uses_builtin_ssh_connection(monkeypatch):
    host = MonitoringHost.objects.create(
        hostname="node-01",
        address="10.0.0.10",
        ssh_user="root",
        ssh_auth_type=MonitoringHost.SSH_AUTH_PASSWORD,
        ssh_password="secret",
        ssh_key="stale-key.pem",
    )
    monkeypatch.setattr(
        "monitoring_stack.services.core.host_ssh_key_path",
        lambda selected_host: "/tmp/stale-key.pem",
    )

    inventory = render_inventory([host])

    assert "ansible_connection=ssh" in inventory
    assert "ansible_connection=paramiko" not in inventory
    assert "ansible_password=secret" in inventory
    assert "ansible_ssh_private_key_file" not in inventory


@pytest.mark.django_db
def test_job_serializer_exposes_queued_progress():
    job = AnsibleInstallJob.objects.create(
        base_url="http://hyperops.local/installer",
        host_ids=[],
    )

    progress = AnsibleInstallJobSerializer(job).data["progress"]

    assert progress["stage"] == "queued"
    assert progress["current"] == 1
    assert progress["total"] == 6
    assert progress["percent"] == 0
    assert progress["reason_code"] == "queued"
    assert "message" not in progress


@pytest.mark.django_db
def test_job_serializer_inventory_preview_uses_builtin_ssh_connection():
    job = AnsibleInstallJob.objects.create(
        base_url="http://hyperops.local/installer",
        hosts_snapshot=[
            {
                "id": 1,
                "hostname": "node-01",
                "address": "10.0.0.10",
                "ssh_user": "root",
                "ssh_port": 22,
                "ssh_auth_type": MonitoringHost.SSH_AUTH_PASSWORD,
                "has_ssh_password": True,
                "ssh_key": "stale-key.pem",
            }
        ],
    )

    inventory = AnsibleInstallJobSerializer(job).data["inventory"]

    assert "ansible_connection=ssh" in inventory
    assert "ansible_connection=paramiko" not in inventory
    assert "ansible_password=<configured>" in inventory
    assert "ansible_ssh_private_key_file" not in inventory


def test_failure_reason_code_classifies_ssh_key_and_auth_errors():
    assert (
        ansible_progress.failure_reason_code(
            ['fatal: [node-01]: UNREACHABLE! Load key "/tmp/key": error in libcrypto']
        )
        == "ssh_key_invalid"
    )
    assert (
        ansible_progress.failure_reason_code(
            ["fatal: [node-01]: UNREACHABLE! Permission denied (publickey,password)"]
        )
        == "ssh_auth_failed"
    )


@pytest.mark.django_db
def test_unreachable_install_marks_ssh_verification_failed():
    host = MonitoringHost.objects.create(
        hostname="node-01",
        address="10.0.0.10",
        ssh_verification_status=MonitoringHost.SSH_VERIFICATION_VERIFIED,
    )

    core_service.mark_unreachable_host_verification_failed(
        [host],
        [
            'fatal: [node-01]: UNREACHABLE! => {"msg": '
            '"Load key /tmp/key: error in libcrypto"}'
        ],
    )

    host.refresh_from_db()
    assert host.ssh_verification_status == MonitoringHost.SSH_VERIFICATION_FAILED
    assert host.ssh_verification_error_code == "SSH_KEY_OR_PROTOCOL_FAILED"


def test_ansible_output_updates_install_and_verify_stages():
    assert (
        progress_stage_for_line("TASK [Run unified Categraf installer] ***")
        == "installing"
    )
    assert progress_stage_for_line("PLAY RECAP ************************") == "verifying"
    assert progress_stage_for_line("changed: [node-01]") is None


def test_build_progress_tracks_current_host():
    progress = build_progress("installing", current_host="node-01")
    assert progress["current_host"] == "node-01"
    assert progress["percent"] == 60


def test_ansible_output_extracts_current_host():
    assert current_host_for_line("changed: [node-01]") == "node-01"
    assert current_host_for_line("fatal: [node-02]: FAILED!") == "node-02"
    assert current_host_for_line("PLAY RECAP ***") == ""


class FakeProcess:
    def __init__(self, lines, returncode, events):
        self.stdout = io.StringIO("".join(lines))
        self.returncode = returncode
        self.events = events

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.events.append("wait")
        return self.returncode

    def terminate(self):
        self.events.append("terminate")

    def kill(self):
        self.events.append("kill")


class BlockingStream:
    def readline(self):
        time.sleep(1)
        return ""


class BlockingFakeProcess(FakeProcess):
    def __init__(self):
        super().__init__([], None, [])
        self.stdout = BlockingStream()
        self.terminated = False

    def terminate(self):
        self.terminated = True
        self.returncode = -15


def test_stream_process_flushes_logs_before_waiting_for_exit():
    events = []
    process = FakeProcess(
        lines=[
            "PLAY [Install]\n",
            "TASK [Run unified Categraf installer]\n",
            "PLAY RECAP ***\n",
        ],
        returncode=0,
        events=events,
    )

    result = stream_process_output(
        process,
        timeout_seconds=30,
        on_flush=lambda lines, stage: events.append(
            ("flush", list(lines), stage)
        ),
    )

    assert events.index(("flush", ["PLAY [Install]"], None)) < events.index("wait")
    assert any(
        event[-1] == "installing" for event in events if isinstance(event, tuple)
    )
    assert any(
        event[-1] == "verifying" for event in events if isinstance(event, tuple)
    )
    assert result.timed_out is False


def test_stream_process_terminates_after_timeout():
    process = BlockingFakeProcess()

    result = stream_process_output(
        process,
        timeout_seconds=0.01,
        on_flush=lambda lines, stage: None,
    )

    assert result.timed_out is True
    assert process.terminated is True


@pytest.mark.django_db
def test_worker_exception_persists_failed_progress(monkeypatch):
    from monitoring_stack import tasks

    job = AnsibleInstallJob.objects.create(
        base_url="http://hyperops.local/installer",
        host_ids=[],
    )

    def fail_execution(job_id):
        raise RuntimeError("unexpected worker failure")

    monkeypatch.setattr(tasks, "execute_ansible_job", fail_execution)

    with pytest.raises(RuntimeError, match="unexpected worker failure"):
        tasks.run_ansible_install_job.run(job.id)

    job.refresh_from_db()
    assert job.status == AnsibleInstallJob.STATUS_FAILED
    assert job.returncode == 1
    assert job.progress["stage"] == "failed"
    assert "worker execution failed" in job.logs


@pytest.mark.django_db
def test_job_create_only_enqueues_and_returns_queued_job(
    api_client, job_payload, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        "monitoring_stack.tasks.run_ansible_install_job.delay",
        lambda job_id: calls.append(job_id),
    )

    response = api_client.post(
        "/api/v1/monitoring/ansible/jobs/",
        job_payload,
        format="json",
    )

    assert response.status_code == 201
    assert response.data["status"] == "queued"
    assert calls == [response.data["id"]]


@pytest.mark.django_db
def test_job_create_marks_failed_when_celery_dispatch_fails(
    api_client, job_payload, monkeypatch
):
    monkeypatch.setattr(
        "monitoring_stack.tasks.run_ansible_install_job.delay",
        Mock(side_effect=RuntimeError("broker unavailable")),
    )
    response = api_client.post(
        "/api/v1/monitoring/ansible/jobs/",
        job_payload,
        format="json",
    )

    job = AnsibleInstallJob.objects.latest("id")
    assert response.status_code == 503
    assert job.status == "failed"
    assert job.progress["stage"] == "failed"
    assert job.returncode == 1
