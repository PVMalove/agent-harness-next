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

  test(`the header items at ${width} px do not overlap`, async ({ page }) => {
    await open(page, width, "");
    // The header's own children and the brand's text: a clipped or hidden-behind item overlaps.
    const overlaps = await page.evaluate(() => {
      const items = [...document.querySelectorAll(".ds-top > *, .ds-top-end > *, .ds-brand > *")].filter((item) => {
        const box = item.getBoundingClientRect();
        return box.width > 0 && getComputedStyle(item).visibility !== "hidden" && !item.classList.contains("ds-top-end") && !item.classList.contains("ds-brand");
      });
      const found: string[] = [];
      items.forEach((a, i) =>
        items.slice(i + 1).forEach((b) => {
          if (a.contains(b) || b.contains(a)) return;
          const [x, y] = [a.getBoundingClientRect(), b.getBoundingClientRect()];
          if (x.left < y.right - 1 && y.left < x.right - 1 && x.top < y.bottom - 1 && y.top < x.bottom - 1) found.push(`${a.id || a.className} × ${b.id || b.className}`);
        }),
      );
      return found;
    });
    expect(overlaps).toEqual([]);
  });
}
