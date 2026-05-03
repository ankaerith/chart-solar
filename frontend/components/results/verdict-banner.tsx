import { cn } from "@/lib/utils";
import { toneBg, toneBorder, toneText } from "@/lib/tone";
import type { Verdict } from "@/lib/api/forecast";

// design ref · screen-results.jsx:VerdictBanner (5–38)
// Phrasing is intentionally non-imperative ("likely wins", "leans no")
// per the BUSINESS_PLAN.md ethics red-team.

export function VerdictBanner({ verdict }: { verdict: Verdict }) {
  const glyph = verdict.tone === "good" ? "✓" : "~";
  return (
    <section className="border-y border-rule bg-panel">
      <div className="mx-auto grid max-w-[1280px] grid-cols-1 items-center gap-8 px-10 py-8 md:grid-cols-[minmax(0,1fr)_auto]">
        <div>
          <div
            className={cn(
              "mb-4 flex items-center gap-[10px] font-mono text-[11px] uppercase tracking-[0.18em]",
              toneText(verdict.tone),
            )}
          >
            <span
              aria-hidden="true"
              className={cn("inline-block h-px w-6", toneBg(verdict.tone))}
            />
            Verdict · {verdict.label}
          </div>
          <h2 className="mt-1 mb-3 text-[clamp(28px,3.4vw,44px)] leading-[1.1] font-display">
            {verdict.head}
          </h2>
          <p className="m-0 max-w-[720px] text-[15.5px] leading-[1.55] text-ink-2">
            {verdict.body}
          </p>
        </div>
        <div
          aria-hidden="true"
          className={cn(
            "flex h-[90px] w-[90px] items-center justify-center rounded-full border-2 font-display text-[36px] font-bold",
            toneBorder(verdict.tone),
            toneText(verdict.tone),
          )}
        >
          {glyph}
        </div>
      </div>
    </section>
  );
}
