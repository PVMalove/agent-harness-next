/* Open Project, Update Harness, Configuration and Help in the real build over a mocked socket that
   serves the committed fixtures: the content of each route at 1440 and 390 px without horizontal
   overflow, with a full-page screenshot attached for manual review; an Update «Обновить» whose
   cancelled confirmation starts nothing; an Open Project copy that sends no request. No
   screenshot baselines (ADR 0029).

   Manual mockup-conformance checklist (docs/design/web-console-mockups):
   #open-project (README «Проект · шаг 5»)
   - [ ] Title, subtitle, compact stepper: выбор проекта → проверки → установка → настройка → диагностика.
   - [ ] «Текущий проект», «Проекты» and «Детали проекта»; «Проекты» and «Детали» equal height.
   - [ ] Selecting a project row updates the details; the copyable `harness console --web <path>` command.
   - [ ] «Путь к другому проекту» as a separate block under the list; checking it reads no Git or .harness.
   - [ ] «План установки» with the command and the confirmation; «Состав Harness» choice changes the plan.
   - [ ] «Детали проекта»: tracker line, name, path, branch · version, health counts, five check rows.
   - [ ] «Схема внедрения» with Runtime and Health from the Home snapshot; «Состав Harness» with
     descriptions and the footer; «Проверки» with counts, mode chips, fix links and the bar.
   - Deviations: the server never switches project (no «Открыть проект →»); branch and version of
     another candidate are not read; «Uncommitted files» is the local edits of managed files.
   #update-harness (README «Обновление · шаг 4»)
   - [ ] Versions installed → available with capabilities, skills, managed files.
   - [ ] Three modes: Обычное, С перезаписью управляемых файлов, С перезаписью выбранных seed-файлов.
   - [ ] Diff: file list left, diff right; a click shows the file's changes.
   - [ ] Seed panel: paths, «отмечено N из M», warning, «Выбрать все» / «Снять выбор».
   - [ ] «Что изменится» counts; «Версии» + «Что изменится» one block, «Режим» + «План» the second.
   - [ ] The plan changes command, warning and counters with the mode and the seed selection.
   - [ ] «Обновить» opens the confirmation; «Проверить заново» re-reads the snapshot.
   - [ ] Diff rows are one line each (status, path with ellipsis, kind word), the first file is open.
   - [ ] «Миграция runtime-store» from the store facts and «Результат последнего запуска» from this
     console's update jobs, with an in-panel honest «нет данных».
   #configuration (README «Настройки · шаг 11»)
   - [ ] KPI: project.json, orchestration.json validity, schema/orchestration installed, pending write.
   - [ ] Tabs Обзор / project.json / orchestration.json / История.
   - [ ] JSON editor with syntax check, the change list and a confirmed apply / save as version.
   - [ ] Runtime adapters with a confirmed update.
   - [ ] История: version store and «Сохранить текущую конфигурацию как версию».
   - Deviations: no guided «Настройки» wizard, AI hints, version list or restore (not in the snapshot;
     TUI only); no JSON export.
   #help (README «Справка · шаг 12»)
   - [ ] Tabs from the guide sections; intro; hotkeys and safety from the guide text.
   - [ ] Follows the ru/en switch.
   - Deviations: the mockup's fixed KPI counts, quick-link cards and FAQ are not facts of help.snapshot. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { Page, TestInfo, WebSocketRoute } from "@playwright/test";

type Body = Record<string, unknown>;

const base = () => process.env.CONSOLE_BASE_URL!;
const read = (name: string) => JSON.parse(readFileSync(resolve(__dirname, "fixtures", name), "utf-8")) as Body;
const HOME = read("home-snapshot.json");
const PAGED: Readonly<Record<string, Body>> = {
  "open_project.snapshot": read("open-project.json"),
  "update_harness.snapshot": read("update-harness.json"),
  "update_harness.diff": read("update-harness-diff.json"),
  "configuration.snapshot": read("configuration.json"),
};
const HELP: Readonly<Record<string, Body>> = { ru: read("help-ru.json"), en: read("help-en.json") };
const CATALOGS: Readonly<Record<string, Body>> = {
  setup: read("setup-catalog.json"),
  update: read("update-catalog.json"),
  configuration: read("configuration-catalog.json"),
};

const send = (ws: WebSocketRoute, body: Body) => ws.send(JSON.stringify({ v: 1, ok: true, ...body }));

async function mockSocket(page: Page) {
  const sent: Body[] = [];
  await page.routeWebSocket("**/ws", (ws) => {
    ws.onMessage((message) => {
      const request = JSON.parse(String(message)) as Body;
      sent.push(request);
      const id = request.id;
      const type = String(request.type);
      if (type === "home.snapshot") {
        send(ws, { id, type, cached: true, age_seconds: 3, snapshot: HOME });
      } else if (type in PAGED || type === "help.snapshot") {
        const text = JSON.stringify(type === "help.snapshot" ? HELP[String(request.language)] : PAGED[type]);
        const cache = type === "update_harness.diff" ? {} : { cached: false, age_seconds: 0 };
        send(ws, { id, type, snapshot_id: 1, text, next: text.length, done: true, ...cache });
      } else if (type === "job.catalog") {
        send(ws, { id, type, ...(CATALOGS[String(request.section)] ?? { commands: [], cancel_reason: "" }) });
      } else if (type === "job.list") {
        send(ws, { id, type, jobs: [] });
      }
    });
  });
  return sent;
}

async function open(page: Page, route: string, width: number, ready: string) {
  await page.clock.install({ time: new Date("2026-11-09T08:00:00Z") });
  await page.setViewportSize({ width, height: width > 600 ? 900 : 844 });
  await page.goto(`${base()}/#/${route}`);
  await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "connected");
  await expect(page.locator(ready).first()).toBeVisible();
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
}

const noOverflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
const starts = (sent: Body[]) => sent.filter((body) => body.type === "job.start");

async function shot(page: Page, info: TestInfo, name: string) {
  await info.attach(name, { body: await page.screenshot({ fullPage: true }), contentType: "image/png" });
}

for (const width of [1440, 390]) {
  test(`open project at ${width} px: a copied command sends nothing`, async ({ page }, info) => {
    const sent = await mockSocket(page);
    await open(page, "open-project", width, "#open-project-current");
    await expect(page.locator("#open-project-steps")).toContainText("Предварительные проверки");
    await expect(page.locator("#open-project-list [data-path]")).toHaveCount(3);
    await page.locator('[data-path="/work/billing"]').click();
    await expect(page.locator("#open-project-command")).toHaveText("harness console --web /work/billing");
    await expect(page.locator("#open-project-install-command")).toHaveText("harness update /work/project --capability engineering-suite");
    // As in the mockup the title carries only «Диагностика»; the plan is below the rollout scheme.
    await expect(page.locator(".project-title .actions > *")).toHaveCount(1);
    await page.locator("#open-project-plan").scrollIntoViewIfNeeded();
    await expect(page.locator("#open-project-plan")).toBeInViewport();
    await expect(page.locator("#open-project-detail .project-check")).toHaveCount(5);
    const before = sent.length;
    await page.getByLabel("Путь к локальному Git-проекту").fill("/srv/other");
    await expect(page.locator("#open-project-path-command")).toHaveText("harness console --web /srv/other");
    expect(sent.length).toBe(before);
    expect(sent.filter((body) => "project" in body || "path" in body)).toEqual([]);
    expect(await noOverflow(page)).toBe(true);
    await shot(page, info, `open-project-${width}`);
  });

  test(`update harness at ${width} px: a cancelled confirmation starts nothing`, async ({ page }, info) => {
    const sent = await mockSocket(page);
    await open(page, "update-harness", width, "#update-versions");
    await expect(page.locator("#update-changes .update-count-row.err")).toContainText("в конфликте (нужна перезапись)");
    await expect(page.locator("#update-warning")).toContainText("Обычное обновление остановится: 1 конфликт");
    // One compact line per diff entry (44 px); on a phone the mockup moves the kind under the path.
    const rows = await page.locator("#update-diff .diff-file").evaluateAll(
      (items, wide) =>
        items.map((row) => {
          const path = row.querySelector(".diff-path")!.getBoundingClientRect();
          const kind = row.querySelector(".diff-kind")!.getBoundingClientRect();
          return { height: row.getBoundingClientRect().height, sameLine: wide ? Math.abs(path.top - kind.top) < 4 : true };
        }),
      width > 720,
    );
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.filter((row) => row.height > (width > 720 ? 44 : 72) || !row.sameLine)).toEqual([]);
    await expect(page.locator("#update-migration .migration-step")).toHaveCount(4);
    await expect(page.locator("#update-result .result-empty")).toContainText("Ещё не запускалось");
    await page.locator('#update-diff [data-path="AGENTS.md"]').click();
    await expect(page.locator("#update-diff-view")).toContainText("+Package rule.");
    expect(await noOverflow(page)).toBe(true);
    await shot(page, info, `update-harness-${width}`);
    await page.locator("#update-run").click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText("update");
    await dialog.getByRole("button", { name: "Отмена", exact: true }).click();
    await expect(dialog).toHaveCount(0);
    expect(starts(sent)).toEqual([]);
  });

  test(`configuration at ${width} px`, async ({ page }, info) => {
    const sent = await mockSocket(page);
    await open(page, "configuration", width, "#configuration-kpi");
    await expect(page.locator("#configuration-adapters")).toContainText("⚠ требует обновления");
    expect(await noOverflow(page)).toBe(true);
    await shot(page, info, `configuration-${width}`);
    await page.getByRole("tab", { name: "project.json" }).click();
    await expect(page.getByRole("textbox", { name: "project.json" })).toHaveValue(/••••••/);
    expect(await noOverflow(page)).toBe(true);
    await shot(page, info, `configuration-editor-${width}`);
    expect(starts(sent)).toEqual([]);
  });

  test(`help at ${width} px`, async ({ page }, info) => {
    await mockSocket(page);
    await open(page, "help", width, "#help-intro");
    await expect(page.getByRole("tab")).toHaveCount(5);
    await expect(page.locator(".help-kpis")).toBeVisible();
    // The section text is not squeezed into a narrow column (the reviewed 1440x900 defect).
    const width_ = await page.locator("#help-intro").evaluate((element) => element.getBoundingClientRect().width);
    expect(width_).toBeGreaterThan(width > 600 ? 600 : 300);
    expect(await noOverflow(page)).toBe(true);
    for (const name of ["Экраны", "Команды", "Горячие клавиши", "Границы"]) {
      await page.getByRole("tab", { name, exact: true }).click();
      expect(await noOverflow(page)).toBe(true);
    }
    await page.getByRole("tab", { name: "Экраны", exact: true }).click();
    await expect(page.locator(".help-section table")).toBeVisible();
    const height = await page.evaluate(() => document.documentElement.scrollHeight);
    expect(height).toBeLessThan(6000);
    await shot(page, info, `help-${width}`);
  });
}
