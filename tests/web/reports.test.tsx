import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { LanguageProvider, translate } from "../../harness/console/frontend/src/i18n";
import {
  NO_FILTERS,
  qaLogText,
  reportSectionLines,
  reportSections,
  reportsById,
  roleFlowText,
  selectStages,
} from "../../harness/console/frontend/src/reports/format";
import type { Translate } from "../../harness/console/frontend/src/reports/format";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { parseReports, parseTimeline } from "../../harness/console/frontend/src/ws/ledger";
import { FakeSocket, ManualClock, screenPage } from "./fake-socket";
import FACTS from "./fixtures/reports-facts.json";
import REPORT from "./fixtures/reports-report.json";
import REPORTS from "./fixtures/reports.json";
import TIMELINE from "./fixtures/reports-timeline.json";

const answered = new Set<unknown>();

/** Answer every open request of `type` with `value` as a paged snapshot. */
function answer(socket: FakeSocket, type: string, value: unknown, cached = true) {
  const pending = socket.sent.filter((body) => body.type === type && !answered.has(body.id));
  for (const body of pending) {
    answered.add(body.id);
    const page = screenPage(body.id, type, JSON.stringify(value), { cached, age: 3 });
    if (type === "reports.report" || type === "reports.timeline") {
      delete page.cached;
      delete page.age_seconds;
    }
    act(() => socket.reply(page));
  }
}

function renderReports(language = "", snapshot: unknown = REPORTS, report: unknown = REPORT) {
  window.location.hash = `#/reports${language}`;
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
  answer(socket, "reports.snapshot", snapshot);
  answer(socket, "reports.report", report);
  return socket;
}

const content = () => document.querySelector("main#content")?.textContent ?? "";
/* The TUI facts the web Reports page does not repeat: the batch history and its chronology live on
   the Orchestration page (the mockup has no batch block on Reports), and the report sections are
   laid out as the mockup's summary, Evidence and conclusion rather than the TUI's section titles. */
const TUI_ONLY = new Set([
  "▶ в работе",
  "08.11.2026 09:00 UTC",
  "PR ещё не создан",
  "08.11.2026 08:00 UTC",
  "✔ завершён",
  "01.11.2026 08:00 UTC",
  "до PR: 1 дн 2 ч",
  "Вывод",
  "Следующее действие",
  "developer → review → qa → developer",
  "batch создан",
  "developer: d-dev, итог: reported",
  "отчёт developer: completed",
  "review: d-rev, итог: reported",
  "отчёт review: completed",
  "qa: d-qa, итог: reported",
  "developer: d-wip, итог: working",
  "отчёт qa: failed",
  "решение coordinator: developer-retry → developer (policy:auto) — QA упал",
]);
/** A TUI status is a symbol plus words; the mockup's rows show the words only. */
const words = (fact: string) => fact.replace(/^[✔▶Ⅱ○✖⚠] /, "");
const evidenceMarks = () =>
  [...document.querySelectorAll("#reports-evidence .ds-evidence-row")].map((row) =>
    [...row.querySelectorAll(".ds-evidence-cell")].map((cell) => MARKS[cell.getAttribute("data-cell")!]).join(""),
  );
/** A cell's state as one character, so a row of the matrix reads at a glance in the expectations. */
const MARKS: Record<string, string> = { present: "✓", stale: "!", missing: "—", none: "·" };

describe("the Reports route", () => {
  beforeEach(() => {
    FakeSocket.reset();
    answered.clear();
  });

  test("shows every fact the TUI shows for the same snapshot", () => {
    const socket = renderReports();
    expect(socket.request("reports.snapshot")).toMatchObject({ force: false });
    expect(socket.request("reports.report")).toMatchObject({ dispatch_id: "d-qa" });
    const list = content();
    act(() => fireEvent.click(screen.getByRole("tab", { name: /Качество$/ })));
    const shown = list + content();
    // An Evidence row shows the check command and its evidence as name and detail.
    const missing = (FACTS as string[]).filter(
      (fact) => !TUI_ONLY.has(fact) && !words(fact).split(" — ").every((part) => shown.includes(part)),
    );
    expect(missing).toEqual([]);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Отчёты");
  });

  test("the stage list follows the TUI order and filters; the report body stays text", () => {
    const socket = renderReports();
    const order = () => [...document.querySelectorAll("#report-list [data-stage]")].map((row) => row.getAttribute("data-stage"));
    expect(order()).toEqual(["d-qa", "d-wip", "d-rev", "d-dev", "d-arch-888", "d-old"]);
    act(() => fireEvent.change(document.querySelector("#filter-completion") as HTMLElement, { target: { value: "open" } }));
    expect(order()).toEqual(["d-wip", "d-arch-888"]);
    expect(content()).toContain("в работе · отчёта ещё нет");
    expect(content()).not.toContain("⚠ в работе");
    expect(content()).toContain("нет отчёта");
    act(() => fireEvent.change(document.querySelector("#filter-completion") as HTMLElement, { target: { value: "all" } }));
    act(() => fireEvent.change(document.querySelector("#filter-role") as HTMLElement, { target: { value: "rev" } }));
    expect(order()).toEqual(["d-rev"]);
    answer(socket, "reports.report", { output: "<img src=x onerror=alert(1)>", risks: { status: "none", details: "" } });
    expect(document.querySelector("img")).toBeNull();
    expect(content()).toContain("<img src=x onerror=alert(1)>");
  });

  test("the v3 order: header actions on the right, summary with 4 stats and 4 KPI facts, filter row, rows, detail with the QA lane", () => {
    const socket = renderReports();
    expect(document.querySelector(".ds-page.ds-fit[data-section=Reports]")).not.toBeNull();
    // Reports reads reports.* only: no orchestration snapshot is asked for.
    expect(socket.sent.filter((body) => body.type === "orchestration.snapshot")).toEqual([]);
    const title = document.querySelector(".ds-page-head .ds-head-actions")!;
    expect([...title.children].map((item) => item.id)).toEqual(["reports-refresh", "reports-export"]);
    expect(title.querySelector("#reports-export use, #reports-export svg")).not.toBeNull();
    expect(document.querySelector("#reports-updated")!.textContent).toMatch(/^\d{2}:\d{2}:\d{2}$/);
    expect(content()).not.toContain("Новый снимок");
    expect(document.querySelectorAll("#reports-summary .ds-stat")).toHaveLength(4);
    expect(document.querySelectorAll("#reports-tabs .ds-pipe-tab")).toHaveLength(4);
    expect(document.querySelector("main .orch-pill")).toBeNull();
    const kpi = [...document.querySelectorAll("#reports-kpi > div > span")].map((item) => item.textContent);
    expect(kpi).toEqual(["Evidence полно", "Stale evidence", "Задержка отчёта", "QA с первого раза"]);
    expect(document.querySelector("#reports-kpi")!.textContent).not.toContain("С рисками");
    const row = document.querySelector("#report-filter-row")!;
    expect(row.querySelector("select#report-status")).not.toBeNull();
    expect(row.querySelector(".report-search svg")).not.toBeNull();
    expect(row.querySelector("input#reports-search")).not.toBeNull();
    expect(document.querySelector("details#report-more-filters #filter-completion")).not.toBeNull();
    expect(document.querySelector(".report-list-foot")!.textContent).toBe("Отчёты не заменяют решение; evidence доступен в деталях.");
    const first = document.querySelector("#report-list .report-row")!;
    expect([...first.children].map((item) => item.className.split(" ")[0])).toEqual([
      "report-type-icon",
      "report-row-main",
      "ds-status",
      "report-status",
      "report-time",
    ]);
    expect(first.querySelector(".report-status")!.textContent).toBe("отчёт получен · ошибка");
    expect(first.querySelector(".report-time")!.textContent).toBe("12:00");
    const detail = document.querySelector("#report-detail .report-detail-body")!;
    const blocks = [".report-detail-top", "h3", ".report-meta", ".report-summary", ".report-evidences", ".report-conclusion", ".report-actions"];
    const tops = blocks.map((selector) => [...detail.querySelectorAll("*")].indexOf(detail.querySelector(selector)!));
    expect(tops.every((index) => index >= 0)).toBe(true);
    expect([...tops].sort((a, b) => a - b)).toEqual(tops);
    expect(detail.querySelector(".report-meta")!.textContent).not.toMatch(/T\d{2}:/);
    expect(detail.querySelectorAll(".report-evidences .report-evidence")).toHaveLength(3);
    expect(detail.querySelector(".report-actions a")!.getAttribute("href")).toBe("#/orchestration");
    expect(document.querySelector("#reports-detail #report-detail + #qa-lane")).not.toBeNull();
    expect(document.querySelector("#qa-lane details#report-qa-log")).not.toBeNull();
    expect(document.querySelector("#batch-list")).toBeNull();
    act(() => fireEvent.click(screen.getByRole("tab", { name: /Качество$/ })));
    expect(document.querySelector("#reports-quality-kpi")!.textContent).toContain("С рисками");
    expect(document.querySelector("#reports-quality-kpi")!.textContent).toContain("С блокерами");
  });

  test("the search reads ticket, role, outcome and dispatch; the status select reads the report state", () => {
    renderReports();
    const order = () => [...document.querySelectorAll("#report-list [data-stage]")].map((row) => row.getAttribute("data-stage"));
    act(() => fireEvent.change(document.querySelector("#reports-search") as HTMLElement, { target: { value: "rev" } }));
    expect(order()).toEqual(["d-rev"]);
    act(() => fireEvent.change(document.querySelector("#reports-search") as HTMLElement, { target: { value: "failed" } }));
    expect(order()).toEqual(["d-qa"]);
    act(() => fireEvent.change(document.querySelector("#reports-search") as HTMLElement, { target: { value: "#886" } }));
    expect(order()).toEqual(["d-old"]);
    act(() => fireEvent.change(document.querySelector("#reports-search") as HTMLElement, { target: { value: "" } }));
    act(() => fireEvent.change(document.querySelector("#report-status") as HTMLElement, { target: { value: "blocked" } }));
    expect(order()).toEqual(["d-qa"]);
    act(() => fireEvent.change(document.querySelector("#report-status") as HTMLElement, { target: { value: "attention" } }));
    expect(order()).toEqual(["d-rev"]);
    act(() => fireEvent.change(document.querySelector("#report-status") as HTMLElement, { target: { value: "passed" } }));
    expect(order()).toEqual(["d-dev", "d-old"]);
  });

  test("selectStages sorts by ticket and keeps unknown times last", () => {
    const ledger = parseReports(REPORTS)!;
    const reports = reportsById(ledger);
    const stages = [...ledger.stages, { ...ledger.stages[0], dispatch_id: "d-x", at: "вчера" }];
    expect(selectStages(stages, reports, NO_FILTERS).at(-1)?.dispatch_id).toBe("d-x");
    expect(selectStages(stages, reports, { ...NO_FILTERS, sortBy: "ticket", descending: false })[0].ticket).toBe("#886");
  });

  test("the mockup summary, QA lane and the Evidence, Quality and Readiness tabs", () => {
    renderReports();
    expect(document.querySelector("#reports-summary")!.textContent).toContain("Отчётов4");
    expect(document.querySelector("#qa-lane")!.textContent).toContain("QA lane · #887");
    expect(document.querySelector("#report-conclusion p")!.textContent).toBe("developer-retry");
    act(() => fireEvent.click(screen.getByRole("tab", { name: /Evidence$/ })));
    const matrix = document.querySelector("#reports-evidence")!;
    expect(matrix.querySelectorAll(".ds-evidence-row").length).toBeGreaterThan(0);
    expect(matrix.textContent).toContain("receipt");
    act(() => fireEvent.click(screen.getByRole("tab", { name: /Качество$/ })));
    expect(document.querySelector("#reports-quality")).not.toBeNull();
    act(() => fireEvent.click(screen.getByRole("tab", { name: /Готовность$/ })));
    expect(document.querySelector("#reports-readiness")!.textContent).toContain("Release Gate");
    // The QA report of #887 records a blocker: the kernel's verdict is "blocked".
    expect(document.querySelector("#reports-readiness [data-verdict]")!.textContent).toBe("Заблокировано");
    expect(document.querySelector("#reports-readiness .ds-ready-row")!.textContent).not.toMatch(/\b(match|failed|blocked)\b/);
  });

  test("Quality reads reports.snapshot only: results by role, and no findings or latency borrowed from Orchestration", () => {
    renderReports();
    act(() => fireEvent.click(screen.getByRole("tab", { name: /Качество$/ })));
    const roles = [...document.querySelectorAll("#reports-results-by-role [data-role]")].map((row) => row.getAttribute("data-role"));
    expect(roles).toEqual(["developer", "qa", "review"]);
    expect(document.querySelector("#reports-quality")!.textContent).toContain("нет данных в снимке отчётов");
  });

  test("a Readiness row opens the candidate drawer with Evidence, Quality and Readiness tabs from reports.*", () => {
    const socket = renderReports();
    act(() => fireEvent.click(screen.getByRole("tab", { name: /Готовность$/ })));
    act(() => fireEvent.click(document.querySelector('#reports-readiness [data-batch="b-887"] .report-ready-open') as HTMLElement));
    const drawer = screen.getByRole("dialog", { name: /Кандидат · #887/ });
    expect([...within(drawer).getAllByRole("tab")].map((tab) => tab.textContent)).toEqual(["Evidence", "Качество", "Готовность"]);
    expect(drawer.querySelector("#candidate-evidence")!.textContent).toContain("developer");
    answer(socket, "reports.timeline", TIMELINE);
    expect(drawer.querySelector("#report-timeline")).not.toBeNull();
    act(() => fireEvent.click(within(drawer).getByRole("tab", { name: /Качество$/ })));
    expect([...drawer.querySelectorAll("#candidate-reports [data-dispatch]")].map((row) => row.getAttribute("data-dispatch")).sort()).toEqual(["d-dev", "d-qa", "d-rev"]);
    act(() => fireEvent.click(within(drawer).getByRole("tab", { name: /Готовность$/ })));
    expect(drawer.querySelector("#candidate-readiness [data-verdict]")!.textContent).toBe("Заблокировано");
    expect(drawer.querySelectorAll("#candidate-readiness [data-check]")).toHaveLength(5);
    expect(socket.sent.filter((body) => body.type === "orchestration.snapshot")).toEqual([]);
    act(() => fireEvent.click(within(drawer).getByRole("button", { name: "Закрыть" })));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  test("the summary stats are words with figures, and every report row carries its role icon", () => {
    renderReports();
    const labels = [...document.querySelectorAll("#reports-summary .ds-stat-label")].map((item) => item.textContent);
    expect(labels).toEqual(["Отчётов", "Пройдено", "Внимание", "Заблокировано"]);
    const values = [...document.querySelectorAll("#reports-summary .ds-stat-value")].map((item) => item.textContent);
    expect(values.every((value) => /^\d+$/.test(value ?? ""))).toBe(true);
    const rows = [...document.querySelectorAll("#report-list .report-row")];
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.every((row) => row.querySelector(".report-type-icon svg") !== null)).toBe(true);
    expect(document.querySelector("#qa-lane .qa-attempt-state")?.textContent).not.toMatch(/^(pass|fail)$/);
  });

  test("the Publication page words every status and shows no title placeholder", () => {
    window.location.hash = "#/publish";
    const client = createConsoleClient({ url: "ws://127.0.0.1:1/ws", WebSocket: FakeSocket, timers: new ManualClock(), probeHealth: async () => false });
    render(
      <LanguageProvider>
        <App client={client} />
      </LanguageProvider>,
    );
    const socket = FakeSocket.last;
    act(() => socket.open());
    answer(socket, "reports.snapshot", REPORTS);
    const main = () => document.querySelector("main#content")?.textContent ?? "";
    expect(document.querySelector("#publish-verdict")?.textContent).toBe("Заблокировано");
    expect(main()).not.toContain("название");
    expect(main()).not.toMatch(/\b(unknown|missing|blocked|human only|match)\b/);
    act(() => fireEvent.click(screen.getByRole("tab", { name: /Preflight$/ })));
    const words = [...document.querySelectorAll("#publish-preflight .publish-check .ds-status-line > span[aria-hidden=true]")].map((word) => word.textContent);
    expect(words).toEqual(["Заблокировано", "Норма", "Заблокировано", "Норма", "Неизвестно"]);
  });

  test("the evidence matrix shows the kernel's cells", () => {
    renderReports();
    act(() => fireEvent.click(screen.getByRole("tab", { name: /Evidence$/ })));
    expect(evidenceMarks()).toEqual(["✓✓✓✓··", "————··", "✓———··"]);
  });

  test("the evidence matrix is a table with headers, and every cell says its state in words", () => {
    renderReports();
    act(() => fireEvent.click(screen.getByRole("tab", { name: /Evidence$/ })));
    const table = screen.getByRole("table", { name: /Coverage по batch/ });
    expect(within(table).getAllByRole("columnheader").map((cell) => cell.textContent)).toEqual(["batch", "developer", "review", "qa", "QA run", "receipt", "publish"]);
    const first = within(table).getAllByRole("row")[1]!;
    expect(within(first).getByRole("rowheader").textContent).toBe("#887");
    expect(within(first).getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["есть", "есть", "есть", "есть", "впереди", "впереди"]);
    // One frame: the tab's panel carries the only "Evidence" heading.
    expect(document.querySelectorAll("#reports-evidence h2")).toHaveLength(0);
  });

  test("the client does not recompute a cell the kernel marked stale", () => {
    const stale = { ...REPORTS, evidence: REPORTS.evidence.map((row) => ({ ...row, qa_run: "stale" })) };
    renderReports("", stale);
    act(() => fireEvent.click(screen.getByRole("tab", { name: /Evidence$/ })));
    expect(evidenceMarks()).toEqual(["✓✓✓!··", "———!··", "✓——!··"]);
  });

  test("English labels come from the catalog", () => {
    renderReports("?lang=en");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Reports");
    expect([...document.querySelectorAll("#reports-tabs .ds-pipe-label")].map((tab) => tab.textContent)).toEqual(["Reports", "Evidence", "Quality", "Readiness"]);
    expect(content()).toContain("report received · failed");
    expect(content()).toContain("Evidence complete");
  });
});

describe("the report body, QA log and route follow the language", () => {
  const ru: Translate = (text, values) => translate("ru", text, values);
  const en: Translate = (text, values) => translate("en", text, values);
  const ledger = parseReports(REPORTS)!;
  /** A report without checks and with a review: the texts a check list does not show. */
  const REVIEWED = {
    checks_run: [],
    review: {
      candidate_commit: "c0ffee1",
      standards: { severity: "warning", findings: [{ severity: "warning", summary: "s", evidence: "e" }] },
      spec: { severity: "clean", findings: [] },
    },
  };
  const lines = (log: string) =>
    log
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
  const qaLines = (shown: string) => lines(shown).filter((line) => !line.startsWith("2026-11-08T11:40") && !/^(E |FAILED)/.test(line));

  beforeEach(() => {
    FakeSocket.reset();
    answered.clear();
  });

  test("the QA log keeps the TUI's Russian and is English in en", () => {
    const tui = (FACTS as string[]).slice(
      (FACTS as string[]).indexOf("попытки qa-lane: 1"),
      (FACTS as string[]).indexOf("FAILED tests/console/test_reports.py::test_kpi") + 1,
    );
    expect(lines(qaLogText(ledger, "d-qa", ru))).toEqual(tui);
    expect(lines(qaLogText(ledger, "d-qa", en))).toEqual([
      "qa-lane attempts: 1",
      "2026-11-08T11:40:00+00:00 · d-qa · collect: лог QA не найден",
      "qa-run-1.log · 2026-11-08T11:58:00+00:00 · d-qa · #887 · report: failed",
      "result: failed — 2 commands, 1 failed (pytest -q tests/console: exit 1)",
      "log tail (last 2 of 42 lines):",
      "E   assert 3 == 2",
      "FAILED tests/console/test_reports.py::test_kpi",
    ]);
    const bare = { ...ledger, qa_attempts: [], qa_runs: [{ ...ledger.qa_runs[0]!, dispatch_id: "", logged_at: "" }] };
    expect(qaLogText(bare, "", ru)).toContain("qa-run-1.log · время ? · без отчёта · #887 · отчёт: failed");
    expect(qaLogText(bare, "", en)).toContain("qa-run-1.log · time ? · no report · #887 · report: failed");
  });

  test("the report sections and the route keep Russian and are English in en", () => {
    const section = (translate: Translate, title: string) =>
      new Map(reportSectionLines(REVIEWED, translate)).get(title)!.map(([, line]) => line);
    expect(section(ru, "Checks")).toEqual(["проверки не запускались"]);
    expect(section(en, "Checks")).toEqual(["no checks were run"]);
    expect(section(ru, "Review")).toEqual(["candidate: c0ffee1", "standards · находок: 1", "  [warning] s: e", "spec · находок: 0"]);
    expect(section(en, "Review")).toEqual(["candidate: c0ffee1", "standards · findings: 1", "  [warning] s: e", "spec · findings: 0"]);
    const review = (translate: Translate) => new Map(reportSections(REVIEWED, translate)).get("Review");
    expect(review(ru)).toBe("candidate: c0ffee1\nstandards: warning, находок: 1\n  [warning] s: e\nspec: clean, находок: 0");
    expect(review(en)).toBe("candidate: c0ffee1\nstandards: warning, findings: 1\n  [warning] s: e\nspec: clean, findings: 0");
    const timeline = parseTimeline(TIMELINE)!;
    expect(roleFlowText(timeline, en)).toBe("developer → review → qa → developer");
    expect(roleFlowText({ ...timeline, role_flow: [] }, ru)).toBe("dispatch ещё не было");
    expect(roleFlowText({ ...timeline, role_flow: [] }, en)).toBe("no dispatches yet");
  });

  test("with ?lang=en the rendered report and QA log carry no Russian of their own", () => {
    renderReports("?lang=en", REPORTS, REVIEWED);
    const log = document.querySelector("#report-qa-log pre")!.textContent!;
    expect(qaLines(log).filter((line) => /[а-яё]/i.test(line))).toEqual([]);
    expect(log).toContain("log tail (last 2 of 42 lines):");
    const detail = document.querySelector("#report-detail")!.textContent!;
    expect(detail).toContain("no checks were run");
    expect(detail).toContain("standards · findings: 1");
    expect(detail).not.toContain("находок");
  });

  test("in Russian the rendered report and QA log are unchanged", () => {
    renderReports("", REPORTS, REVIEWED);
    const log = document.querySelector("#report-qa-log pre")!.textContent!;
    expect(log).toContain("попытки qa-lane: 1");
    expect(log).toContain("итог: failed — команд 2, с ошибкой 1 (pytest -q tests/console: exit 1)");
    expect(log).toContain("хвост лога (последние 2 из 42 строк):");
    const detail = document.querySelector("#report-detail")!.textContent!;
    expect(detail).toContain("проверки не запускались");
    expect(detail).toContain("standards · находок: 1");
  });
});
