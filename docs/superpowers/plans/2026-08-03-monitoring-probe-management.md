# Monitoring Probe Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split monitoring collection hosts, probe management, and deployment responsibilities into clear product surfaces.

**Architecture:** Add a shared routed tab bar under Probe Management, make the existing probe settings page route-aware for node and access views, and enrich probe discovery with managed-node runtime state. Keep the existing APIs and deployment job pipeline.

**Tech Stack:** Django REST Framework, Vue 3, Vue Router, Tailwind CSS, node contract tests, pytest.

---

### Task 1: Probe runtime contract

**Files:**
- Modify: `backend/monitoring_stack/tests/test_monitoring_stack_api.py`
- Modify: `backend/monitoring_stack/services/core.py`

- [ ] Assert registered endpoints appear in `managed_nodes` with Prometheus health.
- [ ] Run the focused pytest and verify the assertion fails.
- [ ] Map active Prometheus targets to registered node IDs while retaining unmanaged discoveries.
- [ ] Run the focused pytest and verify it passes.

### Task 2: Routed probe management

**Files:**
- Create: `frontend/src/admin/pages/Monitoring/probes/ProbeManagementTabs.vue`
- Modify: `frontend/src/admin/routes.js`
- Modify: `frontend/src/admin/layout/AdminSidebar.vue`
- Modify: `frontend/src/admin/pages/Monitoring/Probes.vue`
- Modify: `frontend/src/admin/pages/Monitoring/ProbeSettings.vue`
- Modify: `frontend/src/admin/locales/zh-CN.json`
- Modify: `frontend/src/admin/locales/en.json`

- [ ] Assert the nodes route, shared tabs, and focused page modes exist.
- [ ] Run the contract test and verify it fails.
- [ ] Add the route and shared tabs.
- [ ] Render node management only on `/nodes` and access configuration only on `/settings`.
- [ ] Show node type, host association, configured state, and Prometheus runtime state.

### Task 3: Move blackbox deployment

**Files:**
- Modify: `frontend/src/admin/pages/Monitoring/ProbeSettings.vue`
- Modify: `frontend/src/admin/pages/Monitoring/Assets.vue`

- [ ] Assert Assets contains no blackbox status or installation flow.
- [ ] Add host association to the probe node form.
- [ ] Add blackbox deployment to the probe node page using the existing job API.
- [ ] Reduce Assets to Categraf installation and runtime columns.

### Task 4: Verification

- [ ] Run focused backend tests.
- [ ] Run frontend contract tests and lint changed files.
- [ ] Run the production frontend build.
- [ ] Verify desktop and mobile layouts in a real browser.
