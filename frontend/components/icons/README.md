# Icon set

Curated icon vocabulary for Chart Solar.

## Convention

- **Bespoke marks** (`Wordmark`, `Arrow`) live under `components/ui/` and are re-exported here. They carry brand semantics — the radiating-sun mark and the editorial chevron — and aren't drop-in replaceable from a third-party set.
- **Everything else** comes from [`lucide-react`](https://lucide.dev) via the `Icon` namespace in `index.tsx`. Each lucide icon is wrapped with editorial defaults (`strokeWidth=1.5`, `size=16`) to match the design ref's weight.

## Adding an icon

1. Confirm the design ref needs it (check `design/solar-decisions/project/screen-*.jsx`).
2. Add the lucide import + `withDefaults` wrap in `index.tsx`.
3. Export it under the `Icon.*` namespace.

Don't import lucide directly from screens — go through `Icon.*` so the editorial weight is consistent and the vocabulary stays small. If a one-off icon is needed (rare), discuss whether the design needs to grow the vocabulary or whether an existing icon covers the case.

## Why the wrapper

`strokeWidth=1.5` is the editorial weight; lucide's default is `2`. If we forgot the wrap, every icon import would have to remember the override — the wrapper makes the default match the design and lets call sites focus on size + colour.
