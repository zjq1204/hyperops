# Language Switcher Polish

## Goal

Replace the visually inconsistent flag-based language menu with a compact, flat selector that matches the HyperOps console and login surface.

## Design

- Keep the shared `LanguageSwitcher` component and its existing language persistence behavior.
- Replace flag emoji with neutral `EN` and `中` language marks.
- Show the current language code in the trigger beside the existing translation icon and a small chevron.
- Render a 9.5rem-wide menu aligned to the trigger's right edge, with a subtle border, 6px radius, restrained shadow, and 36px options.
- Mark the selected language with a pale blue row treatment and a check icon; hover uses a neutral background.
- Add `aria-expanded`, `aria-haspopup`, menu semantics, visible focus states, and Escape-to-close behavior.
- Preserve the existing `default` and `dark` variants so login, workspace, and admin headers continue to share one component.

## Verification

- A contract test verifies that emoji flags are removed and accessibility hooks are present.
- ESLint, Prettier, and the production build must pass.
- Browser review covers open, selected, hover/focus structure, Escape close, and switching between Chinese and English on the login page.
