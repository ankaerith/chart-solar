"use client";

import { useMemo, useState } from "react";
import { Eyebrow, Panel, SegBtn } from "@/components/ui";
import {
  BatteryDispatch,
  HeroChart,
  MonthlyBars,
  TornadoChart,
  demoBatteryDispatch,
  demoHeroData,
  demoMonthlyBars,
  demoTornado,
} from "@/components/charts";

type Scenario = "cash" | "loan" | "lease";

const SCENARIO_OPTIONS: { value: Scenario; label: string; sub: string }[] = [
  { value: "cash", label: "Cash", sub: "$28k upfront" },
  { value: "loan", label: "Loan", sub: "5.5% / 12y" },
  { value: "lease", label: "Lease", sub: "$0 down" },
];

const HERO_BY_SCENARIO = {
  cash: demoHeroData({ upfront: -28000, seed: 42 }),
  loan: demoHeroData({ upfront: -3500, seed: 73, altRate: 0.06 }),
  lease: demoHeroData({ upfront: 0, seed: 117, altRate: 0.05 }),
};

export default function ChartsSandbox() {
  const [scenario, setScenario] = useState<Scenario>("cash");
  const monthly = useMemo(() => demoMonthlyBars(), []);
  const battery = useMemo(() => demoBatteryDispatch(), []);
  const tornado = useMemo(() => demoTornado(), []);

  return (
    <main className="mx-auto max-w-5xl space-y-12 px-8 py-16">
      <header className="space-y-3">
        <Eyebrow>Charts — sandbox</Eyebrow>
        <h1 className="text-4xl">Solstice·Ink — chart primitives</h1>
        <p className="max-w-2xl text-[15px] leading-relaxed text-ink-dim">
          Recharts re-implementations of the SVG mocks in
          <code className="mx-1 font-mono text-[13px] text-ink-2">
            design/solar-decisions/project/charts.jsx
          </code>
          and
          <code className="mx-1 font-mono text-[13px] text-ink-2">
            hero-art.jsx
          </code>
          . Each chart accepts a typed{" "}
          <code className="font-mono text-[13px] text-ink-2">data</code> prop;
          screens stub freely against the deterministic{" "}
          <code className="font-mono text-[13px] text-ink-2">demo-data.ts</code>{" "}
          fixtures.
        </p>
      </header>

      <Section
        label="HeroChart — cumulative net wealth"
        anchor="hero-art.jsx:35"
      >
        <Panel>
          <div className="mb-4 flex items-center justify-between gap-4">
            <div>
              <Eyebrow>Scenario</Eyebrow>
              <p className="text-[13px] text-ink-dim">
                Scenario chips swap the data prop — the chart is otherwise
                identical.
              </p>
            </div>
            <div className="min-w-[320px]">
              <SegBtn
                value={scenario}
                onChange={(v) => setScenario(v)}
                options={SCENARIO_OPTIONS}
              />
            </div>
          </div>
          <HeroChart data={HERO_BY_SCENARIO[scenario]} />
        </Panel>
      </Section>

      <Section label="MonthlyBars — gen vs use" anchor="charts.jsx:6">
        <Panel>
          <MonthlyBars data={monthly} />
        </Panel>
      </Section>

      <Section label="BatteryDispatch — 24h" anchor="charts.jsx:34">
        <Panel>
          <BatteryDispatch data={battery} />
        </Panel>
      </Section>

      <Section label="TornadoChart — sensitivity" anchor="charts.jsx:91">
        <Panel>
          <TornadoChart items={tornado} />
        </Panel>
      </Section>
    </main>
  );
}

function Section({
  label,
  anchor,
  children,
}: {
  label: string;
  anchor: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4 border-t border-rule pt-6">
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-[22px]">{label}</h2>
        <code className="font-mono text-[11px] text-ink-faint">{anchor}</code>
      </div>
      {children}
    </section>
  );
}
