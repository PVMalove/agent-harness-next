/* Agent activity in the real build over a mocked socket: steps arrive without a reload, the
   dispatch and role filters narrow the list, and the route fits 1440 and 390 px without
   horizontal overflow, unfiltered and filtered.

   Manual mockup-match checklist (docs/design/web-console-mockups, #agent-activity; PR body):
   - [ ] Заголовок «Ход работы», подзаголовок о том, что внутренние рассуждения не показываются,
         кнопка «Оркестрация» справа, как в .page-title.work-title макета.
   - [ ] Строка вкладок показывает одну вкладку «Обзор»; «Таймлайн», «Статистика», KPI и сводка
         сессий не выводятся (вне объёма).
   - [ ] Панель «Источники шагов»: Claude Code с пилюлей «структура доступна» (mint) и Codex
         с пилюлей «структура недоступна» (violet), две колонки на 1440 и одна на 390.
   - [ ] Панель «Сессии»: строки .work-row с тикетом, dispatch, ролью, batch, состоянием и числом
         шагов; статусы, тикет и роль в одной строке .work-filters, 5 последних сессий и «Показать все»; выбранная строка подсвечена (.on).
   - [ ] Список «Шаги и события» вместо схемы маршрута: время, роль, текст и детали в .work-event;
         строки оркестрации подписаны «Оркестрация», Codex-строки несут «структура недоступна».
   - [ ] В списке нет thinking, входов инструментов и сырого JSON.
   - [ ] На 390 px сетка складывается в одну колонку, горизонтального скролла страницы нет.
   - [ ] Цвета, шрифты и отступы взяты из execution-console.css без переопределений. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { Page, WebSocketRoute } from "@playwright/test";

type Body = Record<string, unknown>;

const base = () => process.env.CONSOLE_BASE_URL!;
const read = (name: string) => JSON.parse(readFileSync(resolve(__dirname, "fixtures", name), "utf-8")) as unknown;
const HOME = read("home-snapshot.json");
const FEED = read("live-steps.json") as { roster: Body; steps: Body; later: Body };

const send = (ws: WebSocketRoute, body: Body) => ws.send(JSON.stringify({ v: 1, ok: true, ...body }));

/** Answers Home and the step feed; `later()` sends the steps that arrive after the first ones. */
async function mockSocket(page: Page) {
  const subscriptions: Body[] = [];
  let later: () => void = () => undefined;
  await page.routeWebSocket("**/ws", (ws) => {
    ws.onMessage((message) => {
      const request = JSON.parse(String(message)) as Body;
      const id = request.id;
      if (request.type === "home.snapshot") {
        send(ws, { id, type: "home.snapshot", cached: true, age_seconds: 3, snapshot: HOME });
      } else if (request.type === "steps.subscribe") {
        subscriptions.push(request);
        send(ws, { id, type: "steps.subscribe", ...FEED.roster });
        send(ws, { id, type: "steps.subscribe", ...FEED.steps });
        later = () => send(ws, { id, type: "steps.subscribe", ...FEED.later });
      }
    });
  });
  return { subscriptions, later: () => later() };
}

async function open(page: Page, width: number) {
  await page.setViewportSize({ width, height: width > 600 ? 900 : 844 });
  await page.clock.setFixedTime(new Date("2026-11-06T10:35:00Z"));
  await page.goto(`${base()}/#/agent-activity`);
  await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "connected");
  // 13 steps; close steps of one source make one row each (8 rows).
  await expect(page.locator("#work-steps .work-event")).toHaveCount(8);
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
}

const texts = (page: Page) => page.locator(".work-event .work-event-main b");

test("new steps arrive without a reload and the filters narrow the list", async ({ page }) => {
  const feed = await mockSocket(page);
  await open(page, 1440);
  const navigations: string[] = [];
  page.on("framenavigated", (frame) => navigations.push(frame.url()));
  feed.later();
  await expect(texts(page).last()).toHaveText("Тесты сервера прошли");
  expect(navigations).toEqual([]);
  expect(feed.subscriptions).toHaveLength(1);
  await expect(page.locator("#work-steps")).not.toContainText("{");

  await page.locator('[data-dispatch="dispatch-rev"]').click();
  await expect(texts(page)).toHaveText(["exec"]);
  await expect(page.locator("#work-steps .work-cluster-toggle")).toHaveText("×2");
  await expect(page.locator("#work-steps .orch-pill")).toHaveText(["структура недоступна"]);
  await page.locator('[data-dispatch="dispatch-rev"]').click();
  await page.getByLabel("Фильтр по роли").selectOption("architect");
  await expect(texts(page)).toHaveText(["Гейт dispatch-arch: accept"]);
  await expect(page.locator("#work-steps .work-cluster-toggle")).toHaveText("×2");
});

for (const width of [1440, 390]) {
  test(`agent activity at ${width} px`, async ({ page }) => {
    await mockSocket(page);
    await open(page, width);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    // The 5 latest of 7 sessions and one-line step rows inside their own scroll region.
    await expect(page.locator(".work-sessions .work-row")).toHaveCount(5);
    const heights = await page.locator("#work-steps .work-event").evaluateAll((rows) => rows.map((row) => row.getBoundingClientRect().height));
    expect(heights.filter((height) => height > (width > 720 ? 32 : 52))).toEqual([]);
    const panels = await page.locator(".work-page .panel").evaluateAll((items) => items.filter((item) => item.scrollWidth > item.clientWidth + 1).length);
    expect(panels).toBe(0);
  });

  test(`agent activity filtered by dispatch at ${width} px`, async ({ page }) => {
    await mockSocket(page);
    await open(page, width);
    await page.locator('[data-dispatch="dispatch-dev"]').click();
    await expect(page.locator("#work-steps .work-event")).toHaveCount(2);
    await page.locator("#work-steps").scrollIntoViewIfNeeded();
    await expect(page.locator("#work-steps .work-event").first()).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
