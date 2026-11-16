/* WCAG 2.1 AA in the real build (#1066): axe-core finds no violation on the shell and Home, the
   skip link is the first Tab stop, and a tab list follows the WAI-ARIA Tabs pattern with the
   arrow keys. Diagnostics, Update and Project are checked at the five window sizes of
   console-fit.spec.ts in every tab and every inner tab (the feature detail, "how to update").
   The page sweep over every section lives in pages.spec.ts. */
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

const fixture = (name: string) => JSON.parse(readFileSync(resolve(__dirname, "fixtures", name), "utf-8")) as Record<string, unknown>;
const PAGED: Readonly<Record<string, unknown>> = {
  "diagnostics.snapshot": fixture("diagnostics-report.json"),
  "update_harness.snapshot": fixture("update-harness.json"),
  "update_harness.diff": fixture("update-harness-diff.json"),
  "open_project.snapshot": fixture("open-project.json"),
};

/** Home, the feature registry and the paged snapshots of Diagnostics, Update and Project. */
async function mockScreens(page: Page) {
  await page.routeWebSocket("**/ws", (ws) => {
    ws.onMessage((message) => {
      const { id, type } = JSON.parse(String(message)) as { id: string; type: string };
      const send = (body: Record<string, unknown>) => ws.send(JSON.stringify({ v: 1, id, type, ok: true, ...body }));
      if (type === "home.snapshot") send({ cached: false, age_seconds: 0, snapshot: HOME });
      else if (type === "features.snapshot") send(fixture("features-snapshot.json"));
      else if (type in PAGED) {
        const text = JSON.stringify(PAGED[type]);
        send({ snapshot_id: 1, text, next: text.length, done: true, ...(type === "update_harness.diff" ? {} : { cached: false, age_seconds: 0 }) });
      } else if (type === "job.catalog") send({ commands: [], cancel_reason: "" });
      else if (type === "job.list") send({ jobs: [] });
    });
  });
}

const SIZES: readonly [number, number][] = [[1920, 1080], [1920, 1010], [1920, 950], [1680, 950], [1440, 900]];
/** Route -> the tab lists inside its tabs (aria-label) the sweep must reach. */
const NESTED: Readonly<Record<string, readonly string[]>> = {
  diagnostics: ["Функция"],
  "update-harness": ["Как обновить"],
  "open-project": [],
};

for (const [route, ready] of [
  ["diagnostics", "#features-list [data-feature]"],
  ["update-harness", "#update-diff .ds-diff-file"],
  ["open-project", "#open-project-list .project-row"],
] as const) {
  for (const [width, height] of SIZES) {
    test(`${route} at ${width}x${height} has no WCAG 2.1 AA violation in any of its tabs and inner tabs`, async ({ page }) => {
      await page.setViewportSize({ width, height });
      await mockScreens(page);
      await page.goto(`${base()}/#/${route}`);
      await expect(page.locator(ready).first()).toBeVisible({ timeout: 20000 });
      const tabs = page.locator("main#content [role=tablist]").first().getByRole("tab");
      const topId = await page.locator("main#content [role=tablist]").first().getAttribute("id");
      const reached = new Set<string>();
      for (let index = 0; index < (await tabs.count()); index++) {
        await tabs.nth(index).click();
        expect(await axeViolations(page), `${route} tab ${index + 1}`).toEqual([]);
        const inner = page.locator(`main#content [role=tablist]:visible:not([id="${topId}"])`);
        for (let list = 0; list < (await inner.count()); list++) {
          const label = (await inner.nth(list).getAttribute("aria-label")) ?? "";
          reached.add(label);
          const innerTabs = inner.nth(list).getByRole("tab");
          for (let item = 0; item < (await innerTabs.count()); item++) {
            await innerTabs.nth(item).click();
            expect(await axeViolations(page), `${route} tab ${index + 1} › ${label} ${item + 1}`).toEqual([]);
          }
        }
      }
      expect([...reached].sort()).toEqual([...NESTED[route]].sort());
    });
  }
}
