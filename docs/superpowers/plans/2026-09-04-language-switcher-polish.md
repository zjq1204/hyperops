# Language Switcher Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a compact, flat, accessible language selector without flag emoji.

**Architecture:** Refine the existing shared Vue component without changing its preference-store integration. Keep component-level styles in `LanguageSwitcher.vue`, while the login page only provides placement context.

**Tech Stack:** Vue 3, Vue I18n, Pinia, CSS, Node contract tests, Playwright CLI.

---

### Task 1: Lock the visual and accessibility contract

**Files:**

- Create: `frontend/tests/_review/language-switcher-contract.test.mjs`
- Test: `frontend/tests/_review/language-switcher-contract.test.mjs`

- [ ] Assert that the component contains no flag emoji, exposes menu state through ARIA, renders selected-state indicators, and handles Escape.
- [ ] Run `node frontend/tests/_review/language-switcher-contract.test.mjs` and confirm it fails against the current component.

### Task 2: Implement the compact selector

**Files:**

- Modify: `frontend/src/components/ui/LanguageSwitcher.vue`
- Modify: `frontend/src/pages/Auth.vue`

- [ ] Replace utility-heavy flag rows with named component classes, `EN`/`中` marks, a check icon, and a trigger chevron.
- [ ] Add menu semantics, `aria-expanded`, keyboard Escape handling, and visible focus states.
- [ ] Reduce the login page's deep override so it no longer restyles every nested menu button.
- [ ] Run the contract test and confirm it passes.

### Task 3: Verify the real login interaction

**Files:**

- Test: `frontend/tests/_review/language-switcher-contract.test.mjs`

- [ ] Run Prettier, ESLint, `git diff --check`, and `npm run build`.
- [ ] Open `/login`, inspect the expanded menu, press Escape, switch languages, and capture a screenshot.
