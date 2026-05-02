#!/usr/bin/env node
// Compute WCAG 2.1 contrast ratios for the Solstice·Ink token palette.
// Run: `node scripts/check-contrast.js`
//
// Useful when a token changes — confirm the new value still meets the
// guarantees documented in `frontend/lib/theme.md § Contrast`.

function luminance(hex) {
  const c = hex.replace("#", "");
  const rgb = [0, 2, 4].map((i) => parseInt(c.substr(i, 2), 16) / 255);
  const lin = rgb.map((v) =>
    v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4),
  );
  return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
}

function ratio(a, b) {
  const la = luminance(a);
  const lb = luminance(b);
  const [hi, lo] = la > lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
}

const BG = "#ecebe3";
const COLORS = {
  ink: "#0f1421",
  "ink-2": "#1f2a3f",
  "ink-dim": "#566173",
  "ink-faint": "#8a92a0",
  accent: "#1d3461",
  "accent-2": "#7a2826",
  good: "#2e6b48",
  warn: "#a86512",
  bad: "#7a2826",
};

console.log(`Contrast on bg ${BG}:`);
let failed = false;
for (const [name, hex] of Object.entries(COLORS)) {
  const r = ratio(hex, BG);
  const verdict =
    r >= 4.5 ? "AA" : r >= 3 ? "AA-large" : "DECORATIVE / DISABLED ONLY";
  if (r < 3 && name !== "ink-faint") failed = true;
  console.log(
    `  ${name.padEnd(11)} ${hex}  ${r.toFixed(2).padStart(5)}:1  ${verdict}`,
  );
}

process.exit(failed ? 1 : 0);
