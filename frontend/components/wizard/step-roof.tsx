"use client";

import { Field, MonoLabel, Panel, SegBtn } from "@/components/ui";
import { DetectRow } from "./detect-row";
import { StepGrid, StepShell } from "./step-shell";
import type { RoofStep, UsageStep } from "./wizard-state";

const TILT_OPTIONS = [
  { value: "flush" as const, label: "Flush" },
  { value: "15" as const, label: "15°" },
  { value: "25" as const, label: "25°" },
  { value: "35" as const, label: "35°" },
];

const AZIMUTH_OPTIONS = [
  { value: "E" as const, label: "E" },
  { value: "SE" as const, label: "SE" },
  { value: "S" as const, label: "S" },
  { value: "SW" as const, label: "SW" },
  { value: "W" as const, label: "W" },
];

const SHADING_OPTIONS = [
  { value: "open" as const, label: "Open", sub: "95-100%" },
  { value: "light" as const, label: "Light", sub: "85-95%" },
  { value: "mod" as const, label: "Moderate", sub: "70-85%" },
  { value: "heavy" as const, label: "Heavy", sub: "<70%" },
];

// Step 3 — Roof. System size is a slider with a big mono numeric
// readout; tilt / azimuth / shading are SegBtns. Right Panel reflects
// modeled annual kWh and % of usage covered, recomputed live.
//
// The 1450 kWh/kW yield + 92% solar access numbers are illustrative
// stand-ins for the engine output (pvlib will override these once
// chart-solar-bqq lands).
//
// Visual contract: design/solar-decisions/project/screen-wizard.jsx
// :StepRoof (lines 237–296).

export function StepRoof({
  data,
  setData,
  usage,
  onBack,
  onNext,
}: {
  data: RoofStep;
  setData: (patch: Partial<RoofStep>) => void;
  usage: UsageStep;
  onBack: () => void;
  onNext: () => void;
}) {
  const annualKwh = Math.round(data.size * 1450);
  const coverage =
    usage.kwh > 0 ? Math.round((annualKwh / usage.kwh) * 100) : null;

  return (
    <StepShell
      index={2}
      title="How big should the system be?"
      sub="We start from your usage and the orientation of your roof. You can override, but most homeowners are well-served by ~120% of annual usage in NEM markets, ~80% in NEM 3.0."
      onBack={onBack}
      onNext={onNext}
    >
      <StepGrid>
        <div className="flex flex-col gap-[22px]">
          <Field label="System size" hint="DC kW">
            <div className="flex items-center gap-4">
              <input
                type="range"
                min="3"
                max="14"
                step="0.1"
                value={data.size}
                onChange={(e) =>
                  setData({ size: parseFloat(e.target.value) })
                }
                aria-label="System size in kilowatts DC"
                className="flex-1 accent-accent"
              />
              <div className="min-w-[110px] text-right font-display text-[32px] tabular-nums">
                {data.size.toFixed(1)}{" "}
                <span className="font-mono text-[15px] text-ink-dim">kW</span>
              </div>
            </div>
          </Field>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Field label="Tilt" hint="degrees">
              <SegBtn
                value={data.tilt}
                onChange={(v) => setData({ tilt: v })}
                options={TILT_OPTIONS}
              />
            </Field>
            <Field label="Azimuth" hint="primary roof face">
              <SegBtn
                value={data.azimuth}
                onChange={(v) => setData({ azimuth: v })}
                options={AZIMUTH_OPTIONS}
              />
            </Field>
          </div>
          <Field
            label="Shading"
            hint="annual access"
            footnote="From your address, we estimated 92% solar access. You can override if you've had a tree-trim study."
          >
            <SegBtn
              value={data.shading}
              onChange={(v) => setData({ shading: v })}
              options={SHADING_OPTIONS}
              columns={4}
            />
          </Field>
        </div>
        <Panel className="bg-panel-2">
          <MonoLabel>Modeled output</MonoLabel>
          <div className="mt-2.5 font-display text-[48px] leading-none tabular-nums">
            {annualKwh.toLocaleString()}
            <span className="ml-1.5 font-mono text-[16px] text-ink-dim">
              kWh / yr
            </span>
          </div>
          <div className="mt-1.5 text-[12px] text-ink-dim">
            {coverage !== null
              ? `≈ ${coverage}% of your annual usage`
              : "Add usage on Step 02 for a coverage estimate."}
          </div>
          <div className="mt-4 flex flex-col gap-3">
            <DetectRow
              label="DC capacity"
              value={`${data.size.toFixed(1)} kW`}
              sub={`~${Math.round(data.size * 2.5)} panels @ 400 W`}
            />
            <DetectRow
              label="DC:AC ratio"
              value="1.18"
              sub="modest clipping"
            />
            <DetectRow
              label="Solar access"
              value="92%"
              sub="Sunroof + LIDAR"
            />
            <DetectRow
              label="Usable roof"
              value="~620 ft²"
              sub="south + southwest faces"
            />
          </div>
        </Panel>
      </StepGrid>
    </StepShell>
  );
}
