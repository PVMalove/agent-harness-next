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
  [...document.querySelectorAll("#update-changes .update-count-row")].map((row) => [
    row.querySelector(".count-value")?.textContent,
    row.querySelector(".count-label")?.textContent,
    row.querySelector(".count-icon svg") !== null,
  ]);
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
    const first = document.querySelector("#update-diff .diff-file") as HTMLElement;
    expect(first.getAttribute("aria-selected")).toBe("true");
    expect(socket.sent.filter((body) => body.type === "update_harness.diff").map((body) => body.path)).toEqual([first.dataset.path]);
    act(() => fireEvent.click(document.querySelector('#update-diff [data-path="AGENTS.md"]') as HTMLElement));
    const diff = answer(socket, "update_harness.diff", DIFF);
    expect(diff).toEqual({ id: diff.id, type: "update_harness.diff", path: "AGENTS.md" });
    expect(FACTS.diff.filter((fact) => !content().includes(fact))).toEqual([]);
    expect(document.querySelector(".diff-line.add")?.textContent).toBe("+Package rule.\n");
    expect(document.querySelector(".diff-line.del")?.textContent).toBe("-Local rule.\n");
  });

  test("lays out the mockup blocks: versions with changes, modes with the plan, seeds only in the seed mode", () => {
    renderPage();
    const grid = document.querySelector(".update-top-grid") as HTMLElement;
    expect([...grid.children].map((child) => child.id)).toEqual(["update-versions", "update-modes-card"]);
    expect(grid.querySelector("#update-versions #update-changes")).not.toBeNull();
    expect(grid.querySelector("#update-modes-card #update-plan-command")).not.toBeNull();
    const facts = [...document.querySelectorAll(".update-title .home-facts span")].map((item) => item.textContent);
    expect(facts.slice(0, 4)).toEqual(["1.5.1 → 2.0.0", "259 управляемых файлов", "32 навыка", "schema 3 → 4"]);
    expect(facts[4]).toMatch(/^\d{2}:\d{2}:\d{2}$/);
    expect(document.querySelector(".update-title .home-facts span:last-child")?.getAttribute("title")).toBe("Новый снимок · 0 s");
    expect(document.querySelector("#update-versions .update-pill")?.textContent).toBe("доступно");
    expect([...document.querySelectorAll(".update-mode-card")].map((card) => [card.querySelector("b")?.textContent, card.querySelector(".mode-tag")?.textContent])).toEqual([
      ["Обычное", "рекомендуется"],
      ["С перезаписью управляемых файлов", "опасно"],
      ["С перезаписью выбранных seed-файлов", "выборочно"],
    ]);
    expect(document.querySelector("#update-seeds")).toBeNull();
    expect(document.querySelector('.update-title a[href="#/diagnostics"]')).not.toBeNull();
    mode("С перезаписью выбранных seed-файлов");
    expect(document.querySelector("#update-seeds")).not.toBeNull();
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
    act(() => fireEvent.click(screen.getByLabelText(".harness/project.json")));
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

  test("the diff lists one compact row per file: status icon, path and the kind word", () => {
    renderPage();
    expect(document.querySelector("#update-diff")?.classList.contains("diff-panel")).toBe(true);
    expect(document.querySelector("#update-diff .panel-head .small")?.textContent).toMatch(/^выбор файла · 7 файлов · \d{2}:\d{2}:\d{2}$/);
    const rows = [...document.querySelectorAll("#update-diff .diff-file")];
    expect(rows.length).toBe(7);
    for (const row of rows) {
      expect([...row.children].map((child) => child.className.split(" ")[0])).toEqual(["diff-status", "diff-path", "diff-kind"]);
      expect(row.querySelector(".diff-kind")?.textContent).not.toMatch(/[✔⚠✖○]/);
      expect(row.querySelector(".diff-kind")?.className).toMatch(/ (ok|warn|err|active|muted)$/);
    }
    expect(document.querySelector("#update-diff .diff-detail .diff-detail-head")).not.toBeNull();
  });

  test("versions carry the schema row and a refresh in the foot, without doubled glyphs", () => {
    const { socket } = renderPage();
    const versions = document.querySelector("#update-versions") as HTMLElement;
    const rows = [...versions.querySelectorAll(".version-facts > div")].map((row) => [row.querySelector("dt")?.textContent, row.querySelector("dd")?.textContent]);
    expect(rows).toContainEqual(["Schema", "3 → 4"]);
    expect(versions.querySelector(".version-status")?.textContent?.trim()).toBe("Доступно обновление");
    expect(document.querySelector("#update-warning b")?.textContent).not.toMatch(/^⚠/);
    const refresh = versions.querySelector(".changes-foot button") as HTMLButtonElement;
    const before = socket.sent.filter((body) => body.type === "update_harness.snapshot").length;
    act(() => fireEvent.click(refresh));
    expect(socket.sent.filter((body) => body.type === "update_harness.snapshot").length).toBe(before + 1);
  });

  test("the runtime-store migration panel shows the plan of a file-ledger project, never a run button", () => {
    renderPage();
    const panel = document.querySelector("#update-migration.migration-panel") as HTMLElement;
    expect(panel.querySelector(".panel-head .small")?.textContent).toBe("schema 3 → 4");
    const steps = [...panel.querySelectorAll(".migration-step")].map((step) => [
      step.querySelector(".migration-num")?.textContent,
      step.querySelector("b")?.textContent,
      step.querySelector(".migration-state")?.textContent,
    ]);
    expect(steps).toEqual([
      ["01", "Backup", "ожидает"],
      ["02", "Schema 3 → 4", "ожидает"],
      ["03", "Cutover", "ожидает"],
      ["04", "Health", "после миграции"],
    ]);
    const facts = Object.fromEntries([...panel.querySelectorAll(".migration-facts > div")].map((row) => [row.querySelector("span")?.textContent, row.querySelector("b")?.textContent]));
    expect(facts).toEqual({ authority: "file-ledger", generation: "generation-0007", audit: "128", cutover: "нет данных" });
    expect(panel.querySelector("button")).toBeNull();
    expect(panel.querySelector('a[href="#/diagnostics"]')).not.toBeNull();
  });

  test("a runtime-store project shows schema and cutover done and an honest backup gap", () => {
    renderPage({ ...UPDATE, store: { ...UPDATE.store, authority: "runtime-store", schema: 4, cutover_at: "2026-10-27T18:38:00Z" } });
    const states = [...document.querySelectorAll("#update-migration .migration-state")].map((item) => item.textContent);
    expect(states).toEqual(["нет данных", "выполнено", "выполнено", "после миграции"]);
    expect(document.querySelector("#update-migration .migration-step small")?.textContent).toBe("факт резервной копии в указателе не хранится");
  });

  test("the last run result is an in-panel honest empty state before any run of this console", () => {
    renderPage();
    const panel = document.querySelector("#update-result.result-panel") as HTMLElement;
    expect(panel.querySelector(".panel-head h2")?.textContent).toBe("Результат последнего запуска");
    expect(panel.querySelector(".result-empty")?.textContent).toContain("Ещё не запускалось в этой консоли");
    expect(panel.querySelector(".result-empty")?.textContent).toContain("harness update");
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
