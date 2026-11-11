/* Diagnostics in the real build over a mocked socket: the health report arrives in several
   snapshot pages, the list filters and selects, the export downloads under the real CSP, a fix
   job's report replaces the view, and the page fits 1440 and 390 px without horizontal overflow.

   Manual mockup-conformance checklist (docs/design/web-console-mockups, route #diagnostics):
   - [x] Title: h1, subtitle, facts (total checks, groups, mode, cache), actions «Проверить»,
         «Экспорт», «Обновление».
   - [x] «Сводка здоровья»: four counters and the health strip from the report summary, the
         Офлайн/Онлайн switch, the checked count and the CLI line.
   - [x] «Проверки»: chips Все/Проблемы/Пропущено/Пройдено with the summary counts, search, rows
         sorted fail → warn → skip → ok with status icon, check title, group · message and status word.
   - [x] Master-detail of equal height; the detail shows pill, group, id, message, «Как исправить:»,
         the manual command with «Копировать команду», the source line and the skip callout.
   - [x] «Экспорт» saves JSON of the visible checks with the filter (Blob, no CSP change).
   - Deviations: every check of the report instead of the mockup's «7 ключевых»; «Что проверено» is
     the check message and «Почему важно» the kernel catalog of check rationales; «Исправить» runs the section's
     server fix command (all internal fixers, as `harness health --fix`), not a per-check plan;
     no jump links from a check (TUI-only routes); no download/search icons (not in the icon set). */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { Page, WebSocketRoute } from "@playwright/test";

type Body = Record<string, unknown>;

const base = () => process.env.CONSOLE_BASE_URL!;
const read = (name: string) => JSON.parse(readFileSync(resolve(__dirname, "fixtures", name), "utf-8")) as Body;
const HOME = read("home-snapshot.json");
const REPORT = read("diagnostics-report.json");

const FIX_COMMAND = {
  command_id: "diagnostics-fix",
  title: "Применить локальные фиксы Диагностики",
  section: "diagnostics",
  reversibility: "reversible",
  reversibility_label: "✔ обратимо",
  needs_confirmation: false,
  confirmation_reason: null,
  typed_confirmation: null,
  read_only: false,
  inputs: [],
  plan_required: false,
  available: true,
};
const ONLINE_FIX = {
  ...FIX_COMMAND,
  command_id: "diagnostics-online-fix",
  title: "Применить фиксы Диагностики с онлайн-проверками",
  reversibility: "external-change",
  reversibility_label: "⚠ внешнее",
  needs_confirmation: true,
  confirmation_reason: "Команда меняет внешнюю систему: это видят другие люди или это расходует токены.",
};

const send = (ws: WebSocketRoute, body: Body) => ws.send(JSON.stringify({ v: 1, ok: true, ...body }));

/** Serves `report` as diagnostics.snapshot in three pages; `onStart` answers job.start. */
async function mockSocket(page: Page, onStart: (ws: WebSocketRoute, request: Body) => void = () => {}) {
  const requests: Body[] = [];
  await page.routeWebSocket("**/ws", (ws) => {
    let text = "";
    ws.onMessage((message) => {
      const request = JSON.parse(String(message)) as Body;
      requests.push(request);
      const id = request.id;
      if (request.type === "home.snapshot") {
        send(ws, { id, type: "home.snapshot", cached: true, age_seconds: 3, snapshot: HOME });
      } else if (request.type === "diagnostics.snapshot") {
        text = JSON.stringify({ ...REPORT, online: request.online === true });
        const next = Math.floor(text.length / 3);
        send(ws, { id, type: "diagnostics.snapshot", snapshot_id: 4, text: text.slice(0, next), next, done: false, cached: true, age_seconds: 3 });
      } else if (request.type === "snapshot.page") {
        const offset = Number(request.offset);
        const next = Math.min(text.length, offset + Math.floor(text.length / 3));
        send(ws, { id, type: "snapshot.page", text: text.slice(offset, next), next, done: next >= text.length });
      } else if (request.type === "job.catalog") {
        send(ws, { id, type: "job.catalog", commands: [FIX_COMMAND, ONLINE_FIX], cancel_reason: "Отмена останавливает команду; уже внесённые изменения не откатываются." });
      } else if (request.type === "job.list") {
        send(ws, { id, type: "job.list", jobs: [] });
      } else if (request.type === "job.start") {
        onStart(ws, request);
      }
    });
  });
  return requests;
}

async function open(page: Page, width: number) {
  await page.setViewportSize({ width, height: width > 600 ? 900 : 844 });
  await page.clock.setFixedTime(new Date("2026-11-05T10:41:00Z"));
  await page.goto(`${base()}/#/diagnostics`);
  await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "connected");
  await expect(page.locator("#diag-total")).toHaveText("12 проверок");
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
}

const rows = (page: Page) => page.locator("#diag-list [data-check]");

test("the paged report is read to its end and filters and selects", async ({ page }) => {
  const requests = await mockSocket(page);
  await open(page, 1440);
  expect(requests.filter((request) => request.type === "snapshot.page").length).toBeGreaterThanOrEqual(2);
  await expect(page.locator("#diag-fail")).toHaveText("2");
  await expect(rows(page).first()).toHaveAttribute("data-check", "files.managed");
  await page.getByRole("button", { name: "Пропущено 2" }).click();
  await expect(rows(page)).toHaveCount(2);
  await rows(page).nth(1).click();
  await expect(page.locator("#diag-detail .diag-callout")).toBeVisible();
  await page.getByRole("button", { name: "Все 12" }).click();
  await page.getByRole("searchbox").fill("repo map");
  await expect(rows(page)).toHaveCount(1);
  await expect(page.locator("#diag-detail")).toContainText("harness repo-map build .");
});

test("the export downloads the visible checks as JSON under the real CSP", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  await mockSocket(page);
  await open(page, 1440);
  await page.getByRole("button", { name: "Проблемы 4" }).click();
  const [download] = await Promise.all([page.waitForEvent("download"), page.locator("#diag-export").click()]);
  expect(download.suggestedFilename()).toBe("harness-diagnostics-2026-11-05-10-41-00.json");
  const saved = JSON.parse(readFileSync(await download.path(), "utf-8")) as Body;
  expect(saved).toMatchObject({ schema_version: 1, filter: "problem", summary: REPORT.summary });
  expect((saved.checks as Body[]).map((check) => check.id)).toEqual([
    "files.managed",
    "hooks.policy",
    "hooks.codex",
    "repo_map.cache",
  ]);
  expect(errors.filter((text) => text.includes("Content Security Policy"))).toEqual([]);
});

test("a finished fix job's report replaces the shown one", async ({ page }) => {
  const fixed = {
    ...REPORT,
    summary: { ok: 7, warn: 2, fail: 1, skipped: 2 },
    checks: (REPORT.checks as Body[]).map((check) =>
      check.id === "hooks.policy" ? { ...check, status: "ok", fix: null } : check,
    ),
    fixes_applied: ["Записана .harness/hook-policy.json"],
  };
  await mockSocket(page, (ws, request) => {
    send(ws, {
      id: request.id,
      type: "job.start",
      job: {
        id: "job-1",
        command_id: "diagnostics-fix",
        mutating: true,
        phase: "completed",
        cursor: 1,
        done: true,
        truncated: false,
        returncode: 1,
        error: "",
        output: [{ channel: "stdout", text: JSON.stringify(fixed) }],
      },
    });
  });
  await open(page, 1440);
  await page.locator("#diag-detail").getByRole("button", { name: "Исправить" }).click();
  await expect(page.locator("#diag-fail")).toHaveText("1");
  await expect(page.locator("#diag-fixes")).toContainText("Записана .harness/hook-policy.json");
});

for (const width of [1440, 390]) {
  test(`diagnostics at ${width} px`, async ({ page }) => {
    await mockSocket(page);
    await open(page, width);
    await expect(page.locator(".command-panel [data-command]")).toHaveCount(2);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
