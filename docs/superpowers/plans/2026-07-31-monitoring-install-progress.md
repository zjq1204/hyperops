# Monitoring Installation Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make monitoring installation submission non-blocking, restore supported SSH connectivity, and expose structured live progress and logs through the deployment task detail.

**Architecture:** Celery remains the execution boundary. A focused `ansible_progress` service owns progress normalization and incremental output persistence, while `core.execute_ansible_job` owns playbook construction and process lifecycle. The frontend uses the existing Toast action API and one-second HTTP polling for active jobs; no new transport or frontend dependency is introduced.

**Tech Stack:** Django 5, Django REST Framework, Celery, PostgreSQL, Ansible Core 2.21, OpenSSH/sshpass, Vue 3, Vue Router, vue-i18n, Vite, pytest, Node contract tests, Playwright.

---

## File Map

- Modify `Dockerfile`: install the system SSH client and password helper used by `ansible.builtin.ssh`.
- Modify `backend/monitoring_stack/models.py`: persist structured installation progress.
- Create `backend/monitoring_stack/migrations/0015_ansibleinstalljob_progress.py`: add the JSON progress column.
- Create `backend/monitoring_stack/services/ansible_progress.py`: define stages, progress payloads, line classification, and throttled persistence.
- Modify `backend/monitoring_stack/services/core.py`: generate SSH inventory and stream Ansible output with timeout handling.
- Modify `backend/monitoring_stack/serializers.py`: expose normalized progress.
- Modify `backend/monitoring_stack/views.py`: enqueue only; never run installation in the HTTP request.
- Modify `backend/monitoring_stack/tasks.py`: preserve terminal failure state for unexpected worker errors.
- Create `backend/monitoring_stack/tests/test_ansible_job_progress.py`: focused model, runner, and dispatch regressions.
- Modify `frontend/src/admin/api/monitoringStack.js`: fetch an individual job for polling.
- Modify `frontend/src/admin/pages/Monitoring/Assets.vue`: close after dispatch and show a Toast action linking to task detail.
- Modify `frontend/src/admin/pages/Monitoring/Jobs.vue`: open deep-linked jobs, poll active jobs, and render progress.
- Modify `frontend/src/admin/locales/en.json`: add installation progress and dispatch labels.
- Modify `frontend/src/admin/locales/zh-CN.json`: add installation progress and dispatch labels.
- Modify `frontend/tests/_review/admin-monitoring-stack-contract.test.mjs`: guard dispatch, deep-link, and polling behavior.

### Task 1: Restore Supported SSH Connectivity

**Files:**
- Modify: `Dockerfile:35-70`
- Modify: `backend/monitoring_stack/services/core.py:1767-1790`
- Test: `backend/monitoring_stack/tests/test_ansible_job_progress.py`

- [ ] **Step 1: Write the failing inventory test**

```python
import pytest

from monitoring_stack.models import MonitoringHost
from monitoring_stack.services.core import render_inventory


@pytest.mark.django_db
def test_inventory_uses_builtin_ssh_connection():
    host = MonitoringHost.objects.create(
        hostname="node-01",
        address="10.0.0.10",
        ssh_user="root",
        ssh_auth_type=MonitoringHost.SSH_AUTH_PASSWORD,
        ssh_password="secret",
    )

    inventory = render_inventory([host])

    assert "ansible_connection=ssh" in inventory
    assert "ansible_connection=paramiko" not in inventory
    assert "ansible_password=secret" in inventory
```

- [ ] **Step 2: Run the test and confirm the current Paramiko inventory fails it**

Run:

```bash
env DJANGO_SETTINGS_MODULE=core.settings PYTHONPATH=backend \
  .venv/bin/pytest \
  backend/monitoring_stack/tests/test_ansible_job_progress.py::test_inventory_uses_builtin_ssh_connection -q
```

Expected: FAIL because the inventory contains `ansible_connection=paramiko`.

- [ ] **Step 3: Switch inventory generation to the built-in SSH plugin**

Change the inventory fragment in `render_inventory` to:

```python
f"ansible_port={host.ssh_port or 22} "
f"ansible_connection=ssh{key_arg}{password_arg}"
```

- [ ] **Step 4: Add the required OS packages to the backend image**

Add these entries to the existing `apt-get install` block in `Dockerfile`:

```dockerfile
    openssh-client \
    sshpass \
```

- [ ] **Step 5: Run the focused test**

Run the command from Step 2.

Expected: `1 passed`.

- [ ] **Step 6: Commit the SSH execution change**

```bash
git add Dockerfile backend/monitoring_stack/services/core.py \
  backend/monitoring_stack/tests/test_ansible_job_progress.py
git commit -m "fix: use supported ssh for monitoring installs"
```

### Task 2: Add a Stable Progress Contract

**Files:**
- Modify: `backend/monitoring_stack/models.py:257-315`
- Create: `backend/monitoring_stack/migrations/0015_ansibleinstalljob_progress.py`
- Create: `backend/monitoring_stack/services/ansible_progress.py`
- Modify: `backend/monitoring_stack/serializers.py:590-665`
- Test: `backend/monitoring_stack/tests/test_ansible_job_progress.py`

- [ ] **Step 1: Write failing tests for normalized progress and line classification**

```python
from monitoring_stack.models import AnsibleInstallJob
from monitoring_stack.serializers import AnsibleInstallJobSerializer
from monitoring_stack.services.ansible_progress import (
    build_progress,
    current_host_for_line,
    progress_stage_for_line,
)


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


def test_ansible_output_updates_install_and_verify_stages():
    assert progress_stage_for_line("TASK [Run unified Categraf installer] ***") == "installing"
    assert progress_stage_for_line("PLAY RECAP ******************************") == "verifying"
    assert progress_stage_for_line("changed: [node-01]") is None


def test_build_progress_tracks_current_host():
    progress = build_progress("installing", current_host="node-01")
    assert progress["current_host"] == "node-01"
    assert progress["percent"] == 60


def test_ansible_output_extracts_current_host():
    assert current_host_for_line("changed: [node-01]") == "node-01"
    assert current_host_for_line("fatal: [node-02]: FAILED!") == "node-02"
    assert current_host_for_line("PLAY RECAP ***") == ""
```

- [ ] **Step 2: Run the tests and confirm missing field/module failures**

Run:

```bash
env DJANGO_SETTINGS_MODULE=core.settings PYTHONPATH=backend \
  .venv/bin/pytest backend/monitoring_stack/tests/test_ansible_job_progress.py \
  -q -k 'progress or output_updates'
```

Expected: collection fails because `ansible_progress` and `progress` do not exist.

- [ ] **Step 3: Add the model field and migration**

Add to `AnsibleInstallJob`:

```python
progress = models.JSONField(default=dict, blank=True)
```

Create migration `0015_ansibleinstalljob_progress.py` with dependency
`("monitoring_stack", "0014_monitoringhost_ssh_verification")` and:

```python
migrations.AddField(
    model_name="ansibleinstalljob",
    name="progress",
    field=models.JSONField(blank=True, default=dict),
)
```

- [ ] **Step 4: Implement the progress service**

Create `backend/monitoring_stack/services/ansible_progress.py`:

```python
import re

from django.utils import timezone

from monitoring_stack.models import AnsibleInstallJob

STAGES = {
    "queued": (1, 0),
    "preparing": (2, 20),
    "connecting": (3, 40),
    "installing": (4, 60),
    "verifying": (5, 85),
    "completed": (6, 100),
    "failed": (6, 100),
}


def build_progress(stage, *, current_host="", reason_code=""):
    current, percent = STAGES[stage]
    return {
        "stage": stage,
        "current": current,
        "total": 6,
        "percent": percent,
        "reason_code": reason_code or stage,
        "current_host": current_host,
        "updated_at": timezone.now().isoformat(),
    }


def normalize_progress(progress, status="queued"):
    if isinstance(progress, dict) and progress.get("stage") in STAGES:
        return progress
    terminal = "completed" if status == AnsibleInstallJob.STATUS_SUCCESS else status
    return build_progress(terminal if terminal in STAGES else "queued")


def progress_stage_for_line(line):
    stripped = str(line or "").strip()
    if stripped.startswith("TASK ["):
        return "installing"
    if stripped.startswith("PLAY RECAP"):
        return "verifying"
    return None


def current_host_for_line(line):
    match = re.match(
        r"^(?:ok|changed|fatal|skipping|unreachable):\s*\[([^]]+)]",
        str(line or "").strip(),
        re.IGNORECASE,
    )
    return match.group(1) if match else ""
```

- [ ] **Step 5: Expose normalized progress from the serializer**

Add `progress = serializers.SerializerMethodField()`, include `progress` in
`fields` and `read_only_fields`, and implement:

```python
def get_progress(self, obj):
    return normalize_progress(obj.progress, obj.status)
```

- [ ] **Step 6: Run migrations and tests**

```bash
env DJANGO_SETTINGS_MODULE=core.settings PYTHONPATH=backend \
  .venv/bin/python backend/manage.py migrate monitoring_stack
env DJANGO_SETTINGS_MODULE=core.settings PYTHONPATH=backend \
  .venv/bin/pytest backend/monitoring_stack/tests/test_ansible_job_progress.py -q
```

Expected: progress tests pass.

- [ ] **Step 7: Commit the progress contract**

```bash
git add backend/monitoring_stack/models.py \
  backend/monitoring_stack/migrations/0015_ansibleinstalljob_progress.py \
  backend/monitoring_stack/services/ansible_progress.py \
  backend/monitoring_stack/serializers.py \
  backend/monitoring_stack/tests/test_ansible_job_progress.py
git commit -m "feat: persist monitoring install progress"
```

### Task 3: Stream Ansible Logs and Progress

**Files:**
- Modify: `backend/monitoring_stack/services/ansible_progress.py`
- Modify: `backend/monitoring_stack/services/core.py:1968-2140`
- Modify: `backend/monitoring_stack/tasks.py`
- Test: `backend/monitoring_stack/tests/test_ansible_job_progress.py`

- [ ] **Step 1: Write failing stream persistence and timeout tests**

```python
import io
import time

from monitoring_stack.services.ansible_progress import stream_process_output


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
        on_flush=lambda lines, stage: events.append(("flush", list(lines), stage)),
    )

    assert events.index(("flush", ["PLAY [Install]"], None)) < events.index("wait")
    assert any(event[-1] == "installing" for event in events if isinstance(event, tuple))
    assert any(event[-1] == "verifying" for event in events if isinstance(event, tuple))
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
```

- [ ] **Step 2: Run the tests and confirm `stream_process_output` is missing**

```bash
env DJANGO_SETTINGS_MODULE=core.settings PYTHONPATH=backend \
  .venv/bin/pytest backend/monitoring_stack/tests/test_ansible_job_progress.py \
  -q -k 'stream_process'
```

Expected: FAIL because streaming is not implemented.

- [ ] **Step 3: Implement a queue-backed stdout reader**

```python
import queue
import subprocess
import threading
import time
from dataclasses import dataclass


@dataclass
class StreamResult:
    returncode: int
    timed_out: bool
    lines: list[str]


_STREAM_EOF = object()


def _read_process_lines(stream, output_queue):
    try:
        while True:
            line = stream.readline()
            if line == "":
                break
            output_queue.put(line)
    finally:
        output_queue.put(_STREAM_EOF)


def stream_process_output(process, *, timeout_seconds, on_flush):
    output_queue = queue.Queue()
    reader = threading.Thread(
        target=_read_process_lines,
        args=(process.stdout, output_queue),
        daemon=True,
    )
    reader.start()
    deadline = time.monotonic() + timeout_seconds
    all_lines = []
    buffered = []
    buffered_stage = None
    last_flush = time.monotonic()
    timed_out = False

    def flush():
        nonlocal buffered, buffered_stage, last_flush
        if buffered:
            on_flush(buffered, buffered_stage)
            buffered = []
            buffered_stage = None
            last_flush = time.monotonic()

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            break
        try:
            item = output_queue.get(timeout=min(0.25, remaining))
        except queue.Empty:
            continue
        if item is _STREAM_EOF:
            break
        line = item.strip()
        if not line:
            continue
        stage = progress_stage_for_line(line)
        if stage:
            flush()
            buffered_stage = stage
        buffered.append(line)
        all_lines.append(line)
        if stage or len(buffered) >= 10 or time.monotonic() - last_flush >= 1:
            flush()

    flush()
    if timed_out:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        return StreamResult(returncode=124, timed_out=True, lines=all_lines)
    return StreamResult(
        returncode=process.wait(),
        timed_out=False,
        lines=all_lines,
    )
```

- [ ] **Step 4: Persist incremental output from the worker**

Replace the `subprocess.run` block and terminal save in `execute_ansible_job`
with this lifecycle, retaining the existing temporary inventory/playbook setup
and `_ansible_execution_result` call:

```python
job.progress = build_progress("preparing")
job.save(update_fields=["progress"])
logs = []
current_stage = "connecting"
current_host = ""

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
    reason_code="timeout" if stream_result.timed_out else "",
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
```

- [ ] **Step 5: Persist unexpected worker exceptions**

Replace the task body with:

```python
import logging

from celery import shared_task
from django.utils import timezone
from monitoring_stack.models import AnsibleInstallJob
from monitoring_stack.services.ansible_progress import build_progress
from monitoring_stack.services.core import execute_ansible_job

logger = logging.getLogger(__name__)


@shared_task
def run_ansible_install_job(job_id):
    try:
        execute_ansible_job(job_id)
    except Exception:
        logger.exception("monitoring install job %s failed unexpectedly", job_id)
        job = AnsibleInstallJob.objects.filter(pk=job_id).first()
        if job:
            job.status = AnsibleInstallJob.STATUS_FAILED
            job.returncode = 1
            job.logs = [*(job.logs or []), "worker execution failed"]
            job.progress = build_progress("failed", reason_code="worker_failed")
            job.finished_at = timezone.now()
            job.save(
                update_fields=[
                    "status",
                    "returncode",
                    "logs",
                    "progress",
                    "finished_at",
                ]
            )
        raise
```

- [ ] **Step 6: Run focused execution tests**

```bash
env DJANGO_SETTINGS_MODULE=core.settings PYTHONPATH=backend \
  .venv/bin/pytest \
  backend/monitoring_stack/tests/test_ansible_job_progress.py \
  backend/monitoring_stack/tests/test_monitoring_stack_api.py::test_execute_ansible_job_uses_recap_failure_when_process_returns_zero \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit streaming execution**

```bash
git add backend/monitoring_stack/services/ansible_progress.py \
  backend/monitoring_stack/services/core.py \
  backend/monitoring_stack/tasks.py \
  backend/monitoring_stack/tests/test_ansible_job_progress.py
git commit -m "feat: stream monitoring install progress"
```

### Task 4: Make HTTP Submission Strictly Asynchronous

**Files:**
- Modify: `backend/monitoring_stack/views.py:1178-1230`
- Test: `backend/monitoring_stack/tests/test_ansible_job_progress.py`

- [ ] **Step 1: Write failing create and dispatch-error tests**

```python
from unittest.mock import Mock

from django.contrib.auth import get_user_model
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
def test_job_create_only_enqueues_and_returns_queued_job(
    api_client, job_payload, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        "monitoring_stack.tasks.run_ansible_install_job.delay",
        lambda job_id: calls.append(job_id),
    )
    execute = Mock(side_effect=AssertionError("must not execute inline"))
    monkeypatch.setattr("monitoring_stack.views.execute_ansible_job", execute)

    response = api_client.post(
        "/api/v1/monitoring/ansible/jobs/",
        job_payload,
        format="json",
    )

    assert response.status_code == 201
    assert response.data["status"] == "queued"
    assert calls == [response.data["id"]]
    execute.assert_not_called()


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
```

- [ ] **Step 2: Run tests and confirm the synchronous fallback is detected**

```bash
env DJANGO_SETTINGS_MODULE=core.settings PYTHONPATH=backend \
  .venv/bin/pytest backend/monitoring_stack/tests/test_ansible_job_progress.py \
  -q -k 'create_only_enqueues or dispatch_fails'
```

Expected: FAIL because `views.py` currently calls `execute_ansible_job` in the
exception branch.

- [ ] **Step 3: Replace fallback execution with explicit dispatch failure**

```python
def _dispatch_job(self, job):
    try:
        from monitoring_stack.tasks import run_ansible_install_job

        run_ansible_install_job.delay(job.id)
    except Exception:
        job.status = AnsibleInstallJob.STATUS_FAILED
        job.returncode = 1
        job.logs = ["installation task dispatch failed"]
        job.progress = build_progress(
            "failed",
            reason_code="dispatch_failed",
        )
        job.finished_at = timezone.now()
        job.save(
            update_fields=[
                "status",
                "returncode",
                "logs",
                "progress",
                "finished_at",
            ]
        )
        return Response(
            {
                "detail": "installation task dispatch failed",
                "code": "MONITORING_JOB_DISPATCH_FAILED",
                "job_id": job.id,
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return None


def create(self, request, *args, **kwargs):
    response = super().create(request, *args, **kwargs)
    job = self.get_queryset().get(pk=response.data["id"])
    dispatch_error = self._dispatch_job(job)
    return dispatch_error or response
```

In `retry`, call `dispatch_error = self._dispatch_job(retry_job)` immediately
after creating the retry job and return it when non-null. Do not call
`execute_ansible_job` from either HTTP action.

- [ ] **Step 4: Run dispatch tests**

Run the Step 2 command.

Expected: selected tests pass and complete in less than the execution timeout.

- [ ] **Step 5: Commit asynchronous dispatch**

```bash
git add backend/monitoring_stack/views.py \
  backend/monitoring_stack/tests/test_ansible_job_progress.py
git commit -m "fix: keep monitoring install dispatch asynchronous"
```

### Task 5: Add Submission Toast and Task Detail Link

**Files:**
- Modify: `frontend/src/admin/pages/Monitoring/Assets.vue:823-865,1721-1765`
- Modify: `frontend/src/admin/locales/en.json`
- Modify: `frontend/src/admin/locales/zh-CN.json`
- Modify: `frontend/tests/_review/admin-monitoring-stack-contract.test.mjs`

- [ ] **Step 1: Add a failing frontend contract assertion**

```javascript
assert.match(
  assetsSource,
  /showSuccess\([\s\S]*action:\s*\{[\s\S]*jobs[\s\S]*job:/,
  'asset installation should show a task-detail action after dispatch'
)
```

- [ ] **Step 2: Run the contract and confirm it fails**

```bash
node frontend/tests/_review/admin-monitoring-stack-contract.test.mjs
```

Expected: FAIL with the new task-detail action assertion.

- [ ] **Step 3: Implement the reusable dispatch notification**

Import `useToast`, initialize `showSuccess`, and add:

```javascript
function notifyJobDispatched(job) {
  showSuccess(
    t('adminPages.monitoring.jobDispatched', { id: job.id }),
    8000,
    {
      title: t('adminPages.monitoring.jobDispatchedTitle'),
      action: {
        label: t('adminPages.monitoring.viewTaskDetails'),
        onClick: () => router.push({
          path: '/management/monitoring/jobs',
          query: { job: String(job.id) }
        })
      }
    }
  )
}
```

After Categraf or blackbox job creation, close the corresponding modal, call
`notifyJobDispatched(data)`, then refresh assets without storing the serialized
job inside the preview panel.

- [ ] **Step 4: Add localized labels**

Add equivalent English and Chinese keys:

```json
"jobDispatchedTitle": "Task dispatched",
"jobDispatched": "Installation task #{id} was dispatched",
"viewTaskDetails": "View task details"
```

```json
"jobDispatchedTitle": "任务已下发",
"jobDispatched": "安装任务 #{id} 已进入队列",
"viewTaskDetails": "查看安装任务详情"
```

- [ ] **Step 5: Run the contract test**

Run the Step 2 command.

Expected: `admin-monitoring-stack-contract.test.mjs: OK`.

- [ ] **Step 6: Commit the dispatch interaction**

```bash
git add frontend/src/admin/pages/Monitoring/Assets.vue \
  frontend/src/admin/locales/en.json frontend/src/admin/locales/zh-CN.json \
  frontend/tests/_review/admin-monitoring-stack-contract.test.mjs
git commit -m "feat: link monitoring dispatch to task detail"
```

### Task 6: Render and Poll Live Task Progress

**Files:**
- Modify: `frontend/src/admin/api/monitoringStack.js:108-122`
- Modify: `frontend/src/admin/pages/Monitoring/Jobs.vue`
- Modify: `frontend/src/admin/locales/en.json`
- Modify: `frontend/src/admin/locales/zh-CN.json`
- Modify: `frontend/tests/_review/admin-monitoring-stack-contract.test.mjs`

- [ ] **Step 1: Add failing deep-link and polling contract assertions**

```javascript
assert.match(jobsSource, /useRoute\(\)/, 'jobs should read the task deep link')
assert.match(
  jobsSource,
  /route\.query\.job/,
  'jobs should open the task selected by the job query parameter'
)
assert.match(
  jobsSource,
  /setInterval\([\s\S]*getJob/,
  'jobs should poll the selected active job'
)
assert.match(
  jobsSource,
  /onBeforeUnmount\([\s\S]*clearInterval/,
  'jobs should stop polling when the page unmounts'
)
assert.match(
  jobsSource,
  /selectedJob\.progress/,
  'job detail should render structured progress'
)
```

- [ ] **Step 2: Run the contract and confirm the assertions fail**

```bash
node frontend/tests/_review/admin-monitoring-stack-contract.test.mjs
```

Expected: FAIL on missing route/polling/progress behavior.

- [ ] **Step 3: Add a detail API method**

In `monitoringStack.js` add:

```javascript
getJob(id) {
  return apiClient.get(`/v1/monitoring/ansible/jobs/${id}/`).then(extractData)
},
```

- [ ] **Step 4: Implement selected-job polling lifecycle**

In `Jobs.vue` import `onBeforeUnmount`, `watch`, and `useRoute`. Maintain one
`pollTimer` variable. Poll every 1000 ms only while the selected job status is
`queued` or `running`. Replace both the selected job and its matching row after
each response. Clear the interval when the job becomes `success` or `failed`,
the modal closes, or the component unmounts.

After the initial list load, parse `Number(route.query.job)`, fetch that job,
and open it even if it is not on the current filtered list.

- [ ] **Step 5: Render a compact six-stage progress indicator**

Above the detail tabs, render stable equal-width stages using the ordered codes
`queued`, `preparing`, `connecting`, `installing`, `verifying`, and terminal.
Use circles and connecting lines, not nested cards. Show beneath it:

```text
<localized current stage> · <percent>% · <current host when present>
```

Use the existing emerald, sky, rose, and slate status colors. Preserve the
existing modal width, result tabs, and retry controls.

- [ ] **Step 6: Add localized stage labels**

Add English and Chinese labels for:

```text
Queued / 已下发
Preparing / 准备执行环境
Connecting / 连接主机
Installing / 执行安装
Verifying / 校验结果
Completed / 已完成
Failed / 安装失败
Current host / 当前主机
```

- [ ] **Step 7: Run contract and production build**

```bash
node frontend/tests/_review/admin-monitoring-stack-contract.test.mjs
npm run build
```

Run from `frontend/` for the build command.

Expected: contract reports `OK`; Vite exits zero.

- [ ] **Step 8: Commit live progress UI**

```bash
git add frontend/src/admin/api/monitoringStack.js \
  frontend/src/admin/pages/Monitoring/Jobs.vue \
  frontend/src/admin/locales/en.json frontend/src/admin/locales/zh-CN.json \
  frontend/tests/_review/admin-monitoring-stack-contract.test.mjs
git commit -m "feat: show live monitoring install progress"
```

### Task 7: Rebuild and Verify the End-to-End Flow

**Files:**
- Verify only; no planned source edits.

- [ ] **Step 1: Run backend regressions**

```bash
env DJANGO_SETTINGS_MODULE=core.settings PYTHONPATH=backend \
  .venv/bin/pytest \
  backend/monitoring_stack/tests/test_ansible_job_progress.py \
  backend/monitoring_stack/tests/test_monitoring_stack_api.py::test_execute_ansible_job_marks_component_status_failed_when_ansible_missing \
  backend/monitoring_stack/tests/test_monitoring_stack_api.py::test_execute_ansible_job_uses_recap_failure_when_process_returns_zero \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run frontend verification**

```bash
node frontend/tests/_review/admin-monitoring-stack-contract.test.mjs
cd frontend && npm run build
```

Expected: contract `OK` and Vite exits zero.

- [ ] **Step 3: Rebuild the backend image and apply migrations**

```bash
docker-compose -p hyperops -f docker-compose.dev.yml build \
  backend-api backend-worker backend-scheduler
docker-compose -p hyperops -f docker-compose.dev.yml up -d \
  backend-api backend-worker backend-scheduler
docker exec backend-api-dev python manage.py migrate
docker exec backend-worker-dev sh -lc 'ssh -V && command -v sshpass'
docker exec backend-worker-dev ansible-doc -t connection ansible.builtin.ssh
```

Expected: migration applies, OpenSSH and sshpass exist, and Ansible resolves the
built-in SSH plugin.

- [ ] **Step 4: Verify task submission in the browser**

Using Playwright at `http://192.168.7.168:18080/management/monitoring/assets`:

1. submit a Categraf installation;
2. confirm the modal closes immediately and the Toast contains the task ID;
3. click `查看安装任务详情`;
4. confirm the URL contains `?job=<id>` and the matching detail opens;
5. observe at least two non-terminal progress stages or incremental log updates;
6. confirm polling stops at success or failure;
7. capture desktop and mobile screenshots under `output/playwright/`.

- [ ] **Step 5: Verify stored task data**

Fetch the task detail API and confirm:

```json
{
  "status": "failed",
  "progress": {
    "stage": "failed",
    "percent": 100
  },
  "logs": ["PLAY [Install Categraf by unified installer]"],
  "results": [{"hostname": "nexus", "status": "failed"}]
}
```

If the real target installation succeeds, the equivalent accepted terminal
values are `status=success`, `progress.stage=completed`, and a successful host
result. In either outcome, the four terminal fields must agree.

The final UI status, return code, recap, and failed host count must agree.

- [ ] **Step 6: Review the final diff**

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only intended project changes are included in
the implementation commits.
