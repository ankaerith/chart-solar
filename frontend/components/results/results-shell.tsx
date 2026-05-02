import { Eyebrow } from "@/components/ui";
import type { ForecastResultMock } from "@/lib/api/forecast";
import { CaveatsBlock } from "./caveats-block";
import { HeadlineGrid } from "./headline-grid";
import { NextStepsRow } from "./next-steps-row";
import { ScenariosBlock } from "./scenarios-block";
import { SectionHead } from "./section-head";
import { VerdictBanner } from "./verdict-banner";
import { WorkshopTeaser } from "./workshop-teaser";

// ResultsShell — composes the full /forecast/[id] surface. Order
// matches the editorial flow in the design source:
//
//   1. Hero kicker + display headline ("25 years, 500 paths…")
//   2. Cumulative-net-wealth fan chart with cash/loan/lease chips
//   3. Headline grid (six tiles)
//   4. Verdict banner (lens-aware)
//   5. Workshop teaser (free-tier only)  OR  scenarios + sensitivity
//      panels (Decision Pack tier — P2, follow-up)
//   6. Caveats block (KNOWN / PARTIAL / UNKNOWN)
//   7. Next-steps row (Audit primary · Save · Track-coming-soon)
//
// Visual contract: design/solar-decisions/project/screen-results.jsx
// :ScreenResults (lines 347–449).

const SIM_COUNT_FREE = 50;
const SIM_COUNT_PACK = 500;

export function ResultsShell({
  result,
}: {
  result: ForecastResultMock;
}) {
  const simulations =
    result.tier === "free" ? SIM_COUNT_FREE : SIM_COUNT_PACK;

  return (
    <div className="flex flex-col gap-0">
      <section className="mx-auto w-full max-w-[1280px] px-10 pt-12 pb-8">
        <Eyebrow>{result.summary}</Eyebrow>
        <h1 className="mt-1 mb-4 text-[clamp(40px,5.5vw,72px)] leading-[1.02] font-display text-balance">
          25 years, {simulations.toLocaleString()} paths,
          <br />
          one distribution.
        </h1>
        <p className="m-0 max-w-[720px] text-[16px] leading-[1.55] text-ink-2">
          Below is the full distribution of cumulative-net-wealth
          outcomes for your roof, given everything you told us and the
          things we know about your address, utility, and tariff. The
          headline number is the median; the band is the 80% confidence
          interval.
        </p>
      </section>

      <section className="mx-auto w-full max-w-[1280px] px-10 pb-6">
        <ScenariosBlock
          scenarios={result.scenarios}
          simulations={simulations}
        />
      </section>

      <section className="mx-auto w-full max-w-[1280px] px-10">
        <HeadlineGrid headline={result.headline} />
      </section>

      <VerdictBanner verdict={result.verdict} />

      {result.tier === "free" && (
        <section className="mx-auto w-full max-w-[1280px] px-10 py-10">
          <WorkshopTeaser />
        </section>
      )}

      <section className="mx-auto w-full max-w-[1280px] px-10 pb-10">
        <CaveatsBlock caveats={result.caveats} />
      </section>

      <section className="mx-auto w-full max-w-[1280px] px-10 pb-20">
        <SectionHead kicker="04 · what next" title="Next steps" />
        <NextStepsRow
          tier={result.tier}
          creditsAudit={result.creditsAudit}
        />
      </section>
    </div>
  );
}
