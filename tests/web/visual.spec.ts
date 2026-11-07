/* Shell and Home at 1440 and 390 px without horizontal overflow, from the fixture snapshot
   through a mocked socket with a frozen clock. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const base = () => process.env.CONSOLE_BASE_URL!;
const FIXTURE = JSON.parse(readFileSync(resolve(__dirname, "fixtures/home-snapshot.json"), "utf-8")) as unknown;

async function open(page: Page, width: number, route: string) {
  await page.setViewportSize({ width, height: width > 600 ? 900 : 844 });
  await page.clock.setFixedTime(new Date("2026-11-05T10:41:00Z"));
  await page.routeWebSocket("**/ws", (ws) => {
    ws.onMessage((message) => {
      const request = JSON.parse(String(message)) as { id: string; type: string };
      if (request.type === "home.snapshot") {
        ws.send(
          JSON.stringify({ v: 1, id: request.id, type: "home.snapshot", ok: true, cached: true, age_seconds: 3, snapshot: FIXTURE }),
        );
      }
    });
  });
  await page.goto(`${base()}/#/${route}`);
  await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "connected");
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
}

for (const width of [1440, 390]) {
  test(`shell at ${width} px`, async ({ page }) => {
    // A section the web console does not show yet: the shell around its placeholder.
    await open(page, width, "reports");
    if (width < 600) {
      await page.getByRole("button", { name: "Открыть меню" }).click();
      await expect(page.locator("#nav-scrim")).toBeVisible();
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });

  test(`Home at ${width} px`, async ({ page }) => {
    await open(page, width, "");
    await expect(page.locator("#health-ok")).toHaveText("42");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
