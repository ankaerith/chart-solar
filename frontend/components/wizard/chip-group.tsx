"use client";

import { cn } from "@/lib/utils";

// design ref · screen-wizard.jsx:StepUsage (197–214) + StepBattery (333–349)

export function ChipGroup({
  options,
  value,
  onChange,
  ariaLabel,
}: {
  options: ReadonlyArray<string>;
  value: ReadonlyArray<string>;
  onChange: (next: ReadonlyArray<string>) => void;
  ariaLabel: string;
}) {
  return (
    <div role="group" aria-label={ariaLabel} className="flex flex-wrap gap-2">
      {options.map((opt) => {
        const active = value.includes(opt);
        return (
          <button
            key={opt}
            type="button"
            role="checkbox"
            aria-checked={active}
            onClick={() => {
              const next = active
                ? value.filter((v) => v !== opt)
                : [...value, opt];
              onChange(next);
            }}
            className={cn(
              "cursor-pointer rounded-md border px-[14px] py-2 text-[12.5px] font-sans transition-colors duration-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg",
              active
                ? "border-ink bg-ink text-bg"
                : "border-rule-strong bg-transparent text-ink-2 hover:bg-panel-2",
            )}
          >
            {opt}
          </button>
        );
      })}
    </div>
  );
}
