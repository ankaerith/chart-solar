"use client";

import type { ReactNode } from "react";
import { Arrow } from "@/components/icons";
import { Btn, Eyebrow } from "@/components/ui";
import { STEPS } from "./wizard-state";

// design ref · screen-wizard.jsx:StepShell (44–71)

export function StepShell({
  index,
  title,
  sub,
  children,
  onBack,
  onNext,
  nextLabel = "Continue",
  onSkip,
  nextDisabled,
}: {
  index: number;
  title: string;
  sub?: ReactNode;
  children: ReactNode;
  onBack: () => void;
  onNext: () => void;
  nextLabel?: string;
  onSkip?: () => void;
  nextDisabled?: boolean;
}) {
  const step = STEPS[index];
  return (
    <div className="mx-auto w-full max-w-[1080px] px-10 pt-10 pb-20">
      <Eyebrow>
        Step {step.n} · {step.label}
      </Eyebrow>
      <h1 className="mt-1 mb-3 text-[clamp(32px,4vw,52px)] leading-[1.05] font-display text-balance">
        {title}
      </h1>
      {sub && (
        <p className="mb-8 max-w-[680px] text-[16px] leading-[1.55] text-ink-2">
          {sub}
        </p>
      )}
      <div className="mt-6">{children}</div>
      <div className="mt-10 flex flex-wrap items-center justify-between gap-3">
        <Btn kind="ghost" onClick={onBack}>
          ← Back
        </Btn>
        <div className="flex items-center gap-3">
          {onSkip && (
            <button
              type="button"
              onClick={onSkip}
              className="cursor-pointer bg-transparent text-[13px] text-ink-dim underline underline-offset-[3px] hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:rounded-sm"
            >
              Skip — use defaults
            </button>
          )}
          <Btn kind="primary" onClick={onNext} disabled={nextDisabled}>
            {nextLabel} <Arrow />
          </Btn>
        </div>
      </div>
    </div>
  );
}

// Two-column form/preview grid used inside every step body. Left column
// is the input column (~1.4fr), right is the preview Panel (~1fr).
// Stacks at the small breakpoint so the wizard stays usable on phones.
export function StepGrid({ children }: { children: ReactNode }) {
  return (
    <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
      {children}
    </div>
  );
}
