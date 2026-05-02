import type { ReactNode } from "react";
import { MonoLabel } from "@/components/ui";
import { cn } from "@/lib/utils";

// MetricRow — left/right pair used inside HeroPanel. Six rows split
// across two columns; the "Median NPV" row gets the accent color and
// is the only display-color tile in the panel.
//
// Visual contract: design/solar-decisions/project/screen-landing.jsx
// :MetricRow (lines 41–58).

export function MetricRow({
  label,
  value,
  sub,
  accent = false,
}: {
  label: string;
  value: ReactNode;
  sub?: string;
  accent?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-rule py-2.5">
      <MonoLabel>{label}</MonoLabel>
      <div className="text-right">
        <div
          className={cn(
            "font-display text-[18px] tabular-nums",
            accent ? "text-accent" : "text-ink",
          )}
        >
          {value}
        </div>
        {sub && (
          <div className="font-mono text-[11px] text-ink-dim">{sub}</div>
        )}
      </div>
    </div>
  );
}
