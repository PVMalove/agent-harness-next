import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { NO_FILTERS, reportsById, selectStages } from "../../harness/console/frontend/src/reports/format";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { parseReports } from "../../harness/console/frontend/src/ws/ledger";
import { FakeSocket, ManualClock, screenPage } from "./fake-socket";
import FACTS from "./fixtures/reports-facts.json";
import REPORT from "./fixtures/reports-report.json";
import REPORTS from "./fixtures/reports.json";

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

function renderReports(language = "", snapshot: unknown = REPORTS) {
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
  answer(socket, "reports.report", REPORT);
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
  "до PR: 1 д 2 ч 30 мин",
  "Output",
  "Checks",
  "Next action",
  "developer → review → qa → developer",
  "батч создан",
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
  [...document.querySelectorAll("#reports-evidence .report-evidence-row")].map((row) =>
    [...row.querySelectorAll(".report-evidence-cell")].map((cell) => cell.textContent).join(""),
  );

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
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Качество" })));
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

  test("the mockup order: two title actions, 4 + 4 KPI, one filter row, compact rows, detail, then the QA lane", () => {
    renderReports();
    const title = document.querySelector(".reports-title .actions")!;
    expect([...title.children].map((item) => item.id)).toEqual(["reports-refresh", "reports-export"]);
    expect(title.querySelector("#reports-export use, #reports-export svg")).not.toBeNull();
    expect(document.querySelector("#reports-updated")!.textContent).toMatch(/^\d{2}:\d{2}:\d{2}$/);
    expect(content()).not.toContain("Новый снимок");
    expect(document.querySelectorAll("#reports-summary > div")).toHaveLength(4);
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
    const grid = document.querySelector(".reports-grid")!;
    expect(grid.nextElementSibling?.id).toBe("qa-lane");
    expect(document.querySelector("#qa-lane details#report-qa-log")).not.toBeNull();
    expect(document.querySelector("#batch-list")).toBeNull();
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Качество" })));
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
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Evidence" })));
    const matrix = document.querySelector("#reports-evidence")!;
    expect(matrix.querySelectorAll(".report-evidence-row").length).toBeGreaterThan(0);
    expect(matrix.textContent).toContain("receipt");
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Качество" })));
    expect(document.querySelector("#reports-quality")).not.toBeNull();
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Готовность" })));
    expect(document.querySelector("#reports-readiness")!.textContent).toContain("Release Gate");
    // The QA report of #887 records a blocker: the kernel's verdict is "blocked".
    expect(document.querySelector("#reports-readiness [data-verdict]")!.textContent).toBe("Заблокировано");
    expect(document.querySelector("#reports-readiness .report-ready-row")!.textContent).not.toMatch(/\b(match|failed|blocked)\b/);
  });

  test("the title facts are words, and every report row carries its role icon", () => {
    renderReports();
    const facts = [...document.querySelectorAll(".reports-title .home-facts span")].map((item) => item.textContent);
    expect(facts.slice(1, 4).join(" ")).not.toMatch(/passed|attention|blocked/);
    expect(facts.slice(1, 4).every((fact) => /^\d+ \S/.test(fact ?? ""))).toBe(true);
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
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Preflight" })));
    const pills = [...document.querySelectorAll("#publish-preflight .publish-check .orch-pill")].map((pill) => pill.textContent);
    expect(pills).toEqual(["Заблокировано", "Норма", "Заблокировано", "Норма", "Неизвестно"]);
  });

  test("the evidence matrix shows the kernel's cells", () => {
    renderReports();
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Evidence" })));
    expect(evidenceMarks()).toEqual(["✓✓✓✓··", "————··", "✓———··"]);
  });

  test("the client does not recompute a cell the kernel marked stale", () => {
    const stale = { ...REPORTS, evidence: REPORTS.evidence.map((row) => ({ ...row, qa_run: "stale" })) };
    renderReports("", stale);
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Evidence" })));
    expect(evidenceMarks()).toEqual(["✓✓✓!··", "———!··", "✓——!··"]);
  });

  test("English labels come from the catalog", () => {
    renderReports("?lang=en");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Reports");
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Reports", "Evidence", "Quality", "Readiness"]);
    expect(content()).toContain("report received · failed");
    expect(content()).toContain("Evidence complete");
  });
});
