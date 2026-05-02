// Deterministic demo data for the chart primitives. Used by the sandbox
// + by SSR-friendly hero fallbacks. Pure functions, no randomness — the
// "Monte Carlo" here is a seeded PRNG so output is reproducible.

import type {
  BatteryDatum,
  HeroDatum,
  MonthDatum,
  TornadoItem,
} from "./types";

function lcg(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0xffffffff;
  };
}

export function demoHeroData({
  years = 25,
  simulations = 28,
  seed = 42,
  upfront = -28000,
  altRate = 0.045,
}: {
  years?: number;
  simulations?: number;
  seed?: number;
  upfront?: number;
  altRate?: number;
} = {}): HeroDatum[] {
  // Run the same Monte Carlo as design/solar-decisions/project/hero-art.jsx,
  // then collapse to per-year P10 / P50 / P90 envelope + HYSA opportunity-cost.
  const paths: number[][] = [];
  for (let k = 0; k < simulations; k++) {
    const r = lcg(seed + k * 7);
    const escal = 0.02 + r() * 0.04;
    const degr = 0.004 + r() * 0.004;
    const noise = () => (r() - 0.5) * 0.06;
    let baseSavings = 1900 + r() * 500;
    let cum = upfront;
    const pts: number[] = [cum];
    for (let y = 1; y <= years; y++) {
      baseSavings *= (1 + escal) * (1 - degr);
      cum += baseSavings * (1 + noise());
      pts.push(cum);
    }
    paths.push(pts);
  }

  const out: HeroDatum[] = [];
  for (let y = 0; y <= years; y++) {
    const vals = paths.map((p) => p[y]).sort((a, b) => a - b);
    out.push({
      year: y,
      p10: vals[Math.floor(vals.length * 0.1)],
      p50: vals[Math.floor(vals.length * 0.5)],
      p90: vals[Math.floor(vals.length * 0.9)],
      alt: upfront + Math.abs(upfront) * (Math.pow(1 + altRate, y) - 1),
    });
  }
  return out;
}

export function demoMonthlyBars(): MonthDatum[] {
  const months = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
  // Northern-hemisphere shape: gen peaks summer, use bimodal heat / cool.
  return months.map((m, i) => {
    const sun = Math.sin(((i - 2) / 12) * Math.PI);
    const gen = 350 + Math.max(0, sun) * 700;
    const use = 720 + Math.abs(Math.sin((i / 12) * Math.PI * 2)) * 280;
    return { month: m, gen: Math.round(gen), use: Math.round(use) };
  });
}

export function demoBatteryDispatch(): BatteryDatum[] {
  const out: BatteryDatum[] = [];
  for (let i = 0; i < 24; i++) {
    const solar = Math.max(0, Math.sin(((i - 6) / 12) * Math.PI)) * 4.5;
    const load =
      0.8 + (i >= 17 && i <= 22 ? 2.4 : 0.4) + Math.sin(i / 4) * 0.2;
    const isOnPeak = i >= 16 && i <= 21;
    const isOffPeak = i >= 0 && i <= 6;
    let battery = 0;
    if (isOffPeak) battery = 1.5;
    else if (isOnPeak) battery = -2.2;
    else if (solar > load) battery = Math.min(solar - load, 1.5);
    out.push({
      hour: i,
      solar: Number(solar.toFixed(2)),
      load: Number(load.toFixed(2)),
      battery: Number(battery.toFixed(2)),
    });
  }
  return out;
}

export function demoTornado(): TornadoItem[] {
  return [
    { name: "Rate escalation (2–6 % / yr)", low: -22000, high: 31000 },
    { name: "Production estimate (±8 %)", low: -15000, high: 17000 },
    { name: "Discount rate (3–7 %)", low: -12500, high: 14000 },
    { name: "Battery degradation", low: -8000, high: 6000 },
    { name: "Loan APR (5.5–9.5 %)", low: -7200, high: 4800 },
    { name: "Resale-value uplift", low: -2000, high: 4500 },
  ];
}
