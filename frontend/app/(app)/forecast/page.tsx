import type { Metadata } from "next";
import { WizardShell } from "@/components/wizard";

// /forecast — the 5-step Explore wizard (Address → Usage → Roof →
// Battery → Financing). Anonymous-friendly: no signup gate, state
// lives in memory until submit. CTA on Step 5 POSTs to the mock
// endpoint and routes to /forecast/[id]. The auth-gated persistence
// (saved-forecast modal + Postgres migration) lands separately under
// the auth epic.

export const metadata: Metadata = {
  title: "Run my forecast — Chart Solar",
  description:
    "Plan a solar install in 5 steps. Honest math, no installers in the loop.",
  robots: { index: false, follow: false },
};

export default function ForecastPage() {
  return <WizardShell />;
}
