# Editable Capability Deployment Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the last successful Categraf deployment settings during capability updates and allow operators to change them safely.

**Architecture:** Keep the successful job as the inheritance baseline. The frontend submits the displayed values; the backend uses non-blank submitted deployment settings and falls back to the baseline only when a value is omitted. Preview and execution continue through the existing transactional installer and rollback path.

**Tech Stack:** Django REST Framework, Django TestCase, Vue 3, Vue I18n, Vite.

---

### Task 1: Backend override semantics

**Files:**
- Modify: `backend/monitoring_stack/tests/test_capability_update_safety.py`
- Modify: `backend/monitoring_stack/views.py`

- [ ] Add a failing test that submits new `base_url`, `n9e_url`, `install_dir`, and `image` values with a successful `base_job_id` and expects those values in the resolved payload.
- [ ] Run `docker exec backend-api-dev python manage.py test monitoring_stack.tests.test_capability_update_safety --verbosity 2` and confirm the new assertion fails because baseline values are returned.
- [ ] Resolve each deployment field as `submitted non-blank value -> baseline value -> component default`.
- [ ] Re-run the safety tests and confirm all tests pass.

### Task 2: Editable deployment settings UI

**Files:**
- Modify: `frontend/src/admin/pages/Monitoring/Assets.vue`
- Modify: `frontend/src/admin/locales/zh-CN.json`
- Modify: `frontend/src/admin/locales/en.json`

- [ ] Capture the inherited deployment settings when adjustment mode opens.
- [ ] Render the existing four deployment fields in both install and adjustment modes.
- [ ] In adjustment mode, label unchanged values as inherited, changed values as part of this update, and provide a reset action.
- [ ] Add a preview summary showing only changed deployment settings, or an inherited-all message when none changed.

### Task 3: Verification

**Files:**
- Test: `backend/monitoring_stack/tests/test_capability_update_safety.py`
- Test: `frontend/tests/_review/admin-monitoring-stack-contract.test.mjs`

- [ ] Run Django safety tests, system checks, migration checks, ESLint, frontend contract tests, and `npm run build`.
- [ ] Use Playwright to open host 13 capability adjustment, modify one deployment field, preview Ansible, and confirm the preview contains the changed value without dispatching a job.
- [ ] Verify the 390px viewport has no horizontal overflow.
