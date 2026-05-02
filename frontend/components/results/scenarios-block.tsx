"use client";

import { useState } from "react";
import { HeroChart } from "@/components/charts";
import { MonoLabel, Panel } from "@/components/ui";
import { Currency } from "@/lib/intl";
import { cn } from "@/lib/utils";
import type {
  FinancingScenario,
  ScenarioPaths,
} from "@/lib/api/forecast";

// Cumulative-net-wealth fan chart with cash / loan / lease scenario
// chips. Same Recharts component as the landing hero, fed real Monte
// Carlo P10 / P50 / P90 paths per scenario. The chip switch swaps the
// active dataset; chart axes stay pinned across switches so visual
// comparison is honest.
//
// Visual contract: design/solar-decisions/project/screen-results.jsx
// :ScenariosBlock (lines 125–150) + the inline Recharts area inside
// ScreenResults (376–398).

const CHIP_LABELS: Record<FinancingScenario, string> = {
  cash: "cash",
  loan: "loan",
  lease: "lease",
};

export function ScenariosBlock({
  scenarios,
  simulations,
}: {
  scenarios: ReadonlyArray<ScenarioPaths>;
  simulations: number;
}) {
  const initial: FinancingScenario =
    scenarios.find((s) => s.method === "cash")?.method ??
    scenarios[0]?.method ??
    "cash";
  const [active, setActive] = useState<FinancingScenario>(initial);
  const current =
    scenarios.find((s) => s.method === active) ?? scenarios[0];

  return (
    <Panel className="p-7">
      <div className="mb-3.5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <MonoLabel>Cumulative net wealth · solar vs do-nothing</MonoLabel>
          <div className="mt-1 font-display text-[22px]">
            Year-by-year, {simulations.toLocaleString()} simulated paths
          </div>
        </div>
        <div
          role="tablist"
          aria-label="Financing scenario"
          className="flex flex-wrap gap-2"
        >
          {scenarios.map((s) => {
            const selected = s.method === active;
            return (
              <button
                key={s.method}
                type="button"
                role="tab"
                aria-selected={selected}
                onClick={() => setActive(s.method)}
                className={cn(
                  "cursor-pointer rounded-md border px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.1em] transition-colors duration-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg",
                  selected
                    ? "border-ink bg-ink text-bg"
                    : "border-rule bg-bg text-ink-dim hover:bg-panel-2 hover:text-ink-2",
                )}
              >
                {CHIP_LABELS[s.method]}
              </button>
            );
          })}
        </div>
      </div>
      <div className="min-h-[320px]">
        <HeroChart data={current.paths} />
      </div>
      <div className="mt-3.5 flex flex-wrap items-baseline justify-between gap-3 border-t border-rule pt-3.5 text-[12.5px] text-ink-dim">
        <span>
          P50 net wealth at year 25:{" "}
          <Currency
            value={current.npv}
            className={cn(
              "text-[13.5px] font-semibold",
              current.npv >= 0 ? "text-good" : "text-bad",
            )}
          />
        </span>
        <span className="font-mono text-[11px] text-ink-dim">
          dashed line · do-nothing baseline at the same discount rate
        </span>
      </div>
    </Panel>
  );
}
