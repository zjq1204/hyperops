# HyperOps Orbit H Logo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every current HyperOps product mark with the approved Orbit H logo system and regenerate browser/app icons from one SVG source.

**Architecture:** Keep the canonical logo geometry in static SVG assets under `frontend/public`. Existing Vue surfaces reference the same `logo-mark.svg` asset with stable dimensions; favicon raster files are generated from `logo-source.svg` through the existing Sharp script. A source contract test prevents the sidebars and authentication page from drifting to independent symbols again.

**Tech Stack:** Vue 3, Vite, SVG, Node.js, Sharp, `node:assert`, Playwright.

---

### Task 1: Brand Asset Contract

**Files:**
- Create: `frontend/tests/_review/hyperops-logo-contract.test.mjs`

- [x] **Step 1: Write the failing source contract**

The test must assert that the four SVG variants exist, include the approved Orbit H paths, use a `64 x 64` view box, and that `AppSidebar.vue`, `AdminSidebar.vue`, and `Auth.vue` reference `/logo-mark.svg`. It must also reject `/logo-app.png` and the old cloud path in those Vue components.

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
node frontend/tests/_review/hyperops-logo-contract.test.mjs
```

Expected: failure because the new SVG assets and component references do not exist.

### Task 2: Orbit H Vector and Raster Assets

**Files:**
- Create: `frontend/public/logo-source.svg`
- Create: `frontend/public/logo-mark.svg`
- Create: `frontend/public/logo-mark-dark.svg`
- Create: `frontend/public/logo-mark-mono.svg`
- Modify by generation: `frontend/public/logo-app.png`
- Modify by generation: `frontend/public/favicon.svg`
- Modify by generation: `frontend/public/favicon-16x16.png`
- Modify by generation: `frontend/public/favicon-32x32.png`
- Modify by generation: `frontend/public/favicon.ico`
- Modify by generation: `frontend/public/apple-touch-icon.png`
- Create by generation: `frontend/public/android-chrome-192x192.png`
- Create by generation: `frontend/public/android-chrome-512x512.png`

- [x] **Step 1: Add the canonical two-color SVG**

Use the approved `64 x 64` geometry, `#102A43` navy, `#00A6B8` cyan, rounded line caps, and no background, gradient, filter, mask, or shadow.

- [x] **Step 2: Add dark and monochrome variants**

The dark variant uses white plus `#29D3DC`; the monochrome variant uses `currentColor` so it can be recolored by its consumer.

- [x] **Step 3: Generate all raster assets**

Run:

```bash
cd frontend && npm run generate-favicons
```

Expected: the script reports every PNG, ICO, `logo-app.png`, and `favicon.svg` as written.

### Task 3: Product Surface Integration

**Files:**
- Modify: `frontend/src/components/layout/AppSidebar.vue`
- Modify: `frontend/src/admin/layout/AdminSidebar.vue`
- Modify: `frontend/src/pages/Auth.vue`
- Modify: `frontend/index.html`

- [x] **Step 1: Replace workspace and administration raster references**

Use `/logo-mark.svg` at stable `32 x 32` and `40 x 40` dimensions with localized HyperOps text left intact.

- [x] **Step 2: Replace the authentication cloud symbol**

Render `/logo-mark.svg` inside `auth-brand__mark`, remove the gradient/shadow styling that made the container look like a separate logo, and preserve the existing test id and layout.

- [x] **Step 3: Prefer the scalable favicon**

Add `/favicon.svg` as the first favicon source in `frontend/index.html`, keeping PNG/ICO fallbacks.

- [x] **Step 4: Run the contract and verify GREEN**

Run:

```bash
node frontend/tests/_review/hyperops-logo-contract.test.mjs
```

Expected: `HyperOps logo contracts passed`.

### Task 4: Build and Visual Verification

**Files:**
- Verify: workspace sidebar, administration sidebar, authentication page, favicon outputs

- [x] **Step 1: Build the frontend**

Run:

```bash
cd frontend && npm run build
```

Expected: Vite exits successfully with no missing asset errors.

- [x] **Step 2: Inspect generated assets**

Verify SVG files are valid XML, raster dimensions are correct, and the 16px/32px icons contain visible non-transparent pixels.

- [x] **Step 3: Capture desktop and mobile screenshots**

Use Playwright against the active development server for `/management/users` and the authentication route at desktop and mobile widths. Confirm the logo is nonblank, not stretched, not clipped, and does not overlap the localized title.

- [x] **Step 4: Run final checks**

Run:

```bash
git diff --check
node frontend/tests/_review/hyperops-logo-contract.test.mjs
```

Expected: both commands exit successfully.
