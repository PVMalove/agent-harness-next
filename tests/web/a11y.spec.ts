/* WCAG 2.1 AA in the real build (#1066): axe-core finds no violation on the shell and Home, the
   skip link is the first Tab stop, and a tab list follows the WAI-ARIA Tabs pattern with the
   arrow keys. The page sweep over every section lives in pages.spec.ts. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const base = () => process.env.CONSOLE_BASE_URL!;
const HOME = JSON.parse(readFileSync(resolve(__dirname, "fixtures/home-snapshot.json"), "utf-8")) as unknown;

async function mockHome(page: Page) {
  await page.routeWebSocket("**/ws", (ws) => {
    ws.onMessage((message) => {
      const request = JSON.parse(String(message)) as { id: string; type: string };
      if (request.type === "home.snapshot") {
        ws.send(JSON.stringify({ v: 1, id: request.id, type: "home.snapshot", ok: true, cached: false, age_seconds: 0, snapshot: HOME }));
      }
    });
  });
}

export async function axeViolations(page: Page) {
  const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  return result.violations.map((violation) => `${violation.id}: ${violation.nodes.map((node) => node.target.join(" ")).slice(0, 3).join(", ")}`);
}

test("Home and the shell have no WCAG 2.1 AA violation", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await mockHome(page);
  await page.goto(`${base()}/#/`);
  await expect(page.locator("#health-ok")).toHaveText("42");
  expect(await axeViolations(page)).toEqual([]);
});

test("the skip link is the first Tab stop and focuses the page content", async ({ page }) => {
  await mockHome(page);
  await page.goto(`${base()}/#/diagnostics`);
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Перейти к содержимому" });
  await expect(skip).toBeFocused();
  await expect(skip).toBeInViewport();
  await page.keyboard.press("Enter");
  await expect(page.locator("main#content")).toBeFocused();
  expect(page.url()).toContain("#/diagnostics");
});

test("tabs move with the arrow keys and every tab controls an existing panel", async ({ page }) => {
  await mockHome(page);
  await page.goto(`${base()}/#/harness`);
  const tabs = page.getByRole("tablist").first().getByRole("tab");
  await expect(tabs.first()).toHaveAttribute("aria-selected", "true");
  await tabs.first().focus();
  await page.keyboard.press("ArrowRight");
  await expect(tabs.nth(1)).toBeFocused();
  await expect(tabs.nth(1)).toHaveAttribute("aria-selected", "true");
  for (const id of await tabs.evaluateAll((nodes) => nodes.map((node) => node.getAttribute("aria-controls")))) {
    await expect(page.locator(`[id="${id}"][role="tabpanel"]`)).toHaveCount(1);
  }
});
