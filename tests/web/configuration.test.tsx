import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { draftRequest, holdsMask, leafChanges } from "../../harness/console/frontend/src/configuration/changes";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { FakeSocket, ManualClock, screenPage } from "./fake-socket";
import CATALOG from "./fixtures/configuration-catalog.json";
import FACTS from "./fixtures/configuration-facts.json";
import CONFIGURATION from "./fixtures/configuration.json";

function renderPage(value: unknown = CONFIGURATION) {
  window.location.hash = "#/configuration";
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
  const request = socket.request("configuration.snapshot");
  act(() => socket.reply(screenPage(request.id, "configuration.snapshot", JSON.stringify(value), { cached: true, age: 3 })));
  const catalog = socket.sent.find((body) => body.type === "job.catalog");
  if (catalog) act(() => socket.reply({ v: 1, id: catalog.id, type: "job.catalog", ok: true, ...CATALOG }));
  return { socket, request };
}

const content = () => document.querySelector("main#content")?.textContent ?? "";
const starts = (socket: FakeSocket) => socket.sent.filter((body) => body.type === "job.start");
const tab = (name: string) => act(() => fireEvent.click(screen.getByRole("tab", { name })));
const button = (command: string) => document.querySelector(`[data-run="${command}"]`) as HTMLButtonElement;
const confirm = () => act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Запустить" })));
const edit = (name: string, document: unknown) =>
  act(() => fireEvent.change(screen.getByRole("textbox", { name }), { target: { value: JSON.stringify(document, null, 2) } }));
const PROJECT = CONFIGURATION.files["project.json"].document;

describe("the Configuration route", () => {
  beforeEach(() => FakeSocket.reset());

  test("shows every fact the TUI shows on the overview and the history tab", () => {
    renderPage();
    const store = CONFIGURATION.store_root;
    expect((FACTS as string[]).filter((fact) => fact !== store && !content().includes(fact))).toEqual([]);
    tab("История");
    expect(content()).toContain(store);
    expect(content()).toContain("Список версий и восстановление доступны в TUI.");
  });

  test("the leaf change set is that of the TUI draft; an untouched masked secret is not sent", () => {
    const edited = { ...PROJECT, tracker: { ...PROJECT.tracker, kind: "gitlab" }, qa_gate_commands: ["make lint", "make test"] };
    const { branch_pattern: _removed, ...rest } = edited;
    // Base keys first, in their order (the fixture's keys are sorted), as `_changed_paths` walks them.
    expect(leafChanges(PROJECT, rest, "project.json")).toEqual([
      { file: "project.json", path: ["branch_pattern"], remove: true },
      { file: "project.json", path: ["qa_gate_commands"], value: ["make lint", "make test"] },
      { file: "project.json", path: ["tracker", "kind"], value: "gitlab" },
    ]);
    expect(holdsMask({ a: ["••••••"] })).toBe(true);
    expect(draftRequest([], {}, "")).toBe('{"changes":[],"expected":{},"description":""}');
  });

  test("apply sends the changes and only the changed file's digest after a confirmation", () => {
    const { socket } = renderPage();
    tab("project.json");
    expect(button("configuration-apply").disabled).toBe(true);
    edit("project.json", { ...PROJECT, tracker: { ...PROJECT.tracker, kind: "gitlab" } });
    act(() => fireEvent.click(button("configuration-apply")));
    act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Отмена" })));
    expect(starts(socket)).toEqual([]);
    act(() => fireEvent.click(button("configuration-apply")));
    confirm();
    const [start] = starts(socket);
    expect(start).toMatchObject({ command_id: "configuration-apply", confirmed: true });
    expect(JSON.parse(String((start!.values as Record<string, string>).request))).toEqual({
      changes: [{ file: "project.json", path: ["tracker", "kind"], value: "gitlab" }],
      expected: { "project.json": "d".repeat(64) },
      description: "",
    });
  });

  test("a mask typed into a value and broken JSON are refused in the page", () => {
    const { socket } = renderPage();
    tab("orchestration.json");
    edit("orchestration.json", { roles: { developer: { model: "••••••" } } });
    expect(content()).toContain("Скрытое значение нельзя записать: введите его заново");
    expect(button("configuration-save-draft").disabled).toBe(true);
    act(() => fireEvent.change(screen.getByRole("textbox", { name: "orchestration.json" }), { target: { value: "{" } }));
    expect(button("configuration-apply").disabled).toBe(true);
    expect(starts(socket)).toEqual([]);
  });

  test("adapters, the current version and a pending write each run behind the dialog", () => {
    const { socket } = renderPage({ ...CONFIGURATION, transaction_pending: true });
    expect(button("configuration-adapters").disabled).toBe(true);
    act(() => fireEvent.click(button("configuration-recover")));
    confirm();
    expect(starts(socket).at(-1)).toMatchObject({ command_id: "configuration-recover", values: {}, confirmed: true });
    FakeSocket.reset();
    document.body.innerHTML = "";
    const next = renderPage();
    act(() => fireEvent.click(button("configuration-adapters")));
    confirm();
    expect(starts(next.socket).at(-1)).toMatchObject({
      command_id: "configuration-adapters",
      values: { request: JSON.stringify({ fingerprint: "f".repeat(64) }) },
    });
    tab("История");
    act(() => fireEvent.click(button("configuration-save-current")));
    confirm();
    expect(starts(next.socket).at(-1)).toMatchObject({
      command_id: "configuration-save-current",
      values: { request: '{"description":""}' },
      confirmed: true,
    });
  });

  test("without the schema no file can be written", () => {
    renderPage({ ...CONFIGURATION, schema_installed: false });
    expect(content()).toContain("Сначала установите engineering-suite или backend-orchestration через меню подключения проекта");
    tab("project.json");
    expect(button("configuration-apply").disabled).toBe(true);
  });
});
