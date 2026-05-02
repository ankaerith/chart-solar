import { defineConfig, devices } from "@playwright/test";

// Playwright config — used only by `bun run test:a11y` (axe-core sweeps
// across critical paths). Not a general E2E setup; the broader
// Playwright + golden-flow harness lives under `chart-solar-an62`.
//
// `webServer` boots `next start` against the production build, so the
// suite reflects what ships and doesn't depend on dev-mode behaviour.

export default defineConfig({
  testDir: "./tests",
  testMatch: /.*\.spec\.ts/,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: process.env.A11Y_BASE_URL ?? "http://127.0.0.1:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: process.env.A11Y_BASE_URL
    ? undefined
    : {
        command: "bun --bun run start",
        url: "http://127.0.0.1:3000",
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
});
