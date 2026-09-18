# Object Storage Overview Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove duplicate in-page object-storage navigation and suppress the redundant Bucket load-error alert across the employee object-storage pages.

**Architecture:** Keep the sidebar as the sole navigation surface. Employee pages will continue to load data and expose refresh behavior, while failed Bucket loading falls through to each page's existing empty state instead of rendering a separate alert. Other operation-specific alerts remain available.

**Tech Stack:** Vue 3, Vue Router, node:test contract tests, Vite.

---

### Task 1: Lock the overview presentation contract

**Files:**
- Modify: `frontend/tests/_review/object-storage-employee-contract.test.mjs`

- [ ] **Step 1: Write the failing test**

Add a test that reads all four employee object-storage pages and asserts they do not render or import `ObjectStorageNav` or reference the Bucket load-error message key; for `Overview.vue`, also assert it does not render or import `InlineAlert`, since that page has no other alert use.

- [ ] **Step 2: Run the focused test**

Run: `node --test tests/_review/object-storage-employee-contract.test.mjs`

Expected: FAIL because the current overview still contains both the duplicate navigation and the Bucket load-error alert.

### Task 2: Remove duplicate overview UI

**Files:**
- Modify: `frontend/src/pages/ObjectStorage/Overview.vue`
- Modify: `frontend/src/pages/ObjectStorage/Buckets.vue`
- Modify: `frontend/src/pages/ObjectStorage/Credentials.vue`
- Modify: `frontend/src/pages/ObjectStorage/Applications.vue`

- [ ] **Step 1: Remove page-level `<ObjectStorageNav />` blocks and the Bucket load-error `InlineAlert` block**

Remove the duplicate navigation from all four pages. Remove the Bucket load-error alert from `Buckets.vue`; leave each page's other informational, submission, and detail alerts intact. Keep each loader and refresh action so failed requests still reset data and can be retried.

- [ ] **Step 2: Remove unused imports and state**

Remove `ObjectStorageNav` imports from all four pages, the `InlineAlert` import from `Overview.vue`, and the now-unused `loadError` state and assignments from `Overview.vue` and `Buckets.vue`; retain all other page dependencies and error state.

- [ ] **Step 3: Run the focused test**

Run: `node --test tests/_review/object-storage-employee-contract.test.mjs`

Expected: PASS with zero failures.

### Task 3: Verify the frontend

**Files:**
- No additional files.

- [ ] **Step 1: Build the frontend**

Run: `npm run build`

Expected: Vite exits with status 0 and produces the production bundle.

- [ ] **Step 2: Review the diff**

Run: `git diff -- frontend/src/pages/ObjectStorage/Overview.vue tests/_review/object-storage-employee-contract.test.mjs`

Expected: Only the requested overview UI and its focused contract test are changed.
