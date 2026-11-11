/* Page fit at 1440×900 (#1066): Diagnostics, Reports and the Agent activity session list keep
   the page inside the window; the long list scrolls in its own block. Real server, empty project:
   Diagnostics lists every health check, so its list is long. DOM only, no screenshots. */
import { expect, test } from "@playwright/test";

const base = () => process.env.CONSOLE_BASE_URL!;
const token = () => process.env.CONSOLE_TOKEN!;

const PAGES: [route: string, list: string][] = [
  ["diagnostics", "#diag-list"],
  ["agent-activity", ".work-sessions .work-list"],
];

for (const [route, list] of PAGES) {
  test(`${route}: the list scrolls in its block and the page fits 1440×900`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${base()}/?token=${token()}`);
    await page.goto(`${base()}/#/${route}`);
    const block = page.locator(list).first();
    await expect(block).toBeVisible({ timeout: 20000 });
    const facts = await block.evaluate((node) => ({
      overflow: getComputedStyle(node).overflowY,
      bottom: node.getBoundingClientRect().bottom,
    }));
    expect(facts.overflow).toBe("auto");
    expect(facts.bottom).toBeLessThanOrEqual(900);
  });
}
