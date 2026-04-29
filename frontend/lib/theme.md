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

## Why a single locked theme

`solar-decisions/project/themes.jsx` ships Solstice·Ink as the locked editorial direction — cool oyster paper, prussian-blue ink, oxblood secondary, with Newsreader/Inter/IBM Plex Mono. We honour that at v1: no dark mode, no theme picker, no per-tenant skinning. Tokenizing now keeps a future theme switch a single `data-theme` attribute swap.
