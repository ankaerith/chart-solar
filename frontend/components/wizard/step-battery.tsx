"use client";

import { useMemo } from "react";
import {
  BatteryDispatch,
  demoBatteryDispatch,
} from "@/components/charts";
import { Field, MonoLabel, Panel, SegBtn } from "@/components/ui";
import { Currency } from "@/lib/intl";
import { ChipGroup } from "./chip-group";
import { DetectRow } from "./detect-row";
import { StepGrid, StepShell } from "./step-shell";
import { CRITICAL_LOADS, type BatteryStep } from "./wizard-state";

const INCLUDE_OPTIONS = [
  { value: "no" as const, label: "No battery", sub: "cheaper, simpler" },
  { value: "yes" as const, label: "Add battery", sub: "backup + arbitrage" },
];

const DISPATCH_OPTIONS = [
  { value: "self" as const, label: "Self-consumption", sub: "eat your solar" },
  { value: "tou" as const, label: "TOU arbitrage", sub: "shave on-peak" },
  { value: "backup" as const, label: "Backup-first", sub: "reserve 80%" },
];

// Step 4 — Battery. Skip-with-defaults supported (the StepShell skip
// link routes straight to Financing with `include=false`). When a
// battery is included, capacity slider + dispatch SegBtn + critical-
// loads chips reveal, and the right Panel renders the demo dispatch
// chart.
//
// Visual contract: design/solar-decisions/project/screen-wizard.jsx
// :StepBattery (lines 298–375).

export function StepBattery({
  data,
  setData,
  onBack,
  onNext,
  onSkip,
}: {
  data: BatteryStep;
  setData: (patch: Partial<BatteryStep>) => void;
  onBack: () => void;
  onNext: () => void;
  onSkip: () => void;
}) {
  // demoBatteryDispatch() is a deterministic seed so memoising once
  // keeps the chart stable across rerenders without recomputing the
  // 24-hour profile on every keystroke elsewhere in the wizard.
  const dispatchSample = useMemo(() => demoBatteryDispatch(), []);
  return (
    <StepShell
      index={3}
      title="A battery — yes or no?"
      sub="In a NEM 1:1 market like yours, a battery rarely pays back on financial terms alone. Worth it for outage resilience, or under TOU arbitrage. We'll show both lenses."
      onBack={onBack}
      onNext={onNext}
      onSkip={onSkip}
    >
      <StepGrid>
        <div className="flex flex-col gap-[22px]">
          <Field label="Include battery">
            <SegBtn
              value={data.include ? "yes" : "no"}
              onChange={(v) => setData({ include: v === "yes" })}
              options={INCLUDE_OPTIONS}
            />
          </Field>
          {data.include && (
            <>
              <Field label="Capacity" hint="kWh usable">
                <div className="flex items-center gap-4">
                  <input
                    type="range"
                    min="5"
                    max="40"
                    step="2.5"
                    value={data.capacity}
                    onChange={(e) =>
                      setData({ capacity: parseFloat(e.target.value) })
                    }
                    aria-label="Battery capacity in kilowatt-hours"
                    className="flex-1 accent-accent"
                  />
                  <div className="min-w-[110px] text-right font-display text-[28px] tabular-nums">
                    {data.capacity}{" "}
                    <span className="font-mono text-[13px] text-ink-dim">
                      kWh
                    </span>
                  </div>
                </div>
              </Field>
              <Field label="Dispatch strategy">
                <SegBtn
                  value={data.dispatch}
                  onChange={(v) => setData({ dispatch: v })}
                  options={DISPATCH_OPTIONS}
                />
              </Field>
              <Field label="Critical loads" hint="for backup-first">
                <ChipGroup
                  ariaLabel="Critical loads"
                  options={CRITICAL_LOADS}
                  value={data.critical}
                  onChange={(next) => setData({ critical: next })}
                />
              </Field>
            </>
          )}
        </div>
        <Panel className="bg-panel-2">
          <MonoLabel>Sample 24-hour dispatch</MonoLabel>
          <div className="mt-3.5">
            {data.include ? (
              <BatteryDispatch data={dispatchSample} />
            ) : (
              <div className="rounded-md border border-dashed border-rule p-7 text-center italic text-ink-dim">
                No battery selected — solar exports directly to the grid at
                full retail credit (your NEM 1:1 makes this fine).
              </div>
            )}
          </div>
          {data.include && (
            <div className="mt-3.5 flex flex-col gap-3">
              <DetectRow
                label="Days of backup"
                value="0.9 day"
                sub="critical loads only"
              />
              <DetectRow
                label="Self-consumption"
                value="74%"
                sub="vs 38% solo solar"
              />
              <DetectRow
                label="Annual savings"
                value={
                  <>
                    <Currency value={280} /> / yr
                  </>
                }
                sub="modest in NEM 1:1"
              />
            </div>
          )}
        </Panel>
      </StepGrid>
    </StepShell>
  );
}
