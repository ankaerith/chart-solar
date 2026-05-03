"use client";

import { Field, MonoLabel, Panel, SegBtn, TextInput } from "@/components/ui";
import { Currency } from "@/lib/intl";
import { DetectRow } from "./detect-row";
import { StepGrid, StepShell } from "./step-shell";
import type { FinanceStep } from "./wizard-state";

const METHOD_OPTIONS = [
  { value: "cash" as const, label: "Cash", sub: "best NPV" },
  { value: "loan" as const, label: "Loan", sub: "most common" },
  { value: "lease" as const, label: "Lease", sub: "no upfront" },
  { value: "ppa" as const, label: "PPA", sub: "$/kWh deal" },
];

const TERM_OPTIONS = [
  { value: "10" as const, label: "10 yr" },
  { value: "15" as const, label: "15 yr" },
  { value: "20" as const, label: "20 yr" },
  { value: "25" as const, label: "25 yr" },
];

const DEALER_FEE_OPTIONS = [
  { value: "no" as const, label: "Not disclosed", sub: "we estimate ~22%" },
  { value: "yes" as const, label: "Disclosed", sub: "enter %" },
  { value: "zero" as const, label: "No fee", sub: "rare" },
];

const ESCALATOR_OPTIONS = [
  { value: "0" as const, label: "0%" },
  { value: "1.9" as const, label: "1.9%" },
  { value: "2.9" as const, label: "2.9%" },
  { value: "3.9" as const, label: "3.9%" },
];

const DISCOUNT_OPTIONS = [
  { value: "4.5" as const, label: "4.5%", sub: "HYSA" },
  { value: "5.5" as const, label: "5.5%", sub: "mortgage" },
  { value: "7" as const, label: "7.0%", sub: "S&P long-run" },
  { value: "custom" as const, label: "Custom" },
];

// design ref · screen-wizard.jsx:StepFinance (377–455)
// Discount-rate is on this step on purpose — HYSA / mortgage / S&P
// comparators belong next to the upfront, not on a later screen.

export function StepFinance({
  data,
  setData,
  onBack,
  onNext,
  isSubmitting,
}: {
  data: FinanceStep;
  setData: (patch: Partial<FinanceStep>) => void;
  onBack: () => void;
  onNext: () => void;
  isSubmitting?: boolean;
}) {
  const upfront = data.method === "cash" ? 28400 : 0;

  return (
    <StepShell
      index={4}
      title="Cash, loan, or lease?"
      sub="The financing wrapper changes the math more than panel brand ever will. We model dealer fees, escalators, and assumability — the things installers don't volunteer."
      onBack={onBack}
      onNext={onNext}
      nextLabel={isSubmitting ? "Running…" : "See my forecast"}
      nextDisabled={isSubmitting}
    >
      <StepGrid>
        <div className="flex flex-col gap-[22px]">
          <Field label="Method">
            <SegBtn
              value={data.method}
              onChange={(v) => setData({ method: v })}
              options={METHOD_OPTIONS}
              columns={4}
            />
          </Field>

          {data.method === "loan" && (
            <>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Field label="Loan term">
                  <SegBtn
                    value={data.term}
                    onChange={(v) => setData({ term: v })}
                    options={TERM_OPTIONS}
                  />
                </Field>
                <Field label="Stated APR">
                  <TextInput
                    value={data.apr}
                    onChange={(v) => setData({ apr: v })}
                    suffix="% APR"
                    inputMode="decimal"
                  />
                </Field>
              </div>
              <Field
                label="Dealer fee disclosed?"
                hint="critical input"
                footnote="Solar loans typically embed 20–30% fees in the system price. A '3.99% APR' loan with a 25% dealer fee has an effective real cost of capital of 8–10%. We surface the actual cost."
              >
                <SegBtn
                  value={data.dealerFee}
                  onChange={(v) => setData({ dealerFee: v })}
                  options={DEALER_FEE_OPTIONS}
                />
              </Field>
            </>
          )}

          {data.method === "lease" && (
            <Field
              label="Escalator"
              footnote="Industry standard is 2.9%. Anything above 3.5% is aggressive — flagged as a potential audit issue."
            >
              <SegBtn
                value={data.escalator}
                onChange={(v) => setData({ escalator: v })}
                options={ESCALATOR_OPTIONS}
              />
            </Field>
          )}

          <Field
            label="Discount rate"
            hint="opportunity cost"
            footnote="What could your capital have done instead? Pick a benchmark — your mortgage APR, a HYSA, or long-run equity returns."
          >
            <SegBtn
              value={data.discount}
              onChange={(v) => setData({ discount: v })}
              options={DISCOUNT_OPTIONS}
            />
          </Field>
        </div>
        <Panel className="bg-panel-2">
          <MonoLabel>Estimated upfront</MonoLabel>
          <div className="mt-2.5 font-display text-[44px] leading-none">
            <Currency value={upfront} className="font-display" />
          </div>
          <div className="mt-1.5 text-[12px] text-ink-dim">
            {data.method === "cash" && (
              <>
                Net of <Currency value={0} /> federal credit (post-2025) +{" "}
                <Currency value={4250} /> state rebate.
              </>
            )}
            {data.method === "loan" && (
              <>
                <Currency value={0} /> down. Loan principal ~
                <Currency value={28400} />. Effective APR after dealer fee:
                8.2%.
              </>
            )}
            {data.method === "lease" && (
              <>
                <Currency value={0} /> down. Year-1 lease payment ~
                <Currency value={118} />/mo. Title stays with installer.
              </>
            )}
            {data.method === "ppa" && (
              <>
                <Currency value={0} /> down. Per-kWh purchase,{" "}
                <Currency
                  value={0.078}
                  options={{
                    minimumFractionDigits: 3,
                    maximumFractionDigits: 3,
                  }}
                />
                /kWh year 1, escalator applies.
              </>
            )}
          </div>
          <div className="mt-4 flex flex-col gap-3">
            <DetectRow
              label="Gross system"
              value={<Currency value={32650} />}
              sub={
                <>
                  <Currency
                    value={3.2}
                    options={{
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    }}
                  />
                  /W · regional median
                </>
              }
            />
            <DetectRow
              label="State + utility"
              value={<Currency value={-4250} />}
              sub="rebates · DSIRE-verified"
            />
            <DetectRow label="Net cost" value={<Currency value={28400} />} />
            {data.method === "loan" && (
              <DetectRow
                label="Effective COC"
                value="8.2%"
                sub="incl. ~22% dealer fee est"
              />
            )}
          </div>
        </Panel>
      </StepGrid>
    </StepShell>
  );
}
