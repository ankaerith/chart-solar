import { Panel } from "@/components/ui";
import { cn } from "@/lib/utils";
import { toneBorder, toneText, type Tone } from "@/lib/tone";
import type { Caveat, CaveatTag } from "@/lib/api/forecast";
import { SectionHead } from "./section-head";

// design ref · screen-results.jsx:CaveatsBlock (175–202)
// Pinned disclaimer is part of chart-solar-6s7 (AI-assist + not-
// financial-advice on every audit/export).

const TAG_TONE: Record<CaveatTag, Tone> = {
  KNOWN: "good",
  PARTIAL: "warn",
  UNKNOWN: "bad",
};

export function CaveatsBlock({
  caveats,
}: {
  caveats: ReadonlyArray<Caveat>;
}) {
  return (
    <Panel className="p-7">
      <SectionHead
        kicker="03 · honest limits"
        title="What this forecast does and doesn't know"
      />
      <ul className="mt-2 flex flex-col gap-3.5">
        {caveats.map((c, i) => {
          const tone = TAG_TONE[c.tag];
          return (
            <li
              key={i}
              className="grid grid-cols-[90px_1fr] items-start gap-4"
            >
              <span
                className={cn(
                  "border-t-2 py-1 font-mono text-[10px] font-semibold uppercase tracking-[0.14em]",
                  toneText(tone),
                  toneBorder(tone),
                )}
              >
                {c.tag}
              </span>
              <p className="pt-1 text-[14px] leading-[1.55] text-ink-2">
                {c.body}
              </p>
            </li>
          );
        })}
      </ul>
      <div className="mt-5 border-t border-rule pt-3 text-[12px] italic leading-[1.5] text-ink-dim">
        Forecasts are AI-assisted projections, not financial advice.
        Assumptions and source data are listed above; methodology export
        unlocks with Decision Pack.
      </div>
    </Panel>
  );
}
