# Monitoring Host SSH Connection Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gate monitoring host Save behind a successful SSH test for the exact current form values.

**Architecture:** A DRF collection action validates transient connection data and delegates to a focused Paramiko service without persisting it. The Vue form tracks a deterministic connection signature and enables Save only when the latest successful test matches that signature.

**Tech Stack:** Django REST Framework, Paramiko, pytest, Vue 3 Composition API, vue-i18n.

---

### Task 1: Define the backend connection-test contract

**Files:**
- Modify: `backend/monitoring_stack/tests/test_monitoring_stack_api.py`
- Modify: `backend/monitoring_stack/serializers.py`

- [ ] Add failing API tests for a password test, retained existing password,
  and selected saved key.
- [ ] Assert the host database is unchanged after each test.
- [ ] Add a serializer that validates address, port, auth type, host ID, password,
  and saved key ID without using `MonitoringHostSerializer.save()`.

### Task 2: Implement SSH testing

**Files:**
- Modify: `backend/monitoring_stack/services/core.py`
- Modify: `backend/monitoring_stack/views.py`

- [ ] Add a Paramiko service that connects with an eight-second timeout and
  executes `printf hyperops-ssh-ok`.
- [ ] Map authentication, timeout, socket, key, and command failures to safe
  result codes and messages.
- [ ] Add `MonitoringHostViewSet.test_connection` and return success metadata
  without persisting form data.
- [ ] Run focused backend tests until green.

### Task 3: Add frontend API and state contract

**Files:**
- Modify: `frontend/src/admin/api/monitoringStack.js`
- Modify: `frontend/tests/_review/admin-monitoring-stack-contract.test.mjs`

- [ ] Add `testHostConnection(body)` to the monitoring API client.
- [ ] Add failing contract assertions for test invocation, signature tracking,
  invalidation, and Save gating.

### Task 4: Build the host-form interaction

**Files:**
- Modify: `frontend/src/admin/pages/Monitoring/Assets.vue`
- Modify: `frontend/src/admin/locales/zh-CN.json`
- Modify: `frontend/src/admin/locales/en.json`

- [ ] Add idle, testing, success, and failure state variables.
- [ ] Compute the current connection signature and invalidate stale success
  through a watcher.
- [ ] Add Test connection below authentication controls with concise feedback.
- [ ] Disable Save until the current signature is verified and guard `saveHost`.
- [ ] Add localized labels and safe failure messages.

### Task 5: Verify the workflow

**Files:**
- Verify: `frontend/src/admin/pages/Monitoring/Assets.vue`

- [ ] Run monitoring backend tests, frontend contract tests, ESLint, and build.
- [ ] Use the live form to confirm a failed test keeps Save disabled.
- [ ] Use an existing reachable host to confirm success enables Save, then close
  without persisting changes.
- [ ] Confirm browser console errors are zero.
