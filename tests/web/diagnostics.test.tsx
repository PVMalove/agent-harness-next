import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { exportName, exportPayload } from "../../harness/console/frontend/src/diagnostics/exportReport";
import { LanguageProvider, checkRationale } from "../../harness/console/frontend/src/i18n";
import { fixReport } from "../../harness/console/frontend/src/routes/Diagnostics";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { CANCEL_REASON, FakeSocket, HEALTH_REPORT, ManualClock, jobReply, screenPage } from "./fake-socket";
import FEATURES from "./fixtures/features-snapshot.json";
import CONFIGURATION_CATALOG from "./fixtures/configuration-catalog.json";

const FIX = {
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

/** Answers the last features.snapshot request with `snapshot`. */
function replyFeatures(socket: FakeSocket, snapshot: unknown = FEATURES) {
  const request = socket.request("features.snapshot");
  act(() => socket.reply({ v: 1, id: request.id, type: "features.snapshot", ok: true, ...(snapshot as object) }));
}

function renderDiagnostics(report: unknown = HEALTH_REPORT, language = "") {
  window.location.hash = `#/diagnostics${language}`;
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
  const request = socket.request("diagnostics.snapshot");
  act(() => socket.reply(screenPage(request.id, "diagnostics.snapshot", JSON.stringify(report), { cached: true, age: 2 })));
  replyFeatures(socket);
  act(() => fireEvent.click(document.querySelector("#diagnostics-tab-checks-button")!));
  const catalog = socket.request("job.catalog");
  act(() =>
    socket.reply({ v: 1, id: catalog.id, type: "job.catalog", ok: true, commands: [FIX], cancel_reason: CANCEL_REASON }),
  );
  return { socket, client };
}

const rows = () => [...document.querySelectorAll("#diag-list [data-check]")].map((row) => row.getAttribute("data-check"));
const detail = () => document.querySelector("#diag-detail") as HTMLElement;

describe("the Diagnostics route", () => {
  beforeEach(() => FakeSocket.reset());

  test("shows the report's own counts and lists the checks by severity", () => {
    const { socket } = renderDiagnostics();
    expect(socket.request("diagnostics.snapshot")).toMatchObject({ online: false, force: false });
    expect(socket.request("job.catalog")).toMatchObject({ section: "diagnostics" });
    expect(document.querySelector("#diag-ok")?.textContent).toBe("2");
    expect(document.querySelector("#diag-warn")?.textContent).toBe("1");
    expect(document.querySelector("#diag-fail")?.textContent).toBe("1");
    expect(document.querySelector("#diag-skipped")?.textContent).toBe("1");
    expect(document.querySelector("#diag-total")?.textContent).toBe("5 проверок");
    expect(document.querySelector("#diag-checked")?.textContent).toContain("проверено 4 из 5");
    expect(rows()).toEqual(["hooks.policy", "environment.uv", "tracker.online", "files.lock", "directories.sandboxes"]);
    expect(within(detail()).getAllByText("Нет .harness/hook-policy.json").length).toBe(1);
    expect(within(detail()).getByText("Почему важно").nextElementSibling!.textContent).toBe(
      checkRationale("ru", "hooks.policy"),
    );
    expect(within(detail()).getByText("Запустите обновление")).toBeTruthy();
    expect(within(detail()).getByText("harness update .")).toBeTruthy();
    expect(within(detail()).getByText("Hooks проекта")).toBeTruthy();
  });

  test("a check the kernel catalog does not describe keeps the explicit no-data rationale", () => {
    renderDiagnostics();
    expect(checkRationale("en", "hooks.policy")).toMatch(/^Without a recorded hook policy/);
    expect(checkRationale("ru", "tracker.online")).toBeNull();
    act(() => fireEvent.click(document.querySelector('[data-check="tracker.online"]')!));
    const why = within(detail()).getByText("Почему важно").nextElementSibling as HTMLElement;
    expect(why.textContent).toBe("нет данных · обоснование для проверки не записано");
    expect(why.className).toContain("no-data");
  });

  test("the title facts end with the snapshot time, not the cache age", () => {
    renderDiagnostics();
    const clock = document.querySelector("#diag-cache")?.textContent ?? "";
    expect(clock.trim()).toMatch(/^\d{2}:\d{2}:\d{2}$/);
    expect(document.querySelector("#diag-summary")?.textContent).not.toContain("Новый снимок");
  });

  test("the summary counts are the server's even when they differ from the list", () => {
    renderDiagnostics({ ...HEALTH_REPORT, summary: { ok: 40, warn: 0, fail: 0, skipped: 0 } });
    expect(document.querySelector("#diag-ok")?.textContent).toBe("40");
    expect(screen.getByRole("button", { name: "Пройдено 40" })).toBeTruthy();
  });

  test("filters, searches and shows the skip callout and the missing command", () => {
    renderDiagnostics();
    act(() => fireEvent.click(screen.getByRole("button", { name: "Проблемы 2" })));
    expect(rows()).toEqual(["hooks.policy", "environment.uv"]);
    act(() => fireEvent.click(document.querySelector('[data-check="environment.uv"]')!));
    expect(within(detail()).getByText("Команда отсутствует — проверьте настройки вручную")).toBeTruthy();
    act(() => fireEvent.click(screen.getByRole("button", { name: "Все 5" })));
    act(() => fireEvent.change(screen.getByRole("searchbox"), { target: { value: "трекер" } }));
    expect(rows()).toEqual(["tracker.online"]);
    expect(within(detail()).getByText("Пропуск не считается успехом. Онлайн-проверки требуют сети и прав.")).toBeTruthy();
    act(() => fireEvent.change(screen.getByRole("searchbox"), { target: { value: "нет такой" } }));
    expect(rows()).toEqual([]);
    act(() => fireEvent.click(screen.getByRole("button", { name: "Сбросить" })));
    expect(rows()).toHaveLength(5);
  });

  test("the online switch and the refresh ask the server for that report", () => {
    const { socket } = renderDiagnostics();
    act(() => fireEvent.click(screen.getByRole("button", { name: "Онлайн" })));
    expect(socket.request("diagnostics.snapshot")).toMatchObject({ online: true, force: false });
    act(() => fireEvent.click(document.querySelector("#diag-refresh")!));
    expect(socket.request("diagnostics.snapshot")).toMatchObject({ online: true, force: true });
  });

  test("a finished fix job's report replaces the shown one with the fixes it applied", () => {
    const { socket } = renderDiagnostics();
    act(() => fireEvent.click(within(detail()).getByRole("button", { name: /Исправить/ })));
    const start = socket.request("job.start");
    expect(start).toMatchObject({ command_id: "diagnostics-fix", confirmed: false });
    const fixed = {
      ...HEALTH_REPORT,
      summary: { ok: 3, warn: 1, fail: 0, skipped: 1 },
      checks: HEALTH_REPORT.checks.map((check) =>
        check.id === "hooks.policy" ? { ...check, status: "ok", fix: null } : check,
      ),
      fixes_applied: ["Записана .harness/hook-policy.json"],
    };
    const text = JSON.stringify(fixed);
    act(() =>
      socket.reply(
        jobReply(start.id, "job.start", {
          command_id: "diagnostics-fix",
          mutating: true,
          phase: "completed",
          done: true,
          returncode: 0,
          cursor: 1,
          output: [{ channel: "stdout", text }],
        }),
      ),
    );
    expect(document.querySelector("#diag-fail")?.textContent).toBe("0");
    expect(within(document.querySelector("#diag-fixes") as HTMLElement).getByText("Записана .harness/hook-policy.json")).toBeTruthy();
  });

  test("a fix job without a report is a failure, never a report", () => {
    const failed = jobReply("x", "job.start", { command_id: "diagnostics-fix", phase: "failed", done: true, returncode: null });
    expect(fixReport(failed.job as never)).toBeNull();
    const garbage = jobReply("x", "job.start", {
      command_id: "diagnostics-fix",
      phase: "completed",
      done: true,
      returncode: 1,
      cursor: 1,
      output: [{ channel: "stdout", text: "{\"schema_version\": 1" }],
    });
    expect(fixReport(garbage.job as never)).toBeNull();
  });

  test("the export holds the report facts, the filter and only the visible checks", () => {
    const report = HEALTH_REPORT as Parameters<typeof exportPayload>[0];
    const payload = exportPayload(report, "problem", "", report.checks.slice(1, 3));
    expect(payload).toMatchObject({ schema_version: 1, online: false, filter: "problem", summary: report.summary });
    expect(payload.checks.map((check) => check.id)).toEqual(["hooks.policy", "environment.uv"]);
    expect(exportName(new Date("2026-11-05T10:41:00Z"))).toBe("harness-diagnostics-2026-11-05-10-41-00.json");
  });

  test("the Russian page names checks by title and statuses in words, never raw ids or FAIL/WARN/SKIP/OK", () => {
    renderDiagnostics();
    const list = document.querySelector("#diag-list") as HTMLElement;
    const text = `${list.textContent} ${detail().textContent}`;
    for (const raw of ["FAIL", "WARN", "SKIP", "hooks.policy", "environment.uv", "files.lock"]) expect(text).not.toContain(raw);
    expect(text).not.toMatch(/\bOK\b/);
    expect(within(list).getByText("Политика хуков")).toBeTruthy();
    expect(within(list).getByText("Менеджер пакетов uv")).toBeTruthy();
    expect(within(list).getAllByText("Ошибка").length).toBeGreaterThan(0);
    expect(within(list).getAllByText("Норма").length).toBeGreaterThan(0);
    expect(within(detail()).getByRole("heading", { level: 3, name: "Политика хуков" })).toBeTruthy();
    act(() => fireEvent.change(screen.getByRole("searchbox"), { target: { value: "менеджер пакетов" } }));
    expect(rows()).toEqual(["environment.uv"]);
  });

  test("in English the check titles and status words come from the catalog", () => {
    renderDiagnostics(HEALTH_REPORT, "?lang=en");
    const list = document.querySelector("#diag-list") as HTMLElement;
    expect(within(list).getByText("Hook policy")).toBeTruthy();
    expect(within(list).getAllByText("Failure").length).toBeGreaterThan(0);
    expect(within(list).getAllByText("Skipped").length).toBeGreaterThan(0);
  });

  test("in English the page labels and the check groups are translated", () => {
    renderDiagnostics(HEALTH_REPORT, "?lang=en");
    expect(screen.getByRole("region", { name: "Health summary" })).toBeTruthy();
    expect(within(detail()).getByText("Project hooks")).toBeTruthy();
    expect(within(detail()).getByText("What to do")).toBeTruthy();
  });
});

/** Opens Diagnostics on its Features tab with the fixture registry. */
function renderFeatures(snapshot: unknown = FEATURES) {
  window.location.hash = "#/diagnostics";
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
  replyFeatures(socket, snapshot);
  return { socket };
}

const featureRows = () => [...document.querySelectorAll("#features-list [data-feature]")].map((row) => row.getAttribute("data-feature"));
const pick = (id: string) => act(() => fireEvent.click(document.querySelector(`#features-list [data-feature="${id}"]`)!));

describe("the Diagnostics Features tab", () => {
  beforeEach(() => FakeSocket.reset());

  test("two tabs; the 26 features grouped by the 8 categories with their states", () => {
    const { socket } = renderFeatures();
    expect(socket.request("features.snapshot")).toMatchObject({ force: false });
    const tabs = screen.getAllByRole("tab").map((tab) => tab.textContent);
    expect(tabs.slice(0, 2)).toEqual(["1Функции26", "2Проверки—"]);
    expect(featureRows()).toHaveLength(26);
    const groups = [...document.querySelectorAll("#features-list [data-category]")].map((group) => group.getAttribute("data-category"));
    expect(groups).toEqual(["execution", "roles", "hooks", "context", "process", "publication", "capabilities", "platform"]);
    const memory = document.querySelector('#features-list [data-feature="memory"]') as HTMLElement;
    expect(memory.getAttribute("data-state")).toBe("disabled");
    expect(within(memory).getAllByText("Выключена").length).toBeGreaterThan(0);
    expect(memory.querySelector(".ds-status-off")).toBeTruthy();
    // This tab mounts the configuration command panel only, never the diagnostics one.
    const sections = socket.sent.filter((body) => body.type === "job.catalog").map((body) => body.section);
    expect(sections).toEqual(["configuration"]);
  });

  test("filters by state and category and searches", () => {
    renderFeatures();
    act(() => fireEvent.click(document.querySelector('[data-feature-filter="not_working"]')!));
    expect(featureRows()).toEqual(["containers", "git-guard"]);
    act(() => fireEvent.click(document.querySelector('[data-feature-filter="all"]')!));
    act(() => fireEvent.change(screen.getByRole("combobox", { name: "Категория" }), { target: { value: "process" } }));
    expect(featureRows()).toEqual(["approval", "retry", "preflight"]);
    act(() => fireEvent.change(screen.getByRole("combobox", { name: "Категория" }), { target: { value: "all" } }));
    act(() => fireEvent.change(screen.getByRole("searchbox", { name: "Найти функцию" }), { target: { value: "память" } }));
    expect(featureRows()).toEqual(["memory"]);
  });

  test("the detail shows readiness, configuration and links; a feature without a key cannot be switched", () => {
    renderFeatures();
    pick("git-guard");
    const detail = document.querySelector("#feature-detail") as HTMLElement;
    expect(within(detail).getAllByText("Файл хука отсутствует").length).toBe(1);
    expect(within(detail).getByText(".claude/hooks/block-pr-merge.sh")).toBeTruthy();
    const toggle = screen.getByRole("switch");
    expect(toggle.getAttribute("aria-disabled")).toBe("true");
    expect(toggle.getAttribute("aria-describedby")).toBe("feature-switch-reason");
    expect(document.querySelector("#feature-switch-reason")?.textContent).toBe("Нет булевого ключа конфигурации для переключения");
    pick("memory");
    act(() => fireEvent.click(document.querySelector("#feature-detail-tab-config-button")!));
    expect(within(document.querySelector("#feature-detail-config") as HTMLElement).getByText("memory.enabled")).toBeTruthy();
    pick("orchestration");
    act(() => fireEvent.click(document.querySelector("#feature-detail-tab-links-button")!));
    const links = document.querySelector("#feature-detail-links") as HTMLElement;
    expect(within(links).getByRole("button", { name: /Контейнерный executor/ })).toBeTruthy();
  });

  test("a pending configuration write disables every switch with its reason", () => {
    renderFeatures({ ...FEATURES, transaction_pending: true });
    pick("memory");
    expect(screen.getByRole("switch").getAttribute("aria-disabled")).toBe("true");
    expect(document.querySelector("#feature-switch-reason")?.textContent).toBe("Есть незавершённая запись конфигурации");
  });

  test("the switch plan shows the kernel's forecast: memory without sources becomes partial", () => {
    renderFeatures();
    pick("memory");
    const count = (id: string, state: string) => Number(document.querySelector(`#${id} [data-state="${state}"] b`)?.textContent);
    const plan = document.querySelector("#feature-plan") as HTMLElement;
    expect(within(plan).getByText("Выключена → Частично")).toBeTruthy();
    expect(count("feature-plan-before", "disabled")).toBe(4);
    expect(count("feature-plan-after", "disabled")).toBe(3);
    expect(count("feature-plan-after", "partial")).toBe(count("feature-plan-before", "partial") + 1);
    expect(count("feature-plan-after", "working")).toBe(count("feature-plan-before", "working"));
  });

  test("the forecast is the server's toggle.state_after, not a rule of the page", () => {
    const snapshot = {
      ...FEATURES,
      features: FEATURES.features.map((item) =>
        item.id === "retry" && item.toggle ? { ...item, toggle: { ...item.toggle, state_after: "not_working" } } : item,
      ),
    };
    renderFeatures(snapshot);
    pick("retry");
    const count = (id: string, state: string) => Number(document.querySelector(`#${id} [data-state="${state}"] b`)?.textContent);
    expect(within(document.querySelector("#feature-plan") as HTMLElement).getByText("Выключена → Не работает")).toBeTruthy();
    expect(count("feature-plan-after", "not_working")).toBe(count("feature-plan-before", "not_working") + 1);
  });
});

/** Opens the Features tab and answers the configuration catalog its command panel asks for. */
function renderToggle(snapshot: unknown = FEATURES) {
  const { socket } = renderFeatures(snapshot);
  const catalog = socket.request("job.catalog");
  expect(catalog).toMatchObject({ section: "configuration" });
  act(() => socket.reply({ v: 1, id: catalog.id, type: "job.catalog", ok: true, ...CONFIGURATION_CATALOG }));
  return { socket };
}

const starts = (socket: FakeSocket) => socket.sent.filter((body) => body.type === "job.start");

describe("switching a feature", () => {
  beforeEach(() => FakeSocket.reset());

  test("disabling a real-fixture feature names its off effect and the forecast; no registry dependent stops", () => {
    const { socket } = renderToggle();
    pick("attestation");
    act(() => fireEvent.click(screen.getByRole("switch")));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/^Выключить «Worker attestation»\. Состояние worker принимается без подтверждения\.$/)).toBeTruthy();
    expect(within(dialog).queryByText(/Перестанут работать/)).toBeNull();
    const context = dialog.querySelector("pre")!.textContent!;
    expect(context).toContain("orchestration.json › worker_attestation_required: true → false");
    expect(context).toContain("Worker attestation: Работает → Выключена");
    act(() => fireEvent.click(within(dialog).getByRole("button", { name: "Отмена" })));
    expect(starts(socket)).toEqual([]);
  });

  // `required_by` is fabricated here: no feature of the real registry depends on a switchable one.
  test("disabling a feature others need asks first and shows what stops and the before/after plan", () => {
    const snapshot = {
      ...FEATURES,
      features: FEATURES.features.map((item) =>
        item.id === "attestation" ? { ...item, required_by: ["containers", "memory"] } : item,
      ),
    };
    const { socket } = renderToggle(snapshot);
    pick("attestation");
    act(() => fireEvent.click(screen.getByRole("switch")));
    const dialog = screen.getByRole("dialog");
    // Only the dependents that work today stop: memory is already disabled.
    expect(within(dialog).getByText(/Перестанут работать: Контейнерный executor$/)).toBeTruthy();
    expect(within(dialog).getByText(/Состояние worker принимается без подтверждения\./)).toBeTruthy();
    const context = dialog.querySelector("pre")!.textContent!;
    expect(context).toContain("orchestration.json › worker_attestation_required: true → false");
    expect(context).toContain("Worker attestation: Работает → Выключена");
    expect(starts(socket)).toEqual([]);
    act(() => fireEvent.click(within(dialog).getByRole("button", { name: "Отмена" })));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(starts(socket)).toEqual([]);
  });

  test("a confirmed switch is the configuration-apply job with the snapshot digests", () => {
    const { socket } = renderToggle();
    pick("memory");
    act(() => fireEvent.click(screen.getByRole("switch")));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("configuration-apply")).toBeTruthy();
    expect(
      within(dialog).getByText(
        "Включить «Память проекта». Будет работать частично: Память включена без источников (memory_policy.source_types, memory_policy.allow_paths)",
      ),
    ).toBeTruthy();
    expect(dialog.querySelector("pre")!.textContent).toContain("Память проекта: Выключена → Частично");
    act(() => fireEvent.click(within(dialog).getByRole("button", { name: "Запустить" })));
    const [start] = starts(socket);
    expect(start).toMatchObject({ command_id: "configuration-apply", confirmed: true });
    const request = JSON.parse(String((start.values as Record<string, string>).request));
    expect(request.changes).toEqual([{ file: "project.json", path: ["memory", "enabled"], value: true }]);
    expect(request.expected).toEqual({ "project.json": FEATURES.config_digests["project.json"] });
    // The write finished: the registry is read again from the server, bypassing its cache.
    act(() =>
      socket.reply(
        jobReply(start.id, "job.start", { command_id: "configuration-apply", mutating: true, phase: "completed", done: true, returncode: 0 }),
      ),
    );
    expect(socket.request("features.snapshot")).toMatchObject({ force: true });
    expect(document.querySelector("#feature-write-error")).toBeNull();
  });

  test("a stale file refusal shows the server's text next to the feature", () => {
    const { socket } = renderToggle();
    pick("retry");
    act(() => fireEvent.click(screen.getByRole("switch")));
    act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Запустить" })));
    const [start] = starts(socket);
    const stale = "Файл изменён другим процессом; загрузите внешние изменения и заново просмотрите итог";
    act(() =>
      socket.reply(
        jobReply(start.id, "job.start", {
          command_id: "configuration-apply",
          mutating: true,
          phase: "failed",
          done: true,
          returncode: 3,
          cursor: 1,
          output: [{ channel: "stderr", text: `${stale}\n` }],
        }),
      ),
    );
    replyFeatures(socket);
    const alert = document.querySelector("#feature-write-error") as HTMLElement;
    expect(alert.getAttribute("data-stale")).toBe("true");
    expect(alert.textContent).toBe(`Конфликт версии конфигурации: ${stale}`);
  });
});
