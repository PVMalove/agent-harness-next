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

/* Window fit of Home, Task board and Workflow (#1092) on the five sizes the console is checked at.
   Home fits from 1800 px wide and is a scrolling column below; the board and the workflow never
   scroll the page and scroll only inside their lists. With `CONSOLE_FIT_OUT=<dir>` the measures
   and screenshots are written there. */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import type { Page, WebSocketRoute } from "@playwright/test";

const SIZES: [number, number][] = [
  [1920, 1080],
  [1920, 1010],
  [1920, 950],
  [1680, 950],
  [1440, 900],
];
const OUT = process.env.CONSOLE_FIT_OUT;
const measures: Record<string, unknown>[] = [];

type Body = Record<string, unknown>;
const fixture = (name: string) => JSON.parse(readFileSync(resolve(__dirname, "fixtures", name), "utf-8")) as Body;
const HOME = fixture("home-snapshot.json");
const SPECS = fixture("task-board-specs.json");
const BOARD = fixture("task-board.json") as Body & { tickets: Body[] };
const FEED = fixture("live-steps.json") as { roster: Body & { dispatches: Body[] }; steps: Body };

const send = (ws: WebSocketRoute, body: Body) => ws.send(JSON.stringify({ v: 1, ok: true, ...body }));
const paged = (ws: WebSocketRoute, id: unknown, type: string, value: unknown) => {
  const text = JSON.stringify(value);
  send(ws, { id, type, cached: false, age_seconds: 0, snapshot_id: 1, text, next: text.length, done: true });
};

interface Mocks {
  board?: Body;
  roster?: Body;
  steps?: Body[];
  home?: Body;
}

async function mock(page: Page, mocks: Mocks) {
  await page.routeWebSocket("**/ws", (ws) => {
    ws.onMessage((message) => {
      const request = JSON.parse(String(message)) as Body;
      const id = request.id;
      if (request.type === "home.snapshot") {
        send(ws, { id, type: "home.snapshot", cached: true, age_seconds: 0, snapshot: mocks.home ?? HOME });
      } else if (request.type === "task_board.specs") {
        paged(ws, id, "task_board.specs", SPECS);
      } else if (request.type === "task_board.snapshot") {
        paged(ws, id, "task_board.snapshot", mocks.board ?? BOARD);
      } else if (request.type === "steps.subscribe") {
        send(ws, { id, type: "steps.subscribe", ...(mocks.roster ?? FEED.roster) });
        send(ws, { id, type: "steps.subscribe", kind: "steps", steps: mocks.steps ?? [] });
      }
    });
  });
}

async function openAt(page: Page, route: string, [width, height]: [number, number]) {
  await page.setViewportSize({ width, height });
  await page.clock.setFixedTime(new Date("2026-11-06T10:35:00Z"));
  await page.goto(`${base()}/#/${route}`);
  await expect(page.locator("#connection-state")).toHaveAttribute("data-status", /connected|empty/, { timeout: 30000 });
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
}

/** How the window is used: the main column and the page, and what of `#content` leaves its box. */
async function fit(page: Page) {
  return page.evaluate(() => {
    const main = document.querySelector("main#content") as HTMLElement;
    const box = main.getBoundingClientRect();
    const blocks = [...main.querySelectorAll<HTMLElement>(".panel, .board-col")].filter((node) => {
      const rect = node.getBoundingClientRect();
      return rect.height > 0;
    });
    return {
      main: { scroll: main.scrollHeight, client: main.clientHeight, overflowY: getComputedStyle(main).overflowY },
      page: { scroll: document.documentElement.scrollHeight, client: document.documentElement.clientHeight },
      cut: blocks.filter((node) => node.getBoundingClientRect().bottom > box.bottom + 1).length,
    };
  });
}

async function record(page: Page, name: string, size: [number, number], extra: Body = {}) {
  const facts = await fit(page);
  measures.push({ name, size: size.join("x"), ...facts, ...extra });
  if (OUT) {
    mkdirSync(OUT, { recursive: true });
    await page.screenshot({ path: resolve(OUT, `${name}-${size.join("x")}.png`) });
  }
  return facts;
}

test.afterAll(() => {
  if (OUT && measures.length) writeFileSync(resolve(OUT, "fit-measurements-1092.json"), JSON.stringify(measures, null, 1));
});

const NOT_SCROLLING = (facts: Awaited<ReturnType<typeof fit>>) => {
  expect(facts.page.scroll).toBeLessThanOrEqual(facts.page.client);
  expect(facts.main.scroll).toBeLessThanOrEqual(facts.main.client + 1);
  expect(facts.cut).toBe(0);
};

for (const size of SIZES) {
  const [width] = size;
  const label = size.join("x");

  test(`Home on an empty project at ${label}: ${width >= 1800 ? "fits without page scroll" : "a scrolling column"}`, async ({ page }) => {
    await page.goto(`${base()}/?token=${process.env.CONSOLE_TOKEN!}`);
    await openAt(page, "", size);
    await expect(page.locator("#home-contour")).toBeVisible();
    const facts = await record(page, "home-empty", size);
    if (width >= 1800) NOT_SCROLLING(facts);
    else {
      expect(facts.main.overflowY).toBe("auto");
      expect(facts.main.scroll).toBeGreaterThan(facts.main.client);
    }
  });

  test(`Home with a long problem list at ${label} scrolls inside its blocks`, async ({ page }) => {
    const problems = Array.from({ length: 100 }, (_, index) => ({
      status: index % 3 ? "warn" : "fail",
      id: `check.${index}`,
      message: `Проверка ${index} не пройдена: длинное пояснение, которое занимает место в списке`,
      group: "files",
    }));
    const sessions = Array.from({ length: 30 }, (_, index) => ({
      batch_id: `batch-${index}`,
      ticket: `#${900 + index}`,
      state: "active",
      branch: `feature/issue-${900 + index}`,
      created_at: "2026-11-06T09:00:00+00:00",
      updated_at: "2026-11-06T10:00:00+00:00",
      route: [{ role: "developer", state: "working" }],
    }));
    await mock(page, { home: { ...HOME, problems, problems_total: 100, recent_sessions: sessions } });
    await openAt(page, "", size);
    await expect(page.locator("#attention-list .it").first()).toBeVisible();
    const facts = await record(page, "home-long", size);
    if (width >= 1800) {
      NOT_SCROLLING(facts);
      const lists = await page.evaluate(() =>
        ["#attention-list", "#home-tasks .task-list"].map((selector) => {
          const node = document.querySelector<HTMLElement>(selector)!;
          return { overflowY: getComputedStyle(node).overflowY, scrolls: node.scrollHeight > node.clientHeight };
        }),
      );
      expect(lists).toEqual([
        { overflowY: "auto", scrolls: true },
        { overflowY: "auto", scrolls: true },
      ]);
    } else {
      expect(facts.main.scroll).toBeGreaterThan(facts.main.client);
    }
  });

  test(`Task board with 220 cards at ${label}: only the columns scroll`, async ({ page }) => {
    const first = BOARD.tickets[0]!;
    const tickets = Array.from({ length: 220 }, (_, index) => ({
      ...first,
      id: `#${1000 + index}`,
      n: 1000 + index,
      title: `Карточка ${index}`,
      column: ["backlog", "ready", "progress", "review", "done"][index % 5],
    }));
    await mock(page, { board: { ...BOARD, tickets, truncated: false } });
    await openAt(page, "board", size);
    await expect(page.locator("[data-board-ticket]").first()).toBeVisible();
    const facts = await record(page, "board-long", size);
    NOT_SCROLLING(facts);
    const columns = await page.locator("[data-board-col]").evaluateAll((nodes) =>
      nodes.map((node) => {
        const scroller = [node, ...node.querySelectorAll<HTMLElement>("*")].find(
          (item) => getComputedStyle(item).overflowY === "auto" && item.scrollHeight > item.clientHeight,
        );
        return scroller !== undefined;
      }),
    );
    expect(columns).toEqual([true, true, true, true, true]);
  });

  for (const state of ["board-empty", "board-no-batch", "board-stale"]) {
    test(`Task board ${state} at ${label}: no page scroll`, async ({ page }) => {
      const empty = {
        ...BOARD,
        tickets: [],
        columns: (BOARD.columns as Body[]).map((column) => ({ ...column, count: 0 })),
        kpis: { open: 0, total: 0, with_open_blockers: 0, active_batch: 0 },
      };
      const boards: Record<string, Body> = {
        "board-empty": empty,
        // The ledger cannot be read: no active batch is known.
        "board-no-batch": { ...BOARD, ledger: "unavailable", kpis: { ...(BOARD.kpis as Body), active_batch: 0 } },
        "board-stale": { ...BOARD, stale: { reason: "timeout", message: "" }, age_seconds: 600 },
      };
      await mock(page, { board: boards[state]! });
      await openAt(page, "board", size);
      await expect(page.locator(state === "board-empty" ? '[data-board-state="empty"]' : "#board-columns")).toBeVisible();
      NOT_SCROLLING(await record(page, state, size));
    });
  }

  test(`Workflow on an empty project at ${label}: no page scroll`, async ({ page }) => {
    await page.goto(`${base()}/?token=${process.env.CONSOLE_TOKEN!}`);
    await openAt(page, "agent-activity", size);
    await expect(page.locator(".work-page")).toBeVisible();
    NOT_SCROLLING(await record(page, "workflow-empty", size));
  });

  test(`Workflow with 600 steps at ${label}: the events scroll, the page does not`, async ({ page }) => {
    const steps = Array.from({ length: 600 }, (_, index) => ({
      origin: "agent",
      dispatch_id: `dispatch-${index % 7}`,
      batch_id: "batch-885",
      role: "developer",
      source: "structured",
      structure: "available",
      kind: "output",
      text: `Шаг ${index}`,
      observed_at: `2026-11-06T10:${String(Math.floor(index / 60)).padStart(2, "0")}:${String(index % 60).padStart(2, "0")}+00:00`,
    }));
    await mock(page, { steps });
    await openAt(page, "agent-activity", size);
    await expect(page.locator("#work-steps .work-event").first()).toBeVisible();
    const facts = await record(page, "workflow-long", size);
    NOT_SCROLLING(facts);
    const events = await page.locator("#work-steps").evaluate((node) => ({
      overflowY: getComputedStyle(node).overflowY,
      scrolls: node.scrollHeight > node.clientHeight,
    }));
    expect(events).toEqual({ overflowY: "auto", scrolls: true });
  });

  test(`Workflow with no live session at ${label}: no page scroll`, async ({ page }) => {
    const idle = { ...FEED.roster, dispatches: FEED.roster.dispatches.map((entry) => ({ ...entry, state: "reported" })) };
    await mock(page, { roster: idle, steps: (FEED.steps as Body & { steps: Body[] }).steps });
    await openAt(page, "agent-activity", size);
    await expect(page.locator("#work-steps .work-event").first()).toBeVisible();
    NOT_SCROLLING(await record(page, "workflow-idle", size));
  });
}
