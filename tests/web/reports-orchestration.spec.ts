/* Reports, Orchestration, Recovery and Container route in the real build over a mocked socket that
   serves the committed fixtures: the content of each route at 1440 and 390 px without horizontal
   overflow, the hidden routes absent from the menu with «Оркестрация» highlighted, and a Recovery
   confirmation that, cancelled, starts nothing. No screenshot baselines (ADR 0029).

   Manual mockup-conformance checklist (docs/design/web-console-mockups):
   #reports
   - [ ] Title: h1 «Отчёты», subtitle, facts ending with the snapshot time, actions «Обновить» and
         «Экспорт» (download icon).
   - [ ] `reports-summary` (4) and `report-kpis` (4): Evidence полно, Stale evidence, Задержка
         отчёта, QA с первого раза; the risk and blocker tiles sit on the «Качество» tab.
   - [ ] `reports-grid`: «Отчёты» with type chips, one row (status select, search) and the TUI
         filters folded under «Ещё фильтры»; compact rows (icon, role · ticket, status words, HH:MM);
         «Детали отчёта» in the mockup order (summary, Evidence, conclusion, actions).
   - [ ] QA lane full width under the grid with the QA log folded inside.
   - Deviations: the batch history and chronology stay on Orchestration; «Открыть отчёт» has no
     reader in the web console (docs/design/web-console-mockups/parity-1066.md).
   #orchestration
   - [ ] Title with links «Восстановление», «Контейнерный маршрут», «Ход работы», «Отчёты».
   - [ ] KPI row (`orch-kpis`) of the eight TUI tiles.
   - [ ] «Аналитика» with tabs Поток работ / Качество / Runtime / Гейты; «Состояние и
         статистика»; «Lock ledger».
   - [ ] «История batch» with the state filter; a chosen batch opens its chronology and is carried
         to Recovery and Container route.
   - [ ] «Решения»: the pending human decisions with their confirmations.
   - Deviations: no flow map, heatmap or gate charts (no TUI facts); the TUI command menu is not
     reproduced (decisions cover the human gate).
   #recovery (hidden)
   - [ ] No menu item; «Оркестрация» highlighted; reached from Orchestration with the batch.
   - [ ] History, the recovery gate (mark and reason) and «Открыть recovery».
   - [ ] Blockers first, facts by group, unavailable actions with their reasons, notes.
   - [ ] Every action that changes something opens the confirmation; Cancel starts nothing.
   - Deviations: Fix offers the core's normalization only (no «edit at pointer» wizard).
   #container-route (hidden)
   - [ ] No menu item; «Оркестрация» highlighted; batch, role and runtime selection.
   - [ ] Executor context strip; six stage tabs with state marks that only switch the pane.
   - [ ] Per stage: blockers, facts by group, unavailable actions with reasons, notes.
   - [ ] Only the re-check is interactive; propose, approve, send, QA and cleanup are disabled with
         «Действие доступно только в TUI: команда не входит в каталог job сервера».
   - Deviations: the Harness «Контейнеры» tab (engine inventory) stays unshown: no TUI facts. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { Page, WebSocketRoute } from "@playwright/test";

type Body = Record<string, unknown>;

const base = () => process.env.CONSOLE_BASE_URL!;
const read = (name: string) => JSON.parse(readFileSync(resolve(__dirname, "fixtures", name), "utf-8")) as Body;
const HOME = read("home-snapshot.json");
const PAGED: Readonly<Record<string, Body>> = {
  "reports.snapshot": read("reports.json"),
  "reports.report": read("reports-report.json"),
  "reports.timeline": read("reports-timeline.json"),
  "orchestration.snapshot": read("orch-snapshot.json"),
  "recovery.view": read("recovery.json"),
  "container_route.view": read("container-route.json"),
};
const UNCACHED = new Set(["reports.report", "reports.timeline"]);
const RECOVERY_CATALOG = read("recovery-catalog.json");

const send = (ws: WebSocketRoute, body: Body) => ws.send(JSON.stringify({ v: 1, ok: true, ...body }));

async function mockSocket(page: Page) {
  const starts: Body[] = [];
  await page.routeWebSocket("**/ws", (ws) => {
    ws.onMessage((message) => {
      const request = JSON.parse(String(message)) as Body;
      const id = request.id;
      const type = String(request.type);
      if (type === "home.snapshot") {
        send(ws, { id, type, cached: true, age_seconds: 3, snapshot: HOME });
      } else if (type in PAGED) {
        const text = JSON.stringify(PAGED[type]);
        const cache = UNCACHED.has(type) ? {} : { cached: false, age_seconds: 0 };
        send(ws, { id, type, snapshot_id: 1, text, next: text.length, done: true, ...cache });
      } else if (type === "decisions.snapshot") {
        send(ws, { id, type, snapshot: { version: 1, items: [], total: 0, unavailable: false } });
      } else if (type === "job.catalog") {
        send(ws, { id, type, ...(request.section === "recovery" ? RECOVERY_CATALOG : { commands: [], cancel_reason: "" }) });
      } else if (type === "job.list") {
        send(ws, { id, type, jobs: [] });
      } else if (type === "job.start") {
        starts.push(request);
      }
    });
  });
  return starts;
}

async function open(page: Page, route: string, width: number, ready: string) {
  await page.setViewportSize({ width, height: width > 600 ? 900 : 844 });
  await page.goto(`${base()}/#/${route}`);
  await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "connected");
  await expect(page.locator(ready).first()).toBeVisible();
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
}

const noOverflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);

async function menuKeepsOrchestration(page: Page, width: number) {
  if (width < 600) await page.locator("#menu-toggle").click();
  const nav = page.getByRole("navigation", { name: "Разделы консоли" });
  await expect(nav.getByRole("link")).toHaveCount(13);
  await expect(nav.locator('a[href*="recovery"], a[href*="container-route"]')).toHaveCount(0);
  await expect(nav.locator('a[aria-current="page"]')).toHaveAttribute("href", "#/orchestration");
}

for (const width of [1440, 390]) {
  test(`reports at ${width} px`, async ({ page }) => {
    await mockSocket(page);
    await open(page, "reports", width, "#reports-kpi");
    await expect(page.locator("#report-list [data-stage]")).toHaveCount(6);
    await expect(page.locator("#report-detail .report-evidences .report-evidence")).toHaveCount(3);
    await expect(page.locator("#qa-lane #report-qa-log")).toContainText("хвост лога (последние 2 из 42 строк):");
    await expect(page.locator("#batch-list")).toHaveCount(0);
    // Every block of the page stays inside its frame, and a report row is one line.
    const wide = await page.evaluate(() =>
      [...document.querySelectorAll(".reports-page .panel, .reports-page .report-kpis, .reports-page .reports-summary, .report-row, .report-section")]
        .filter((box) => box.scrollWidth > box.clientWidth + 1)
        .map((box) => box.className),
    );
    expect(wide).toEqual([]);
    // On a phone the mockup moves the time under the row (its 720 px rule); on a desktop a row is one line.
    const rowHeight = await page.locator("#report-list .report-row").first().evaluate((row) => row.getBoundingClientRect().height);
    expect(rowHeight).toBeLessThanOrEqual(width > 600 ? 64 : 96);
    await page.getByRole("tab", { name: "Готовность" }).click();
    const pills = await page.evaluate(() =>
      [...document.querySelectorAll("#reports-readiness .orch-pill")].filter((pill) => pill.scrollWidth > pill.clientWidth + 1).length,
    );
    expect(pills).toBe(0);
    expect(await noOverflow(page)).toBe(true);
  });

  test(`orchestration at ${width} px`, async ({ page }) => {
    await mockSocket(page);
    await open(page, "orchestration", width, "#orch-mockup-kpis");
    await expect(page.locator("main [role=tablist]")).toHaveCount(1);
    await page.locator("#orch-tabs").getByRole("tab", { name: "Гейты" }).click();
    await expect(page.getByRole("heading", { name: "Ожидающие решения" })).toBeVisible();
    await page.locator("#orch-tabs").getByRole("tab", { name: "Runtime" }).click();
    await expect(page.locator("#ledger-lock")).toContainText("Lock ledger занят: report submit");
    await page.locator('#batch-history [data-batch="b-887"]').click();
    await expect(page.locator("#open-recovery")).toHaveAttribute("href", "#/recovery?batch=b-887");
    expect(await noOverflow(page)).toBe(true);
    // The blocks after the diagram: three batch cards (one row on a wide screen) and five-column dispatch rows.
    const cards = await page.locator(".orch-batches > article.orch-batch").evaluateAll((items) => items.map((item) => Math.round(item.getBoundingClientRect().top)));
    expect(cards).toHaveLength(3);
    if (width > 1100) expect(new Set(cards).size).toBe(1);
    const children = await page.locator(".orch-dispatch-row").evaluateAll((rows) => rows.map((row) => row.children.length));
    expect(children.every((count) => count === 5)).toBe(true);
    await expect(page.locator(".orch-ticket-table .orch-ticket-row")).toHaveCount(3);
  });

  test(`orchestration at ${width} px: only the live step moves, and never under reduced motion`, async ({ page }) => {
    await mockSocket(page);
    await open(page, "orchestration", width, "#orch-mockup-kpis");
    const animations = () =>
      page.locator("#orch-scheme").evaluate((map) => ({
        edges: [...map.querySelectorAll(".orch-map-edge.active")].map((edge) => getComputedStyle(edge).animationName),
        nodes: [...map.querySelectorAll(".orch-map-node.active .orch-map-bg, .orch-map-node.live .orch-map-bg")].map((bg) => getComputedStyle(bg).animationName),
      }));
    const moving = await animations();
    expect(moving.edges).toEqual(["orchMapFlow", "orchMapFlow"]);
    expect(moving.nodes).toEqual(["orchMapPulse", "orchMapPulse"]);
    await page.emulateMedia({ reducedMotion: "reduce" });
    const still = await animations();
    expect([...still.edges, ...still.nodes].every((name) => name === "none")).toBe(true);
  });

  test(`recovery at ${width} px: hidden route, a cancelled confirmation starts nothing`, async ({ page }) => {
    const starts = await mockSocket(page);
    await open(page, "recovery?batch=b-887", width, "#recovery-view");
    await expect(page.locator("#recovery-view")).toContainText("✖ недоступно: Resume — ядро: проверка не пройдена");
    expect(await noOverflow(page)).toBe(true);
    await page.locator('#view-actions [data-action="reload"] button').click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("recovery-reload");
    await dialog.getByRole("button", { name: "Отмена", exact: true }).click();
    await expect(dialog).toHaveCount(0);
    expect(starts).toEqual([]);
    await page.locator('#view-actions [data-action="abort"] button').click();
    await expect(page.getByRole("dialog")).toContainText("recovery-abort");
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    expect(starts).toEqual([]);
    await menuKeepsOrchestration(page, width);
  });

  test(`container route at ${width} px: hidden route, tabs only switch the pane`, async ({ page }) => {
    const starts = await mockSocket(page);
    await open(page, "container-route?batch=b-887&role=developer", width, "#route-view");
    await expect(page.locator("#route-context")).toContainText("Worker: не создан");
    await page.getByRole("tab", { name: "✖ Plan / approval" }).click();
    await expect(page.locator('#view-actions [data-action="propose"] button')).toBeDisabled();
    expect(await noOverflow(page)).toBe(true);
    expect(starts).toEqual([]);
    await menuKeepsOrchestration(page, width);
  });
}
