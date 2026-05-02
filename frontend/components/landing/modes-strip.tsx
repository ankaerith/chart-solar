import { MonoLabel } from "@/components/ui";
import { Currency } from "@/lib/intl";
import { ModeCard } from "./mode-card";

// Modes strip — three cards, one per product mode. Auto-fit grid so
// the cards stack at narrow widths without losing the editorial
// 3-up rhythm at desktop. Explore is the primary card (accent
// headline color); Audit + Track are equal-weighted.
//
// Visual contract: design/solar-decisions/project/screen-landing.jsx
// :ModesStrip (lines 158–178).

const AUDIT_PRICE_USD = 79;
const TRACK_MONTHLY_USD = 9;

export function ModesStrip() {
  return (
    <section className="mx-auto max-w-[1360px] px-10 pt-10 pb-16">
      <MonoLabel>── one engine, three questions ──</MonoLabel>
      <div className="mt-4 grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
        <ModeCard
          index="01"
          name="Explore"
          tag="free"
          head="Should I go solar?"
          body="Address + a utility bill. We run an independent production model and a Monte Carlo across rate-escalation paths. Output is a distribution of 25-year outcomes, not a single headline number."
          footer="PVWatts v8 · Sunroof shading · NSRDB"
          href="/forecast"
          primary
        />
        <ModeCard
          index="02"
          name="Audit"
          tag={<Currency value={AUDIT_PRICE_USD} />}
          head="Check this proposal."
          body="Drop your installer's PDF. We diff their math against independent benchmarks — where the year-1 kWh, escalator, dealer fee, or DC:AC ratio drift, by how much, and which levers drive the gap."
          footer="Vertex AI extraction · NREL baseline"
          href="/audit"
        />
        <ModeCard
          index="03"
          name="Track"
          tag={
            <>
              <Currency value={TRACK_MONTHLY_USD} /> / mo
            </>
          }
          head="Did it actually work?"
          body="Post-install. Bill ingestion + Enphase / SolarEdge / Tesla monitoring. Monthly variance vs. the forecast you were sold — bill-level and production-level."
          footer="green button · monitoring api · TTL 25 yr"
          href="/track"
        />
      </div>
    </section>
  );
}
