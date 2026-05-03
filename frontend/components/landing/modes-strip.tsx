import type { ReactNode } from "react";
import { MonoLabel } from "@/components/ui";
import { Currency } from "@/lib/intl";
import { AUDIT_PRICE_USD, TRACK_MONTHLY_USD } from "@/lib/pricing";
import { ModeCard } from "./mode-card";

// design ref · screen-landing.jsx:ModesStrip (158–178)

type Mode = {
  name: string;
  tag: ReactNode;
  head: string;
  body: string;
  footer: string;
  href: string;
};

const MODES: ReadonlyArray<Mode> = [
  {
    name: "Explore",
    tag: "free",
    head: "Should I go solar?",
    body: "Address + a utility bill. We run an independent production model and a Monte Carlo across rate-escalation paths. Output is a distribution of 25-year outcomes, not a single headline number.",
    footer: "PVWatts v8 · Sunroof shading · NSRDB",
    href: "/forecast",
  },
  {
    name: "Audit",
    tag: <Currency value={AUDIT_PRICE_USD} />,
    head: "Check this proposal.",
    body: "Drop your installer's PDF. We diff their math against independent benchmarks — where the year-1 kWh, escalator, dealer fee, or DC:AC ratio drift, by how much, and which levers drive the gap.",
    footer: "Vertex AI extraction · NREL baseline",
    href: "/audit",
  },
  {
    name: "Track",
    tag: (
      <>
        <Currency value={TRACK_MONTHLY_USD} /> / mo
      </>
    ),
    head: "Did it actually work?",
    body: "Post-install. Bill ingestion + Enphase / SolarEdge / Tesla monitoring. Monthly variance vs. the forecast you were sold — bill-level and production-level.",
    footer: "green button · monitoring api · TTL 25 yr",
    href: "/track",
  },
];

export function ModesStrip() {
  return (
    <section className="mx-auto max-w-[1360px] px-10 pt-10 pb-16">
      <MonoLabel>── one engine, three questions ──</MonoLabel>
      <div className="mt-4 grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
        {MODES.map((mode, i) => (
          <ModeCard
            key={mode.name}
            index={String(i + 1).padStart(2, "0")}
            primary={i === 0}
            {...mode}
          />
        ))}
      </div>
    </section>
  );
}
