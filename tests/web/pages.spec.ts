/* The page sweep of the real build: every menu section at 1440 and 390 px over the recorded
   fixtures has no horizontal overflow and no WCAG 2.1 AA violation found by axe-core, on every tab
   of the page no panel leaves its frame, and under
   prefers-reduced-motion nothing on the live pages animates. DOM assertions only; no screenshot
   comparison (ADR 0029). */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { Page, WebSocketRoute } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

type Body = Record<string, unknown>;

const base = () => process.env.CONSOLE_BASE_URL!;
const read = (name: string) => JSON.parse(readFileSync(resolve(__dirname, "fixtures", name), "utf-8")) as Body;
const HOME = read("home-snapshot.json");
const FEED = read("live-steps.json") as { roster: Body; steps: Body };
const HELP: Readonly<Record<string, Body>> = { ru: read("help-ru.json"), en: read("help-en.json") };
const PAGED: Readonly<Record<string, Body>> = {
  "reports.snapshot": read("reports.json"),
  "reports.report": read("reports-report.json"),
  "reports.timeline": read("reports-timeline.json"),
  "orchestration.snapshot": read("orch-snapshot.json"),
  "diagnostics.snapshot": read("diagnostics-report.json"),
  "harness.maintenance": read("harness-maintenance.json"),
  "repo_map.snapshot": read("repo-map.json"),
  "open_project.snapshot": read("open-project.json"),
  "update_harness.snapshot": read("update-harness.json"),
  "configuration.snapshot": read("configuration.json"),
  "task_board.specs": read("task-board-specs.json"),
  "task_board.snapshot": read("task-board.json"),
};
const OVERVIEW = read("harness-overview.json");

const send = (ws: WebSocketRoute, body: Body) => ws.send(JSON.stringify({ v: 1, ok: true, ...body }));

async function mockSocket(page: Page) {
  await page.routeWebSocket("**/ws", (ws) => {
    ws.onMessage((message) => {
      const request = JSON.parse(String(message)) as Body;
      const id = request.id;
      const type = String(request.type);
      const paged = (value: Body) => {
        const text = JSON.stringify(value);
        send(ws, { id, type, snapshot_id: 1, text, next: text.length, done: true, cached: false, age_seconds: 0 });
      };
      if (type === "home.snapshot") send(ws, { id, type, cached: true, age_seconds: 3, snapshot: HOME });
      else if (type === "help.snapshot") paged(HELP[String(request.language)] ?? HELP.ru!);
      else if (type in PAGED) paged(PAGED[type]!);
      else if (type === "harness.overview") send(ws, { id, type, cached: false, age_seconds: 0, ...OVERVIEW });
      else if (type === "steps.subscribe") {
        send(ws, { id, type, ...FEED.roster });
        send(ws, { id, type, ...FEED.steps });
      } else if (type === "decisions.snapshot") send(ws, { id, type, snapshot: { version: 1, items: [], total: 0, unavailable: false } });
      else if (type === "job.catalog") send(ws, { id, type, commands: [], cancel_reason: "" });
      else if (type === "job.list") send(ws, { id, type, jobs: [] });
    });
  });
}

const ROUTES = [
  "",
  "diagnostics",
  "update-harness",
  "open-project",
  "board",
  "agent-activity",
  "orchestration",
  "reports",
  "publish",
  "harness",
  "repo-map",
  "configuration",
  "help",
];

async function open(page: Page, route: string, width: number) {
  await page.setViewportSize({ width, height: width > 600 ? 900 : 844 });
  await page.goto(`${base()}/#/${route}`);
  await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "connected");
  await expect(page.locator("main#content h1")).toBeVisible();
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
}

async function axeViolations(page: Page) {
  const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  return result.violations.map((violation) => `${violation.id}: ${violation.nodes.map((node) => node.target.join(" ")).slice(0, 3).join(", ")}`);
}

const overflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth - innerWidth);

for (const width of [1440, 390]) {
  for (const route of ROUTES) {
    test(`#/${route} at ${width} px: no horizontal overflow, no axe violation`, async ({ page }) => {
      await mockSocket(page);
      await open(page, route, width);
      expect(await overflow(page)).toBeLessThanOrEqual(0);
      expect(await axeViolations(page)).toEqual([]);
    });
  }
}

/** Panels whose content is wider than the panel itself while the panel does not scroll: a block
    that leaves its frame. A scrolling region (overflow-x auto/scroll) is an intended scroll. */
const leaking = (page: Page) =>
  page.evaluate(() =>
    [...document.querySelectorAll("main .panel, main .ds-panel, main [class*='-kpis']")]
      .filter((element) => {
        const box = element as HTMLElement;
        if (box.offsetParent === null) return false;
        const style = getComputedStyle(box);
        if (style.overflowX === "auto" || style.overflowX === "scroll") return false;
        return box.scrollWidth > box.clientWidth + 1;
      })
      .map((element) => `${element.tagName.toLowerCase()}.${[...element.classList].join(".")}#${element.id} ${element.scrollWidth}>${element.clientWidth}`),
  );

for (const width of [1440, 390]) {
  for (const route of ROUTES) {
    test(`#/${route} at ${width} px: every tab keeps its panels in their frames, axe-clean`, async ({ page }) => {
      await mockSocket(page);
      await open(page, route, width);
      const tabs = page.locator("main [role=tablist]").first().getByRole("tab");
      const count = await tabs.count();
      for (let index = 0; index < Math.max(count, 1); index++) {
        if (count > 0) {
          await tabs.nth(index).click();
          await expect(tabs.nth(index)).toHaveAttribute("aria-selected", "true");
        }
        const label = count > 0 ? await tabs.nth(index).textContent() : "page";
        expect(await leaking(page), `${route} · ${label}`).toEqual([]);
        expect(await overflow(page), `${route} · ${label}`).toBeLessThanOrEqual(0);
        expect(await axeViolations(page), `${route} · ${label}`).toEqual([]);
      }
    });
  }
}

test("under prefers-reduced-motion no element of the live pages animates", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mockSocket(page);
  for (const route of ["", "agent-activity", "orchestration", "board"]) {
    await open(page, route, 1440);
    const moving = await page.evaluate(() =>
      [...document.querySelectorAll("*")]
        .filter((element) => {
          const style = getComputedStyle(element);
          return style.animationName !== "none" && style.animationPlayState === "running" && parseFloat(style.animationDuration) > 0;
        })
        .map((element) => `${element.tagName.toLowerCase()}.${[...element.classList].join(".")}`),
    );
    expect(moving, `#/${route}`).toEqual([]);
  }
});
