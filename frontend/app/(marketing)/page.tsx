import type { Metadata } from "next";
import { Hero, MathRow, ModesStrip } from "@/components/landing";

// Landing — the public homepage. Hero + modes strip + math row.
// SEO surface, server-rendered through the (marketing) layout (which
// adds NavBar + Footer + SunBackdrop chrome).
//
// Visual contract: design/solar-decisions/project/screen-landing.jsx
// :ScreenLanding (lines 210–222).

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
