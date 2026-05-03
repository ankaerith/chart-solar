import type { ReactNode } from "react";
import { MonoLabel } from "@/components/ui";
import { cn } from "@/lib/utils";

// design ref · screen-landing.jsx:MetricRow (41–58)
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
