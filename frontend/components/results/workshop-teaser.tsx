"use client";

import { useState } from "react";
import { Arrow, Icon } from "@/components/icons";
import { Btn, DemoWatermark, Modal, MonoLabel } from "@/components/ui";
import { Currency } from "@/lib/intl";
import { cn } from "@/lib/utils";
import { DECISION_PACK_PRICE_USD } from "@/lib/pricing";

// design ref · tiers.jsx:WorkshopTeaser (227–386)
// Single consolidated paywall — replaces three earlier per-section
// gates that all said the same thing.

type Tool = {
  kicker: string;
  title: string;
  sub: string;
  v: string;
};

const TOOLS: ReadonlyArray<Tool> = [
  {
    kicker: "capital allocation",
    title: "Compare solar vs your other capital options",
    sub: "Solar isn't free; the question is whether it beats HYSA, mortgage paydown, and the index fund — over 25 years.",
    v: "Compare solar vs HYSA, mortgage paydown, S&P 500 — the do-something-else baselines installer tools never show.",
  },
  {
    kicker: "tornado sensitivity",
    title: "Which assumption actually moves your NPV",
    sub: "Rank-ordered, dollar-weighted impact on median NPV. Tells you which knob to actually argue about.",
    v: "Which assumption actually moves your NPV. Rank-ordered, dollar-weighted.",
  },
  {
    kicker: "battery dispatch · 8760",
    title: "Hour-by-hour battery dispatch",
    sub: "8,760-hour simulation. Charge off-peak, discharge at peak. NEM 3.0 / NBT and TOU arbitrage modeled.",
    v: "Hour-by-hour charge/discharge under your tariff. NEM 3.0 + TOU arbitrage modeled.",
  },
  {
    kicker: "sale-scenario",
    title: "What happens if you sell in year X",
    sub: "Probability-weighted across hold duration. Solar home-value uplift, remaining loan, buyer-market conditions.",
    v: "Probability-weighted across hold duration. Solar home-value uplift, remaining loan, buyer market.",
  },
  {
    kicker: "proposal audit",
    title: "Audit a real installer proposal",
    sub: "Drop a PDF. We extract every field, diff their year-1 kWh, escalator, dealer fee, and DC:AC against this baseline. One credit included.",
    v: "Drop the installer's PDF. Variance report + ask-your-installer questions. 1 credit included.",
  },
  {
    kicker: "methodology PDF + share",
    title: "Every assumption, every source — pinned",
    sub: "Engine version, irradiance source, tariff-table hash. Re-open the audit in 2030 and the numbers don't silently drift.",
    v: "Every assumption, every source. Reproducible — engine + irradiance + tariff hash pinned.",
  },
];

export function WorkshopTeaser() {
  const [preview, setPreview] = useState<Tool | null>(null);
  return (
    <section
      aria-label="Workshop · Decision Pack"
      className="overflow-hidden rounded-lg border border-rule-strong bg-panel"
    >
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1.5fr)]">
        <div className="flex min-h-[280px] flex-col justify-between bg-ink p-8 text-bg">
          <div>
            <span className="inline-flex items-center gap-2 rounded-md border border-bg/20 bg-bg/10 px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.16em] text-bg/75">
              <Icon.Lock size={10} aria-hidden="true" />
              Workshop · Decision Pack
            </span>
            <h3 className="mt-4 mb-3 text-[30px] leading-[1.1] font-display">
              You have the verdict. The work is behind this.
            </h3>
            <p className="m-0 max-w-[380px] text-[13.5px] leading-[1.6] text-bg/80">
              Six tools that turn the headline number into a defensible
              decision — plus one proposal-audit credit.
            </p>
          </div>
          <div className="mt-6 flex items-baseline gap-3 border-t border-bg/20 pt-5">
            <Btn
              kind="ghost"
              className="border-bg bg-bg !text-ink hover:opacity-90"
            >
              Unlock workshop — <Currency value={DECISION_PACK_PRICE_USD} />{" "}
              <Arrow />
            </Btn>
            <span className="font-mono text-[11px] tracking-[0.06em] text-bg/60">
              one-time · refundable 14 days
            </span>
          </div>
        </div>
        <div className="bg-panel p-7">
          <MonoLabel>What unlocks · 6 tools + 1 audit credit</MonoLabel>
          <div className="mt-3.5 grid grid-cols-1 gap-x-6 sm:grid-cols-2">
            {TOOLS.map((t, i) => (
              <div
                key={t.kicker}
                className={cn(
                  "flex flex-col gap-1.5 py-3",
                  i < TOOLS.length - (i % 2 === 0 ? 1 : 2) &&
                    "border-b border-dashed border-rule",
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-accent">
                    {t.kicker}
                  </span>
                  <button
                    type="button"
                    onClick={() => setPreview(t)}
                    className="inline-flex cursor-pointer items-center gap-1 bg-transparent p-0.5 font-mono text-[10px] uppercase tracking-[0.1em] text-accent-2 underline underline-offset-[3px] hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:rounded-sm"
                    aria-label={`Preview — ${t.title}`}
                  >
                    Preview
                  </button>
                </div>
                <p className="text-[12.5px] leading-[1.45] text-ink-2">
                  {t.v}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
      <Modal
        open={preview !== null}
        onClose={() => setPreview(null)}
        kicker={preview ? `Preview · ${preview.kicker} · sample data` : ""}
        title={preview?.title ?? ""}
        subtitle={preview?.sub}
        maxWidth={680}
      >
        <div className="relative px-7 pt-5 pb-3">
          <DemoWatermark />
          <p className="text-[13.5px] leading-[1.55] text-ink-2">
            Sample data here in production. Each tool surfaces with the
            real Recharts component fed your forecast — battery dispatch
            against your tariff schedule, tornado sensitivity over your
            Monte Carlo, capital-allocation rows scaled to your upfront.
          </p>
          <p className="mt-3 text-[12.5px] italic text-ink-dim">
            Sample data is shown. Your audit runs against your address,
            your bill, your tariff — and your numbers replace these.
          </p>
        </div>
        <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-4 border-t border-rule bg-panel-2 px-7 py-4">
          <span className="text-[12px] italic text-ink-dim">
            One Decision Pack unlocks all six tools.
          </span>
          <Btn kind="primary">
            Unlock — <Currency value={DECISION_PACK_PRICE_USD} /> <Arrow />
          </Btn>
        </div>
      </Modal>
    </section>
  );
}
