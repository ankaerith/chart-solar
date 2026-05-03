"use client";

import { cn } from "@/lib/utils";

// Range slider with a mono numeric readout to its right. Used inside
// the wizard's roof-size and battery-capacity fields. Visual + spacing
// match design/solar-decisions/project/screen-wizard.jsx — both the
// roof and battery instances render through this single primitive.

export function Slider({
  value,
  onChange,
  min,
  max,
  step = 1,
  display,
  unit,
  ariaLabel,
  readoutSize = 32,
  className,
}: {
  value: number;
  onChange: (next: number) => void;
  min: number;
  max: number;
  step?: number;
  display: string;
  unit: string;
  ariaLabel: string;
  readoutSize?: number;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center gap-4", className)}>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        aria-label={ariaLabel}
        className="flex-1 accent-accent"
      />
      <div
        className="min-w-[110px] text-right font-display tabular-nums"
        style={{ fontSize: readoutSize }}
      >
        {display}{" "}
        <span className="font-mono text-[13px] text-ink-dim">{unit}</span>
      </div>
    </div>
  );
}
