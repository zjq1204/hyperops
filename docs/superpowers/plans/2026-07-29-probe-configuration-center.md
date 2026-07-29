# Probe Configuration Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current mixed probe page with a target-first configuration center and a separate foundational settings route while keeping Prometheus HTTP SD behavior explicit and safe.

**Architecture:** Keep the existing monitoring APIs and split the current large Vue page by responsibility. A pure JavaScript state helper derives target lifecycle state from target, probe-node, and Prometheus summary data; the target page renders and filters that state, while a separate route owns probe-node and Prometheus access configuration. The backend HTTP SD renderer excludes targets that have no enabled probe node.

**Tech Stack:** Django 5, Django REST Framework, Vue 3 `<script setup>`, Vue Router, Vue I18n, Tailwind CSS, Node contract tests, pytest.

---

## File Structure

- Modify `backend/monitoring_stack/services/core.py`: enforce complete probe-node bindings in HTTP SD output.
- Modify `backend/monitoring_stack/tests/test_monitoring_stack_api.py`: cover incomplete and disabled-node HTTP SD behavior.
- Create `frontend/src/admin/pages/Monitoring/probes/targetState.js`: target validation, label normalization, and lifecycle-state derivation.
- Create `frontend/tests/_review/probe-target-state.test.mjs`: executable unit coverage for pure state helpers.
- Create `frontend/src/admin/pages/Monitoring/probes/ProbeTargetForm.vue`: create/edit modal with type-aware validation.
- Create `frontend/src/admin/pages/Monitoring/probes/ProbeTargetDrawer.vue`: read-only target details drawer.
- Rewrite `frontend/src/admin/pages/Monitoring/Probes.vue`: target-first list, filters, row menu, CRUD orchestration.
- Create `frontend/src/admin/pages/Monitoring/ProbeSettings.vue`: probe-node and Prometheus access configuration.
- Modify `frontend/src/admin/routes.js`: add `/management/monitoring/probes/settings`.
- Modify `frontend/src/locales/zh-CN.json` and `frontend/src/locales/en.json`: add all new user-facing strings.
- Modify `frontend/tests/_review/admin-monitoring-stack-contract.test.mjs`: assert the new route and responsibility boundaries.

### Task 1: Make HTTP SD reject incomplete target bindings

**Files:**
- Modify: `backend/monitoring_stack/tests/test_monitoring_stack_api.py`
- Modify: `backend/monitoring_stack/services/core.py`

- [ ] **Step 1: Write the failing backend test**

Add a test that creates three enabled targets: one with an enabled node, one without a node, and one with a disabled node. Assert that only the complete target appears:

```python
@pytest.mark.django_db
def test_http_sd_excludes_targets_without_enabled_probe_nodes(client):
    enabled_node = BlackboxProbeNode.objects.create(
        name="blackbox-enabled", address="10.0.0.10", enabled=True
    )
    disabled_node = BlackboxProbeNode.objects.create(
        name="blackbox-disabled", address="10.0.0.11", enabled=False
    )
    ProbeTarget.objects.create(
        type="http", target="https://ready.example.com", probe_node=enabled_node
    )
    ProbeTarget.objects.create(type="http", target="https://missing.example.com")
    ProbeTarget.objects.create(
        type="http", target="https://disabled.example.com", probe_node=disabled_node
    )
    config = MonitoringIntegrationConfig.current()
    config.prometheus_http_sd_token = "database-token"
    config.save(update_fields=["prometheus_http_sd_token", "updated_at"])

    response = APIClient().get(
        "/api/v1/monitoring/prometheus/http-sd/blackbox/http/",
        HTTP_AUTHORIZATION="Bearer database-token",
    )

    assert [group["targets"] for group in _payload(response)] == [
        ["https://ready.example.com"]
    ]
```

- [ ] **Step 2: Run the test and verify failure**

Run:

```bash
DJANGO_SETTINGS_MODULE=monitoring_stack.tests_settings \
PYTHONPATH=/home/zjq/apps/hyperops/backend \
/home/zjq/apps/hyperops/.venv/bin/pytest \
backend/monitoring_stack/tests/test_monitoring_stack_api.py \
-k http_sd_excludes_targets_without_enabled_probe_nodes -q
```

Expected: failure because incomplete targets are currently returned.

- [ ] **Step 3: Implement the smallest backend change**

Filter the queryset and always emit node labels:

```python
ProbeTarget.objects.filter(
    type=target_type,
    enabled=True,
    probe_node__isnull=False,
    probe_node__enabled=True,
).select_related("probe_node")
```

- [ ] **Step 4: Run focused backend tests**

Run the command from Step 2. Expected: pass.

### Task 2: Add a tested target lifecycle model

**Files:**
- Create: `frontend/src/admin/pages/Monitoring/probes/targetState.js`
- Create: `frontend/tests/_review/probe-target-state.test.mjs`

- [ ] **Step 1: Write failing pure-JavaScript tests**

Cover these exact states:

```javascript
assert.equal(targetEffectState(disabledTarget, nodes, connectedSummary).key, 'disabled')
assert.equal(targetEffectState(noNodeTarget, nodes, connectedSummary).key, 'incomplete')
assert.equal(targetEffectState(enabledTarget, nodes, disconnectedSummary).key, 'unknown')
assert.equal(targetEffectState(enabledTarget, nodes, emptySummary).key, 'pending')
assert.equal(targetEffectState(enabledTarget, nodes, upSummary).key, 'effective')
assert.equal(targetEffectState(enabledTarget, nodes, downSummary).key, 'abnormal')
assert.equal(validateProbeTarget('http', 'example.com'), 'invalid_http')
assert.equal(validateProbeTarget('tcp', 'db.example.com:3306'), '')
assert.equal(validateProbeTarget('icmp', '8.8.8.8'), '')
```

- [ ] **Step 2: Run the test and verify failure**

Run:

```bash
cd frontend
node tests/_review/probe-target-state.test.mjs
```

Expected: module-not-found failure.

- [ ] **Step 3: Implement pure helpers**

Export:

```javascript
export function targetEffectState(target, nodes, prometheusSummary) {}
export function validateProbeTarget(type, target) {}
export function probeLabelPairs(labels) {}
export function matchesProbeFilters(target, state, filters) {}
```

State priority must be `disabled`, `incomplete`, `unknown`, `pending`, `effective` or `abnormal`.

- [ ] **Step 4: Run the helper tests**

Run the command from Step 2. Expected: `OK`.

### Task 3: Define frontend route and contract boundaries

**Files:**
- Modify: `frontend/tests/_review/admin-monitoring-stack-contract.test.mjs`
- Modify: `frontend/src/admin/routes.js`

- [ ] **Step 1: Add failing contract assertions**

Assert that `ProbeSettings.vue` exists, the settings route is registered, and Prometheus config calls are owned by the settings page instead of `Probes.vue`:

```javascript
assert.match(routesSource, /path:\s*'\/management\/monitoring\/probes\/settings'/)
assert.doesNotMatch(probesSource, /getPrometheusHttpSdConfig\(\)/)
assert.match(probeSettingsSource, /getPrometheusHttpSdConfig\(\)/)
assert.match(probeSettingsSource, /getProbeNodes\(\)/)
```

- [ ] **Step 2: Run the contract and verify failure**

Run:

```bash
cd frontend
node tests/_review/admin-monitoring-stack-contract.test.mjs
```

Expected: failure because the settings page and route do not exist.

- [ ] **Step 3: Register the route**

Add `AdminMonitoringProbeSettings` with the same auth and module metadata as `AdminMonitoringProbes`.

### Task 4: Build the target form and details drawer

**Files:**
- Create: `frontend/src/admin/pages/Monitoring/probes/ProbeTargetForm.vue`
- Create: `frontend/src/admin/pages/Monitoring/probes/ProbeTargetDrawer.vue`

- [ ] **Step 1: Implement `ProbeTargetForm.vue`**

Required component contract:

```javascript
defineProps({ show: Boolean, target: Object, nodes: Array, saving: Boolean })
defineEmits(['close', 'submit', 'open-settings'])
```

Use a three-option segmented type control, target input with `validateProbeTarget`, enabled-node select, enabled toggle, and collapsed optional labels. Empty optional labels must not be emitted.

- [ ] **Step 2: Implement `ProbeTargetDrawer.vue`**

Required component contract:

```javascript
defineProps({ show: Boolean, target: Object, effectState: Object })
defineEmits(['close', 'edit', 'toggle-enabled'])
```

Render one lifecycle status, base configuration, labels, recent Prometheus error, and final blackbox address. Use a teleported right-side sheet with Escape and backdrop dismissal.

- [ ] **Step 3: Build frontend to catch template errors**

Run `npm run build` in `frontend/`. Expected: success.

### Task 5: Rewrite the target-first configuration page

**Files:**
- Rewrite: `frontend/src/admin/pages/Monitoring/Probes.vue`

- [ ] **Step 1: Replace the mixed three-tab layout**

Render only:

- title with `Basic configuration` and `Add probe` actions;
- keyword, type, config-state, and effect-state filters;
- responsive target table/list;
- one effect state per row;
- a row overflow menu for edit, enable/disable, and delete;
- empty, loading, partial-error, and retry states.

- [ ] **Step 2: Preserve filter state in URL query**

Initialize filters from `route.query`, then call `router.replace({ query })` when filters change. Do not request on every keystroke; filtering is local over loaded data.

- [ ] **Step 3: Wire CRUD and feedback**

Use `ProbeTargetForm`, `ProbeTargetDrawer`, `ConfirmDialog`, and `useToast`. Keep target CRUD in `Probes.vue`; remove node CRUD, governance actions, Token, YAML, and Prometheus settings UI.

- [ ] **Step 4: Run helper and contract tests**

Run:

```bash
cd frontend
node tests/_review/probe-target-state.test.mjs
node tests/_review/admin-monitoring-stack-contract.test.mjs
```

Expected: both print `OK`.

### Task 6: Build the foundational settings page

**Files:**
- Create: `frontend/src/admin/pages/Monitoring/ProbeSettings.vue`

- [ ] **Step 1: Implement probe-node management**

Load targets and nodes together, derive each node's target count, and keep create/edit/delete behavior. Warn before deleting a node that is referenced by targets.

- [ ] **Step 2: Implement Prometheus access management**

Show only connection status and Token status initially. Put Token rotation and generated-token copy in one modal, and YAML preview/copy in a separate modal. Token rotation must use an explicit confirmation before calling the API.

- [ ] **Step 3: Preserve navigation behavior**

The back action routes to `/management/monitoring/probes`; browser refresh remains on `/management/monitoring/probes/settings`.

### Task 7: Complete localization and UI contracts

**Files:**
- Modify: `frontend/src/locales/zh-CN.json`
- Modify: `frontend/src/locales/en.json`
- Modify: `frontend/tests/_review/admin-monitoring-stack-contract.test.mjs`

- [ ] **Step 1: Add complete locale keys**

Add matching Chinese and English keys for filters, lifecycle states, form hints, validation, drawer content, settings sections, confirmation messages, and toast feedback. Components must not hard-code Chinese or English user-facing copy.

- [ ] **Step 2: Update contract assertions for responsibility boundaries**

Remove assertions that require governance and Prometheus setup in `Probes.vue`; assert those responsibilities are absent or moved to `ProbeSettings.vue`.

- [ ] **Step 3: Run contract and production build**

Run:

```bash
cd frontend
node tests/_review/probe-target-state.test.mjs
node tests/_review/admin-monitoring-stack-contract.test.mjs
npm run build
```

Expected: tests print `OK`, build exits 0.

### Task 8: Full verification and browser review

**Files:**
- Verify all files changed above.

- [ ] **Step 1: Run the complete monitoring backend test file**

```bash
DJANGO_SETTINGS_MODULE=monitoring_stack.tests_settings \
PYTHONPATH=/home/zjq/apps/hyperops/backend \
/home/zjq/apps/hyperops/.venv/bin/pytest \
backend/monitoring_stack/tests/test_monitoring_stack_api.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend contract tests and build**

Run the three commands from Task 7 Step 3. Expected: all pass.

- [ ] **Step 3: Review live page at desktop and mobile sizes**

Use Playwright at `1398x986` and `390x844`. Verify the list, add modal, details drawer, settings route, Token modal, YAML modal, and that `document.documentElement.scrollWidth === document.documentElement.clientWidth` on mobile.

- [ ] **Step 4: Review the final diff**

Confirm no unrelated files were reverted, no raw Chinese/English was introduced in Vue components, and no hidden incomplete target can leak into HTTP SD output.
