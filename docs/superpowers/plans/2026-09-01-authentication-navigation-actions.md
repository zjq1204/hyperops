# Authentication Navigation Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** Make authentication list actions state-aware and make LDAP/Feishu detail pages preserve clear source context and predictable navigation.

**Architecture:** Keep the existing authentication list and focused detail routes. Derive each row's action label from its current state, pass the selected provider identity in the existing `instance` or `tenant` query, and add shared context/back navigation within the two detail pages without changing API contracts.

**Tech Stack:** Vue 3, Vue Router, existing HyperOps admin components, Vue I18n, Node contract tests, Vite.

---

### Task 1: Lock navigation behavior in the frontend contract test

**Files:**
- Modify: `frontend/tests/_review/object-storage-admin-contract.test.mjs`

- [ ] **Step 1: Add failing assertions**

Assert the list derives state-aware action labels and that both detail pages expose a shared context/back affordance without falling back to a second provider selection.

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `node tests/_review/object-storage-admin-contract.test.mjs`
Expected: the authentication navigation subtest fails on the new assertions.

### Task 2: Implement state-aware list actions

**Files:**
- Modify: `frontend/src/admin/pages/Management/Authentication.vue`
- Modify: `frontend/src/admin/locales/zh-CN.json`
- Modify: `frontend/src/admin/locales/en.json`

- [ ] **Step 1: Add row action metadata**

Use `authenticationAction(config, provider)` to map configured/valid rows to `manage`, missing rows to `start`, pending/invalid rows to `continue` or `resolve`, and use the existing provider query in each route.

- [ ] **Step 2: Replace the generic action label**

Render the derived action label and a familiar arrow affordance while retaining keyboard-accessible `RouterLink` navigation.

- [ ] **Step 3: Run the focused contract test**

Run: `node tests/_review/object-storage-admin-contract.test.mjs`
Expected: PASS.

### Task 3: Unify detail-page context and return behavior

**Files:**
- Modify: `frontend/src/admin/pages/Management/Ldap.vue`
- Modify: `frontend/src/admin/pages/Management/FeishuAuthentication.vue`
- Modify: `frontend/src/admin/locales/zh-CN.json`
- Modify: `frontend/src/admin/locales/en.json`

- [ ] **Step 1: Add explicit context navigation**

Show a consistent back link to authentication management, a compact provider identity summary, and preserve the selected `instance`/`tenant` query when switching or saving.

- [ ] **Step 2: Add state-aware detail actions**

Use existing save/validate operations and change only their labels and feedback so users can distinguish first setup, continued setup, and maintenance.

- [ ] **Step 3: Run lint and contract tests**

Run: `npx prettier --write ... && npx eslint ... && node tests/_review/object-storage-admin-contract.test.mjs`
Expected: no lint errors and all contract tests pass.

### Task 4: Validate production behavior

**Files:**
- No additional files.

- [ ] **Step 1: Build the frontend**

Run: `npm run build` from `frontend/`.
Expected: Vite exits with code 0.

- [ ] **Step 2: Verify the running routes**

Use the local dev server to inspect `/management/authentication`, `/management/ldap?instance=1`, and `/management/authentication/feishu?tenant=1` at desktop and mobile widths.

- [ ] **Step 3: Check the final diff**

Run: `git diff --check` and confirm no unrelated files were modified by this task.
