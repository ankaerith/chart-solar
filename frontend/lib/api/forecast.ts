// Mock forecast client — POSTs the wizard's WizardState to the local
// `/api/forecast` Next route, which returns a deterministic mock id.
// `getMockForecast(id)` reads the same hardcoded fixture back. Once
// the real engine endpoint lands (chart-solar-bqq), this module's
// surface stays — only the path changes — so call sites don't churn.

import { demoHeroData, type HeroDatum } from "@/components/charts";
import type { WizardState } from "@/components/wizard";

export type FinancingScenario = "cash" | "loan" | "lease";

export type Verdict = {
  // Lens-free summary the banner displays. Real engine output picks
  // this from a small set of templates keyed on the headline numbers
  // and tone (good = above-baseline by margin; warn = within noise;
  // bad = below baseline).
  label: string;
  head: string;
  body: string;
  tone: "good" | "warn" | "bad";
};

export type CaveatTag = "KNOWN" | "PARTIAL" | "UNKNOWN";

export type Caveat = {
  tag: CaveatTag;
  body: string;
};

export type ScenarioPaths = {
  method: FinancingScenario;
  // 26 points: year 0 → year 25. P10 / P50 / P90 envelope plus an
  // optional alt baseline (HYSA opportunity-cost line on the cash
  // path; lease/PPA payments line on those scenarios).
  paths: HeroDatum[];
  npv: number;
};

export type ResultTier = "free" | "pack" | "founders";

export type ForecastResultMock = {
  id: string;
  inputs: WizardState;
  // Single-line forecast summary (address · system size). Used as the
  // results-screen kicker.
  summary: string;
  headline: {
    nplv50: number;
    nplv10: number;
    nplv90: number;
    paybackYears: number;
    crossoverYear: number;
    irrPct: number;
    lifetimeTonsCO2: number;
    annualKwh: number;
    coveragePct: number;
  };
  verdict: Verdict;
  scenarios: ScenarioPaths[];
  caveats: ReadonlyArray<Caveat>;
  // Tier the result was generated against. The real engine writes
  // this from the user's entitlement at request time; the mock stays
  // on "free" so the workshop teaser surface renders by default.
  tier: ResultTier;
  // Audit credits remaining on the user's account at the time the
  // forecast was returned. Drives the Audit next-step CTA copy.
  creditsAudit: number;
  generatedAt: string;
};

const FORECAST_PATH = "/api/forecast";

export async function runMockForecast(
  inputs: WizardState,
): Promise<ForecastResultMock> {
  const res = await fetch(FORECAST_PATH, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(inputs),
  });
  if (!res.ok) {
    throw new Error(`Forecast request failed (${res.status})`);
  }
  return (await res.json()) as ForecastResultMock;
}

export async function getMockForecast(
  id: string,
): Promise<ForecastResultMock> {
  const res = await fetch(`${FORECAST_PATH}/${encodeURIComponent(id)}`, {
    method: "GET",
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Forecast lookup failed (${res.status})`);
  }
  return (await res.json()) as ForecastResultMock;
}

// Pure: derive a stable id from the inputs so refresh/share works
// without state. `crypto.subtle.digest` is browser/Node-portable in
// recent runtimes, but for the mock the simple FNV-1a fold is fine —
// it just needs to be deterministic.
export function deriveMockForecastId(inputs: WizardState): string {
  const json = JSON.stringify(inputs);
  let h = 2166136261 >>> 0;
  for (let i = 0; i < json.length; i++) {
    h ^= json.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return `mock-${h.toString(36)}`;
}

// Stable summary line for the results-screen kicker.
function buildSummary(inputs: WizardState): string {
  const addr = inputs.address.address.trim() || "Your roof";
  const size = inputs.roof.size.toFixed(1);
  return `Forecast · ${addr} · ${size} kW`;
}

const CAVEATS: ReadonlyArray<Caveat> = [
  {
    tag: "KNOWN",
    body: "Federal residential credit not modeled for systems placed in service after 2025-12-31. State + utility incentives only.",
  },
  {
    tag: "KNOWN",
    body: "Hold duration default is ZIP-defaulted from US Census mobility data. Overrideable; actually staying 25 yr typically moves NPV by tens of thousands.",
  },
  {
    tag: "PARTIAL",
    body: "Battery dispatch is rule-based (charge off-peak / discharge at peak) at launch. LP-optimized dispatch lands Phase 2 — typically ±3-5% NPV delta.",
  },
  {
    tag: "PARTIAL",
    body: "Hourly load profile is a ResStock archetype until you connect Green Button. Real intervals usually shift sizing recommendation by ±0.5 kW.",
  },
  {
    tag: "UNKNOWN",
    body: "Future policy. NEM rules can change. We model rate escalation, not regulatory shocks. The P10 path captures some of this.",
  },
];

// Hardcoded headline + scenario fixture — illustrative numbers that
// match the editorial copy (median NPV ≈ thirty-one-thousand-four-
// hundred, an eight-year payback, etc.). The real engine output will
// overwrite this once chart-solar-bqq lands.
export function buildMockResult(inputs: WizardState): ForecastResultMock {
  const annualKwh = Math.round(inputs.roof.size * 1450);
  const coveragePct =
    inputs.usage.kwh > 0 ? Math.round((annualKwh / inputs.usage.kwh) * 100) : 0;

  // Three deterministic Monte-Carlo runs feed the scenario chips —
  // same shape, different upfront and yield assumptions per financing
  // wrapper. The seeded PRNG keeps them reproducible.
  const cashPaths = demoHeroData({ seed: 42, upfront: -28000, altRate: 0.045 });
  const loanPaths = demoHeroData({ seed: 51, upfront: -2000, altRate: 0.055 });
  const leasePaths = demoHeroData({ seed: 64, upfront: 0, altRate: 0.029 });

  const final = (paths: HeroDatum[]) => paths[paths.length - 1].p50;

  return {
    id: deriveMockForecastId(inputs),
    inputs,
    summary: buildSummary(inputs),
    headline: {
      nplv50: 31400,
      nplv10: 8200,
      nplv90: 58700,
      paybackYears: 8.4,
      crossoverYear: 9,
      irrPct: 6.8,
      lifetimeTonsCO2: 247,
      annualKwh,
      coveragePct,
    },
    verdict: {
      label: "balanced read · go",
      head: "Solar likely wins — modestly.",
      body: "Median NPV is positive over 25 years at your discount rate; crossover with the grid happens in year 9. Even at 3% rate escalation you stay net-positive in the 80% band. Battery sizing trims financial upside but adds typical-load backup.",
      tone: "good",
    },
    scenarios: [
      { method: "cash", paths: cashPaths, npv: final(cashPaths) },
      { method: "loan", paths: loanPaths, npv: final(loanPaths) },
      { method: "lease", paths: leasePaths, npv: final(leasePaths) },
    ],
    caveats: CAVEATS,
    tier: "free",
    creditsAudit: 0,
    generatedAt: new Date().toISOString(),
  };
}
