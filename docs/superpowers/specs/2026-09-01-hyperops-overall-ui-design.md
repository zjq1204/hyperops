# HyperOps Overall UI Design

## Status

Approved by the user for implementation on 2026-09-01.

## Goal

Create one calm, flat, low-noise visual language across the HyperOps management console and user workspace. The interface keeps the existing HyperOps logo, SVG icon system, routes, data flows, and operational capabilities while improving hierarchy, scanability, state feedback, and responsive behavior.

## Visual direction

- Use a neutral light canvas and solid surfaces.
- Use blue as the action and link color; reserve green, amber, and red for semantic state.
- Prefer whitespace, type scale, and alignment over shadows or decorative borders.
- Keep surface corners restrained: approximately 0–6px for flat sections and 6–10px where a control needs a touch target cue.
- Remove default backdrop blur, gradients, and large elevation shadows from the primary page shell.
- Preserve existing logo assets and SVG icons, but standardize icon scale, stroke weight, muted color, active color, hover, and focus behavior.

## Information hierarchy

Each page should have one clear title and primary action. The first viewport should answer the page's main operational question. Show only the most useful summary values; move activity streams, explanations, and secondary metrics behind a clear route or disclosure when they compete with the primary content.

Use a consistent structure:

1. Page title and short purpose statement.
2. Optional primary action aligned with the title.
3. One summary or filter row when it helps the task.
4. Main table/list/form.
5. Secondary details, history, or help after the main task.

## State language

Loading, empty, not configured, forbidden, and service failure are distinct states. “Not configured” uses a neutral informational treatment and names the next step, such as contacting an administrator. Actual failures retain an actionable error treatment with retry or request context. A status must have text or an accessible label in addition to color.

## Shared implementation scope

- Base tokens in `frontend/src/assets/css/base.css`.
- Shared controls and page primitives in `frontend/src/assets/css/components-core.css`.
- Workspace shell in `frontend/src/assets/css/workspace.css`.
- Management shell in `frontend/src/assets/css/admin-core.css` and the admin layout components.
- Representative pages: management users, management object storage overview, Jenkins workspace, and user object storage overview.

Do not rewrite business logic, API contracts, permissions, or page-specific data loading as part of this visual pass.

## Interaction and responsive rules

- Keep interactive controls keyboard reachable with a visible focus ring.
- Keep icon-only controls labelled with `aria-label` or an equivalent accessible name.
- Use 150–220ms transitions for feedback and disable non-essential motion under `prefers-reduced-motion`.
- Keep touch targets at least 44px where controls are used on mobile.
- At narrow widths, allow actions to wrap and let tables switch to a deliberate compact layout rather than causing page-wide horizontal overflow.

## Validation

Run frontend lint and production build. Review at 375px, 1024px, and 1440px widths. Check that management and workspace shells share the same visual tokens and that state components retain distinct semantics.
