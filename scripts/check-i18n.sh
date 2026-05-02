#!/usr/bin/env bash
# Block raw currency symbols in JSX/TSX. Run from repo root.
#
# Matches `$<digit>` and `£<digit>` in source code under
# frontend/{app,components,lib} — those are user-visible currency strings
# that should flow through `@/lib/intl` (Currency, formatCurrency, …).
#
# Allowed:
#   - Unit notations like "$/W" (no digit after the symbol)
#   - Sandbox routes (frontend/app/sandbox/) — developer-facing component
#     review pages where literal sample strings demonstrate typography
#   - This script itself
#
# AC for chart-solar-ac8k: "ESLint rule blocks raw '$' / '£' in JSX/TSX
# (or grep test in CI)." Grep test wins on simplicity + allowlisting.

set -euo pipefail

ROOT="${1:-frontend}"

# `\$\d` and `£\d` — currency symbol immediately followed by a digit.
# Use POSIX character classes so this works on macOS bash too.
PATTERN='[$£][0-9]'

# Search only the user-facing source. Sandbox pages are excluded by path.
matches=$(grep -RnE "$PATTERN" \
  --include='*.ts' --include='*.tsx' \
  --exclude-dir=node_modules --exclude-dir=.next --exclude-dir=sandbox \
  "$ROOT/app" "$ROOT/components" "$ROOT/lib" 2>/dev/null || true)

if [[ -n "$matches" ]]; then
  echo "✗ Raw currency symbols found in JSX/TSX (use @/lib/intl helpers):" >&2
  echo "$matches" >&2
  exit 1
fi

echo "✓ No raw currency symbols in user-facing JSX/TSX."
