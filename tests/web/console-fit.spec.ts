/* Window fit of the screens moved to the design system v3: Help (7 tabs), Harness (5) and Repo Map
   (3) of #1091, Diagnostics (Функции, Проверки), Update (the file tabs Изменения, Решение),
   Project (the five wizard steps), Settings (5 tabs, the JSON file tabs), Orchestration (6 tabs),
   Reports (4) and Publication (4) at five window sizes. Every other tab list on the screen is
   walked in each of these tabs too: the feature detail (Готовность / Конфигурация / Связи) of
   Diagnostics and "how to update" (Режим / Seed / План / Миграция) of Update. In every tab the page does not
   scroll, main does not scroll and the empty strip under the last block is at most 24 px (RFC
   section 5). Diagnostics is measured with a 57-check report, whose list really scrolls inside its
   panel at every size.

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
const FEATURES = read("features-snapshot.json");
const VERSION_ID = "20261116T101500Z-0123456789ab";
const CONFIGURATION: Body = {
  ...read("configuration.json"),
  versions: [{ id: VERSION_ID, created_at: "2026-11-16T10:15:00+00:00", description: "перед QA", files: ["project.json"], package_version: "2.1.0", problem: "" }],
};
const PAGED: Readonly<Record<string, Body>> = {
  "diagnostics.snapshot": read("diagnostics-report-57.json"),
  "update_harness.snapshot": read("update-harness.json"),
  "update_harness.diff": read("update-harness-diff.json"),
  "open_project.snapshot": read("open-project.json"),
  "reports.snapshot": read("reports.json"),
  "orchestration.snapshot": read("orch-snapshot.json"),
  "reports.report": read("reports-report.json"),
  "reports.timeline": read("reports-timeline.json"),
};
/** Paged replies the server sends without cache facts. */
const UNCACHED = new Set(["update_harness.diff", "reports.report", "reports.timeline"]);

const SIZES: readonly [number, number][] = [[1920, 1080], [1920, 1010], [1920, 950], [1680, 950], [1440, 900]];
/** Route and the number of tabs the design promises. */
const SCREENS: readonly [route: string, tabs: number][] = [
  ["help", 7],
  ["harness", 5],
  ["repo-map", 3],
  ["diagnostics", 2],
  ["update-harness", 2],
  ["open-project", 5],
  ["configuration", 5],
  ["orchestration", 6],
  ["reports", 4],
  ["publish", 4],
];
/** Route -> the tab lists inside its tabs (aria-label) and their tab counts. */
const NESTED: Readonly<Record<string, Readonly<Record<string, number>>>> = {
  diagnostics: { Функция: 3 },
  "update-harness": { "Как обновить": 4 },
  configuration: { Файл: 2 },
};
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
      else if (type === "features.snapshot") send(ws, { id, type, ...FEATURES });
      else if (type === "configuration.snapshot")
        paged(ws, id, type, request.version ? { ...CONFIGURATION, version: { id: VERSION_ID, error: "", files: CONFIGURATION.files } } : CONFIGURATION);
      else if (typeof type === "string" && type in PAGED) paged(ws, id, type, PAGED[type], UNCACHED.has(type) ? { cached: undefined, age_seconds: undefined } : {});
      else if (type === "decisions.snapshot") send(ws, { id, type, snapshot: { version: 1, items: [], total: 0, unavailable: false } });
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
  /** Elements whose content is cut or only reachable by an inner scroll (class and path). */
  clipped: string[];
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
    // A box whose content is taller than the box and whose overflow is not visible hides data: the
    // content is cut or sits behind an inner scroll. Only the long lists of the RFC (section 5) may
    // do that and they carry data-scroll (Panel `scroll`). Visually hidden text (.ds-sr) is not content.
    const clipped: string[] = [];
    for (const element of main.querySelectorAll<HTMLElement>("*")) {
      if (element.closest("[data-scroll], [hidden], svg, .ds-sr")) continue;
      const style = getComputedStyle(element);
      if (style.display === "none" || style.display === "contents" || element.clientHeight === 0) continue;
      if (style.overflowY === "visible") continue;
      if (element.scrollHeight > element.clientHeight + 1) {
        const id = element.id ? `#${element.id}` : "";
        const label = element.closest<HTMLElement>(".ds-panel")?.querySelector(".ds-panel-title")?.textContent ?? "";
        clipped.push(`${element.tagName.toLowerCase()}${id}.${String(element.className).trim().split(/\s+/).join(".")} [${label}] ${element.scrollHeight}>${element.clientHeight}`);
      }
    }
    return {
      pageScrolls: root.scrollHeight > innerHeight,
      mainScrolls: main.scrollHeight > main.clientHeight,
      strip: Math.round(box.bottom - bottom),
      clipped,
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
      const topId = await page.locator("main#content [role=tablist]").first().getAttribute("id");
      const size = `${width}x${height}`;
      const fits: Fit[] = [];
      const nested: Record<string, number> = {};
      const check = async (name: string, tabCount: number) => {
        await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
        const fit = await measure(page);
        fits.push({ route, tab: name, size, tabs: tabCount, ...fit });
        expect.soft(fit.pageScrolls, `${route}/${name} ${size}: the page scrolls`).toBe(false);
        expect.soft(fit.mainScrolls, `${route}/${name} ${size}: main scrolls`).toBe(false);
        expect.soft(fit.strip, `${route}/${name} ${size}: empty strip under the last block`).toBeLessThanOrEqual(MAX_STRIP);
        expect.soft(fit.clipped, `${route}/${name} ${size}: content cut off or behind an inner scroll`).toEqual([]);
      };
      for (let index = 0; index < count; index++) {
        await tabs.nth(index).click();
        const name = ((await tabs.nth(index).textContent()) ?? "").trim();
        await check(name, count);
        if (OUT && index === 0) {
          mkdirSync(OUT, { recursive: true });
          await page.screenshot({ path: resolve(OUT, `${route}-${size}.png`) });
        }
        // The other tab lists shown in this tab: every one of their tabs is measured as well.
        const inner = page.locator(`main#content [role=tablist]:visible:not([id="${topId}"])`);
        for (let list = 0; list < (await inner.count()); list++) {
          const label = (await inner.nth(list).getAttribute("aria-label")) ?? "";
          const innerTabs = inner.nth(list).getByRole("tab");
          const innerCount = await innerTabs.count();
          nested[label] = innerCount;
          for (let item = 0; item < innerCount; item++) {
            await innerTabs.nth(item).click();
            await check(`${name} › ${label} › ${((await innerTabs.nth(item).textContent()) ?? "").trim()}`, innerCount);
          }
        }
      }
      record(fits);
      expect.soft(count, `${route}: tab count`).toBe(expectedTabs);
      expect.soft(nested, `${route}: tab lists inside the tabs`).toEqual(NESTED[route] ?? {});
    });
  }
}

test("harness at 390x800: the grids collapse to one column and a label shares its row with the value", async ({ page }) => {
  await mockSocket(page);
  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto(`${base()}/#/harness`);
  await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "connected");
  const tracks = (selector: string) =>
    page.locator(selector).first().evaluate((element) => getComputedStyle(element).gridTemplateColumns.split(" ").length);
  await expect(page.locator(".ds-loop").first()).toBeVisible({ timeout: 20000 });
  expect(await tracks(".ds-overview-top"), ".ds-overview-top tracks").toBe(1);
  expect(await tracks(".ds-loop"), ".ds-loop tracks").toBe(1);
  await page.getByRole("tab", { name: /Runtime/ }).click();
  const pairs = await page.locator("#harness-runtime .ds-kv dt").evaluateAll((labels) =>
    labels.map((label) => ({ label: label.textContent, label_top: Math.round(label.getBoundingClientRect().top), value_top: Math.round(label.nextElementSibling!.getBoundingClientRect().top) })),
  );
  expect(pairs.length).toBeGreaterThan(0);
  for (const pair of pairs) expect(Math.abs(pair.value_top - pair.label_top), `${pair.label}: value on the label's row`).toBeLessThanOrEqual(2);
  await page.setViewportSize({ width: 1440, height: 900 });
  const wide = await page.locator("#harness-runtime .ds-kv").evaluate((list) => getComputedStyle(list).gridTemplateColumns.split(" ").length);
  expect(wide, "a two-column list of pairs").toBe(2);
});

/** Whether the body of the panel `selector` scrolls inside it while the page and main do not. */
const innerScroll = (page: Page, selector: string) =>
  page.locator(selector).evaluate((panel) => {
    const body = panel.querySelector<HTMLElement>(".ds-panel-body")!;
    const main = document.querySelector<HTMLElement>("main#content")!;
    return {
      scrolls: body.scrollHeight > body.clientHeight,
      overflow: getComputedStyle(body).overflowY,
      pageScrolls: document.scrollingElement!.scrollHeight > innerHeight,
      mainScrolls: main.scrollHeight > main.clientHeight,
    };
  });
const SCROLLS_INSIDE = { scrolls: true, overflow: "auto", pageScrolls: false, mainScrolls: false };

test("diagnostics: the 26-feature list scrolls inside its panel at 1440x900", async ({ page }) => {
  await mockSocket(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${base()}/#/diagnostics`);
  await expect(page.locator("#features-list [data-feature]")).toHaveCount(26, { timeout: 20000 });
  expect(await innerScroll(page, "#features-list")).toEqual(SCROLLS_INSIDE);
});

for (const [width, height] of SIZES) {
  test(`diagnostics: the 57-check list scrolls inside its panel at ${width}x${height}`, async ({ page }) => {
    await mockSocket(page);
    await page.setViewportSize({ width, height });
    await page.goto(`${base()}/#/diagnostics`);
    await expect(page.locator("#features-list [data-feature]")).toHaveCount(26, { timeout: 20000 });
    await page.getByRole("tab", { name: /Проверки/ }).click();
    await expect(page.locator("#diag-list [data-check]")).toHaveCount(57);
    expect(await innerScroll(page, "#diag-checks")).toEqual(SCROLLS_INSIDE);
  });
}
