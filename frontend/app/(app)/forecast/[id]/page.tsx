import type { Metadata } from "next";
import { ResultsShell } from "@/components/results";
import { DEFAULT_WIZARD_STATE } from "@/components/wizard";
import { buildMockResult } from "@/lib/api/forecast";

// Real engine wiring lands under chart-solar-bqq; this surface stays
// the same — only the data source changes.

type Params = { id: string };

export async function generateMetadata({
  params,
}: {
  params: Promise<Params>;
}): Promise<Metadata> {
  const { id } = await params;
  return {
    title: `Forecast ${id} — Chart Solar`,
    robots: { index: false, follow: false },
  };
}

export default async function ForecastResultPage({
  params,
}: {
  params: Promise<Params>;
}) {
  const { id } = await params;
  // Same-process: call the fixture builder directly rather than
  // self-looping through /api/forecast/[id]. The HTTP route stays
  // for client-side lookups via getMockForecast().
  const result = { ...buildMockResult(DEFAULT_WIZARD_STATE), id };
  return <ResultsShell result={result} />;
}
