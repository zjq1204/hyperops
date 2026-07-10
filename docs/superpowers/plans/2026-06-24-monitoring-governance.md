# Monitoring Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. This plan intentionally defers broad verification to the final phase, per product direction.

**Goal:** Upgrade HyperOps monitoring from an access/config console into a governance console that shows real n9e/Prometheus state, compares it with HyperOps configuration, and gives operators clear next actions.

**Architecture:** Keep `monitoring_stack` as the backend boundary. Add read-only sync snapshots and reconciliation services before adding repair actions. Keep frontend pages in the current Vue admin module, but reorganize page responsibilities around governance workflows instead of raw feature areas.

**Tech Stack:** Django REST Framework, Django models/migrations, existing Celery task style, Vue 3 admin pages, existing admin shared components, existing `monitoringStack.js` API client.

---

## Product Direction

The current implementation proves that HyperOps can store monitoring access configuration, installer assets, probe targets, hosts, and install jobs. That is necessary, but not sufficient. Operators need to know whether the real monitoring platform matches what HyperOps thinks should exist.

The next version should answer five questions:

1. What did HyperOps configure?
2. What does n9e actually know?
3. What does Prometheus actually scrape?
4. Where are they inconsistent?
5. What can the operator do next?

Do not add more explanatory cards. Add real state, clear diff categories, and direct actions.

---

## Phase Goal Ledger

This plan is executed as one active goal with staged completion. Do not treat a phase as complete because code exists; mark it complete only when its product outcome is visible in the monitoring workflow. Broad verification is intentionally deferred to Phase 6.

| Phase | Phase Target | Completion Signal | Current Status |
| --- | --- | --- | --- |
| 1 | Real-state sync foundation | HyperOps can fetch and store n9e/Prometheus snapshots, and overview can trigger sync | Implemented |
| 2 | Reconciliation foundation | Backend produces open findings from HyperOps config vs real monitoring state | Implemented for hosts, components, probes, rules, and failed jobs |
| 3 | Governance UI structure | Overview/assets/probes/rules/jobs/settings each have one clear operational purpose | Implemented |
| 4 | Repair actions | Main findings can be resolved, ignored, or converted into install/create/import/retry actions | Implemented |
| 5 | UI cleanup and copy reduction | Monitoring pages remove repeated explanations and raw i18n keys, keeping only actionable labels | Implemented |
| 6 | Final verification | Backend tests, frontend contract, build, and browser checks all pass after the full workflow lands | Verified |

### Stage Completion Rules

- A phase can be marked complete only when the user-facing workflow for that phase works end-to-end.
- Phase 1 and Phase 2 are backend-led; Phase 3 and Phase 5 are frontend-led; Phase 4 touches both.
- Do not run broad test suites after every phase. Use focused checks only when a new endpoint or contract is added; run the full test plan in Phase 6.
- Do not introduce new monitoring concepts unless they answer one of the five product questions above.
- Do not add long explanatory UI text. If the UI needs a paragraph to explain itself, improve the structure instead.

---

## File Map

### Backend

- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/models.py`
  - Add snapshot models for n9e objects, Prometheus targets, and reconciliation findings.
- Create migration: `/home/zjq/apps/hyperops/backend/monitoring_stack/migrations/0008_monitoring_governance_snapshots.py`
  - Persist the new snapshot and finding tables.
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/serializers.py`
  - Add serializers for snapshots, findings, overview health, and action payloads.
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/services/core.py`
  - Keep installer/Ansible helpers.
  - Add small orchestration functions that call dedicated sync/reconcile helpers.
- Create: `/home/zjq/apps/hyperops/backend/monitoring_stack/services/sync.py`
  - Fetch and normalize n9e business groups, datasources, targets/objects, and rules.
  - Fetch and normalize Prometheus active targets.
- Create: `/home/zjq/apps/hyperops/backend/monitoring_stack/services/reconcile.py`
  - Compare HyperOps hosts, component status, probe targets, rule templates, n9e snapshots, and Prometheus snapshots.
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/views.py`
  - Add governance overview, snapshot sync, finding list, and finding action endpoints.
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/urls.py`
  - Add `/governance/overview/`, `/governance/sync/`, `/governance/findings/`, `/governance/findings/<id>/resolve/`.
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/tasks.py`
  - Add optional background sync task wrapper.
- Modify: `/home/zjq/apps/hyperops/backend/monitoring_stack/tests/test_monitoring_stack_api.py`
  - Add final end-to-end API tests in the last phase.

### Frontend

- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/api/monitoringStack.js`
  - Add governance overview, sync, findings, and resolve methods.
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/pages/Monitoring/Overview.vue`
  - Convert to monitoring health report and diff summary.
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/pages/Monitoring/Assets.vue`
  - Show host governance state: unmanaged, not installed, runtime abnormal, healthy.
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/pages/Monitoring/Probes.vue`
  - Show probe governance state: configured, discovered, orphan, abnormal.
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/pages/Monitoring/Rules.vue`
  - Show rule template vs n9e rule import state.
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/pages/Monitoring/Jobs.vue`
  - Keep as task audit and retry surface.
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/pages/Monitoring/Settings.vue`
  - Keep only integration and installer defaults.
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/locales/zh-CN.json`
  - Add concise Chinese labels for governance states and actions.
- Modify: `/home/zjq/apps/hyperops/frontend/src/admin/locales/en.json`
  - Keep parity for locale contract tests.
- Modify: `/home/zjq/apps/hyperops/frontend/tests/_review/admin-monitoring-stack-contract.test.mjs`
  - Update contract to require governance API usage and forbid explanatory clutter.

---

## Phase 1: Real-State Snapshot Foundation

**Stage Goal:** HyperOps can fetch and persist read-only snapshots from n9e and Prometheus without changing any real monitoring platform state.

### Backend Work

- Add `MonitoringSnapshotRun`.
  - Fields: `id`, `source`, `status`, `started_at`, `finished_at`, `error`, `summary`.
  - `source` values: `n9e`, `prometheus`, `all`.
- Add `N9eBusinessGroupSnapshot`.
  - Fields: `external_id`, `name`, `raw`, `last_seen_run`, `last_seen_at`.
- Add `N9eDatasourceSnapshot`.
  - Fields: `external_id`, `name`, `type`, `raw`, `last_seen_run`, `last_seen_at`.
- Add `N9eTargetSnapshot`.
  - Fields: `identity`, `hostname`, `address`, `labels`, `raw`, `last_seen_run`, `last_seen_at`.
- Add `N9eRuleSnapshot`.
  - Fields: `identity`, `group_id`, `name`, `enabled`, `severity`, `raw`, `last_seen_run`, `last_seen_at`.
- Add `PrometheusTargetSnapshot`.
  - Fields: `identity`, `job`, `instance`, `scrape_pool`, `health`, `probe_type`, `probe_target`, `last_error`, `raw`, `last_seen_run`, `last_seen_at`.
- Add sync functions in `services/sync.py`:
  - `sync_n9e_snapshot()`
  - `sync_prometheus_snapshot()`
  - `sync_monitoring_snapshots(source='all')`
- Add endpoint:
  - `POST /api/v1/monitoring/governance/sync/`
  - Request: `{ "source": "all" | "n9e" | "prometheus" }`
  - Response: snapshot run summary.

### Frontend Work

- Add `syncGovernance(source)` to `monitoringStack.js`.
- Add one sync button on overview page:
  - Label: `同步真实状态`
  - Loading state while request is running.
  - Show last sync time from backend response.

### Completion Definition

- The database stores the latest normalized n9e and Prometheus records.
- Failed n9e or Prometheus calls create a failed run with a clear `error`.
- Overview can trigger sync and show the last sync result.
- No repair action is introduced in this phase.

---

## Phase 2: Reconciliation Engine

**Stage Goal:** HyperOps can calculate actionable differences between local config, n9e state, and Prometheus state.

### Backend Work

- Add `MonitoringGovernanceFinding`.
  - Fields: `id`, `category`, `severity`, `status`, `title`, `subject_type`, `subject_key`, `source`, `details`, `recommended_action`, `created_at`, `updated_at`, `resolved_at`.
  - `category` values:
    - `host_unmanaged`
    - `host_not_in_n9e`
    - `categraf_not_installed`
    - `categraf_runtime_abnormal`
    - `blackbox_not_installed`
    - `probe_configured_not_discovered`
    - `probe_discovered_not_configured`
    - `probe_abnormal`
    - `rule_template_not_imported`
    - `n9e_rule_untracked`
  - `severity` values: `critical`, `warning`, `info`.
  - `status` values: `open`, `resolved`, `ignored`.
- Add `services/reconcile.py` functions:
  - `reconcile_hosts()`
  - `reconcile_components()`
  - `reconcile_probes()`
  - `reconcile_rules()`
  - `rebuild_governance_findings()`
- Add endpoint:
  - `GET /api/v1/monitoring/governance/findings/`
  - Query filters: `category`, `severity`, `status`.
- Add endpoint:
  - `GET /api/v1/monitoring/governance/overview/`
  - Response includes:
    - config counts
    - real-state counts
    - finding counts by severity
    - top open findings
    - last sync metadata.

### Frontend Work

- Add API methods:
  - `getGovernanceOverview()`
  - `getGovernanceFindings(params)`
- Update `Overview.vue`:
  - Top: health summary.
  - Middle: open findings grouped by severity.
  - Bottom: direct navigation to assets/probes/rules/jobs.
- Keep copy minimal:
  - No long explanation blocks.
  - No “后续会...” text.
  - Use state labels and counts.

### Completion Definition

- Overview is driven by backend reconciliation instead of frontend-only comparisons.
- Every open finding has a category, severity, subject, and recommended action.
- Operator can see the highest-priority issues without visiting every page.

---

## Phase 3: Governance Page Reorganization

**Stage Goal:** Monitoring pages reflect real operations workflows, not implementation modules.

### Frontend Work

- `Overview.vue`
  - Rename visual purpose to `监控体检`.
  - Show:
    - `平台连接`
    - `采集覆盖`
    - `探测覆盖`
    - `规则覆盖`
    - `待处理问题`
- `Assets.vue`
  - Host table columns:
    - host
    - address
    - Categraf install state
    - Categraf runtime state
    - n9e visibility
    - action
  - Keep install wizard, but move it behind selected-host actions.
- `Probes.vue`
  - Probe table columns:
    - type
    - target
    - HyperOps config state
    - Prometheus discovery state
    - health
    - action
  - Add filter chips:
    - `全部`
    - `异常`
    - `未发现`
    - `未纳管`
- `Rules.vue`
  - Split into:
    - local rule templates
    - n9e imported state
    - findings for missing/untracked rules.
- `Jobs.vue`
  - Keep install task audit.
  - Add filter for failed jobs first.
- `Settings.vue`
  - Keep integration settings only.
  - Remove installer file table if it duplicates installers page.
- `Installers.vue`
  - Treat as advanced tool page.
  - It should not be the main user path.

### Backend Work

- Add finding filters needed by each page.
- Add endpoint query support:
  - `/governance/findings/?subject_type=host`
  - `/governance/findings/?subject_type=probe`
  - `/governance/findings/?subject_type=rule`

### Completion Definition

- Each page has one primary job.
- No page relies on explanatory copy to explain why it exists.
- Issues found on overview can be followed into the relevant detail page.

---

## Phase 4: Actionable Repair Entrypoints

**Stage Goal:** Findings become operational tasks, not passive warnings.

### Backend Work

- Add `resolve` action endpoint:
  - `POST /api/v1/monitoring/governance/findings/<id>/resolve/`
  - Request: `{ "action": "...", "payload": {} }`
- Supported actions:
  - `create_host`
  - `install_categraf`
  - `install_blackbox`
  - `create_probe_target`
  - `import_rule_template`
  - `retry_job`
  - `ignore`
- Reuse existing services:
  - host CRUD
  - Ansible install job creation
  - probe target CRUD
  - n9e rule import
  - job retry.
- Store action result in finding `details.resolution`.

### Frontend Work

- On overview finding rows:
  - Show one primary action based on `recommended_action`.
  - Secondary action: `忽略`.
- On detail pages:
  - Host findings: install Categraf / install blackbox.
  - Probe findings: create probe / edit probe / view Prometheus error.
  - Rule findings: import rule / view raw result.
  - Job findings: retry failed hosts / view logs.

### Completion Definition

- At least one repair path exists for each high-value category:
  - Categraf not installed
  - blackbox not installed
  - configured probe not discovered
  - discovered probe not configured
  - rule template not imported
  - failed install job.
- Operator can resolve or ignore findings without leaving the monitoring section.

---

## Phase 5: UI Cleanup And Copy Reduction

**Stage Goal:** Monitoring pages become simpler and more operational: less repeated explanation, fewer decorative panels, clearer labels, and no raw translation keys.

### Frontend Work

- Review all monitoring pages:
  - `/management/monitoring/overview`
  - `/management/monitoring/assets`
  - `/management/monitoring/probes`
  - `/management/monitoring/rules`
  - `/management/monitoring/jobs`
  - `/management/monitoring/settings`
  - `/management/monitoring/installers`
- Remove repeated explanatory blocks such as:
  - “这里用于...”
  - “后续可以...”
  - duplicate subtitles that restate the page title.
- Keep concise state labels:
  - `已连接`
  - `未连接`
  - `待处理`
  - `已纳管`
  - `未发现`
  - `异常`
  - `已忽略`
- Keep product/component names as-is where appropriate:
  - n9e
  - Prometheus
  - Grafana
  - Categraf
  - blackbox
- Replace mixed English metric labels in Chinese UI:
  - `Active targets` -> `正常采集目标`
  - `Down targets` -> `异常采集目标`
  - `blackbox targets` -> `blackbox 探测目标`
- Remove low-value status fields from tables when they do not drive action.
  - Example: host `已启用` should be removed or replaced with an operational state such as `Categraf 状态` or `n9e 可见性`.
- Add missing locale keys in:
  - `/home/zjq/apps/hyperops/frontend/src/admin/locales/zh-CN.json`
  - `/home/zjq/apps/hyperops/frontend/src/admin/locales/en.json`
- Update frontend contract test to catch:
  - raw `adminPages.monitoring.*` keys
  - repeated source labels
  - removed explanatory phrases.

### Completion Definition

- Monitoring pages no longer feel like documentation pages.
- No visible raw i18n keys remain.
- Chinese UI uses concise Chinese labels, with only product names kept in English.
- Tables and panels show operational state and next action, not passive metadata.

---

## Phase 6: Final Verification And Cleanup

**Stage Goal:** Run all verification after the full workflow is implemented, then fix remaining regressions and restart runtime services.

### Backend Verification

Run from `/home/zjq/apps/hyperops`:

```bash
DJANGO_SETTINGS_MODULE=core.settings.base \
PYTHONPATH=/home/zjq/apps/hyperops/backend \
/home/zjq/apps/hyperops/.venv/bin/python -m pytest \
backend/monitoring_stack/tests/test_monitoring_stack_api.py -q
```

Expected:

```text
all monitoring_stack tests pass
```

### Frontend Verification

Run from `/home/zjq/apps/hyperops/frontend`:

```bash
node tests/_review/admin-monitoring-stack-contract.test.mjs
npm run build
```

Expected:

```text
admin-monitoring-stack-contract.test.mjs: OK
vite build completes
```

### Browser Verification

Check these pages:

- `/management/monitoring/overview`
- `/management/monitoring/assets`
- `/management/monitoring/probes`
- `/management/monitoring/rules`
- `/management/monitoring/jobs`
- `/management/monitoring/settings`

Acceptance criteria:

- Overview reads as a health report, not a config explanation page.
- n9e, Prometheus, and HyperOps counts are visually separated.
- Every high-priority finding has a clear next action.
- No Chinese UI shows raw untranslated keys.
- No long “说明/后续/这里会...” paragraphs remain in monitoring pages.
- Long URLs, target names, and raw errors do not overflow tables or modals.

### Verification Record

Verified on 2026-06-24:

- Backend monitoring API tests:
  - `DJANGO_SETTINGS_MODULE=core.settings.base PYTHONPATH=/home/zjq/apps/hyperops/backend /home/zjq/apps/hyperops/.venv/bin/python -m pytest backend/monitoring_stack/tests/test_monitoring_stack_api.py -q`
  - Result: `33 passed, 5 warnings`.
- Migration drift check:
  - `DJANGO_SETTINGS_MODULE=core.settings.base PYTHONPATH=/home/zjq/apps/hyperops/backend /home/zjq/apps/hyperops/.venv/bin/python backend/manage.py makemigrations monitoring_stack --check --dry-run`
  - Result: `No changes detected in app 'monitoring_stack'`.
- Frontend contract:
  - `node tests/_review/admin-monitoring-stack-contract.test.mjs`
  - Result: `admin-monitoring-stack-contract.test.mjs: OK`.
- Frontend production build:
  - `npm run build`
  - Result: build completed; existing Vite dynamic/static import chunk warnings remain.
- Browser runtime check:
  - Playwright logged in as the dev admin user and checked `/management/monitoring/overview`, `/assets`, `/probes`, `/rules`, `/jobs`, `/settings`, and `/installers`.
  - Result: `monitoring-pages-ok`; no login redirect, no visible `adminPages.monitoring.*` raw key, no `接口未提供`, and no stale asset `已启用` status.

### Runtime Refresh

After frontend verification:

```bash
docker restart 40393a23b758_frontend-dev
```

If backend code changed and the running API needs refresh:

```bash
docker restart c82c65d07162 backend-worker-dev backend-scheduler-dev
```

---

## Phase Execution Order

1. Complete Phase 1 before Phase 2. Reconciliation without persisted snapshots will be unstable.
2. Complete Phase 2 before Phase 3. UI should be shaped around real findings, not guessed frontend state.
3. Complete Phase 3 before Phase 4. Repair actions need stable finding placement.
4. Complete Phase 4 before Phase 5. Copy cleanup should preserve the final action model.
5. Run full tests only in Phase 6, but keep code locally runnable after each phase.

---

## Non-Goals

- Do not manage Grafana dashboards in this cycle.
- Do not replace n9e as the source of truth for alert rules.
- Do not auto-delete anything from n9e or Prometheus.
- Do not make HyperOps counts pretend to be full n9e platform counts.
- Do not add more instructional panels to compensate for unclear workflows.
