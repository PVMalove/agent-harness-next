import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { lockLines } from "../../harness/console/frontend/src/orchestration/format";
import { TicketList } from "../../harness/console/frontend/src/orchestration/OrchViews";
import type { OrchestrationSnapshot } from "../../harness/console/frontend/src/ws/ledger";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { CANCEL_REASON, FakeSocket, ManualClock, screenPage } from "./fake-socket";
import FACTS from "./fixtures/orch-snapshot-facts.json";
import ORCHESTRATION from "./fixtures/orch-snapshot.json";
import TIMELINE from "./fixtures/reports-timeline.json";

function renderOrchestration(language = "") {
  window.location.hash = `#/orchestration${language}`;
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
  const snapshot = socket.request("orchestration.snapshot");
  act(() => socket.reply(screenPage(snapshot.id, "orchestration.snapshot", JSON.stringify(ORCHESTRATION), { cached: true, age: 4 })));
  // The pending decisions live in the Gates tab: they are asked for when the tab opens.
  answerDecisions(socket);
  return socket;
}

function answerDecisions(socket: FakeSocket) {
  const asked = socket.sent.filter((body) => body.type === "decisions.snapshot").at(-1);
  if (asked) {
    act(() =>
      socket.reply({ v: 1, id: asked.id, type: "decisions.snapshot", ok: true, snapshot: { version: 1, items: [], total: 0, unavailable: false } }),
    );
  }
  const catalog = socket.sent.filter((body) => body.type === "job.catalog").at(-1);
  if (catalog) act(() => socket.reply({ v: 1, id: catalog.id, type: "job.catalog", ok: true, commands: [], cancel_reason: CANCEL_REASON }));
}

function openBatch(socket: FakeSocket, batch: string) {
  act(() => fireEvent.click(document.querySelector(`#batch-history [data-batch="${batch}"]`) as HTMLElement));
  const request = socket.request("reports.timeline");
  expect(request).toMatchObject({ batch_id: batch });
  const page = screenPage(request.id, "reports.timeline", JSON.stringify(TIMELINE));
  delete page.cached;
  delete page.age_seconds;
  act(() => socket.reply(page));
}

const TUI_ONLY = new Set([
  "В работе (WIP)", "старейший 5 ч 0 мин", "Ждёт подтверждения", "старейший —", "Заблокировано", "активные > 6 ч",
  "0 / 1  (0%)", "по тикетам", "Доработки", "повторные диспатчи", "Батчи по состояниям", "в работе 2 · завершён 1",
  "Возраст незавершённых", "< 1 дн 2 · 1–3 дн 0 · 3–7 дн 0 · > 7 дн 0", "PR по дням, 7 дней", "█        (1 0 0 0 0 0 0)",
  "Доработки по ролям", "developer 1", "developer 2 · qa 1 · review 1", "completed 3 · failed 1", "reported 4 · working 2",
  "missing 2 · found 1",
]);
const content = () => document.querySelector("main#content")?.textContent ?? "";

describe("the Orchestration route", () => {
  beforeEach(() => FakeSocket.reset());

  test("shows every fact the TUI shows for the same snapshot and keeps the decisions", () => {
    const socket = renderOrchestration();
    expect(socket.request("orchestration.snapshot")).toMatchObject({ force: false });
    // The facts are spread over the mockup tabs: gather the page text of every tab.
    const tabs = document.querySelector("#orch-tabs") as HTMLElement;
    let shown = "";
    for (const tab of within(tabs).getAllByRole("tab")) {
      act(() => fireEvent.click(tab));
      answerDecisions(socket);
      shown += content();
    }
    // The TUI's KPI row and analytics text rows have no mockup slot: their figures are the mockup
    // KPI cards and the tab charts (parity-1066.md), so only their wording is not repeated.
    const tuiOnly = (fact: string) => TUI_ONLY.has(fact);
    expect((FACTS as string[]).filter((fact) => !shown.includes(fact) && !tuiOnly(fact))).toEqual([]);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Оркестрация");
    expect(screen.getByRole("heading", { name: "Ожидающие решения" })).toBeTruthy();
  });

  test("the QA lane follows the newest batch; the snapshot lists batches newest first", () => {
    renderOrchestration();
    expect(ORCHESTRATION.ledger.batches.map((batch) => batch.ticket)).toEqual(["#887", "#888", "#886"]);
    const lane = document.querySelector("#qa-lane") as HTMLElement;
    expect(within(lane).getByRole("heading").textContent).toBe("QA lane · #887");
    expect(lane.querySelectorAll(".qa-attempt")).toHaveLength(2);
  });

  test("a chosen batch opens its chronology and is carried to Recovery and Container route", () => {
    const socket = renderOrchestration();
    act(() => fireEvent.click(within(document.querySelector("#orch-tabs") as HTMLElement).getByRole("tab", { name: "Runtime" })));
    expect(document.querySelector("#open-recovery")?.getAttribute("href")).toBe("#/recovery");
    openBatch(socket, "b-887");
    expect(content()).toContain("developer → review → qa → developer");
    expect(document.querySelector("#open-recovery")?.getAttribute("href")).toBe("#/recovery?batch=b-887");
    expect(document.querySelector("#open-container-route")?.getAttribute("href")).toBe("#/container-route?batch=b-887");
  });

  test("the state filter narrows the history; analytics tabs only switch the rows", () => {
    renderOrchestration();
    const history = () => [...document.querySelectorAll("#batch-history [data-batch]")].map((row) => row.getAttribute("data-batch"));
    expect(history()).toEqual(["b-887", "b-888", "b-886"]);
    act(() => fireEvent.change(document.querySelector("#state-filter") as HTMLElement, { target: { value: "completed" } }));
    expect(history()).toEqual(["b-886"]);
  });

  test("the page follows the mockup: two title actions, one tablist, the moved blocks in their tabs", () => {
    renderOrchestration();
    expect([...document.querySelectorAll(".orch-title .actions > *")].map((item) => item.textContent?.trim())).toEqual(["Обновить", "Отчёты"]);
    expect(document.querySelectorAll("main [role=tablist]")).toHaveLength(1);
    expect(document.querySelector("#orch-analytics")).toBeNull();
    expect(document.querySelector("#orch-kpi")).toBeNull();
    const tabs = document.querySelector("#orch-tabs") as HTMLElement;
    const view = () => document.querySelector('main [role="tabpanel"]:not([hidden])') as HTMLElement;
    const titles = () => [...view().querySelectorAll(".orch-chart h3, .panel h2")].map((title) => title.textContent);
    act(() => fireEvent.click(within(tabs).getByRole("tab", { name: "Поток" })));
    expect(view().querySelector(".orch-mini-flow")).not.toBeNull();
    expect(view().querySelector("#pipeline-stats")).not.toBeNull();
    act(() => fireEvent.click(within(tabs).getByRole("tab", { name: "Качество" })));
    expect(titles()).toEqual(expect.arrayContaining(["Evidence по стадиям", "Local QA attempts"]));
    expect(view().querySelector("#orch-qa-attempts")?.textContent).toContain("лог QA не найден");
    act(() => fireEvent.click(within(tabs).getByRole("tab", { name: "Runtime" })));
    expect(titles()).toContain("Recovery checks");
    expect(view().textContent).toContain("проверки восстановления в снимке не собираются");
    expect(view().querySelector("#ledger-lock")).not.toBeNull();
    act(() => fireEvent.click(within(tabs).getByRole("tab", { name: "Гейты" })));
    answerDecisions(FakeSocket.last);
    expect(within(view()).getByRole("heading", { name: "Ожидающие решения" })).toBeTruthy();
    const order = [...document.querySelectorAll("#orch-tickets, #batch-history")].map((block) => block.id);
    expect(order).toEqual(["orch-tickets", "batch-history"]);
  });

  test("the tabs follow the mockup: the grouped pipeline map and chart cards over the kernel figures", () => {
    renderOrchestration();
    const map = document.querySelector("#orch-scheme") as HTMLElement;
    expect(map.querySelectorAll(".orch-group")).toHaveLength(3);
    // The live step of each active batch: #888's architect is at work, #887's QA reported and
    // waits for the coordinator's QA gate; #887's older developer stage is open but not live.
    const node = (name: string) => map.querySelector(`[data-node="${name}"]`) as Element;
    expect(node("Архитектор").getAttribute("class")).toContain("active");
    expect(node("Approve QA").getAttribute("class")).toContain("live");
    expect(node("Разработчик").getAttribute("class")).not.toContain("active");
    expect(node("Разработчик").querySelector(".orch-map-count text")?.textContent).toBe("1");
    expect(map.querySelectorAll(".orch-map-edge.active")).toHaveLength(2);
    expect(map.querySelector(".orch-map-statusbar .orch-live")?.textContent).toBe("живой шаг: #887 · Approve QA; #888 · Architect");
    const tabs = document.querySelector("#orch-tabs") as HTMLElement;
    act(() => fireEvent.click(within(tabs).getByRole("tab", { name: "Поток" })));
    const flow = document.querySelector('#orch-tab-view[data-tab="flow"]') as HTMLElement;
    expect([...flow.querySelectorAll(".orch-chart h3")].map((h) => h.textContent)).toContain("Время цикла p50 / p95");
    expect(flow.textContent).toContain("Developer");
    expect(flow.textContent).not.toMatch(/\bcompleted\b/);
    act(() => fireEvent.click(within(tabs).getByRole("tab", { name: "Качество" })));
    expect(document.querySelector('#orch-tab-view[data-tab="quality"]')?.textContent).toContain("QA с первого раза");
    // A batch card and a ticket row never print a title placeholder.
    expect(content()).not.toContain("название: нет данных");
  });

  test("the Gates tab draws the kernel's hourly latency trend of the last day", () => {
    renderOrchestration();
    const gates = ORCHESTRATION.analytics.gates.latency_p50_by_hour;
    expect(gates).toHaveLength(24);
    expect(gates[23]).toBe(600);
    const tabs = document.querySelector("#orch-tabs") as HTMLElement;
    act(() => fireEvent.click(within(tabs).getByRole("tab", { name: "Гейты" })));
    const trend = document.querySelector("#orch-gate-trend") as HTMLElement;
    expect(trend.querySelector("h3")?.textContent).toBe("Тренд latency за сутки");
    // One hour with a decision: a dot per series, no line, no no-data state.
    expect(trend.querySelectorAll("circle.orch-line-avg-dot, circle.orch-line-p95-dot")).toHaveLength(2);
    expect(trend.querySelector(".no-data")).toBeNull();
    expect(document.querySelector("#orch-tab-view")?.textContent).not.toContain("нет данных");
  });

  test("the lock panel words a free, an unreadable and a held lock as the TUI does", () => {
    expect(lockLines({ locked: false }, null, "ru")).toEqual(["Lock ledger свободен."]);
    expect(lockLines(null, "boom", "en")).toEqual(["Ledger lock: state unavailable: boom"]);
    expect(lockLines({ locked: false, qa_lease: null }, null, "en")).toEqual(["The ledger lock is free.", "The QA lease is free."]);
    expect(lockLines({ ...ORCHESTRATION.lock.lock, release_available: true }, null, "ru")[2]).toBe(
      "Держится: 1 мин 15 с · до снятия по таймауту: доступно",
    );
  });

  test("English labels come from the catalog", () => {
    renderOrchestration("?lang=en");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Orchestration");
    act(() => fireEvent.click(within(document.querySelector("#orch-tabs") as HTMLElement).getByRole("tab", { name: "Runtime" })));
    expect(content()).toContain("Ledger lock held: report submit");
    expect(content()).toContain("Pipeline state, batch history and human decisions.");
    expect(content()).toContain("in progress (2)");
  });

  test("after the diagram: three batch cards, five-column dispatch rows and the all-tickets table", () => {
    renderOrchestration();
    const cards = [...document.querySelectorAll(".orch-batches > article.orch-batch")];
    expect(cards).toHaveLength(3);
    expect(cards.map((card) => card.className.split(" ").at(-1))).toEqual(["awaiting", "working", "done"]);
    expect(cards[0]!.querySelector("h3")?.textContent).toBe("#887 · feature/issue-887");
    expect(cards[0]!.querySelector(".orch-batch-meta")?.textContent).toContain("QA");
    expect([...cards[0]!.querySelectorAll(".orch-mini .orch-mini-step")].map((step) => step.className.replace("orch-mini-step", "").trim())).toEqual(["", "done", "done", "done", ""]);
    expect(cards[0]!.querySelector('.orch-batch-foot a[href="#/agent-activity"]')).not.toBeNull();
    const rows = [...document.querySelectorAll("#orch-dispatch-list .orch-dispatch-row")];
    expect(rows.length).toBeGreaterThan(0);
    for (const row of rows) {
      expect(row.classList.contains("row")).toBe(false);
      expect([...row.children].map((child) => child.className.split(" ")[0])).toEqual(["orch-role", "orch-dispatch-main", "orch-status", "orch-heartbeat", "orch-link"]);
      expect(row.querySelector(".orch-dispatch-main small")?.textContent).not.toMatch(/T\d{2}:\d{2}/);
    }
    const table = document.querySelector("#orch-tickets .orch-ticket-table") as HTMLElement;
    expect([...table.querySelectorAll(".orch-ticket-head span")].map((cell) => cell.textContent)).toEqual(["тикет", "название", "стадия / роль", "статус", "возраст", "обновлён"]);
    expect(table.querySelectorAll(".orch-ticket-row")).toHaveLength(3);
    expect(document.querySelector("#orch-tickets .panel-head .small")?.textContent).toBe("3 в выборке");
  });
});

describe("the All tickets table", () => {
  test("a ticket with several batches shows its newest batch", () => {
    const base = ORCHESTRATION.ledger.batches[0];
    const data = {
      ...ORCHESTRATION,
      ledger: {
        ...ORCHESTRATION.ledger,
        batches: [
          { ...base, batch_id: "b-old", branch: "feature/old", created_at: "2026-11-01T08:00:00+00:00", state: "failed", ticket: "#900" },
          { ...base, batch_id: "b-new", branch: "feature/new", created_at: "2026-11-08T08:00:00+00:00", state: "active", ticket: "#900" },
        ],
        stages: [],
      },
    } as unknown as OrchestrationSnapshot;
    render(
      <LanguageProvider>
        <TicketList data={data} now={Date.parse("2026-11-08T10:00:00+00:00")} />
      </LanguageProvider>,
    );
    const rows = [...document.querySelectorAll("#orch-tickets .orch-ticket-row")];
    expect(rows.map((row) => row.getAttribute("data-batch"))).toEqual(["b-new"]);
  });
});
