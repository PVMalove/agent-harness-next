/* Run from harness/console/frontend: `npm run test:e2e` (build first). Chromium only. */
import { resolve } from "node:path";
import { defineConfig } from "@playwright/test";

const FRONTEND = resolve(__dirname, "../../harness/console/frontend");

export default defineConfig({
  testDir: __dirname,
  testMatch: "**/*.spec.ts",
  outputDir: resolve(FRONTEND, "test-results"),
  // Visual baselines live next to the specs: tests/web/__screenshots__/<name>.png.
  snapshotPathTemplate: "{testDir}/__screenshots__/{arg}{ext}",
  globalSetup: resolve(__dirname, "global-setup.ts"),
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { outputFolder: resolve(FRONTEND, "playwright-report"), open: "never" }]],
  use: {
    browserName: "chromium",
    locale: "ru-RU",
    timezoneId: "UTC",
    colorScheme: "dark",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
