"use client";

import { cn } from "@/lib/utils";

export type SegOption<T extends string = string> =
  | T
  | { value: T; label: string; sub?: string };

export function SegBtn<T extends string = string>({
  value,
  options,
  onChange,
  columns,
  className,
}: {
  value: T;
  options: ReadonlyArray<SegOption<T>>;
  onChange: (value: T) => void;
  columns?: number;
  className?: string;
}) {
  const cols = columns ?? options.length;
  return (
    <div
      role="radiogroup"
      className={cn(
        "grid divide-x divide-rule-strong overflow-hidden rounded-md border border-rule-strong",
        className,
      )}
      style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
    >
      {options.map((opt) => {
        const v = (typeof opt === "string" ? opt : opt.value) as T;
        const label = typeof opt === "string" ? opt : opt.label;
        const sub = typeof opt === "object" ? opt.sub : null;
        const selected = value === v;
        return (
          <button
            key={v}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(v)}
            className={cn(
              "flex flex-col items-center gap-[2px] px-3 py-[11px] text-center text-[13px] font-sans transition-colors duration-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
              selected
                ? "bg-ink font-semibold text-bg"
                : "bg-bg font-medium text-ink hover:bg-panel-2",
            )}
          >
            <span>{label}</span>
            {sub && (
              <span
                className={cn(
                  "font-mono text-[10px] tracking-[0.06em]",
                  selected ? "text-bg/70" : "text-ink-faint",
                )}
              >
                {sub}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
