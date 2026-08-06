# Monitoring Assets Single-Line Status Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make monitoring assets a compact single-line inventory with a permanently visible installation entry and independent Categraf/blackbox installation and service columns.

**Architecture:** Keep the existing backend `collection_state`, `probe_state`, and SSH verification model. Recompose `Assets.vue` with a two-row grouped table header, one status per body cell, and a host selector inside the existing component chooser. Keep filtering and fallback normalization in `hostListState.js`.

**Tech Stack:** Vue 3 `<script setup>`, Tailwind CSS, Vue I18n, Node assertion tests, Vite, Playwright CLI.

---

### Task 1: Lock the Single-Line Page Contract

**Files:**
- Modify: `frontend/tests/_review/admin-monitoring-stack-contract.test.mjs`
- Modify: `frontend/tests/_review/monitoring-assets-state.test.mjs`

- [ ] Assert the page has grouped Categraf and blackbox installation/service headers.
- [ ] Assert the next-action column, role chips, and multi-component loops are absent.
- [ ] Assert the installation chooser renders all hosts and can open with zero selected hosts.
- [ ] Run `node tests/_review/monitoring-assets-state.test.mjs && node tests/_review/admin-monitoring-stack-contract.test.mjs` and verify RED.

### Task 2: Recompose the Toolbar and Table

**Files:**
- Modify: `frontend/src/admin/pages/Monitoring/Assets.vue`
- Modify: `frontend/src/admin/locales/zh-CN.json`
- Modify: `frontend/src/admin/locales/en.json`

- [ ] Keep search, filter, refresh, install, and add-host commands visible in one toolbar state.
- [ ] Make `Install components` the primary always-active command and make `Add host` secondary.
- [ ] Add host selection to the existing component chooser and disable component choices until at least one host is selected.
- [ ] Replace the body with one-line host, connection, Categraf installation, Categraf service, blackbox installation, blackbox service, and actions cells.
- [ ] Render ordinary-host blackbox installation as `Not enabled` and service as a dash.
- [ ] Remove unused role/next-action rendering helpers while retaining backend next-action data for existing filters.
- [ ] Re-run the Task 1 tests and verify GREEN.

### Task 3: Verify Responsive Behavior

**Files:**
- Verify: `frontend/src/admin/pages/Monitoring/Assets.vue`
- Artifact: `output/playwright/monitoring-assets-single-line.png`
- Artifact: `output/playwright/monitoring-assets-single-line-narrow.png`

- [ ] Run `npm run build` from `frontend/` and require exit code 0.
- [ ] Run targeted ESLint and require 0 errors.
- [ ] Inspect the live page at 1291x986 and 900x986.
- [ ] Verify document and table container widths do not overflow.
- [ ] Capture desktop and narrow screenshots.
