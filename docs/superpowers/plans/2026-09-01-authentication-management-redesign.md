# Authentication Management Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mixed authentication dashboard with a concise authentication-method list and dedicated provider configuration pages.

**Architecture:** `Authentication.vue` becomes a read-only aggregation view over local accounts, LDAP instances, and enterprise Feishu configurations. The existing Feishu form moves to `FeishuAuthentication.vue`; LDAP retains its current page and backend. Route metadata keeps the list available to user administrators while preserving superuser-only Feishu writes.

**Tech Stack:** Vue 3 `<script setup>`, Vue Router, Vue I18n, Tailwind CSS, existing HyperOps admin APIs and Node contract tests.

---

### Task 1: Lock the information architecture with a failing contract

**Files:**
- Modify: `frontend/tests/_review/object-storage-admin-contract.test.mjs`

- [ ] Assert the sidebar label resolves through `adminNav.authentication` and no longer contains a `/management/ldap` item.
- [ ] Assert `Authentication.vue` renders an `AdminTable`, loads LDAP instances, and links to a dedicated Feishu route.
- [ ] Assert `FeishuAuthentication.vue` owns `saveFeishu` and `validateFeishu`.
- [ ] Run `node tests/_review/object-storage-admin-contract.test.mjs` and confirm the new assertions fail before implementation.

### Task 2: Build the authentication-method list

**Files:**
- Modify: `frontend/src/admin/pages/Management/Authentication.vue`
- Modify: `frontend/src/admin/layout/AdminSidebar.vue`
- Modify: `frontend/src/admin/routes.js`
- Modify: `frontend/src/admin/locales/zh-CN.json`
- Modify: `frontend/src/admin/locales/en.json`

- [ ] Replace source cards and inline Feishu form with one `AdminTable` containing source, type, scope, status, and action columns.
- [ ] Add the built-in local account row and one row per LDAP instance.
- [ ] When object storage is enabled for a superuser, add one Feishu row per enterprise and load its validation status.
- [ ] Rename the navigation and page to “认证管理” / “Authentication”.
- [ ] Keep `/management/ldap` routable but remove it from the sidebar.

### Task 3: Move Feishu editing to a dedicated page

**Files:**
- Create: `frontend/src/admin/pages/Management/FeishuAuthentication.vue`
- Modify: `frontend/src/admin/routes.js`
- Modify: `frontend/src/admin/pages/ObjectStorage/EnterpriseAccess.vue`

- [ ] Move the existing enterprise selector and Feishu write-only credential form into the new page.
- [ ] Add `/management/authentication/feishu` with superuser and object-storage guards.
- [ ] Update authentication-list actions and object-storage review links to include the selected enterprise query parameter.
- [ ] Preserve one-enterprise-to-one-Feishu-application behavior through the existing API.

### Task 4: Verify behavior and layout

**Files:**
- Test: `frontend/tests/_review/object-storage-admin-contract.test.mjs`

- [ ] Run Prettier and targeted ESLint on all changed frontend files.
- [ ] Run the Node contract and confirm all tests pass.
- [ ] Run `npm run build` and confirm Vite exits successfully.
- [ ] Inspect list and Feishu detail pages in a real browser at desktop and 390px widths.
- [ ] Confirm no browser console errors, no duplicated provider summaries, and no horizontal overflow.
