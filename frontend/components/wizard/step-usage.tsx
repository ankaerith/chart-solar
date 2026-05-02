"use client";

import { MonthlyBars, type MonthDatum } from "@/components/charts";
import { Btn, Field, MonoLabel, Panel, SegBtn, TextInput } from "@/components/ui";
import { ChipGroup } from "./chip-group";
import { DetectRow } from "./detect-row";
import { StepGrid, StepShell } from "./step-shell";
import { UPCOMING_LOADS, type UsageStep } from "./wizard-state";

const METHOD_OPTIONS = [
  { value: "greenbutton" as const, label: "Green Button", sub: "hourly, 1 yr" },
  { value: "pdf" as const, label: "Upload bill", sub: "PDF / image" },
  { value: "manual" as const, label: "Type it in", sub: "monthly avg" },
];

// Stub monthly profile — peak in July (A/C), winter shoulder.
// Numbers are illustrative; the real wiring pulls from Green Button or
// the bill-extraction pipeline.
const SAMPLE_PROFILE: MonthDatum[] = [
  { month: "J", gen: 0, use: 980 },
  { month: "F", gen: 0, use: 880 },
  { month: "M", gen: 0, use: 740 },
  { month: "A", gen: 0, use: 680 },
  { month: "M", gen: 0, use: 710 },
  { month: "J", gen: 0, use: 920 },
  { month: "J", gen: 0, use: 1180 },
  { month: "A", gen: 0, use: 1120 },
  { month: "S", gen: 0, use: 880 },
  { month: "O", gen: 0, use: 720 },
  { month: "N", gen: 0, use: 820 },
  { month: "D", gen: 0, use: 990 },
];

// Step 2 — Usage. Three-method input (Green Button OAuth, PDF upload,
// manual entry) with a right-hand load-profile preview. Manual is the
// only fully-wired path for v1; the OAuth and PDF panels render their
// editorial frames + CTAs but don't yet connect to backends.
//
// Visual contract: design/solar-decisions/project/screen-wizard.jsx
// :StepUsage (lines 134–235).

export function StepUsage({
  data,
  setData,
  onBack,
  onNext,
}: {
  data: UsageStep;
  setData: (patch: Partial<UsageStep>) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const valid =
    data.method !== "manual" || (data.kwh > 0 && data.bill > 0);

  return (
    <StepShell
      index={1}
      title="What does your house actually use?"
      sub="The honest math starts here. We can pull a year of hourly data from your utility (Green Button), accept a recent bill, or use a ResStock archetype matched to your home."
      onBack={onBack}
      onNext={onNext}
      nextDisabled={!valid}
    >
      <StepGrid>
        <div className="flex flex-col gap-[22px]">
          <Field label="Method">
            <SegBtn
              value={data.method}
              onChange={(v) => setData({ method: v })}
              options={METHOD_OPTIONS}
            />
          </Field>

          {data.method === "manual" && (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <Field
                label="Annual usage"
                footnote="From any 12-month bill summary."
              >
                <TextInput
                  value={String(data.kwh || "")}
                  onChange={(v) =>
                    setData({ kwh: Number(v.replace(/[^0-9]/g, "")) || 0 })
                  }
                  suffix="kWh / yr"
                  inputMode="numeric"
                />
              </Field>
              <Field label="Avg monthly bill">
                <TextInput
                  value={String(data.bill || "")}
                  onChange={(v) =>
                    setData({
                      bill: Number(v.replace(/[^0-9.]/g, "")) || 0,
                    })
                  }
                  prefix="$"
                  suffix="/ mo"
                  inputMode="decimal"
                />
              </Field>
            </div>
          )}

          {data.method === "pdf" && (
            <Panel className="border-dashed bg-panel-2 text-center">
              <div className="mb-1.5 text-[18px] font-display">
                Drop a recent utility bill
              </div>
              <div className="mb-3.5 text-[13px] text-ink-dim">
                PDF, PNG, or JPG. We extract usage + rate, delete the file
                within 24h.
              </div>
              <Btn kind="ghost">Choose file</Btn>
            </Panel>
          )}

          {data.method === "greenbutton" && (
            <Panel className="bg-panel-2">
              <div className="flex items-center gap-3.5">
                <span
                  aria-hidden="true"
                  className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full bg-accent"
                >
                  <svg
                    width="22"
                    height="22"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="text-accent-ink"
                  >
                    <path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    <path d="M9 12l2 2 4-4" />
                  </svg>
                </span>
                <div>
                  <div className="text-[17px] font-display">
                    Sign in to your utility
                  </div>
                  <div className="text-[12.5px] text-ink-dim">
                    OAuth via DataCustodian.org · we read 13 months of hourly
                    intervals · never write
                  </div>
                </div>
              </div>
              <div className="mt-3.5">
                <Btn kind="primary">Connect utility →</Btn>
              </div>
            </Panel>
          )}

          <Field
            label="Major loads coming"
            hint="optional, big-impact"
            footnote="Heat-pump and EV adoption can double your kWh — your future system size should know."
          >
            <ChipGroup
              ariaLabel="Major loads coming"
              options={UPCOMING_LOADS}
              value={data.upcoming}
              onChange={(next) => setData({ upcoming: next })}
            />
          </Field>
        </div>
        <Panel className="bg-panel-2">
          <MonoLabel>Your load profile</MonoLabel>
          <div className="mt-3.5">
            <MonthlyBars data={SAMPLE_PROFILE} />
          </div>
          <div className="mt-3.5 flex flex-col gap-3">
            <DetectRow
              label="Annual"
              value={`${(data.kwh || 0).toLocaleString()} kWh`}
            />
            <DetectRow
              label="Peak month"
              value="July (1,180 kWh)"
              sub="A/C-driven"
            />
            <DetectRow
              label="Archetype"
              value="ResStock 2400 ft²"
              sub="gas heat · CZ5B"
            />
          </div>
        </Panel>
      </StepGrid>
    </StepShell>
  );
}
