/* Mockup parity of the shell and the ten implemented pages: the DOM structure of each page (the
   mockup's blocks, tabs, filters and tiles in its order) at 1440 and 390 px without horizontal
   overflow, and the connection states on every page. DOM assertions only; no screenshot
   comparison (ADR 0029). The owner accepts the look by hand against the mockup. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { Page, WebSocketRoute } from "@playwright/test";

type Body = Record<string, unknown>;

const base = () => process.env.CONSOLE_BASE_URL!;
const read = (name: string) => JSON.parse(readFileSync(resolve(__dirname, "fixtures", name), "utf-8")) as Body;
const HOME = read("home-snapshot.json");
const FEED = read("live-steps.json") as { roster: Body; steps: Body };
const PAGED: Readonly<Record<string, Body>> = {
  "reports.snapshot": read("reports.json"),
  "reports.report": read("reports-report.json"),
  "reports.timeline": read("reports-timeline.json"),
  "orchestration.snapshot": read("orch-snapshot.json"),
  "recovery.view": read("recovery.json"),
  "container_route.view": read("container-route.json"),
  "diagnostics.snapshot": read("diagnostics-report.json"),
  "harness.maintenance": read("harness-maintenance.json"),
  "repo_map.snapshot": read("repo-map.json"),
};
const OVERVIEW = read("harness-overview.json");

const send = (ws: WebSocketRoute, body: Body) => ws.send(JSON.stringify({ v: 1, ok: true, ...body }));

/** Answers every page's reads from the fixtures; `home` replaces the Home snapshot reply. */
async function mockSocket(page: Page, home: (ws: WebSocketRoute, id: unknown) => void = (ws, id) =>
  send(ws, { id, type: "home.snapshot", cached: true, age_seconds: 3, snapshot: HOME })) {
  await page.routeWebSocket("**/ws", (ws) => {
    ws.onMessage((message) => {
      const request = JSON.parse(String(message)) as Body;
      const id = request.id;
      const type = String(request.type);
      if (type === "home.snapshot") home(ws, id);
      else if (type in PAGED) {
        const text = JSON.stringify(PAGED[type]);
        send(ws, { id, type, snapshot_id: 1, text, next: text.length, done: true, cached: false, age_seconds: 0 });
      } else if (type === "harness.overview") send(ws, { id, type, cached: false, age_seconds: 0, ...OVERVIEW });
      else if (type === "steps.subscribe") {
        send(ws, { id, type, ...FEED.roster });
        send(ws, { id, type, ...FEED.steps });
      } else if (type === "decisions.snapshot") {
        send(ws, { id, type, snapshot: { version: 1, items: [], total: 0, unavailable: false } });
      } else if (type === "job.catalog") send(ws, { id, type, commands: [], cancel_reason: "" });
      else if (type === "job.list") send(ws, { id, type, jobs: [] });
    });
  });
}

async function open(page: Page, route: string, width: number) {
  await page.setViewportSize({ width, height: width > 600 ? 900 : 844 });
  await page.goto(`${base()}/#/${route}`);
  await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "connected");
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
}

const noOverflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
const tabs = (page: Page) => page.locator("main [role=tablist]").first().getByRole("tab");

interface PageSpec {
  route: string;
  title: string | RegExp;
  /** Selectors of the mockup blocks in the mockup's order. */
  blocks: string[];
  tabs?: string[];
}

const PAGES: PageSpec[] = [
  {
    route: "",
    title: "Состояние харнесса",
    blocks: ["#home-chips", "#home-attention", "#home-context", "#home-tasks", "#home-health", "#home-contour"],
  },
  { route: "diagnostics", title: "Диагностика", blocks: [".diag-summary", ".diag-grid"] },
  {
    route: "harness",
    title: "Harness",
    blocks: ["#harness-kpis", "#harness-install", "#harness-runtime", "#harness-adapters", "#harness-maintenance"],
    tabs: ["Обзор", "Runtime", "Адаптеры", "Контейнеры", "Команды"],
  },
  { route: "repo-map", title: "Repo Map", blocks: [".repo-kpis"], tabs: ["Обзор", "Символы", "Связи", "Настройки"] },
  {
    route: "agent-activity",
    title: "Ход работы",
    blocks: ["#work-summary", "#work-kpis", ".work-sources", ".work-sessions", "#work-route", "#work-events-panel"],
    tabs: ["Обзор", "Таймлайн", "Статистика"],
  },
  {
    route: "orchestration",
    title: "Оркестрация",
    blocks: ["#orch-summary", "#orch-mockup-kpis", "#orch-scheme", "#orch-batch-cards", "#orch-dispatch", "#qa-lane", "#orch-tickets", "#ledger-lock"],
    tabs: ["Схема", "Поток", "Качество", "Runtime", "Гейты"],
  },
  {
    route: "reports",
    title: "Отчёты",
    blocks: ["#reports-summary", "#reports-kpi", "#report-types", "#report-detail", "#qa-lane"],
    tabs: ["Отчёты", "Evidence", "Качество", "Готовность"],
  },
  {
    route: "publish",
    title: "Публикация",
    blocks: ["#publish-batch", "#publish-kpis", "#publish-decision"],
    tabs: ["Обзор", "Preflight", "PR / MR", "Evidence"],
  },
  { route: "recovery?batch=b-887", title: "Восстановление", blocks: ["#recovery-note", "#recovery-summary", "#recovery-history"] },
  { route: "container-route?batch=b-887", title: "Контейнерный запуск", blocks: ["#route-summary", "#route-stages", "#route-env"] },
];

/** True when every selector follows the previous one in document order. */
const inOrder = (page: Page, selectors: string[]) =>
  page.evaluate((list) => {
    const nodes = list.map((selector) => document.querySelector(selector));
    if (nodes.some((node) => node === null)) return list.filter((_, index) => nodes[index] === null);
    return nodes.every(
      (node, index) => index === 0 || Boolean(nodes[index - 1]!.compareDocumentPosition(node!) & Node.DOCUMENT_POSITION_FOLLOWING),
    );
  }, selectors);

for (const width of [1440, 390]) {
  test(`shell at ${width} px: title, version, repository, branch, menu captions and counters`, async ({ page }) => {
    await mockSocket(page);
    await open(page, "", width);
    await expect(page.locator(".brand b")).toHaveText("Harness next");
    await expect(page.locator(".brand .version")).toHaveText("1.5.1");
    await expect(page.locator(".brand .channel")).toHaveCount(0);
    await expect(page.locator("#project")).toHaveText("claude-agent-harness");
    if (width < 600) await page.locator("#menu-toggle").click();
    const nav = page.getByRole("navigation", { name: "Разделы консоли" });
    await expect(nav.locator(".nav-label")).toContainText(["Главная", "Диагностика", "Обновление", "Проект"]);
    await expect(nav.locator('[data-route="diagnostics"]')).toHaveText("2");
    await expect(nav.locator('[data-route="update-harness"]')).toHaveText("3");
    await expect(nav.locator('[data-route="repo-map"]')).toHaveText("full");
    await expect(page.locator("#foot-status")).toHaveText("1.5.1 · file-ledger · Главная");
    expect(await noOverflow(page)).toBe(true);
  });

  for (const spec of PAGES) {
    test(`${spec.route.split("?")[0] || "home"} at ${width} px: mockup blocks in order, no overflow`, async ({ page }) => {
      await mockSocket(page);
      await open(page, spec.route, width);
      await expect(page.locator("main h1").first()).toHaveText(spec.title);
      await expect(page.locator(spec.blocks.at(-1)!).first()).toBeAttached();
      expect(await inOrder(page, spec.blocks)).toBe(true);
      if (spec.tabs) await expect(tabs(page)).toHaveText(spec.tabs);
      await expect(page.locator("main")).not.toContainText("данные симулируются");
      expect(await noOverflow(page)).toBe(true);
    });
  }
}

test("a mockup tab without a source shows an explicit no-data state", async ({ page }) => {
  await mockSocket(page);
  await open(page, "harness", 1440);
  await page.getByRole("tab", { name: "Контейнеры" }).click();
  // Running and Disk have no source; the fixture's volume probe failed with its reason.
  await expect(page.locator("#harness-containers .harness-container-summary .no-data")).toHaveCount(3);
  await expect(page.locator("[data-fact='images-volumes'] .no-data")).toHaveAttribute("title", /docker volume ls/);
  await page.getByRole("tab", { name: "Runtime" }).click();
  await expect(page.locator("#harness-tab-runtime")).toContainText("нет данных");
});

for (const width of [1440, 390]) {
  test(`kernel sources at ${width} px fill the former no-data places`, async ({ page }) => {
    await mockSocket(page);
    await open(page, "diagnostics", width);
    await page.locator('#diag-list [data-check="hooks.policy"]').click();
    await expect(page.locator(".diag-detail-panel .diag-rationale")).toHaveText(/^Без записанной политики хуков/);
    // An id the kernel catalog does not describe keeps the no-data state.
    await page.locator('#diag-list [data-check="files.managed"]').click();
    await expect(page.locator(".diag-detail-panel .diag-facts .no-data")).toHaveText("нет данных");
    expect(await noOverflow(page)).toBe(true);

    await open(page, "harness", width);
    await page.getByRole("tab", { name: "Контейнеры" }).click();
    await expect(page.locator("#harness-engine-line")).toHaveText("docker · 27.4.1 · rootless · cgroup v2 · systemd");
    await expect(page.locator("#harness-engine")).toContainText("SELinux выключен");
    expect(await noOverflow(page)).toBe(true);

    await open(page, "repo-map", width);
    const coverage = page.locator(".repo-index", { has: page.getByRole("heading", { name: "Покрытие" }) });
    await expect(coverage.locator(".repo-index-row", { hasText: "excluded" }).locator("b")).toHaveText("2");
    await page.getByRole("tab", { name: "Символы" }).click();
    await expect(page.locator("#repo-kind-chips .chip")).toHaveText(["Все 3", "Functions 2", "Modules 1"]);
    await expect(page.locator(".repo-symbol-row .repo-kind").first()).toHaveText("function");
    expect(await noOverflow(page)).toBe(true);

    await open(page, "orchestration", width);
    await page.locator("#orch-tabs").getByRole("tab", { name: "Гейты" }).click();
    await expect(page.locator("#orch-gate-trend circle")).toHaveCount(2);
    expect(await noOverflow(page)).toBe(true);

    await open(page, "reports", width);
    await page.getByRole("tab", { name: "Evidence" }).click();
    await expect(page.locator("#reports-evidence .report-evidence-row")).toHaveCount(2);
    await page.getByRole("tab", { name: "Готовность" }).click();
    await expect(page.locator("#reports-readiness [data-verdict]")).toHaveText("blocked");
    expect(await noOverflow(page)).toBe(true);

    await open(page, "publish", width);
    await expect(page.locator("#publish-verdict")).toHaveText("blocked");
    expect(await noOverflow(page)).toBe(true);
  });
}

for (const spec of PAGES) {
  const name = spec.route.split("?")[0] || "home";
  test(`${name}: no server and error states`, async ({ page }) => {
    await page.route("**/health/live", (route) => route.abort("connectionrefused"));
    await page.goto(`${base()}/#/${spec.route}`);
    await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "no_server");
    await expect(page.locator(".connection-page")).toContainText("Нет связи с сервером консоли");
    await expect(page.locator(".connection-page")).toContainText("endpoint");

    await page.unroute("**/health/live");
    await mockSocket(page, (ws, id) =>
      ws.send(JSON.stringify({ v: 1, id, type: "home.snapshot", ok: false, error: { code: "busy", message: "later" } })),
    );
    await page.goto(`${base()}/#/${spec.route}`);
    await page.reload();
    await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "error");
    await expect(page.locator(".connection-page")).toContainText("busy");
  });

  test(`${name}: an empty Home snapshot empties only the pages of that data`, async ({ page }) => {
    await mockSocket(page, (ws, id) =>
      send(ws, {
        id,
        type: "home.snapshot",
        cached: false,
        age_seconds: 0,
        snapshot: { ...HOME, health: { ok: 0, warn: 0, fail: 0, skipped: 0 }, problems: [], problems_total: 0 },
      }),
    );
    await page.goto(`${base()}/#/${spec.route}`);
    await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "empty");
    if (name === "home" || name === "diagnostics") {
      await expect(page.locator(".connection-page")).toContainText("Данных пока нет");
    } else {
      await expect(page.locator(".connection-page")).toHaveCount(0);
      await expect(page.locator("main h1").first()).toHaveText(spec.title);
    }
  });
}
