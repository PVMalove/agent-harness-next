/* Harness in the real build over a mocked socket: the overview and maintenance facts, the
   «Очистить…» button that opens the server's confirmation in the Commands tab and starts the
   cleanup bound to the shown plan's digest, and the page at 1440 and 390 px. Update only these
   with `npm run test:e2e:update -- harness.spec.ts`.

   Manual mockup-conformance checklist (docs/design/web-console-mockups, route #harness):
   - [x] Title: h1, subtitle, facts (installed version, skills, drift, lock time), actions
         «Проверить», «Диагностика», «Обновление».
   - [x] KPI row of four tiles (Установлено, Skills, Пайплайн, Временные файлы).
   - [x] Tab bar «Обзор» / «Команды»; both panels mounted, the inactive one hidden.
   - [x] «Обзор»: «Установка» (version pair, capability, components, actions) beside
         «Использование пайплайна»; below it «Обслуживание» with the server's sizes, categories,
         skips, hard-mode extra, plan details and worktrees with «Удалить…».
   - [x] «Команды»: the section's catalog commands as server jobs, the server's confirmation dialog.
   - Deviations: the Runtime store and Audit chain KPIs are replaced by pipeline usage and
     temporary files (the TUI has no runtime or audit facts); the Runtime, Адаптеры and
     Контейнеры tabs and the Python → Rust flow diagram are not shown (no TUI facts yet); the
     command rows carry no CLI line (descriptors carry no argv). */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { Page, WebSocketRoute } from "@playwright/test";

type Body = Record<string, unknown>;

const base = () => process.env.CONSOLE_BASE_URL!;
const read = (name: string) => JSON.parse(readFileSync(resolve(__dirname, "fixtures", name), "utf-8")) as Body;
const HOME = read("home-snapshot.json");
const CATALOG = read("job-catalog.json");
const OVERVIEW = read("harness-overview.json");
const MAINTENANCE = read("harness-maintenance.json");

const send = (ws: WebSocketRoute, body: Body) => ws.send(JSON.stringify({ v: 1, ok: true, ...body }));

async function mockSocket(page: Page) {
  const starts: Body[] = [];
  await page.routeWebSocket("**/ws", (ws) => {
    ws.onMessage((message) => {
      const request = JSON.parse(String(message)) as Body;
      const id = request.id;
      if (request.type === "home.snapshot") {
        send(ws, { id, type: "home.snapshot", cached: true, age_seconds: 3, snapshot: HOME });
      } else if (request.type === "harness.overview") {
        send(ws, { id, type: "harness.overview", cached: true, age_seconds: 3, ...OVERVIEW });
      } else if (request.type === "harness.maintenance") {
        const text = JSON.stringify(MAINTENANCE);
        send(ws, { id, type: "harness.maintenance", snapshot_id: 2, text, next: text.length, done: true, cached: false, age_seconds: 0 });
      } else if (request.type === "job.catalog") {
        send(ws, { id, type: "job.catalog", ...CATALOG });
      } else if (request.type === "job.list") {
        send(ws, { id, type: "job.list", jobs: [] });
      } else if (request.type === "job.start") {
        starts.push(request);
      }
    });
  });
  return starts;
}

async function open(page: Page, width: number) {
  await page.setViewportSize({ width, height: width > 600 ? 900 : 844 });
  await page.clock.setFixedTime(new Date("2026-11-05T10:41:00Z"));
  await page.goto(`${base()}/#/harness`);
  await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "connected");
  await expect(page.locator("#harness-version")).toHaveText("2.0.0");
  await expect(page.locator("#worktree-count")).toBeVisible();
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
}

test("the overview shows the server's facts and the cleanup is bound to the shown plan", async ({ page }) => {
  const starts = await mockSocket(page);
  await open(page, 1440);
  await expect(page.locator("#harness-usage")).toContainText("212");
  await expect(page.locator("#harness-drift")).toHaveText("⚠ дрейф есть");
  await expect(page.locator("#harness-maintenance")).toContainText("Жёсткий режим: +40.0 MiB");
  await page.getByRole("button", { name: "Очистить…" }).click();
  await expect(page.getByRole("tab", { name: "Команды" })).toHaveAttribute("aria-selected", "true");
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("cleanup-apply");
  await dialog.getByRole("button", { name: "Запустить" }).click();
  await expect.poll(() => starts.length).toBe(1);
  const soft = (MAINTENANCE.maintenance as Record<string, Body>).soft!;
  expect(starts[0]).toMatchObject({ command_id: "cleanup-apply", confirmed: true, plan_digest: soft.digest });
});

for (const width of [1440, 390]) {
  test(`harness at ${width} px`, async ({ page }) => {
    await mockSocket(page);
    await open(page, width);
    await expect(page).toHaveScreenshot(`harness-${width}.png`, { fullPage: true });
  });
}
