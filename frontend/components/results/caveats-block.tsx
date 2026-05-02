import { Panel } from "@/components/ui";
import { cn } from "@/lib/utils";
import type { Caveat, CaveatTag } from "@/lib/api/forecast";
import { SectionHead } from "./section-head";

// Three-tier candor list: KNOWN / PARTIAL / UNKNOWN. Each item is a
// row with a tag pill and a body line; tags get a 2px top accent in
// good (green) / warn (amber) / bad (oxblood). Pinned at the bottom is
// the AI-assist + not-financial-advice disclaimer (chart-solar-6s7).
//
// Visual contract: design/solar-decisions/project/screen-results.jsx
// :CaveatsBlock (lines 175–202).

const TAG_TEXT: Record<CaveatTag, string> = {
  KNOWN: "text-good",
  PARTIAL: "text-warn",
  UNKNOWN: "text-bad",
};

const TAG_BORDER: Record<CaveatTag, string> = {
  KNOWN: "border-good",
  PARTIAL: "border-warn",
  UNKNOWN: "border-bad",
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
        {caveats.map((c, i) => (
          <li
            key={`${c.tag}-${i}`}
            className="grid grid-cols-[90px_1fr] items-start gap-4"
          >
            <span
              className={cn(
                "border-t-2 py-1 font-mono text-[10px] font-semibold uppercase tracking-[0.14em]",
                TAG_TEXT[c.tag],
                TAG_BORDER[c.tag],
              )}
            >
              {c.tag}
            </span>
            <p className="pt-1 text-[14px] leading-[1.55] text-ink-2">
              {c.body}
            </p>
          </li>
        ))}
      </ul>
      <div className="mt-5 border-t border-rule pt-3 text-[12px] italic leading-[1.5] text-ink-dim">
        Forecasts are AI-assisted projections, not financial advice.
        Assumptions and source data are listed above; methodology export
        unlocks with Decision Pack.
      </div>
    </Panel>
  );
}
