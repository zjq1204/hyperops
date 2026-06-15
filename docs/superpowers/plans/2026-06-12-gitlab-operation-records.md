# GitLab Operation Records Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a unified GitLab operation record for write and collection actions in GitLab management.

**Architecture:** Store operation audits in one `GitLabOperationRecord` model with actor, action, scope snapshot, request snapshot, summary counts, and per-target details. Backend write endpoints create records after execution. Frontend adds a GitLab management operation records page and links it from GitLab admin navigation.

**Tech Stack:** Django REST Framework, PostgreSQL, Vue 3, Vite, existing admin UI components.

---

### Task 1: Backend Model And API

**Files:**
- Modify: `backend/gitlab_resource/models.py`
- Modify: `backend/gitlab_resource/serializers.py`
- Modify: `backend/gitlab_resource/views.py`
- Modify: `backend/gitlab_resource/urls.py`
- Create: `backend/gitlab_resource/migrations/0004_gitlaboperationrecord.py`
- Test: `backend/gitlab_resource/tests.py`

- [ ] Write a failing test that a GitLab write action creates a `GitLabOperationRecord`.
- [ ] Add `GitLabOperationRecord` with action, status, actor, scope, request, result, counts, timestamps.
- [ ] Add serializer and read-only viewset with `admin_gitlab` permission.
- [ ] Run the targeted test and confirm it passes.

### Task 2: Backend Write Points

**Files:**
- Modify: `backend/gitlab_resource/views.py`
- Test: `backend/gitlab_resource/tests.py`

- [ ] Add helper functions to build operation records consistently.
- [ ] Record group project collection, single/bulk project resource collection, branch bulk operations, tag bulk operations, and webhook create/update/delete.
- [ ] Keep existing API response shapes stable.
- [ ] Run `PYTHONPATH=. DJANGO_SETTINGS_MODULE=core.settings ../.venv/bin/pytest gitlab_resource/tests.py`.

### Task 3: Frontend Operation Records Page

**Files:**
- Modify: `frontend/src/api/gitlab.js`
- Modify: `frontend/src/admin/routes.js`
- Modify: `frontend/src/admin/layout/AdminSidebar.vue`
- Modify: `frontend/src/admin/locales/zh-CN.json`
- Modify: `frontend/src/admin/locales/en.json`
- Create: `frontend/src/admin/pages/GitLab/OperationRecords.vue`

- [ ] Add `listOperationRecords` API wrapper.
- [ ] Add `/management/gitlab/operation-records` route.
- [ ] Add GitLab sidebar entry.
- [ ] Build a table with action, status, actor, target summary, counts, time, and detail modal.
- [ ] Run `npm run build`.
