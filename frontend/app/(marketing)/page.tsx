import type { Metadata } from "next";
import { Hero, MathRow, ModesStrip } from "@/components/landing";

// design ref · screen-landing.jsx:ScreenLanding (210–222)

export const metadata: Metadata = {
  title: "Chart Solar — the honest math for your roof",
  description:
    "Independent solar forecasting and proposal auditing. Hourly physics, Monte Carlo on rate paths, every alternative your capital could be doing instead. No installer affiliations, no lead-gen.",
};

export default function Home() {
  return (
    <>
      <Hero />
      <ModesStrip />
      <MathRow />
    </>
  );
}
