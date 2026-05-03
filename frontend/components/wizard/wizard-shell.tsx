"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { Wordmark } from "@/components/icons";
import { runMockForecast, type ForecastResultMock } from "@/lib/api/forecast";
import { StepAddress } from "./step-address";
import { StepBattery } from "./step-battery";
import { StepFinance } from "./step-finance";
import { StepRoof } from "./step-roof";
import { StepUsage } from "./step-usage";
import { Stepper } from "./stepper";
import {
  DEFAULT_WIZARD_STATE,
  STEPS,
  type WizardState,
} from "./wizard-state";

const LAST_STEP = STEPS.length - 1;

export function WizardShell() {
  const router = useRouter();
  const [state, setState] = useState<WizardState>(DEFAULT_WIZARD_STATE);
  const [index, setIndex] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // One stable patcher per step key so step components don't see a new
  // setData callback on every WizardShell render — opens the door to
  // React.memo on individual steps later.
  const patchAddress = useCallback(
    (next: Partial<WizardState["address"]>) =>
      setState((prev) => ({ ...prev, address: { ...prev.address, ...next } })),
    [],
  );
  const patchUsage = useCallback(
    (next: Partial<WizardState["usage"]>) =>
      setState((prev) => ({ ...prev, usage: { ...prev.usage, ...next } })),
    [],
  );
  const patchRoof = useCallback(
    (next: Partial<WizardState["roof"]>) =>
      setState((prev) => ({ ...prev, roof: { ...prev.roof, ...next } })),
    [],
  );
  const patchBattery = useCallback(
    (next: Partial<WizardState["battery"]>) =>
      setState((prev) => ({ ...prev, battery: { ...prev.battery, ...next } })),
    [],
  );
  const patchFinance = useCallback(
    (next: Partial<WizardState["finance"]>) =>
      setState((prev) => ({ ...prev, finance: { ...prev.finance, ...next } })),
    [],
  );

  const back = () => {
    if (index > 0) {
      setIndex((i) => i - 1);
    } else {
      router.push("/");
    }
  };

  const next = () => {
    if (index < LAST_STEP) {
      setIndex((i) => i + 1);
      return;
    }
    void submit();
  };

  async function submit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const result: ForecastResultMock = await runMockForecast(state);
      router.push(`/forecast/${result.id}`);
    } catch (err) {
      setSubmitError(
        err instanceof Error
          ? err.message
          : "Forecast failed. Try again in a moment.",
      );
      setSubmitting(false);
    }
  }

  function jump(targetIndex: number) {
    if (targetIndex < index) setIndex(targetIndex);
  }

  return (
    <div className="min-h-screen">
      <nav className="flex flex-wrap items-center justify-between gap-4 border-b border-rule bg-bg px-10 py-5">
        <button
          type="button"
          onClick={() => router.push("/")}
          aria-label="Chart Solar — exit wizard"
          className="cursor-pointer rounded-sm bg-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
        >
          <Wordmark />
        </button>
        <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-dim">
          Explore · free · no signup
        </div>
        <button
          type="button"
          onClick={() => router.push("/")}
          className="cursor-pointer bg-transparent text-[13px] text-ink-dim hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:rounded-sm"
        >
          Save & exit ✕
        </button>
      </nav>
      <Stepper index={index} onJump={jump} />

      {index === 0 && (
        <StepAddress
          data={state.address}
          setData={patchAddress}
          onBack={back}
          onNext={next}
        />
      )}
      {index === 1 && (
        <StepUsage
          data={state.usage}
          setData={patchUsage}
          onBack={back}
          onNext={next}
        />
      )}
      {index === 2 && (
        <StepRoof
          data={state.roof}
          setData={patchRoof}
          usage={state.usage}
          onBack={back}
          onNext={next}
        />
      )}
      {index === 3 && (
        <StepBattery
          data={state.battery}
          setData={patchBattery}
          onBack={back}
          onNext={next}
          onSkip={() => {
            patchBattery({ include: false });
            setIndex(LAST_STEP);
          }}
        />
      )}
      {index === 4 && (
        <StepFinance
          data={state.finance}
          setData={patchFinance}
          onBack={back}
          onNext={next}
          isSubmitting={submitting}
        />
      )}

      {submitError && (
        <div
          role="alert"
          className="mx-auto mb-10 max-w-[1080px] rounded-md border border-bad bg-bad/10 px-5 py-3 text-[13px] text-bad"
        >
          {submitError}
        </div>
      )}
    </div>
  );
}
