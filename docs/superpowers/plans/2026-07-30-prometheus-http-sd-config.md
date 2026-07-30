# Prometheus HTTP SD Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate copy-ready Prometheus HTTP SD YAML using the actual HyperOps request origin and active database Token.

**Architecture:** Preserve the complete browser Host header at the Nginx API boundary, then let Django derive the public origin from forwarded request metadata. Keep Token ownership in `MonitoringIntegrationConfig` and render that active Token directly into the protected YAML response.

**Tech Stack:** Nginx, Django REST Framework, pytest, Vue 3, vue-i18n, Playwright CLI.

---

### Task 1: Lock the HTTP SD response contract

**Files:**
- Modify: `backend/monitoring_stack/tests/test_monitoring_stack_api.py`

- [ ] Update `test_prometheus_http_sd_config_preview_returns_copyable_yaml` to send `HTTP_X_FORWARDED_HOST="192.168.7.168:18080"` and assert every generated URL includes that origin.
- [ ] Assert the YAML contains `credentials: database-token` and does not contain `credentials_file`.
- [ ] Run the focused test and confirm it fails against the current implementation.

### Task 2: Preserve the incoming public origin

**Files:**
- Modify: `docker/nginx/default.dev.conf`
- Modify: `docker/nginx/default.conf`

- [ ] Change the `/api/` proxy Host and `X-Forwarded-Host` values from `$host` to `$http_host`, preserving non-default ports.
- [ ] Run `nginx -t` in the development Nginx container.
- [ ] Reload Nginx and confirm Django receives `192.168.7.168:18080` as the forwarded Host.

### Task 3: Embed the active Token in generated YAML

**Files:**
- Modify: `backend/monitoring_stack/services/core.py`

- [ ] Read the active Token once in `prometheus_http_sd_config`.
- [ ] Replace all three `credentials_file` entries with `credentials` using the active Token.
- [ ] Keep the masked Token state fields unchanged for non-YAML UI surfaces.
- [ ] Run the focused backend test and confirm it passes.

### Task 4: Explain Token rotation consequences

**Files:**
- Modify: `frontend/src/admin/locales/zh-CN.json`
- Modify: `frontend/src/admin/locales/en.json`
- Test: `frontend/tests/_review/admin-monitoring-stack-contract.test.mjs`

- [ ] Add a frontend contract assertion that the Token dialog includes the rotation/reload explanation key.
- [ ] Update the localized Token hint to state that Prometheus configuration must be copied and reloaded after rotation.
- [ ] Run the frontend contract test and ESLint for `ProbeSettings.vue`.

### Task 5: End-to-end verification

**Files:**
- Verify: `frontend/src/admin/pages/Monitoring/ProbeSettings.vue`

- [ ] Run monitoring backend tests and frontend production build.
- [ ] Open the live YAML preview and confirm URLs contain `:18080`.
- [ ] Confirm the YAML contains `credentials` and no `credentials_file`.
- [ ] Confirm browser console errors are zero and the HTTP SD endpoint accepts the embedded Token.
