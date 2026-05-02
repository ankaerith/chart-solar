"use client";

import type { KeyboardEvent } from "react";
import { cn } from "@/lib/utils";
import { STEPS, type StepKey } from "./wizard-state";

// Stepper — top-of-wizard step indicator. Five segments, each one of
// {done, active, inactive}. Done segments are click-to-jump (only
// backwards — moving forward requires completing the active step).
//
// Visual contract: design/solar-decisions/project/screen-wizard.jsx:13
// (Stepper). Active segment gets the panel surface and an accent step
// number; done steps get ✓ + accent color; inactive steps render at
// reduced opacity.
//
// Accessibility: the row exposes ARIA tab semantics so a screen reader
// reads "Step 02, Usage, current" rather than only the visual cue.

export function Stepper({
  index,
  onJump,
}: {
  index: number;
  onJump?: (index: number, key: StepKey) => void;
}) {
  function handleKey(e: KeyboardEvent<HTMLLIElement>, i: number, k: StepKey) {
    if (!onJump) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onJump(i, k);
    }
  }

  return (
    <ol
      role="tablist"
      aria-label="Forecast wizard steps"
      className="flex border-y border-rule"
    >
      {STEPS.map((s, i) => {
        const done = i < index;
        const active = i === index;
        const jumpable = done && onJump;
        return (
          <li
            key={s.key}
            role="tab"
            aria-selected={active}
            aria-current={active ? "step" : undefined}
            aria-disabled={!done && !active}
            tabIndex={jumpable ? 0 : -1}
            onClick={jumpable ? () => onJump(i, s.key) : undefined}
            onKeyDown={(e) => handleKey(e, i, s.key)}
            className={cn(
              "flex flex-1 flex-col gap-1 px-5 py-[14px]",
              i < STEPS.length - 1 && "border-r border-rule",
              active && "bg-panel",
              !done && !active && "opacity-55",
              jumpable &&
                "cursor-pointer hover:bg-panel-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
            )}
          >
            <span
              className={cn(
                "font-mono text-[10px] uppercase tracking-[0.14em]",
                active ? "text-accent-2" : "text-ink-faint",
              )}
            >
              {done ? "✓" : s.n} · step
            </span>
            <span
              className={cn(
                "font-display text-[15px]",
                active ? "text-ink" : "text-ink-dim",
              )}
            >
              {s.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
