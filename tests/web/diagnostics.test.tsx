import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { exportName, exportPayload } from "../../harness/console/frontend/src/diagnostics/exportReport";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { fixReport } from "../../harness/console/frontend/src/routes/Diagnostics";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { CANCEL_REASON, FakeSocket, HEALTH_REPORT, ManualClock, jobReply, screenPage } from "./fake-socket";

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
    expect(within(detail()).getByText("Нет .harness/hook-policy.json")).toBeTruthy();
    expect(within(detail()).getByText("Запустите обновление")).toBeTruthy();
    expect(within(detail()).getByText("harness update .")).toBeTruthy();
    expect(within(detail()).getByText("Hooks проекта")).toBeTruthy();
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

  test("in English the page labels and the check groups are translated", () => {
    renderDiagnostics(HEALTH_REPORT, "?lang=en");
    expect(screen.getByRole("heading", { level: 2, name: "Health summary" })).toBeTruthy();
    expect(within(detail()).getByText("Project hooks")).toBeTruthy();
    expect(within(detail()).getByText("How to fix:")).toBeTruthy();
  });
});
