/* Window fit of the three screens moved to the design system v3 (#1091): Help (7 tabs), Harness
   (5) and Repo Map (3) at five window sizes. In every tab the page does not scroll, main does not
   scroll and the empty strip under the last block is at most 24 px (RFC section 5).

   Measurement mode: with CONSOLE_FIT_OUT=<dir> the spec writes fit-measurements.json and one PNG
   per screen and size there (the before/after evidence of the slice). Fixtures only, over a
   mocked socket, so the numbers do not depend on the machine's project. */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { Page, WebSocketRoute } from "@playwright/test";

type Body = Record<string, unknown>;

const base = () => process.env.CONSOLE_BASE_URL!;
const OUT = process.env.CONSOLE_FIT_OUT;
const read = (name: string) => JSON.parse(readFileSync(resolve(__dirname, "fixtures", name), "utf-8")) as Body;
const HOME = read("home-snapshot.json");
const OVERVIEW = read("harness-overview.json");
const MAINTENANCE = read("harness-maintenance.json");
const CATALOG = read("job-catalog.json");
const REPO_MAP = read("repo-map.json");
const HELP = read("help-ru.json");

const SIZES: readonly [number, number][] = [[1920, 1080], [1920, 1010], [1920, 950], [1680, 950], [1440, 900]];
/** Route and the number of tabs the design promises. */
const SCREENS: readonly [route: string, tabs: number][] = [["help", 7], ["harness", 5], ["repo-map", 3]];
const MAX_STRIP = 24;

const send = (ws: WebSocketRoute, body: Body) => ws.send(JSON.stringify({ v: 1, ok: true, ...body }));
const paged = (ws: WebSocketRoute, id: unknown, type: unknown, payload: unknown, extra: Body = {}) => {
  const text = JSON.stringify(payload);
  send(ws, { id, type, snapshot_id: 1, text, next: text.length, done: true, cached: true, age_seconds: 3, ...extra });
};

async function mockSocket(page: Page) {
  await page.routeWebSocket("**/ws", (ws) => {
    ws.onMessage((message) => {
      const request = JSON.parse(String(message)) as Body;
      const { id, type } = request;
      if (type === "home.snapshot") send(ws, { id, type, cached: true, age_seconds: 3, snapshot: HOME });
      else if (type === "harness.overview") send(ws, { id, type, cached: true, age_seconds: 3, ...OVERVIEW });
      else if (type === "harness.maintenance") paged(ws, id, type, MAINTENANCE);
      else if (type === "repo_map.snapshot") paged(ws, id, type, REPO_MAP);
      else if (type === "help.snapshot") paged(ws, id, type, HELP);
      else if (type === "job.catalog") send(ws, { id, type, ...CATALOG });
      else if (type === "job.list") send(ws, { id, type, jobs: [] });
    });
  });
}

interface Fit {
  route: string;
  tab: string;
  size: string;
  pageScrolls: boolean;
  mainScrolls: boolean;
  strip: number;
  tabs: number;
}

/** Merges the measurements of one test into fit-measurements.json: a failed test restarts the
    worker, so the file, not module state, carries the run. */
function record(fits: Fit[]) {
  if (!OUT) return;
  mkdirSync(OUT, { recursive: true });
  const file = resolve(OUT, "fit-measurements.json");
  const old: Fit[] = existsSync(file) ? (JSON.parse(readFileSync(file, "utf-8")) as Fit[]) : [];
  const key = (fit: Fit) => `${fit.route}|${fit.size}|${fit.tab}`;
  const fresh = new Set(fits.map(key));
  writeFileSync(file, JSON.stringify([...old.filter((fit) => !fresh.has(key(fit))), ...fits], null, 2));
}

/** The blocks of a screen: panels, the summary, toolbars, notices and the tab bar. The strip is the
    distance from the lower edge of the lowest block to the lower edge of main. */
const BLOCKS = ".ds-panel, .ds-summary, .ds-toolbar, .ds-alert, .ds-pipe, .ds-page-head, .ds-note";

async function measure(page: Page) {
  return page.evaluate((blocks) => {
    const main = document.querySelector<HTMLElement>("main#content")!;
    const root = document.scrollingElement!;
    const box = main.getBoundingClientRect();
    let bottom = box.top;
    for (const element of main.querySelectorAll<HTMLElement>(blocks)) {
      const rect = element.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0 || rect.bottom > box.bottom + 1) continue;
      bottom = Math.max(bottom, rect.bottom);
    }
    return {
      pageScrolls: root.scrollHeight > innerHeight,
      mainScrolls: main.scrollHeight > main.clientHeight,
      strip: Math.round(box.bottom - bottom),
    };
  }, BLOCKS);
}

for (const [route, expectedTabs] of SCREENS) {
  for (const [width, height] of SIZES) {
    test(`${route} fits ${width}x${height} in every tab`, async ({ page }) => {
      await mockSocket(page);
      await page.setViewportSize({ width, height });
      await page.goto(`${base()}/#/${route}`);
      await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "connected");
      const tabs = page.locator("main#content [role=tablist]").first().getByRole("tab");
      await expect(tabs.first()).toBeVisible({ timeout: 20000 });
      await page.evaluate(() => document.fonts.ready.then(() => undefined));
      const count = await tabs.count();
      const size = `${width}x${height}`;
      const fits: Fit[] = [];
      for (let index = 0; index < count; index++) {
        await tabs.nth(index).click();
        await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
        const name = ((await tabs.nth(index).textContent()) ?? "").trim();
        const fit = await measure(page);
        fits.push({ route, tab: name, size, tabs: count, ...fit });
        if (OUT && index === 0) {
          mkdirSync(OUT, { recursive: true });
          await page.screenshot({ path: resolve(OUT, `${route}-${size}.png`) });
        }
        expect.soft(fit.pageScrolls, `${route}/${name} ${size}: the page scrolls`).toBe(false);
        expect.soft(fit.mainScrolls, `${route}/${name} ${size}: main scrolls`).toBe(false);
        expect.soft(fit.strip, `${route}/${name} ${size}: empty strip under the last block`).toBeLessThanOrEqual(MAX_STRIP);
      }
      record(fits);
      expect.soft(count, `${route}: tab count`).toBe(expectedTabs);
    });
  }
}
