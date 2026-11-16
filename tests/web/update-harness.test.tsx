import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { conflictsText, updateCommand } from "../../harness/console/frontend/src/update/format";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { FakeSocket, ManualClock, jobReply, screenPage } from "./fake-socket";
import CATALOG from "./fixtures/update-catalog.json";
import DIFF from "./fixtures/update-harness-diff.json";
import FACTS from "./fixtures/update-harness-facts.json";
import OPEN from "./fixtures/open-project.json";
import UPDATE from "./fixtures/update-harness.json";

function answer(socket: FakeSocket, type: string, value: unknown) {
  const request = socket.request(type);
  act(() => socket.reply(screenPage(request.id, type, JSON.stringify(value), { cached: false, age: 0 })));
  return request;
}

function renderPage(facts: unknown = UPDATE) {
  window.location.hash = "#/update-harness";
  const client = createConsoleClient({
    url: "ws://127.0.0.1:1/ws",
    WebSocket: FakeSocket,
    timers: new ManualClock(),
    probeHealth: async () => false,
  });
  render(
    <LanguageProvider>
      <App client={client} />
    </LanguageProvider>,
  );
  const socket = FakeSocket.last;
  act(() => socket.open());
  const request = answer(socket, "update_harness.snapshot", facts);
  answer(socket, "open_project.snapshot", OPEN);
  const catalog = socket.sent.find((body) => body.type === "job.catalog");
  if (catalog) act(() => socket.reply({ v: 1, id: catalog.id, type: "job.catalog", ok: true, ...CATALOG }));
  return { socket, request };
}

const content = () => document.querySelector("main#content")?.textContent ?? "";
const starts = (socket: FakeSocket) => socket.sent.filter((body) => body.type === "job.start");
const run = () => document.querySelector("#update-run") as HTMLButtonElement;
const countRows = () =>
  [...document.querySelectorAll("#update-changes .ds-update-count")].map((row) => [
    row.querySelector("b")?.textContent,
    row.querySelector(".ds-row-main")?.textContent,
    row.querySelector(".ds-status svg") !== null,
  ]);
const howTab = (name: string) => act(() => fireEvent.click(document.querySelector(`#update-how-tab-${name}-button`)!));
const mode = (name: string) => act(() => fireEvent.click(screen.getByRole("radio", { name })));

describe("the Update Harness route", () => {
  beforeEach(() => FakeSocket.reset());

  test("shows every fact the TUI shows; a diff is read only for the opened file", () => {
    const { socket, request } = renderPage();
    expect(request).toMatchObject({ force: false });
    // The TUI draws a drift counter as one line «2 ✔ обновятся»; the page draws value, icon and
    // label in the mockup grid, and the seed counter lives in the seed panel of the seed mode.
    // A TUI status glyph is an icon on the page, so the words are compared without it.
    const drift = /^(\d+) [✔⚠✖] (.+)$/;
    const counted = FACTS.page.filter((fact) => drift.test(fact)).map((fact) => fact.match(drift)!.slice(1));
    const words = (fact: string) => fact.replace(/^[✔⚠✖○] /, "");
    expect(FACTS.page.filter((fact) => !drift.test(fact) && !fact.startsWith("отмечено") && !content().includes(words(fact)))).toEqual([]);
    expect(countRows()).toEqual(counted.map(([value, label]) => [value, label, true]));
    // As in the mockup the first file is open, so only its diff is read.
    const first = document.querySelector("#update-diff .ds-diff-file") as HTMLElement;
    expect(first.getAttribute("aria-pressed")).toBe("true");
    expect(socket.sent.filter((body) => body.type === "update_harness.diff").map((body) => body.path)).toEqual([first.dataset.path]);
    act(() => fireEvent.click(document.querySelector('#update-diff [data-path="AGENTS.md"]') as HTMLElement));
    const diff = answer(socket, "update_harness.diff", DIFF);
    expect(diff).toEqual({ id: diff.id, type: "update_harness.diff", path: "AGENTS.md" });
    expect(FACTS.diff.filter((fact) => !content().includes(fact))).toEqual([]);
    expect(document.querySelector(".ds-diff-add")?.textContent).toBe("+Package rule.\n");
    expect(document.querySelector(".ds-diff-del")?.textContent).toBe("-Local rule.\n");
  });

  test("lays out the v3 blocks: summary, files, the selected file and the aside «Как обновить»", () => {
    renderPage();
    const grid = document.querySelector(".ds-update") as HTMLElement;
    expect([...grid.children].map((child) => child.id)).toEqual(["update-diff", "update-diff-view", "update-how"]);
    const stats = [...document.querySelectorAll("#update-versions .ds-stat")].map((stat) => [
      stat.querySelector(".ds-stat-label")?.textContent,
      stat.querySelector(".ds-stat-value")?.textContent,
    ]);
    expect(stats).toEqual([
      ["Установлено", "1.5.1"],
      ["Доступно", "2.0.0"],
      ["Расхождения", "7"],
      ["Runtime store", "schema 3 → 4"],
    ]);
    expect(document.querySelector("#update-versions .ds-verdict-warn")?.textContent).toBe("Доступно обновление");
    expect(document.querySelector("#update-cache")?.textContent?.trim()).toMatch(/^\d{2}:\d{2}:\d{2}$/);
    expect(document.querySelector("#update-cache")?.getAttribute("title")).toBe("Новый снимок · 0 s");
    const tabs = [...document.querySelectorAll("#update-how [role=tab]")].map((tab) => tab.textContent);
    expect(tabs).toEqual(["1Режим", "–Seed", "3План", "4Миграция"]);
    expect([...document.querySelectorAll(".ds-choice")].map((card) => [card.querySelector(".ds-row-title")?.textContent, card.querySelector(".ds-tag")?.textContent])).toEqual([
      ["Обычное", "рекомендуется"],
      ["С перезаписью управляемых файлов", "опасно"],
      ["С перезаписью выбранных seed-файлов", "выборочно"],
    ]);
    // A seed switch works only in the seed mode.
    howTab("seed");
    expect((screen.getByRole("switch", { name: ".harness/project.json" }) as HTMLButtonElement).disabled).toBe(true);
    howTab("mode");
    mode("С перезаписью выбранных seed-файлов");
    howTab("seed");
    expect((screen.getByRole("switch", { name: ".harness/project.json" }) as HTMLButtonElement).disabled).toBe(false);
    expect(document.querySelector('.ds-page-head a[href="#/diagnostics"]')).not.toBeNull();
  });

  test("the fields the snapshot lacks are marked «нет данных», never invented", () => {
    renderPage();
    const view = document.querySelector("#update-diff-view") as HTMLElement;
    expect(within(view).getAllByText("нет данных")).toHaveLength(2);
    expect(within(document.querySelector("#update-versions") as HTMLElement).getByText(/pre-release/).textContent).toContain("нет данных");
    expect(within(document.querySelector("#update-migration") as HTMLElement).getByText("Длительность шагов").nextElementSibling?.textContent).toBe("нет данных");
  });

  test("the decision of a conflict maps only to the real update modes", () => {
    renderPage();
    const decide = () => act(() => fireEvent.click(document.querySelector("#update-file-tab-decide-button")!));
    const choose = (name: string) =>
      act(() => fireEvent.click(within(document.querySelector("#update-decision") as HTMLElement).getByRole("button", { name })));
    act(() => fireEvent.click(document.querySelector('#update-diff [data-path="AGENTS.md"]') as HTMLElement));
    decide();
    choose("Взять версию пакета");
    expect(document.querySelector("#update-plan-command")?.textContent).toBe("harness update /work/project --force-managed-files");
    choose("Оставить мой файл");
    expect(document.querySelector("#update-plan-command")?.textContent).toBe("harness update /work/project");
    act(() => fireEvent.click(document.querySelector('#update-diff [data-path=".harness/project.json"]') as HTMLElement));
    choose("Взять версию пакета");
    expect(document.querySelector("#update-plan-command")?.textContent).toBe("harness update /work/project --force-seed-file .harness/project.json");
  });

  test("the plan follows the mode: command, warning and the seed selection", () => {
    renderPage();
    const plan = () => document.querySelector("#update-plan-command")?.textContent;
    expect(plan()).toBe("harness update /work/project");
    expect(document.querySelector("#update-warning")).not.toBeNull();
    mode("С перезаписью управляемых файлов");
    expect(plan()).toBe("harness update /work/project --force-managed-files");
    expect(document.querySelector("#update-warning")).toBeNull();
    mode("С перезаписью выбранных seed-файлов");
    expect(run().disabled).toBe(true);
    expect(content()).toContain("Отметьте хотя бы один файл");
    howTab("seed");
    act(() => fireEvent.click(screen.getByRole("button", { name: "Выбрать все" })));
    expect(document.querySelector("#update-seed-count")?.textContent).toBe("отмечено 2 из 2");
    expect(plan()).toBe(
      "harness update /work/project --force-seed-file .harness/project.json --force-seed-file docs/agents/git-workflow.md",
    );
    act(() => fireEvent.click(screen.getByRole("button", { name: "Снять выбор" })));
    expect(document.querySelector("#update-seed-count")?.textContent).toBe("отмечено 0 из 2");
    expect(conflictsText(3, "ru")).toBe("3 конфликта");
    expect(conflictsText(11, "ru")).toBe("11 конфликтов");
    expect(updateCommand("update", "/w/a b", [])).toBe("harness update '/w/a b'");
  });

  test("«Обновить» opens the confirmation; cancelling starts nothing, confirming starts one job", () => {
    const { socket } = renderPage();
    act(() => fireEvent.click(run()));
    let dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("update")).toBeTruthy();
    act(() => fireEvent.click(within(dialog).getByRole("button", { name: "Отмена" })));
    expect(starts(socket)).toEqual([]);
    mode("С перезаписью выбранных seed-файлов");
    howTab("seed");
    act(() => fireEvent.click(screen.getByRole("switch", { name: ".harness/project.json" })));
    act(() => fireEvent.click(run()));
    dialog = screen.getByRole("dialog");
    act(() => fireEvent.click(within(dialog).getByRole("button", { name: "Запустить" })));
    expect(starts(socket)).toHaveLength(1);
    expect(starts(socket)[0]).toMatchObject({
      command_id: "update-seed-selected",
      values: { paths: ".harness/project.json" },
      confirmed: true,
    });
    const start = socket.request("job.start");
    act(() => socket.reply(jobReply(start.id, "job.start", { command_id: "update-seed-selected", mutating: true })));
    const follow = socket.request("job.subscribe");
    const reads = socket.sent.filter((body) => body.type === "update_harness.snapshot").length;
    act(() =>
      socket.reply(
        jobReply(follow.id, "job.subscribe", { command_id: "update-seed-selected", mutating: true, phase: "completed", done: true, returncode: 0 }),
      ),
    );
    expect(socket.sent.filter((body) => body.type === "update_harness.snapshot")).toHaveLength(reads + 1);
    expect(socket.request("update_harness.snapshot")).toMatchObject({ force: true });
  });

  test("the files are grouped by what the update does, one compact row each: status icon, path and the kind word", () => {
    renderPage();
    expect(document.querySelector("#update-diff .ds-panel-meta")?.textContent).toBe("7 файлов");
    const groups = [...document.querySelectorAll("#update-diff [data-kind]")].map((group) => group.getAttribute("data-kind"));
    expect(groups).toEqual(["conflict", "package_changed", "added", "local_changed", "seed_differing"]);
    const rows = [...document.querySelectorAll("#update-diff .ds-diff-file")];
    expect(rows.length).toBe(7);
    for (const row of rows) {
      expect([...row.children].map((child) => child.className.split(" ")[0])).toEqual(["ds-status", "ds-row-main", "ds-row-end"]);
      expect(row.querySelector(".ds-diff-kind")?.textContent).not.toMatch(/[✔⚠✖○]/);
    }
  });

  test("the summary carries the version rows and the plan warning has no doubled glyph", () => {
    const { socket } = renderPage();
    const facts = [...document.querySelectorAll("#update-versions .ds-facts-main span")].map((item) => item.textContent);
    expect(facts).toContain("Скилов: 32");
    expect(facts).toContain("Lock обновлён: 2026-11-05 10:00 UTC");
    expect(document.querySelector("#update-warning b")?.textContent).not.toMatch(/^⚠/);
    const before = socket.sent.filter((body) => body.type === "update_harness.snapshot").length;
    act(() => fireEvent.click(document.querySelector("#update-recheck")!));
    expect(socket.sent.filter((body) => body.type === "update_harness.snapshot").length).toBe(before + 1);
  });

  test("the runtime-store migration panel shows the plan of a file-ledger project, never a run button", () => {
    renderPage();
    const panel = document.querySelector("#update-migration") as HTMLElement;
    const steps = [...panel.querySelectorAll(".ds-steps .ds-row")].map((step) => [
      step.querySelector(".ds-row-title")?.textContent,
      step.querySelector(".ds-row-end")?.textContent,
    ]);
    expect(steps).toEqual([
      ["01 · Backup", "ожидает"],
      ["02 · Schema 3 → 4", "ожидает"],
      ["03 · Cutover", "ожидает"],
      ["04 · Health", "после миграции"],
    ]);
    const facts = Object.fromEntries([...panel.querySelectorAll(".ds-kv-row")].map((row) => [row.querySelector("dt")?.textContent, row.querySelector("dd")?.textContent]));
    expect(facts).toEqual({ schema: "3 → 4", authority: "file-ledger", generation: "generation-0007", audit: "128", cutover: "нет данных", "Длительность шагов": "нет данных" });
    expect(panel.querySelector("button")).toBeNull();
    expect(panel.querySelector('a[href="#/diagnostics"]')).not.toBeNull();
  });

  test("a runtime-store project shows schema and cutover done and an honest backup gap", () => {
    renderPage({ ...UPDATE, store: { ...UPDATE.store, authority: "runtime-store", schema: 4, cutover_at: "2026-10-27T18:38:00Z" } });
    const states = [...document.querySelectorAll("#update-migration .ds-steps .ds-row-end")].map((item) => item.textContent);
    expect(states).toEqual(["нет данных", "выполнено", "выполнено", "после миграции"]);
    expect(document.querySelector("#update-migration .ds-steps .ds-row-sub")?.textContent).toBe("факт резервной копии в указателе не хранится");
  });

  test("the last run result is an in-panel honest empty state before any run of this console", () => {
    renderPage();
    const panel = document.querySelector("#update-result") as HTMLElement;
    expect(panel.querySelector("h3")?.textContent).toBe("Результат последнего запуска");
    expect(panel.querySelector(".ds-note")?.textContent).toContain("Ещё не запускалось в этой консоли");
    expect(panel.querySelector(".ds-note")?.textContent).toContain("harness update");
  });

  test("a project without the harness cannot be updated", () => {
    window.location.hash = "#/update-harness";
    const client = createConsoleClient({ url: "ws://127.0.0.1:1/ws", WebSocket: FakeSocket, timers: new ManualClock(), probeHealth: async () => false });
    render(
      <LanguageProvider>
        <App client={client} />
      </LanguageProvider>,
    );
    const socket = FakeSocket.last;
    act(() => socket.open());
    answer(socket, "update_harness.snapshot", { ...UPDATE, state: { ...UPDATE.state, installed: false }, drift: null });
    expect(content()).toContain("Харнесс не установлен: нет читаемого .harness/harness.lock");
    expect(run().disabled).toBe(true);
  });
});
