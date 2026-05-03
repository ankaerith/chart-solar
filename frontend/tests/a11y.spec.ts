import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// Baseline accessibility sweep. Runs axe-core against every critical
// path and fails on WCAG 2.1 AA violations. Routes that do not exist
// yet (wizard / results / audit / pricing / methodology / notes …)
// land here as later beads ship them; the sweep stays narrow until
// then to keep CI honest.
//
// Per the bead (chart-solar-aqs), full WCAG 2.1 AA coverage lives in
// the QA epic — this is the foundational gate that catches landing-
// time regressions.

const ROUTES = [
  { path: "/", name: "landing" },
  { path: "/forecast", name: "wizard-step-1" },
  { path: "/forecast/mock-1abc", name: "results" },
] as const;

for (const { path, name } of ROUTES) {
  test(`${name} (${path}) has no axe-detectable WCAG 2.1 AA violations`, async ({
    page,
  }) => {
    await page.goto(path);
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    expect(
      results.violations,
      `axe violations on ${path}:\n${JSON.stringify(results.violations, null, 2)}`,
    ).toEqual([]);
  });
}
