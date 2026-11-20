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
const tab = (name: string) => act(() => fireEvent.click(screen.getByRole("tab", { name: new RegExp(`${name}$`) })));
const button = (command: string) => document.querySelector(`[data-run="${command}"]`) as HTMLButtonElement;
const confirm = () => act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Запустить" })));
const edit = (name: string, document: unknown) =>
  act(() => fireEvent.change(screen.getByRole("textbox", { name }), { target: { value: JSON.stringify(document, null, 2) } }));
const changeRows = () => [...document.querySelectorAll("#configuration-changes li")].map((item) => item.textContent);
const PROJECT = CONFIGURATION.files["project.json"].document;
const WIZARD = [
  { group: "orchestrator", file: "orchestration.json", path: ["approval_policy"], label: "Политика согласования", type: "enum",
    choices: ["manual_all", "milestone", "low_risk", "auto"], default: "manual_all", minimum: null, description: "Политика согласования шагов.",
    recommendation: { value: "manual_all", reason: "Ручное согласование безопасно для первой настройки." } },
  { group: "project", file: "project.json", path: ["language"], label: "Язык отчётов", type: "enum", choices: ["ru", "en"], default: null, minimum: null, description: "",
    recommendation: null },
  { group: "qa", file: "orchestration.json", path: ["execution_policy", "qa_lease_seconds"], label: "Аренда QA lane, с", type: "integer",
    choices: [], default: 1800, minimum: 1, description: "Срок аренды QA lane в секундах.", recommendation: null },
  { group: "dispatch", file: "orchestration.json", path: ["execution_policy", "dispatch_poll_interval_seconds"], label: "Интервал опроса dispatch, с",
    type: "integer", choices: [], default: 5, minimum: 1, description: "", recommendation: null },
  { group: "hooks", file: "project.json", path: ["branch_pattern"], label: "Шаблон имени ветки", type: "string", choices: [], default: null, minimum: null, description: "",
    recommendation: null },
];
const VERSION_ID = "20261116T101500Z-0123456789ab";
const VERSIONS = [
  { id: VERSION_ID, created_at: "2026-11-16T10:15:00+00:00", description: "перед QA", files: ["project.json"], package_version: "2.1.0", problem: "" },
];

describe("the Configuration route", () => {
  beforeEach(() => FakeSocket.reset());

  test("has five tabs: Overview, Parameters, JSON, Changes, History", () => {
    renderPage({ ...CONFIGURATION, wizard: WIZARD });
    expect(screen.getAllByRole("tab").map((item) => item.textContent)).toEqual(["1Обзор", "2Параметры", "3JSON", "4Изменения", "5История"]);
    expect(document.querySelectorAll("main [role=tablist]")).toHaveLength(1);
  });

  test("shows every fact the TUI shows on the overview and the store root in the history", () => {
    renderPage();
    const store = CONFIGURATION.store_root;
    expect((FACTS as string[]).filter((fact) => fact !== store && !content().includes(fact))).toEqual([]);
    tab("История");
    expect(content()).toContain(store);
    expect(content()).toContain("Восстановление версии доступно в TUI.");
  });

  test("the leaf change set is that of the TUI draft; an untouched masked secret is not sent", () => {
    const edited = { ...PROJECT, tracker: { ...PROJECT.tracker, kind: "gitlab" }, qa_gate_commands: ["make lint", "make test"] };
    const { branch_pattern: _removed, ...rest } = edited;
    expect(leafChanges(PROJECT, rest, "project.json")).toEqual([
      { file: "project.json", path: ["branch_pattern"], remove: true },
      { file: "project.json", path: ["qa_gate_commands"], value: ["make lint", "make test"] },
      { file: "project.json", path: ["tracker", "kind"], value: "gitlab" },
    ]);
    expect(holdsMask({ a: ["••••••"] })).toBe(true);
    expect(draftRequest([], {}, "")).toBe('{"changes":[],"expected":{},"description":""}');
  });

  test("a JSON edit is applied from the Changes tab with only the changed file's digest after a confirmation", () => {
    const { socket } = renderPage();
    tab("Изменения");
    expect(button("configuration-apply").disabled).toBe(true);
    tab("JSON");
    expect(screen.getAllByRole("tab", { name: /json$/ }).map((item) => item.textContent)).toEqual(["project.json", "orchestration.json"]);
    expect(screen.getByRole("tablist", { name: "Файл" })).toBeTruthy();
    edit("project.json", { ...PROJECT, tracker: { ...PROJECT.tracker, kind: "gitlab" } });
    expect(starts(socket)).toEqual([]);
    tab("Изменения");
    expect(changeRows()).toEqual(['project.json → tracker.kind "gitlab"']);
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
    tab("JSON");
    act(() => fireEvent.click(screen.getByRole("tab", { name: "orchestration.json" })));
    edit("orchestration.json", { roles: { developer: { model: "••••••" } } });
    expect(content()).toContain("Скрытое значение нельзя записать: введите его заново");
    tab("Изменения");
    expect(button("configuration-save-draft").disabled).toBe(true);
    tab("JSON");
    act(() => fireEvent.click(screen.getByRole("tab", { name: "orchestration.json" })));
    act(() => fireEvent.change(screen.getByRole("textbox", { name: "orchestration.json" }), { target: { value: "{" } }));
    tab("Изменения");
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

  test("a Parameters answer and the console recommendation change only the draft; Changes writes it", () => {
    const { socket } = renderPage({ ...CONFIGURATION, wizard: WIZARD });
    tab("Параметры");
    const wizard = document.querySelector("#configuration-wizard") as HTMLElement;
    expect([...wizard.querySelectorAll(".ds-wz-group b")].map((item) => item.textContent)).toEqual(["Оркестратор", "Проект", "QA", "Dispatch", "Хуки"]);
    expect(wizard.querySelector(".ds-wz-head code")?.textContent).toBe("orchestration.json → approval_policy");
    expect(wizard.querySelector("#configuration-recommendation")?.textContent).toContain("Ручное согласование безопасно");
    expect(wizard.querySelectorAll("[data-run]")).toHaveLength(0);
    act(() => fireEvent.click(within(wizard).getByRole("button", { name: "Принять рекомендацию консоли" })));
    act(() => fireEvent.click(wizard.querySelectorAll(".ds-wz-group")[2]!));
    expect(wizard.querySelector(".ds-wz-head code")?.textContent).toBe("orchestration.json → execution_policy.qa_lease_seconds");
    expect(within(wizard).getByRole("button", { name: "Принять рекомендацию консоли" })).toHaveProperty("disabled", true);
    act(() => fireEvent.change(within(wizard).getByLabelText("Аренда QA lane, с"), { target: { value: "900" } }));
    expect(starts(socket)).toEqual([]);
    tab("Изменения");
    expect(changeRows()).toEqual([
      'orchestration.json → approval_policy "manual_all"',
      "orchestration.json → execution_policy {\"qa_lease_seconds\":900}",
    ]);
    act(() => fireEvent.click(button("configuration-apply")));
    confirm();
    const [start] = starts(socket);
    expect(start).toMatchObject({ command_id: "configuration-apply", confirmed: true });
    expect(JSON.parse(String((start!.values as Record<string, string>).request))).toMatchObject({
      expected: { "orchestration.json": CONFIGURATION.files["orchestration.json"].digest },
      description: "",
    });
  });

  // Review of PR #1186: the controlled number field snapped back on Backspace and swallowed "-".
  test("a number field can be emptied and retyped; only a valid number reaches the draft", () => {
    renderPage({ ...CONFIGURATION, wizard: WIZARD });
    tab("Параметры");
    const wizard = document.querySelector("#configuration-wizard") as HTMLElement;
    act(() => fireEvent.click(wizard.querySelectorAll(".ds-wz-group")[2]!));
    const field = within(wizard).getByLabelText("Аренда QA lane, с") as HTMLInputElement;
    act(() => fireEvent.change(field, { target: { value: "" } }));
    expect(field.value).toBe("");
    act(() => fireEvent.change(field, { target: { value: "-" } }));
    expect(field.value).toBe("-");
    expect(field.getAttribute("aria-invalid")).toBe("true");
    act(() => fireEvent.change(field, { target: { value: "1200" } }));
    expect(field.value).toBe("1200");
    expect(field.getAttribute("aria-invalid")).toBeNull();
    tab("Изменения");
    expect(changeRows()).toEqual(["orchestration.json → execution_policy {\"qa_lease_seconds\":1200}"]);
  });

  test("a JSON edit and a Parameters answer share one draft", () => {
    renderPage({ ...CONFIGURATION, wizard: WIZARD });
    tab("Параметры");
    act(() => fireEvent.click(document.querySelectorAll("#configuration-wizard .ds-wz-group")[4]!));
    act(() => fireEvent.change(screen.getByLabelText("Шаблон имени ветки"), { target: { value: "feature/{id}" } }));
    tab("JSON");
    expect((screen.getByRole("textbox", { name: "project.json" }) as HTMLTextAreaElement).value).toContain('"branch_pattern": "feature/{id}"');
    tab("Изменения");
    expect(changeRows()).toEqual(['project.json → branch_pattern "feature/{id}"']);
  });

  test("without a wizard catalog the Parameters tab says why", () => {
    renderPage({ ...CONFIGURATION, wizard: null });
    tab("Параметры");
    expect(document.querySelector("#configuration-wizard")?.textContent).toContain("нет данных");
  });

  test("History lists the versions and shows the JSON of the selected one", () => {
    const { socket } = renderPage({ ...CONFIGURATION, versions: VERSIONS });
    tab("История");
    expect(document.querySelector(`[data-version="${VERSION_ID}"]`)?.getAttribute("aria-pressed")).toBe("true");
    const asked = socket.sent.filter((body) => body.type === "configuration.snapshot" && body.version === VERSION_ID);
    expect(asked).toHaveLength(1);
    const version = {
      id: VERSION_ID,
      error: "",
      files: {
        "project.json": { exists: true, digest: "a".repeat(64), document: { language: "ru", tracker: { token: "••••••" } }, error: "" },
        "orchestration.json": { exists: false, digest: "", document: {}, error: "" },
      },
    };
    act(() => socket.reply(screenPage(asked[0]!.id, "configuration.snapshot", JSON.stringify({ ...CONFIGURATION, versions: VERSIONS, version }))));
    const shown = document.querySelector("#configuration-version-json")?.textContent ?? "";
    expect(shown).toContain('"language": "ru"');
    expect(shown).toContain("••••••");
    expect(shown).toContain("Файла нет в этой версии");
  });

  test("a version that cannot be read is a clear error, not an empty panel", () => {
    const { socket } = renderPage({ ...CONFIGURATION, versions: VERSIONS });
    tab("История");
    const asked = socket.sent.filter((body) => body.type === "configuration.snapshot" && body.version === VERSION_ID).at(-1)!;
    const version = { id: VERSION_ID, error: `Версия «${VERSION_ID}» не найдена в .harness/config_versions.`, files: {} };
    act(() => socket.reply(screenPage(asked.id, "configuration.snapshot", JSON.stringify({ ...CONFIGURATION, versions: VERSIONS, version }))));
    const alert = document.querySelector("#configuration-version-error");
    expect(alert?.getAttribute("role")).toBe("alert");
    expect(alert?.textContent).toContain("не найдена в .harness/config_versions");
  });

  test("the page is built on the design system: header, summary, pipe tabs and panels", () => {
    renderPage();
    const actions = [...document.querySelectorAll(".ds-page-head .ds-head-actions > *")];
    expect(actions.map((item) => item.textContent?.trim())).toEqual(["Проверить", "Экспорт", "Диагностика"]);
    const stats = [...document.querySelectorAll("#configuration-kpi .ds-stat")];
    expect(stats.map((card) => card.querySelector(".ds-stat-label")?.textContent)).toEqual(["project.json", "orchestration.json", "Версии", "Runtime store"]);
    expect(stats.map((card) => card.querySelector(".ds-stat-value")?.textContent).slice(0, 2)).toEqual(["valid", "нет файла"]);
    expect(document.querySelector("#configuration-kpi .ds-facts")?.textContent).toContain("1 config");
    expect(document.querySelector("main [role=tablist]")?.className).toBe("ds-pipe");
    const rows = [...document.querySelectorAll("#configuration-files [data-file]")];
    expect(rows.map((row) => row.getAttribute("data-file"))).toEqual(["project.json", "orchestration.json", "hook-policy.json", "runtime-store"]);
    expect(document.querySelector("#configuration-policy .ds-panel-title")?.textContent).toBe("Политики");
    expect(document.querySelector("#configuration-adapters.ds-panel")).toBeTruthy();
  });

  test("without the schema no file can be written", () => {
    renderPage({ ...CONFIGURATION, schema_installed: false });
    expect(content()).toContain("Сначала установите engineering-suite или backend-orchestration через меню подключения проекта");
    tab("Изменения");
    expect(button("configuration-apply").disabled).toBe(true);
  });
});
