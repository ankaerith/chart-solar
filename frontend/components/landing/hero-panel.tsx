import {
  HeroChart,
  demoHeroData,
} from "@/components/charts";
import { MonoLabel, Panel } from "@/components/ui";
import { Currency } from "@/lib/intl";
import { MetricRow } from "./metric-row";

// design ref · screen-landing.jsx:HeroPanel (7–39)
//
// HeroChart relies on a useHasMounted gate to skip Recharts'
// ResponsiveContainer during SSR — the panel paints empty until
// hydration, then fills with the fan. The deterministic-seed SSR
// snapshot (chart-solar-lsc.1) closes that gap.

const SAMPLE_DATA = demoHeroData({
  years: 25,
  simulations: 28,
  seed: 17,
  upfront: -28000,
  altRate: 0.045,
});

export function HeroPanel() {
  return (
    <Panel className="flex flex-col gap-3.5 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <MonoLabel>Sample household · Boulder CO · 7.2 kW</MonoLabel>
          <div className="mt-1 font-display text-[22px]">
            25-year cumulative net wealth
          </div>
        </div>
        <span className="rounded-md border border-rule px-2 py-[3px] font-mono text-[10px] uppercase tracking-[0.1em] text-ink-dim">
          n = 28 sims
        </span>
      </div>
      <div className="min-h-[280px] flex-auto">
        <HeroChart data={SAMPLE_DATA} />
      </div>
      <div className="grid grid-cols-1 border-t border-rule md:grid-cols-2">
        <div className="md:border-r md:border-rule md:pr-4">
          <MetricRow
            label="Median NPV"
            value={<Currency value={31400} />}
            sub="discount 5.0%"
            accent
          />
          <MetricRow
            label="Crossover yr"
            value="yr 9"
            sub="solar > grid $/kWh"
          />
          <MetricRow
            label="P10 outcome"
            value={<Currency value={8200} />}
            sub="rate path stagnant"
          />
        </div>
        <div className="md:pl-4">
          <MetricRow
            label="Disc. payback"
            value="11.2 yr"
            sub="vs installer claim 7"
          />
          <MetricRow
            label="vs HYSA 4.5%"
            value={<Currency value={12900} />}
            sub="opportunity cost"
          />
          <MetricRow
            label="P90 outcome"
            value={<Currency value={58700} />}
            sub="rate path historical"
          />
        </div>
      </div>
    </Panel>
  );
}
