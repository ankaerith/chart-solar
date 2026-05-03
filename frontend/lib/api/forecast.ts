// Mock forecast client — POSTs the wizard's WizardState to the local
// `/api/forecast` Next route, which returns a deterministic mock id.
// `getMockForecast(id)` reads the same hardcoded fixture back. Once
// the real engine endpoint lands (chart-solar-bqq), this module's
// surface stays — only the path changes — so call sites don't churn.

import type { WizardState } from "@/components/wizard";

export type ForecastResultMock = {
  id: string;
  // Headline figures the results screen will render. The shape here is
  // a pared-down preview of the engine's eventual ForecastResult; once
  // the OpenAPI generator emits the full type, swap to that and add
  // adapters where the wizard's UI shape needs translating.
  inputs: WizardState;
  headline: {
    nplv50: number;
    nplv10: number;
    nplv90: number;
    paybackYears: number;
    irrPct: number;
    annualKwh: number;
    coveragePct: number;
  };
  generatedAt: string; // ISO timestamp
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

// Hardcoded headline fixture — illustrative numbers that match the
// editorial copy (median NPV ≈ thirty-one-thousand-four-hundred, an
// eight-year payback, etc.). The real engine output will overwrite
// this once chart-solar-bqq lands.
export function buildMockResult(inputs: WizardState): ForecastResultMock {
  const annualKwh = Math.round(inputs.roof.size * 1450);
  const coveragePct =
    inputs.usage.kwh > 0 ? Math.round((annualKwh / inputs.usage.kwh) * 100) : 0;
  return {
    id: deriveMockForecastId(inputs),
    inputs,
    headline: {
      nplv50: 31400,
      nplv10: 8200,
      nplv90: 58700,
      paybackYears: 8.4,
      irrPct: 9.1,
      annualKwh,
      coveragePct,
    },
    generatedAt: new Date().toISOString(),
  };
}
