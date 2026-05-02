"use client";

import { Field, MonoLabel, Panel, SegBtn, TextInput } from "@/components/ui";
import { Currency } from "@/lib/intl";
import { DetectRow } from "./detect-row";
import { StepGrid, StepShell } from "./step-shell";
import type { AddressStep } from "./wizard-state";

const HOLD_OPTIONS = [
  { value: "5" as const, label: "5 yr", sub: "short" },
  { value: "10" as const, label: "10 yr", sub: "median" },
  { value: "15" as const, label: "15 yr", sub: "long" },
  { value: "25" as const, label: "Lifetime" },
];

// Step 1 — Address. Single TextInput for the street address; on
// resolve the right Panel fills with detected utility, climate zone,
// and net-metering status. The right-hand values are stubbed (the real
// geocoder lives behind a later bead) but the shape mirrors what the
// engine will return so call sites remain stable.
//
// Visual contract: design/solar-decisions/project/screen-wizard.jsx
// :StepAddress (lines 73–120).

export function StepAddress({
  data,
  setData,
  onBack,
  onNext,
}: {
  data: AddressStep;
  setData: (patch: Partial<AddressStep>) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  // Treat any non-empty street address as "resolved" for the mock —
  // good enough to demo the detect column without a geocoder. The real
  // wiring (chart-solar-h8s' geocode integration) will swap this for
  // the actual response shape.
  const resolved = data.address.trim().length > 0;

  return (
    <StepShell
      index={0}
      title="Where's your roof?"
      sub="Address gives us your latitude, climate zone, utility, and tariff schedule. Nothing is shared with installers — there's no installer to share it with."
      onBack={onBack}
      onNext={onNext}
      nextDisabled={!resolved}
    >
      <StepGrid>
        <div className="flex flex-col gap-[22px]">
          <Field label="Street address" hint="US or UK">
            <TextInput
              value={data.address}
              onChange={(v) => setData({ address: v })}
              placeholder="1242 Spruce St, Boulder, CO 80302"
              autoComplete="street-address"
            />
          </Field>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Field label="Utility" hint="auto-detected">
              <TextInput
                value={data.utility}
                onChange={(v) => setData({ utility: v })}
                placeholder="Xcel Energy"
              />
            </Field>
            <Field label="Tariff schedule">
              <TextInput
                value={data.tariff}
                onChange={(v) => setData({ tariff: v })}
                placeholder="RE-TOU residential"
              />
            </Field>
          </div>
          <Field
            label="Hold horizon"
            hint="how long you'll likely own"
            footnote="ZIP-defaulted from US Census mobility data; you can override."
          >
            <SegBtn
              value={data.hold}
              onChange={(v) => setData({ hold: v })}
              options={HOLD_OPTIONS}
            />
          </Field>
        </div>
        <Panel className="bg-panel-2">
          <MonoLabel>Detected for this address</MonoLabel>
          <div className="mt-3.5 flex flex-col gap-3">
            {resolved ? (
              <>
                <DetectRow
                  label="Climate zone"
                  value="Cool, semi-arid (5B)"
                />
                <DetectRow
                  label="Avg ann. irradiance"
                  value="5.6 kWh/m²/day"
                  sub="NREL NSRDB"
                />
                <DetectRow label="Utility" value="Xcel Energy" />
                <DetectRow
                  label="Net-metering"
                  value="NEM (1:1)"
                  sub="not NEM 3.0"
                />
                <DetectRow
                  label="Local incentives"
                  value={
                    <>
                      <Currency
                        value={0.5}
                        options={{
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        }}
                      />
                      /W rebate
                    </>
                  }
                  sub="DSIRE · expires 2027"
                />
              </>
            ) : (
              <p className="text-[12.5px] italic text-ink-dim">
                Type an address to detect utility, tariff, and climate inputs.
              </p>
            )}
          </div>
          <div className="mt-4 border-t border-rule pt-3.5 text-[12px] italic leading-[1.5] text-ink-dim">
            Production model:{" "}
            <span className="font-mono not-italic">
              pvlib-python · NSRDB hourly TMY
            </span>
            . Cached per 1 km bucket; refreshed nightly.
          </div>
        </Panel>
      </StepGrid>
    </StepShell>
  );
}
