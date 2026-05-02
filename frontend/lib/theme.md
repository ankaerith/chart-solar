# Solstice·Ink — Theme Reference

Locked launch theme. Light only at v1 (per `solar-decisions/project/README.md`). Defined as CSS custom properties on `:root[data-theme="solstice-ink"]` in `app/globals.css`, mapped to Tailwind utilities via `@theme inline`.

## Surface

| Token         | Value     | Tailwind        | Use                                  |
|---------------|-----------|-----------------|--------------------------------------|
| `--bg`        | `#ecebe3` | `bg-bg`         | Page canvas (cool oyster paper)      |
| `--bg-2`      | `#dfdecf` | `bg-bg-2`       | Recessed surface                     |
| `--panel`     | `#f7f5ec` | `bg-panel`      | Cards, primary panels                |
| `--panel-2`   | `#e8e6d6` | `bg-panel-2`    | Nested or secondary panels           |

## Ink

| Token          | Value     | Tailwind          | Use                              |
|----------------|-----------|-------------------|----------------------------------|
| `--ink`        | `#0f1421` | `text-ink`        | Primary type                     |
| `--ink-2`      | `#1f2a3f` | `text-ink-2`      | Secondary type                   |
| `--ink-dim`    | `#566173` | `text-ink-dim`    | Tertiary, captions               |
| `--ink-faint`  | `#8a92a0` | `text-ink-faint`  | Disabled, hints                  |

## Rules

| Token             | Value     | Tailwind                | Use                       |
|-------------------|-----------|-------------------------|---------------------------|
| `--rule`          | `#c4bfac` | `border-rule`           | Default hairlines         |
| `--rule-strong`   | `#0f1421` | `border-rule-strong`    | Emphasized borders        |

## Accents

| Token            | Value     | Tailwind             | Use                              |
|------------------|-----------|----------------------|----------------------------------|
| `--accent`       | `#1d3461` | `bg-accent`          | Prussian-blue ink, primary CTAs  |
| `--accent-ink`   | `#f7f5ec` | `text-accent-ink`    | Type on accent surfaces          |
| `--accent-2`     | `#7a2826` | `text-accent-2`      | Oxblood — eyebrows, alerts       |

## Status

| Token       | Value     | Tailwind      | Use                  |
|-------------|-----------|---------------|----------------------|
| `--good`    | `#2e6b48` | `bg-good`     | Positive deltas      |
| `--warn`    | `#a86512` | `bg-warn`     | Caution               |
| `--bad`     | `#7a2826` | `bg-bad`      | Negative deltas      |

## Type

Loaded via `next/font` in `app/layout.tsx`; each font exposes a CSS variable that the theme stack falls back through.

| Stack              | Token / Tailwind     | Source                                |
|--------------------|----------------------|---------------------------------------|
| Display (serif)    | `font-display`       | Newsreader → Source Serif 4 → Georgia |
| Body (sans)        | `font-sans` (default)| Inter → system-ui                     |
| Mono (numerics)    | `font-mono`          | IBM Plex Mono → ui-monospace          |

Display weight is 600, tracking `-0.022em` (`--display-weight`, `--display-tracking`). Headings inherit these in `globals.css`; numeric figures (`$/W`, NPV, IRR, kWh) use `font-mono`.

## Radius

| Token          | Value | Tailwind     |
|----------------|-------|--------------|
| `--radius`     | `6px` | `rounded-md` |
| `--radius-lg`  | `10px`| `rounded-lg` |

## Adding a token

1. Add the CSS custom property under `:root[data-theme="solstice-ink"]` in `app/globals.css`.
2. Map it inside `@theme inline { … }` so Tailwind utilities pick it up (`--color-*`, `--font-*`, `--radius-*`).
3. Document it here.

## Contrast (WCAG 2.1 AA)

Verified against `--bg` `#ecebe3` (the page canvas). Run the helper at
`scripts/check-contrast.js` (or recompute via the WCAG luminance formula)
to refresh after a token change.

| Token        | Hex      | Ratio    | Verdict        |
|--------------|----------|----------|----------------|
| `ink`        | #0f1421  | 15.37:1  | AA             |
| `ink-2`      | #1f2a3f  | 12.02:1  | AA             |
| `ink-dim`    | #566173  | 5.24:1   | AA             |
| `ink-faint`  | #8a92a0  | 2.62:1   | **disabled / decorative only** |
| `accent`     | #1d3461  | 10.23:1  | AA (links)     |
| `accent-2`   | #7a2826  | 8.13:1   | AA             |
| `good`       | #2e6b48  | 5.30:1   | AA             |
| `warn`       | #a86512  | 3.87:1   | AA-large only  |
| `bad`        | #7a2826  | 8.13:1   | AA             |

Constraints:

- **`ink-faint`** is **not** for body copy. Use it only for disabled
  controls, decorative captions, or text that's already paired with a
  full-contrast label — disabled text is exempt under WCAG 1.4.3.
- **`warn`** passes AA only for "large text" (≥18 pt regular or ≥14 pt
  bold). For body-size warning copy, use `ink` text and use `warn` for
  the icon / leading rule only.

Axe-core sweeps every critical path in CI (`bun run test:a11y`); add
new routes to `tests/a11y.spec.ts` as they ship to keep the gate honest.

## Why a single locked theme

`solar-decisions/project/themes.jsx` ships Solstice·Ink as the locked editorial direction — cool oyster paper, prussian-blue ink, oxblood secondary, with Newsreader/Inter/IBM Plex Mono. We honour that at v1: no dark mode, no theme picker, no per-tenant skinning. Tokenizing now keeps a future theme switch a single `data-theme` attribute swap.

## shadcn mapping

`components.json` is configured (`style: new-york`, `tailwind.cssVariables: true`, alias `@/components/ui`). The shadcn CSS-variable contract is aliased to Solstice·Ink tokens in `app/globals.css` so any primitive added via `npx shadcn add …` inherits the editorial look without per-component CSS:

| shadcn var                | Solstice·Ink source | Notes                                              |
|---------------------------|---------------------|----------------------------------------------------|
| `--background` / `--foreground` | `--bg` / `--ink`           | Page canvas + primary type                |
| `--card` / `--card-foreground` | `--panel` / `--ink`         | Cards (= our Panel)                       |
| `--popover` / `--popover-foreground` | `--panel` / `--ink`   | Popovers, dropdowns                       |
| `--primary` / `--primary-foreground` | `--ink` / `--bg`      | Matches our Btn primary (ink-on-bg)        |
| `--secondary` / `--secondary-foreground` | `--panel-2` / `--ink-2` | Recessed surfaces                      |
| `--muted` / `--muted-foreground` | `--panel-2` / `--ink-dim`   | Muted backgrounds + tertiary type         |
| `--accent-foreground`     | `--accent-ink`       | Type on accent surfaces                            |
| `--destructive` / `--destructive-foreground` | `--bad` / `--accent-ink` | Destructive actions                |
| `--border`                | `--rule`             | Default hairlines                                  |
| `--input`                 | `--rule-strong`      | Input borders (matches design `border: 1px solid var(--rule-strong)`) |
| `--ring`                  | `--accent`           | Focus ring (prussian blue)                         |

### Conflict: `--accent`

Our brand `--accent` (`#1d3461` prussian blue) collides with the shadcn convention where `--accent` is the *hover/highlight* background — too loud as a hover. We keep our brand semantics for `--accent` (the SD design uses prussian blue as a deliberate, sparing accent, not a hover state). When a shadcn primitive that hard-codes `bg-accent` for hover is adopted, override the hover to `bg-panel-2` at the call site.

### What we install vs. build bespoke

The Solstice·Ink design (`design/solar-decisions/project/ui.jsx`) ships **bespoke primitives** — `Btn`, `Eyebrow`, `MonoLabel`, `Panel`, `Field`, `TextInput`, `SegBtn`, `Wordmark`, `Modal`, `Footnote`, `DemoWatermark` — all with editorial-specific styling (mono labels, ink/oyster surfaces, prussian-blue accents). These are ported by hand under [`bd show chart-solar-bdi`](#) into `frontend/components/ui/`, **not** scaffolded from shadcn.

shadcn primitives we may pull in later when needed (no upfront install — keeps the dependency surface honest):

- **`dialog`** — could underly the Modal primitive's a11y plumbing (focus trap, scroll lock, Esc handler) once we adopt it as intercepting routes (`bd show chart-solar-2hf.1`). For now the bespoke Modal in `bdi` covers it.
- **`dropdown-menu`** — for the nav profile menu (`bd show chart-solar-dzl`).
- **`select`** / **`popover`** / **`tooltip`** — adopt as specific beads need them.

Rule: **don't pre-install shadcn primitives speculatively.** Add only when a bead needs one, and theme-tweak at adoption time.
