/* Run from harness/console/frontend: `npm run test:e2e` (build first). Chromium only. */
import { resolve } from "node:path";
import { defineConfig } from "@playwright/test";

const FRONTEND = resolve(__dirname, "../../harness/console/frontend");

export default defineConfig({
  testDir: __dirname,
  testMatch: "**/*.spec.ts",
  outputDir: resolve(FRONTEND, "test-results"),
  snapshotPathTemplate: "{testDir}/__screenshots__/{arg}{ext}",
  globalSetup: resolve(__dirname, "global-setup.ts"),
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { outputFolder: resolve(FRONTEND, "playwright-report"), open: "never" }]],
  expect: {
    // The documented screenshot threshold (harness/console/frontend/README.md).
    toHaveScreenshot: { maxDiffPixelRatio: 0.01, threshold: 0.2, animations: "disabled", caret: "hide" },
  },
  use: {
    browserName: "chromium",
    locale: "ru-RU",
    timezoneId: "UTC",
    colorScheme: "dark",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
