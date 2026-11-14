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
const WIZARD = [
  { group: "orchestrator", file: "orchestration.json", path: ["approval_policy"], label: "Политика согласования", type: "enum",
    choices: ["manual_all", "milestone", "low_risk", "auto"], default: "manual_all", minimum: null, description: "Политика согласования шагов." },
  { group: "project", file: "project.json", path: ["language"], label: "Язык отчётов", type: "enum", choices: ["ru", "en"], default: null, minimum: null, description: "" },
  { group: "qa", file: "orchestration.json", path: ["execution_policy", "qa_lease_seconds"], label: "Аренда QA lane, с", type: "integer",
    choices: [], default: 1800, minimum: 1, description: "Срок аренды QA lane в секундах." },
  { group: "dispatch", file: "orchestration.json", path: ["execution_policy", "dispatch_poll_interval_seconds"], label: "Интервал опроса dispatch, с",
    type: "integer", choices: [], default: 5, minimum: 1, description: "" },
  { group: "hooks", file: "project.json", path: ["branch_pattern"], label: "Шаблон имени ветки", type: "string", choices: [], default: null, minimum: null, description: "" },
];

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

  test("the tabs follow the mockup: Overview, Settings, project.json, orchestration.json, History", () => {
    renderPage({ ...CONFIGURATION, wizard: WIZARD });
    expect(screen.getAllByRole("tab").map((item) => item.textContent)).toEqual(["Обзор", "Настройки", "project.json", "orchestration.json", "История"]);
  });

  test("the Settings wizard asks group by group and sends the answer as a confirmed draft", () => {
    const { socket } = renderPage({ ...CONFIGURATION, wizard: WIZARD });
    tab("Настройки");
    const groups = [...document.querySelectorAll("#configuration-wizard .wizard-group")];
    expect(groups.map((item) => item.querySelector("b")?.textContent)).toEqual(["Оркестратор", "Проект", "QA", "Dispatch", "Хуки"]);
    const wizard = document.querySelector("#configuration-wizard") as HTMLElement;
    expect(wizard.querySelector(".wizard-param-head code")?.textContent).toBe("orchestration.json → approval_policy");
    expect(wizard.textContent).toContain("Политика согласования");
    expect(wizard.textContent).toContain("manual_all");
    act(() => fireEvent.change(within(wizard).getByLabelText("Политика согласования"), { target: { value: "milestone" } }));
    act(() => fireEvent.click(groups[2]!));
    expect(wizard.querySelector(".wizard-param-head code")?.textContent).toBe("orchestration.json → execution_policy.qa_lease_seconds");
    act(() => fireEvent.change(within(wizard).getByLabelText("Аренда QA lane, с"), { target: { value: "900" } }));
    expect([...wizard.querySelectorAll(".configuration-changes li")].map((item) => item.textContent)).toEqual([
      'orchestration.json → approval_policy "milestone"',
      "orchestration.json → execution_policy.qa_lease_seconds 900",
    ]);
    act(() => fireEvent.click(within(wizard).getByRole("button", { name: "Применить" })));
    confirm();
    const [start] = starts(socket);
    expect(start).toMatchObject({ command_id: "configuration-apply", confirmed: true });
    expect(JSON.parse(String((start!.values as Record<string, string>).request))).toEqual({
      changes: [
        { file: "orchestration.json", path: ["approval_policy"], value: "milestone" },
        { file: "orchestration.json", path: ["execution_policy", "qa_lease_seconds"], value: 900 },
      ],
      expected: { "orchestration.json": CONFIGURATION.files["orchestration.json"].digest },
      description: "",
    });
  });

  test("without a wizard catalog the Settings tab says why", () => {
    renderPage({ ...CONFIGURATION, wizard: null });
    tab("Настройки");
    expect(document.querySelector("#configuration-wizard")?.textContent).toContain("нет данных");
  });

  test("the page follows the mockup: header, four KPIs, one tab bar, overview, editor and history panels", () => {
    renderPage();
    const actions = [...document.querySelectorAll(".settings-title .actions > *")];
    expect(actions.map((item) => item.textContent?.trim())).toEqual(["Проверить", "Экспорт", "Диагностика"]);
    expect(actions.every((item) => item.querySelector("svg"))).toBe(true);
    const facts = [...document.querySelectorAll(".settings-title .home-facts > span")].map((item) => item.textContent);
    expect(facts).toContain("1 config");
    expect(facts.at(-1)).toMatch(/^\d\d:\d\d:\d\d$/);
    const kpis = [...document.querySelectorAll("#configuration-kpi > div")];
    expect(kpis.map((card) => card.querySelector("span")?.textContent)).toEqual(["project.json", "orchestration.json", "Hook policy", "Runtime store"]);
    expect(kpis.map((card) => card.querySelector("b")?.textContent)).toEqual(["valid", "нет файла", "нет данных", "нет данных"]);
    expect(document.querySelector("#configuration-kpi")?.textContent).not.toMatch(/[✔✖○⚠]/);
    expect(document.querySelectorAll("main [role=tablist]")).toHaveLength(1);
    expect(document.querySelector("main [role=tablist]")?.className).toBe("orch-tabbar settings-tabbar");
    const rows = [...document.querySelectorAll("#configuration-files .settings-config-row")];
    expect(rows.map((row) => row.querySelector("b")?.textContent)).toEqual(["project.json", "orchestration.json", "hook-policy.json", "runtime-store"]);
    expect(rows.every((row) => row.querySelector("svg") && row.querySelector(".orch-pill"))).toBe(true);
    const policy = document.querySelector("#configuration-policy") as HTMLElement;
    expect(policy.querySelector("h2")?.textContent).toBe("Политики");
    expect(within(policy).getByText("Шаблон имени ветки").nextElementSibling?.textContent).toBe("feature/issue-{id}-{slug}");
    expect(policy.querySelectorAll(".settings-policy-chips .orch-pill").length).toBeGreaterThan(0);
    expect(document.querySelector(".settings-note-body a[href='#/diagnostics']")).toBeTruthy();
    tab("project.json");
    expect(document.querySelector("section.settings-editor .panel-head h2")?.textContent).toBe("Редактор · project.json");
    expect(document.querySelector("section.settings-editor .settings-file-line code")?.textContent).toBe(".harness/project.json");
    expect(document.querySelector("aside.settings-editor-side .panel-head h2")?.textContent).toBe("Schema");
    expect(document.querySelector("aside.settings-editor-side [data-run='configuration-apply']")).toBeTruthy();
    tab("История");
    const head = document.querySelector("#configuration-history > .panel-head") as HTMLElement;
    expect(head.className).toBe("panel-head");
    expect(head.querySelector("h2")?.textContent).toBe("История");
  });

  test("without the schema no file can be written", () => {
    renderPage({ ...CONFIGURATION, schema_installed: false });
    expect(content()).toContain("Сначала установите engineering-suite или backend-orchestration через меню подключения проекта");
    tab("project.json");
    expect(button("configuration-apply").disabled).toBe(true);
  });
});
