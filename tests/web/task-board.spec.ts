/* Task Board at 1440 and 390 px over the production build and the real FastAPI process, the
   socket answered with the synthetic #913 fixtures and a frozen clock. The status change has its own
   spec (task-board-status.spec.ts). Manual mockup checklist:
   docs/design/web-console-mockups/board-acceptance.md. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import SPECS from "./fixtures/task-board-specs.json";
import STALE from "./fixtures/task-board-stale.json";
import BOARD from "./fixtures/task-board.json";

const base = () => process.env.CONSOLE_BASE_URL!;
const HOME = JSON.parse(readFileSync(resolve(__dirname, "fixtures/home-snapshot.json"), "utf8")) as unknown;

interface Answers {
  specs?: unknown;
  /** null leaves the board request unanswered: the first-load state. */
  board?: unknown;
}

async function open(page: Page, width: number, answers: Answers = {}) {
  const asked: Record<string, unknown>[] = [];
  await page.setViewportSize({ width, height: width > 600 ? 900 : 844 });
  await page.clock.setFixedTime(new Date("2026-11-09T10:41:00Z"));
  await page.routeWebSocket("**/ws", (ws) => {
    ws.onMessage((raw) => {
      const request = JSON.parse(String(raw)) as Record<string, unknown>;
      const reply = (body: Record<string, unknown>) =>
        ws.send(JSON.stringify({ v: 1, id: request.id, type: request.type, ok: true, ...body }));
      const paged = (value: unknown) => {
        const text = JSON.stringify(value);
        reply({ cached: false, age_seconds: 0, snapshot_id: 1, text, next: text.length, done: true });
      };
      if (request.type === "home.snapshot") reply({ cached: true, age_seconds: 0, snapshot: HOME });
      if (request.type === "task_board.specs") paged(answers.specs ?? SPECS);
      if (request.type === "task_board.snapshot") {
        asked.push(request);
        if (answers.board !== null) paged(answers.board ?? BOARD);
      }
    });
  });
  await page.goto(`${base()}/#/board`);
  await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "connected");
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
  return asked;
}

const noOverflow = (page: Page) =>
  page.evaluate(() => {
    const content = document.querySelector("#content")!;
    return document.documentElement.scrollWidth <= innerWidth && content.scrollWidth <= content.clientWidth;
  });

for (const width of [1440, 390]) {
  test(`Task Board columns, card and modal at ${width} px`, async ({ page }) => {
    const errors: string[] = [];
    const foreign: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("request", (request) => {
      if (!request.url().startsWith(base())) foreign.push(request.url());
    });
    await open(page, width);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Доска задач");
    await expect(page.locator("[data-board-col]")).toHaveCount(5);
    await expect(page.locator(".board-col-count")).toHaveText(["2", "2", "1", "1", "1"]);
    await expect(page.locator(".board-col header b")).toHaveText([
      "Бэклог",
      "Готово к работе",
      "В работе",
      "Review / QA",
      "Готово",
    ]);
    await expect(page.locator("[data-board-ticket]")).toHaveCount(7);
    await expect(page.locator("#board-spec")).toHaveValue("#501");
    await expect(page.locator("#board-kpis > div")).toHaveCount(4);
    await expect(page.locator(".board-search svg.hi")).toBeVisible();
    await page.locator("#board-search").fill("фильтры");
    await expect(page.locator("[data-board-ticket]")).toHaveCount(1);
    await page.locator("#board-search").fill("");
    const card = page.locator('[data-board-ticket="#511"]');
    await expect(card.locator("h3")).toHaveText("Экран списка задач");
    await expect(card.locator(".board-chip")).toHaveText(["/implement", "блокеров: 1"]);
    expect(await noOverflow(page)).toBe(true);

    await card.locator("h3").click();
    const dialog = page.locator("#board-ticket");
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("tab")).toHaveText(["Контекст", "Acceptance (2)", "Промпт"]);
    await expect(dialog.locator("#board-status-label")).toHaveText("Бэклог");
    await expect(dialog.locator("select#board-status")).toHaveValue("backlog");
    await expect(dialog.locator(".board-blocker")).toHaveCount(1);
    await dialog.getByRole("tab", { name: "Acceptance (2)" }).click();
    await expect(dialog.locator(".board-acceptance li")).toHaveCount(2);
    await dialog.getByRole("tab", { name: "Промпт" }).click();
    await expect(dialog.locator("pre.board-prompt")).toContainText("/implement #511");
    const agent = dialog.getByRole("button", { name: "Промпт агента" });
    await expect(agent).toBeVisible();
    expect(await agent.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe("rgb(118, 203, 178)");
    await dialog.getByRole("tab", { name: "Контекст" }).click();
    expect(await noOverflow(page)).toBe(true);
    await dialog.getByRole("button", { name: "Закрыть" }).click();
    await expect(dialog).toHaveCount(0);
    expect(errors).toEqual([]);
    expect(foreign).toEqual([]);
  });
}

const EMPTY = {
  ...BOARD,
  tickets: [],
  columns: BOARD.columns.map((column) => ({ ...column, count: 0 })),
  kpis: { open: 0, total: 0, with_open_blockers: 0, active_batch: 0 },
};

test("Task Board state: no specs", async ({ page }) => {
  await open(page, 1440, { specs: { ...SPECS, specs: [] } });
  await expect(page.locator('[data-board-state="nospecs"] h2')).toHaveText("Спек пока нет");
});

test("Task Board state: empty board", async ({ page }) => {
  await open(page, 1440, { board: EMPTY });
  await expect(page.locator('[data-board-state="empty"] h2')).toHaveText("На доске нет задач");
});

test("Task Board state: tracker unavailable", async ({ page }) => {
  await open(page, 1440, { board: STALE });
  await expect(page.locator(".board-banner.down")).toContainText("Нет доступа к трекеру: tracker login required");
  await expect(page.locator(".board-banner.down")).toContainText("Показан снимок 1 мин назад.");
  await expect(page.locator("[data-board-ticket]")).toHaveCount(7);
});

test("Task Board state: refreshing", async ({ page }) => {
  const asked = await open(page, 390, { board: null });
  await expect(page.locator('[data-board-state="loading"] h2')).toHaveText("Обновление доски");
  expect(asked[0]).toMatchObject({ spec: "#501", force: false });
  expect(await noOverflow(page)).toBe(true);
});

test("the page keeps the strict policy of the server", async ({ page }) => {
  const response = await page.goto(`${base()}/`);
  const policy = response?.headers()["content-security-policy"] ?? "";
  expect(policy).toContain("default-src 'none'");
  expect(policy).toContain("script-src 'self';");
  expect(policy).toContain("style-src 'self';");
  expect(policy).not.toContain("unsafe");
});
