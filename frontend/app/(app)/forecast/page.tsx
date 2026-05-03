import type { Metadata } from "next";
import { WizardShell } from "@/components/wizard";

export const metadata: Metadata = {
  title: "Run my forecast — Chart Solar",
  description:
    "Plan a solar install in 5 steps. Honest math, no installers in the loop.",
  robots: { index: false, follow: false },
};

export default function ForecastPage() {
  return <WizardShell />;
}
