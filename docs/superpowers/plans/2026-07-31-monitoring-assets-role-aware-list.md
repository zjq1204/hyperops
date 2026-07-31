# Monitoring Assets Role-Aware List Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monitoring host table with a role-aware list that retains safe SSH verification evidence, hides irrelevant blackbox warnings, and presents one prioritized next action per host.

**Architecture:** Add persisted SSH verification metadata to `MonitoringHost`, issue short-lived signed receipts from the existing connection-test endpoint, and consume those receipts during host save. Isolate role/component/action normalization in a backend service and expose presentation codes through the host serializer. Keep Vue rendering and filtering in a small pure helper so the existing large `Assets.vue` page remains manageable.

**Tech Stack:** Django 5, Django signing/HMAC, Django REST Framework, Paramiko, Vue 3 `<script setup>`, Tailwind CSS, Node assertion tests, pytest.

---

## File Map

- Create `backend/monitoring_stack/services/ssh_verification.py`: connection fingerprinting, receipt issue/validation, persistence helpers.
- Create `backend/monitoring_stack/services/asset_state.py`: host roles, normalized component states, and next-action decision order.
- Create `backend/monitoring_stack/migrations/0014_monitoringhost_ssh_verification.py`: verification fields and index.
- Modify `backend/monitoring_stack/models.py`: verification choices and fields.
- Modify `backend/monitoring_stack/serializers.py`: receipt input and role-aware read models.
- Modify `backend/monitoring_stack/views.py`: issue receipts and persist matched failures.
- Modify `backend/monitoring_stack/tests/test_monitoring_stack_api.py`: API, receipt, role, and action regressions.
- Create `frontend/src/admin/pages/Monitoring/assets/hostListState.js`: pure filtering, count, and display helpers.
- Modify `frontend/src/admin/pages/Monitoring/Assets.vue`: toolbar modes, role-aware columns, and contextual actions.
- Modify `frontend/src/admin/locales/zh-CN.json`: Chinese labels and safe action copy.
- Modify `frontend/src/admin/locales/en.json`: English labels and action copy.
- Create `frontend/tests/_review/monitoring-assets-state.test.mjs`: pure frontend state tests.
- Modify `frontend/tests/_review/admin-monitoring-stack-contract.test.mjs`: page/API contract assertions.

### Task 1: Persist SSH Verification Evidence

**Files:**
- Modify: `backend/monitoring_stack/models.py`
- Create: `backend/monitoring_stack/migrations/0014_monitoringhost_ssh_verification.py`
- Test: `backend/monitoring_stack/tests/test_monitoring_stack_api.py`

- [ ] **Step 1: Write the failing model/API test**

Add a test that creates a host and asserts the serializer returns a conservative default:

```python
@pytest.mark.django_db
def test_host_list_exposes_unverified_ssh_snapshot_by_default(client):
    host = MonitoringHost.objects.create(
        hostname="asset-01",
        address="10.0.0.21",
        ssh_auth_type=MonitoringHost.SSH_AUTH_PASSWORD,
        ssh_password="secret",
    )

    response = client.get("/api/v1/monitoring/hosts/")
    row = next(item for item in _payload(response)["results"] if item["id"] == host.id)

    assert row["ssh_verification"] == {
        "status": "unverified",
        "checked_at": None,
        "latency_ms": None,
        "error_code": "",
        "matches_current_settings": False,
    }
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings PYTHONPATH=backend .venv/bin/python -m pytest \
  backend/monitoring_stack/tests/test_monitoring_stack_api.py \
  -k host_list_exposes_unverified_ssh_snapshot -q
```

Expected: FAIL because `ssh_verification` is absent.

- [ ] **Step 3: Add model fields and migration**

Add choices and fields to `MonitoringHost`:

```python
SSH_VERIFICATION_UNVERIFIED = "unverified"
SSH_VERIFICATION_VERIFIED = "verified"
SSH_VERIFICATION_FAILED = "failed"
SSH_VERIFICATION_CHOICES = [
    (SSH_VERIFICATION_UNVERIFIED, "Unverified"),
    (SSH_VERIFICATION_VERIFIED, "Verified"),
    (SSH_VERIFICATION_FAILED, "Failed"),
]

ssh_verification_status = models.CharField(
    max_length=16,
    choices=SSH_VERIFICATION_CHOICES,
    default=SSH_VERIFICATION_UNVERIFIED,
)
ssh_verification_checked_at = models.DateTimeField(null=True, blank=True)
ssh_verification_latency_ms = models.PositiveIntegerField(null=True, blank=True)
ssh_verification_error_code = models.CharField(max_length=64, blank=True, default="")
ssh_verification_signature = models.CharField(max_length=64, blank=True, default="")
```

Create migration `0014` depending on `0013_blackboxprobenode_prometheus_source` and add an index on `ssh_verification_status`.

- [ ] **Step 4: Expose the conservative serializer snapshot**

Add `ssh_verification = SerializerMethodField()` to `MonitoringHostSerializer`. Until Task 2 provides signature matching, return the stored values and set `matches_current_settings` to `False` when no signature exists.

- [ ] **Step 5: Run the test and verify GREEN**

Run the Task 1 pytest command. Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/monitoring_stack/models.py \
  backend/monitoring_stack/migrations/0014_monitoringhost_ssh_verification.py \
  backend/monitoring_stack/serializers.py \
  backend/monitoring_stack/tests/test_monitoring_stack_api.py
git commit -m "feat: persist monitoring SSH verification state"
```

### Task 2: Bind Connection Tests to Saved Settings

**Files:**
- Create: `backend/monitoring_stack/services/ssh_verification.py`
- Modify: `backend/monitoring_stack/serializers.py`
- Modify: `backend/monitoring_stack/views.py`
- Test: `backend/monitoring_stack/tests/test_monitoring_stack_api.py`

- [ ] **Step 1: Write failing receipt tests**

Add tests that prove:

```python
@pytest.mark.django_db
def test_successful_connection_test_returns_verification_receipt(client, monkeypatch):
    import monitoring_stack.views as monitoring_views

    monkeypatch.setattr(
        monitoring_views,
        "check_monitoring_ssh_connection",
        lambda **kwargs: {"latency_ms": 12},
    )
    response = client.post(
        "/api/v1/monitoring/hosts/test-connection/",
        {
            "address": "10.0.0.21",
            "ssh_user": "root",
            "ssh_port": 22,
            "ssh_auth_type": "password",
            "ssh_password": "secret",
        },
        format="json",
    )

    assert response.status_code == 200
    assert _payload(response)["verification_receipt"]


@pytest.mark.django_db
def test_host_save_accepts_receipt_for_exact_settings(client, monkeypatch):
    import monitoring_stack.views as monitoring_views

    monkeypatch.setattr(
        monitoring_views,
        "check_monitoring_ssh_connection",
        lambda **kwargs: {"latency_ms": 12},
    )
    settings_payload = {
        "hostname": "asset-01",
        "address": "10.0.0.21",
        "ssh_user": "root",
        "ssh_port": 22,
        "ssh_auth_type": "password",
        "ssh_password": "secret",
    }
    test_response = client.post(
        "/api/v1/monitoring/hosts/test-connection/",
        {key: value for key, value in settings_payload.items() if key != "hostname"},
        format="json",
    )
    settings_payload["ssh_verification_receipt"] = _payload(test_response)[
        "verification_receipt"
    ]

    create_response = client.post(
        "/api/v1/monitoring/hosts/", settings_payload, format="json"
    )
    saved = MonitoringHost.objects.get(id=_payload(create_response)["id"])

    assert saved.ssh_verification_status == "verified"
    assert saved.ssh_verification_latency_ms == 12


@pytest.mark.django_db
def test_host_save_rejects_receipt_after_address_changes(client, monkeypatch):
    import monitoring_stack.views as monitoring_views

    monkeypatch.setattr(
        monitoring_views,
        "check_monitoring_ssh_connection",
        lambda **kwargs: {"latency_ms": 12},
    )
    test_response = client.post(
        "/api/v1/monitoring/hosts/test-connection/",
        {
            "address": "10.0.0.21",
            "ssh_user": "root",
            "ssh_port": 22,
            "ssh_auth_type": "password",
            "ssh_password": "secret",
        },
        format="json",
    )
    response = client.post(
        "/api/v1/monitoring/hosts/",
        {
            "hostname": "asset-01",
            "address": "10.0.0.22",
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

    assert response.status_code == 400
    assert _payload(response)["error_code"] == "SSH_VERIFICATION_MISMATCH"


@pytest.mark.django_db
def test_failed_unsaved_settings_do_not_replace_saved_result(client, monkeypatch):
    host = MonitoringHost.objects.create(
        hostname="asset-01",
        address="10.0.0.21",
        ssh_auth_type="password",
        ssh_password="secret",
        ssh_verification_status="verified",
        ssh_verification_signature="saved-fingerprint",
    )
    import monitoring_stack.views as monitoring_views

    def fail_connection(**kwargs):
        raise MonitoringSshConnectionError("SSH_UNREACHABLE", 502)

    monkeypatch.setattr(
        monitoring_views, "check_monitoring_ssh_connection", fail_connection
    )
    response = client.post(
        "/api/v1/monitoring/hosts/test-connection/",
        {
            "host_id": host.id,
            "address": "10.0.0.99",
            "ssh_user": "root",
            "ssh_port": 22,
            "ssh_auth_type": "password",
            "ssh_password": "different-secret",
        },
        format="json",
    )

    assert response.status_code == 502
    host.refresh_from_db()
    assert host.ssh_verification_status == "verified"
```

Use monkeypatch for `check_monitoring_ssh_connection`; do not open real SSH sessions.

- [ ] **Step 2: Run receipt tests and verify RED**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings PYTHONPATH=backend .venv/bin/python -m pytest \
  backend/monitoring_stack/tests/test_monitoring_stack_api.py \
  -k "verification_receipt or failed_unsaved_settings" -q
```

Expected: FAIL because receipt support does not exist.

- [ ] **Step 3: Implement fingerprint and receipt helpers**

Create focused helpers:

```python
RECEIPT_SALT = "monitoring-stack.ssh-verification.v1"
RECEIPT_MAX_AGE_SECONDS = 600

def connection_fingerprint(*, address, ssh_user, ssh_port, ssh_auth_type,
                           password="", ssh_key_id=None):
    normalized = {
        "address": str(address or "").strip().lower(),
        "ssh_user": str(ssh_user or "root").strip(),
        "ssh_port": int(ssh_port or 22),
        "ssh_auth_type": ssh_auth_type,
        "secret_identity": str(ssh_key_id or "") if ssh_auth_type == "key"
        else salted_hmac(RECEIPT_SALT, str(password or "")).hexdigest(),
    }
    return salted_hmac(RECEIPT_SALT, json.dumps(normalized, sort_keys=True)).hexdigest()

def issue_verification_receipt(*, user_id, host_id, fingerprint, checked_at, latency_ms):
    return signing.dumps({
        "version": 1,
        "user_id": user_id,
        "host_id": host_id,
        "fingerprint": fingerprint,
        "checked_at": checked_at.isoformat(),
        "latency_ms": latency_ms,
    }, salt=RECEIPT_SALT, compress=True)
```

Add a matching `load_verification_receipt()` that calls
`signing.loads(receipt, salt=RECEIPT_SALT, max_age=RECEIPT_MAX_AGE_SECONDS)`
and raises a domain error with `SSH_VERIFICATION_EXPIRED` or
`SSH_VERIFICATION_MISMATCH`.

- [ ] **Step 4: Return receipt and persist exact saved failures**

After a successful connection check, compute the fingerprint from resolved credentials and return the receipt. On failure, persist `failed` only when `host_id` exists and the tested fingerprint equals the current saved fingerprint.

- [ ] **Step 5: Consume receipt during host create/update**

Add write-only `ssh_verification_receipt` to `MonitoringHostSerializer`. Validate it against `request.user`, the instance ID, and the submitted/resolved connection settings. On create/update store verified metadata. If signed connection fields changed without a valid receipt, clear all verification fields to `unverified`.

- [ ] **Step 6: Make serializer matching authoritative**

Update `get_ssh_verification()` so `matches_current_settings` compares the stored signature with a fingerprint generated from current saved settings.

- [ ] **Step 7: Run receipt tests and verify GREEN**

Run the Task 2 pytest command. Expected: all selected tests PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/monitoring_stack/services/ssh_verification.py \
  backend/monitoring_stack/serializers.py backend/monitoring_stack/views.py \
  backend/monitoring_stack/tests/test_monitoring_stack_api.py
git commit -m "feat: bind SSH verification to host settings"
```

### Task 3: Normalize Roles, Components, and Next Actions

**Files:**
- Create: `backend/monitoring_stack/services/asset_state.py`
- Modify: `backend/monitoring_stack/serializers.py`
- Modify: `backend/monitoring_stack/views.py`
- Test: `backend/monitoring_stack/tests/test_monitoring_stack_api.py`

- [ ] **Step 1: Write the decision-table tests**

Cover at least these rows:

```python
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
    result = choose_next_action(
        collection_state={"code": categraf, "job_id": None},
        probe_state={
            "code": blackbox if probe_required else "not_applicable",
            "job_id": None,
        },
        ssh_state={
            "status": ssh,
            "checked_at": timezone.now().isoformat() if ssh == "verified" else None,
        },
        now=timezone.now(),
    )
    assert result["code"] == expected
```

Add an API test asserting an ordinary host has roles `['collection_host']` and `probe_state.code == 'not_applicable'`, while a host referenced by an enabled probe node also has `probe_node`.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
DJANGO_SETTINGS_MODULE=core.settings PYTHONPATH=backend .venv/bin/python -m pytest \
  backend/monitoring_stack/tests/test_monitoring_stack_api.py \
  -k "asset_next_action or host_roles" -q
```

Expected: FAIL because normalized row state does not exist.

- [ ] **Step 3: Implement pure state functions**

Create constants and pure functions:

```python
def host_roles(host):
    roles = ["collection_host"]
    if any(node.enabled for node in host.blackbox_probe_nodes.all()):
        roles.append("probe_node")
    return roles

def choose_next_action(*, collection_state, probe_state, ssh_state, now=None):
    expected = [collection_state]
    if probe_state["code"] != "not_applicable":
        expected.append(probe_state)
    if any(item["code"] == "deploying" for item in expected):
        return {"code": "deployment_in_progress", "component": "", "job_id": None}
    needs_work = any(
        item["code"] in {
            "pending_deployment", "deployment_failed", "abnormal", "unknown"
        }
        for item in expected
    )
    if needs_work and ssh_state["status"] == "failed":
        return {"code": "fix_ssh", "component": "", "job_id": None}
    if needs_work and ssh_verification_required(ssh_state, now=now):
        return {"code": "verify_ssh", "component": "", "job_id": None}
    for state, code in (
        (collection_state, "review_deployment_failure"),
        (probe_state, "review_deployment_failure"),
    ):
        if state["code"] == "deployment_failed":
            return {"code": code, "component": state["component"], "job_id": state["job_id"]}
    if collection_state["code"] == "pending_deployment":
        return {"code": "deploy_categraf", "component": "categraf", "job_id": None}
    if probe_state["code"] == "pending_deployment":
        return {"code": "deploy_blackbox", "component": "blackbox", "job_id": None}
    if collection_state["code"] == "abnormal":
        return {"code": "inspect_collection", "component": "categraf", "job_id": collection_state["job_id"]}
    if probe_state["code"] == "abnormal":
        return {"code": "inspect_probe", "component": "blackbox", "job_id": probe_state["job_id"]}
    if any(item["code"] == "unknown" for item in expected):
        return {"code": "status_unconfirmed", "component": "", "job_id": None}
    return {"code": "running_normally", "component": "", "job_id": None}
```

Keep output code-based: `{"code": "verify_ssh", "component": "categraf", "job_id": None}`. Do not return display-language strings.

- [ ] **Step 4: Expose normalized serializer fields**

Add read-only `roles`, `collection_state`, `probe_state`, and `next_action` to `MonitoringHostSerializer`. Reuse existing component status evidence and governance findings rather than issuing new external calls per row.

Prefetch `component_statuses`, `blackbox_probe_nodes`, and their latest job data in `MonitoringHostViewSet.get_queryset()` to avoid N+1 queries.

- [ ] **Step 5: Run tests and verify GREEN**

Run the Task 3 pytest command. Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/monitoring_stack/services/asset_state.py \
  backend/monitoring_stack/serializers.py backend/monitoring_stack/views.py \
  backend/monitoring_stack/tests/test_monitoring_stack_api.py
git commit -m "feat: add role-aware monitoring asset state"
```

### Task 4: Add Pure Frontend List State

**Files:**
- Create: `frontend/src/admin/pages/Monitoring/assets/hostListState.js`
- Create: `frontend/tests/_review/monitoring-assets-state.test.mjs`

- [ ] **Step 1: Write the failing Node test**

Test search, attention count, and status scopes with realistic rows:

```javascript
assert.equal(hostMatchesScope(ordinaryHost, 'probe_issue'), false)
assert.equal(hostMatchesScope(probeHost, 'probe_issue'), true)
assert.equal(attentionCount([healthyHost, pendingHost]), 1)
assert.equal(hostMatchesSearch(ordinaryHost, '10.0.0.21'), true)
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
cd frontend && node tests/_review/monitoring-assets-state.test.mjs
```

Expected: module-not-found failure.

- [ ] **Step 3: Implement pure filtering helpers**

Export:

```javascript
export function hostMatchesSearch(host, query) {
  const needle = String(query || '').trim().toLowerCase()
  if (!needle) return true
  return [host.hostname, host.address]
    .some((value) => String(value || '').toLowerCase().includes(needle))
}
export function hostMatchesScope(host, scope) {
  if (scope === 'all') return true
  const action = host.next_action?.code || 'status_unconfirmed'
  if (scope === 'needs_attention')
    return !['running_normally', 'deployment_in_progress'].includes(action)
  if (scope === 'healthy') return action === 'running_normally'
  if (scope === 'ssh_issue') return ['verify_ssh', 'fix_ssh'].includes(action)
  if (scope === 'collection_issue')
    return ['pending_deployment', 'deployment_failed', 'abnormal', 'unknown']
      .includes(host.collection_state?.code)
  if (scope === 'probe_issue')
    return isProbeNode(host) &&
      ['pending_deployment', 'deployment_failed', 'abnormal', 'unknown']
        .includes(host.probe_state?.code)
  return false
}
export function filterHosts(hosts, { query, scope }) {
  return hosts.filter(
    (host) => hostMatchesSearch(host, query) && hostMatchesScope(host, scope)
  )
}
export function attentionCount(hosts) {
  return hosts.filter((host) => hostMatchesScope(host, 'needs_attention')).length
}
export function isProbeNode(host) {
  return Array.isArray(host.roles) && host.roles.includes('probe_node')
}
```

Use only normalized API codes. Treat missing fields conservatively as unknown/attention, never healthy.

- [ ] **Step 4: Run the test and verify GREEN**

Run the Task 4 Node command. Expected: no assertion output and exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/admin/pages/Monitoring/assets/hostListState.js \
  frontend/tests/_review/monitoring-assets-state.test.mjs
git commit -m "test: define monitoring asset list state"
```

### Task 5: Rebuild the Assets Toolbar and Table

**Files:**
- Modify: `frontend/src/admin/pages/Monitoring/Assets.vue`
- Modify: `frontend/src/admin/locales/zh-CN.json`
- Modify: `frontend/src/admin/locales/en.json`
- Modify: `frontend/tests/_review/admin-monitoring-stack-contract.test.mjs`
- Test: `frontend/tests/_review/monitoring-assets-state.test.mjs`

- [ ] **Step 1: Add failing contract assertions**

Assert that the page:

```javascript
assert.match(assetsSource, /filters\.query/)
assert.match(assetsSource, /filters\.scope/)
assert.match(assetsSource, /host\.roles/)
assert.match(assetsSource, /host\.collection_state/)
assert.match(assetsSource, /host\.probe_state/)
assert.match(assetsSource, /host\.next_action/)
assert.doesNotMatch(assetsSource, /filters\.blackboxStatus/)
assert.match(assetsSource, /v-if="selectedHostIds\.length"/)
```

- [ ] **Step 2: Run contract tests and verify RED**

Run:

```bash
cd frontend && node tests/_review/admin-monitoring-stack-contract.test.mjs
```

Expected: FAIL on the new role-aware assertions.

- [ ] **Step 3: Replace the normal toolbar**

Use `AdminListSection` slots to render:

- search input;
- one shared-styled status select;
- total/attention summary;
- icon refresh with `aria-label` and `title`;
- install and add commands.

Render a separate bulk toolbar only when `selectedHostIds.length > 0`; include selected count, clear, and install.

- [ ] **Step 4: Replace table columns and rows**

Render host identity and role chips in one cell, use normalized collection/probe status pills, and render one contextual next action. Ordinary hosts display neutral `Not applicable`; no raw `blackbox not installed` label is generated.

Keep row dimensions stable with explicit grid/flex constraints. At narrow widths fold probe details into the host/status stack using responsive utility classes.

- [ ] **Step 5: Wire contextual actions**

Map action codes:

```javascript
function runNextAction(host) {
  const code = host.next_action?.code
  if (['verify_ssh', 'fix_ssh'].includes(code)) return editHost(host, { focus: 'ssh' })
  if (code === 'deploy_categraf') return openCategrafInstall([host.id])
  if (code === 'deploy_blackbox') return openBlackboxInstall([host.id])
  if (['inspect_collection', 'inspect_probe', 'review_deployment_failure'].includes(code))
    return router.push('/management/monitoring/jobs')
}
```

Keep `running_normally`, `deployment_in_progress`, and `status_unconfirmed` non-interactive.

- [ ] **Step 6: Pass receipt during save and clear it on change**

Store `verification_receipt` from `testHostConnection()`, include it in `hostPayload()` as `ssh_verification_receipt`, and clear it in the existing connection-signature watcher.

- [ ] **Step 7: Add i18n codes**

Add Chinese and English labels for roles, normalized component states, scope filters, next actions, summary counts, not applicable, and verification receipt errors. No display-language text is hard-coded in Vue.

- [ ] **Step 8: Run frontend tests and verify GREEN**

Run:

```bash
cd frontend
node tests/_review/monitoring-assets-state.test.mjs
node tests/_review/admin-monitoring-stack-contract.test.mjs
node tests/_review/api-error-contract.test.mjs
```

Expected: all commands exit 0.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/admin/pages/Monitoring/Assets.vue \
  frontend/src/admin/locales/zh-CN.json frontend/src/admin/locales/en.json \
  frontend/tests/_review/admin-monitoring-stack-contract.test.mjs
git commit -m "feat: redesign monitoring asset list"
```

### Task 6: Integration and Visual Verification

**Files:**
- Modify only if verification finds a scoped defect.

- [ ] **Step 1: Run the complete monitoring backend suite**

```bash
DJANGO_SETTINGS_MODULE=core.settings PYTHONPATH=backend .venv/bin/python -m pytest \
  backend/monitoring_stack/tests/test_monitoring_stack_api.py -q
```

Expected: all monitoring tests PASS.

- [ ] **Step 2: Run Django checks and migration check**

```bash
docker exec backend-api-dev python manage.py check
DJANGO_SETTINGS_MODULE=core.settings PYTHONPATH=backend .venv/bin/python \
  backend/manage.py makemigrations --check --dry-run
```

Expected: no issues and no missing migrations.

- [ ] **Step 3: Build the frontend**

```bash
cd frontend && npm run build
```

Expected: Vite exits 0.

- [ ] **Step 4: Run targeted lint without formatting unrelated code**

```bash
cd frontend && ./node_modules/.bin/eslint \
  src/admin/pages/Monitoring/Assets.vue \
  src/admin/pages/Monitoring/assets/hostListState.js \
  tests/_review/monitoring-assets-state.test.mjs
```

Expected: no new errors. Existing unrelated formatting warnings are reported separately rather than auto-fixed across the large page.

- [ ] **Step 5: Verify in a real browser**

At `1398x986` and a narrow admin-content viewport:

1. Confirm ordinary hosts render `Not applicable`, not blackbox missing.
2. Confirm probe-node hosts render blackbox state.
3. Confirm healthy rows hide stale SSH warnings.
4. Confirm pending/abnormal rows surface the correct SSH-first action.
5. Confirm selected rows switch the toolbar to bulk mode.
6. Test password and key connection success/failure, then change one signed field and confirm Save locks again.
7. Confirm no unintended host save or component install is submitted.
8. Check browser console errors and overlapping text.

- [ ] **Step 6: Run diff checks**

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; unrelated dirty files remain untouched.

- [ ] **Step 7: Commit verification fixes if any**

Inspect `git diff --name-only`, stage only files from the File Map that were
changed to fix a verified defect, and commit them with
`git commit -m "fix: harden monitoring asset list states"`. Skip this step when
verification required no code changes.
