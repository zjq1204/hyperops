# Monitoring Jobs Host History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Present monitoring deployment records by host while retaining and exposing every immutable task execution.

**Architecture:** A focused backend aggregation service converts persisted task snapshots into lightweight per-host component histories. The existing task detail endpoint remains the source for logs and parameters, while scoped retry adds an optional host constraint. The Vue page consumes the summary endpoint and switches between host history and existing task detail views.

**Tech Stack:** Django 5, Django REST Framework, Vue 3, Vue Router, vue-i18n, pytest, Node contract tests, Playwright.

---

## File Map

- Create `backend/monitoring_stack/services/job_history.py`: pure task-to-host aggregation helpers.
- Modify `backend/monitoring_stack/views.py`: expose host summaries and validate scoped retries.
- Modify `backend/monitoring_stack/tests/test_ansible_job_progress.py`: aggregation and endpoint regressions.
- Modify `frontend/src/admin/api/monitoringStack.js`: host summary and scoped retry API methods.
- Modify `frontend/src/admin/pages/Monitoring/Jobs.vue`: host-centered list, history modal, and task detail transition.
- Modify `frontend/src/admin/locales/en.json`: host history labels.
- Modify `frontend/src/admin/locales/zh-CN.json`: host history labels.
- Modify `frontend/tests/_review/admin-monitoring-stack-contract.test.mjs`: frontend behavior contract.

### Task 1: Host History Aggregation

- [ ] Write failing tests proving a batch task appears once under every included host and a retry increments only the retried host/component history.
- [ ] Run the focused pytest cases and confirm the missing aggregation module failure.
- [ ] Implement `build_host_job_summaries(jobs)` with per-host result normalization and newest-first component histories.
- [ ] Add the `host-summaries` collection action and rerun the focused tests.

### Task 2: Scoped Host Retry

- [ ] Write failing API tests for valid `host_id`, a successful host ID, and a host outside the source task.
- [ ] Run the retry tests and confirm the current endpoint retries every failed host.
- [ ] Filter the existing failed-host IDs when `host_id` is supplied and return HTTP 400 for invalid scope.
- [ ] Rerun the retry tests and existing retry-all regression.

### Task 3: Host-Centered Deployment Page

- [ ] Extend the Node contract test with assertions for `getJobHostSummaries`, host-centered columns, host history, and `{ host_id }` retry payload.
- [ ] Run the contract test and confirm it fails against the execution-centered page.
- [ ] Add the frontend API methods and rebuild `Jobs.vue` around host summaries while retaining the current task detail interface.
- [ ] Add Chinese and English labels for host search, attempt counts, component history, and task navigation.
- [ ] Run the contract test, targeted ESLint, and production build.

### Task 4: End-to-End Verification

- [ ] Run focused backend tests and Django system checks.
- [ ] Run frontend contract tests, ESLint, build, and `git diff --check`.
- [ ] Open the live page at desktop and mobile sizes, verify one row per host, inspect a four-attempt history, open a task, and return to the host.
- [ ] Verify existing task rows remain persisted in the database and no migration or deletion occurs.
