# HyperOps Orbit H Logo Design

## Objective

Replace the current detailed cloud illustration with a compact brand system that fits an enterprise operations platform. The new mark must remain recognizable in navigation, authentication, favicon, and monochrome contexts without relying on gradients, shadows, or a decorative container.

## Brand Idea

The selected direction is **Orbit H**.

- Two opposing arcs represent continuous delivery, feedback, and coordinated operations across connected systems.
- The central `H` represents HyperOps as the control plane.
- The open arc endpoints keep the mark directional and distinguish it from a loading spinner or generic circular platform icon.
- The flat geometry reflects the quiet, functional visual language of an operations product.

## Primary Geometry

The source mark uses a `64 x 64` SVG view box.

- The upper-left navy arc starts near the top center and ends in the lower-left quadrant.
- The lower-right cyan arc starts near the bottom center and ends in the upper-right quadrant.
- A centered navy `H` uses rounded line caps and visually equal stroke weight.
- The mark must not be placed inside a permanent rounded square, circle, cloud, shield, or hexagon.

The approved source paths are:

```svg
<path d="M27.5 9.2A23.5 23.5 0 0 0 12.7 44.9" />
<path d="M36.5 54.8A23.5 23.5 0 0 0 51.3 19.1" />
<path d="M22.5 24v16M41.5 24v16M23 32h18" />
```

## Color System

| Role | Value | Usage |
| --- | --- | --- |
| HyperOps Navy | `#102A43` | Primary arc, central H, primary wordmark |
| HyperOps Cyan | `#00A6B8` | Secondary arc and `Ops` wordmark emphasis |
| Dark-surface Cyan | `#29D3DC` | Secondary arc on navy or similarly dark backgrounds |
| White | `#FFFFFF` | Primary arc, H, and monochrome mark on dark surfaces |

The two-color mark is the default on light surfaces. On dark surfaces, navy becomes white and cyan becomes dark-surface cyan. A single navy or white version is required for monochrome contexts.

Gradients, glow, drop shadows, opacity effects, textures, and color substitutions are not permitted in the logo asset.

## Wordmark

- Product name remains `HyperOps` with no spacing.
- The primary wordmark uses the application's existing sans-serif UI typeface.
- Weight is semibold (`600`).
- Letter spacing remains `0`.
- `Hyper` uses HyperOps Navy and `Ops` uses HyperOps Cyan on light backgrounds.
- The interface may render the mark and localized product label separately when the navigation already supplies text.

No custom web font dependency is added solely for the wordmark.

## Asset Set

Implementation will provide:

- `public/logo-source.svg`: canonical two-color vector source.
- `public/logo-mark.svg`: product mark for in-app use.
- `public/logo-mark-dark.svg`: dark-surface variant.
- `public/logo-mark-mono.svg`: single-color variant where needed.
- `public/logo-app.png`: generated transparent PNG compatibility asset.
- `public/favicon.svg`: scalable browser icon.
- `public/favicon-16x16.png` and `public/favicon-32x32.png`.
- `public/apple-touch-icon.png`.
- `public/favicon.ico`.

Generated raster assets must come from the SVG source. The existing favicon generation script remains the single generation path.

## Product Integration

### Workspace Sidebar

- Replace `logo-app.png` with the vector mark.
- Display at `32 x 32` pixels.
- Keep the existing localized `HyperOps` label beside it.
- Preserve a stable logo box so image loading cannot shift navigation.

### Administration Sidebar

- Display the vector mark at `40 x 40` pixels.
- Keep the localized administration title beside it.
- The mark must remain vertically centered with the title at desktop and mobile widths.

### Authentication

- Replace the independent cloud/lightning icon with Orbit H.
- Use a `32-36` pixel mark inside the existing authentication brand area.
- The surrounding authentication surface may retain its current subtle border, but that container is UI chrome and is not part of the logo.

### Browser and Installed App Icons

- Use the mark without a wordmark.
- At 16 pixels, preserve the two arcs and central H without extra padding or fine detail.
- Raster output must have a transparent background unless a platform format requires an opaque surface.

## Sizing and Clear Space

- Minimum standalone mark size: `16 x 16` pixels.
- Minimum complete mark and wordmark width: `112` pixels.
- Clear space on every side must be at least the visual height of the central H crossbar.
- The aspect ratio must never be changed.
- The mark must not be cropped or rotated.

## Accessibility

- Meaningful uses have alt text equivalent to `HyperOps`.
- Decorative duplicates use `aria-hidden="true"`.
- The logo is not the only indicator of the current navigation state.
- Dark and light variants retain at least 3:1 graphical contrast against their surface.
- No continuous logo animation is added. This avoids distraction and requires no reduced-motion exception.

## Verification

Implementation is complete only when:

1. The frontend production build passes.
2. Workspace, administration, and authentication views show the same mark.
3. Desktop and mobile screenshots show no clipping, stretching, overlap, or layout shift.
4. The 16px and 32px favicon outputs remain recognizable.
5. Light, dark, and monochrome SVG variants render correctly.
6. Browser console output contains no missing-asset errors.

## Scope

This change covers the HyperOps logo system and its existing product placements. It does not redesign navigation layout, page typography, product naming, or the broader application color system.
