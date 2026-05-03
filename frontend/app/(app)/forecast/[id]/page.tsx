import type { Metadata } from "next";
import Link from "next/link";
import { Eyebrow, MonoLabel, Panel } from "@/components/ui";
import { DEFAULT_WIZARD_STATE, DetectRow } from "@/components/wizard";
import { buildMockResult } from "@/lib/api/forecast";
import { formatCurrency } from "@/lib/intl";

// Placeholder result page — confirms the wizard's mock round-trip.
// The full editorial Results screen lives in chart-solar-hv7.

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
  // Same-process: skip the self-loop fetch through /api/forecast/[id]
  // and call the fixture builder directly. The HTTP route stays for
  // client-side lookups via getMockForecast().
  const result = { ...buildMockResult(DEFAULT_WIZARD_STATE), id };
  const fmtUsd = (n: number) => formatCurrency(n, "en-US");

  return (
    <div className="mx-auto w-full max-w-[1080px] px-10 pt-12 pb-20">
      <Eyebrow>Forecast · mock</Eyebrow>
      <h1 className="mt-1 mb-3 text-[clamp(32px,4vw,52px)] font-display leading-[1.05] text-balance">
        Your roof, the honest math.
      </h1>
      <p className="mb-8 max-w-[680px] text-[16px] leading-[1.55] text-ink-2">
        This is a placeholder for the full Results screen (
        <code className="font-mono text-[13px] text-ink-2">
          chart-solar-83l
        </code>
        ). The numbers below come from the mock forecast endpoint — just
        enough to confirm the wizard round-trip works end-to-end.
      </p>

      <Panel className="grid gap-6 md:grid-cols-2">
        <div>
          <MonoLabel>Headline · 25 yr median</MonoLabel>
          <div className="mt-2 font-display text-[44px] tabular-nums leading-none">
            {fmtUsd(result.headline.nplv50)}
          </div>
          <div className="mt-2 text-[12.5px] text-ink-dim">
            P10 {fmtUsd(result.headline.nplv10)} ·{" "}
            P90 {fmtUsd(result.headline.nplv90)}
          </div>
        </div>
        <div className="flex flex-col gap-3">
          <DetectRow
            label="Payback"
            value={`${result.headline.paybackYears.toFixed(1)} yr`}
          />
          <DetectRow
            label="IRR"
            value={`${result.headline.irrPct.toFixed(1)}%`}
          />
          <DetectRow
            label="Annual production"
            value={`${result.headline.annualKwh.toLocaleString()} kWh`}
          />
          <DetectRow
            label="Coverage"
            value={`${result.headline.coveragePct}%`}
          />
        </div>
      </Panel>

      <div className="mt-6 flex flex-wrap items-center gap-4 text-[13px]">
        <span className="font-mono text-ink-faint">
          forecast id · {result.id}
        </span>
        <Link
          href="/forecast"
          className="rounded-sm underline underline-offset-2 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Run another forecast →
        </Link>
      </div>
    </div>
  );
}
