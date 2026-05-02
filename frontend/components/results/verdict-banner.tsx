import { cn } from "@/lib/utils";
import type { Verdict } from "@/lib/api/forecast";

// Verdict banner — lens-aware, balanced-read summary at the top of the
// Results screen. The tone glyph (✓ vs ~) and tone color reflect the
// engine's verdict; the phrasing is intentionally non-imperative
// ("likely wins", "leans no") per the BUSINESS_PLAN.md ethics red-team.
//
// Visual contract: design/solar-decisions/project/screen-results.jsx
// :VerdictBanner (lines 5–38).

const TONE_TEXT: Record<Verdict["tone"], string> = {
  good: "text-good",
  warn: "text-warn",
  bad: "text-bad",
};

const TONE_BG: Record<Verdict["tone"], string> = {
  good: "bg-good",
  warn: "bg-warn",
  bad: "bg-bad",
};

const TONE_BORDER: Record<Verdict["tone"], string> = {
  good: "border-good",
  warn: "border-warn",
  bad: "border-bad",
};

export function VerdictBanner({ verdict }: { verdict: Verdict }) {
  const glyph = verdict.tone === "good" ? "✓" : "~";
  return (
    <section className="border-y border-rule bg-panel">
      <div className="mx-auto grid max-w-[1280px] grid-cols-1 items-center gap-8 px-10 py-8 md:grid-cols-[minmax(0,1fr)_auto]">
        <div>
          <div
            className={cn(
              "mb-4 flex items-center gap-[10px] font-mono text-[11px] uppercase tracking-[0.18em]",
              TONE_TEXT[verdict.tone],
            )}
          >
            <span
              aria-hidden="true"
              className={cn("inline-block h-px w-6", TONE_BG[verdict.tone])}
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
            TONE_BORDER[verdict.tone],
            TONE_TEXT[verdict.tone],
          )}
        >
          {glyph}
        </div>
      </div>
    </section>
  );
}
