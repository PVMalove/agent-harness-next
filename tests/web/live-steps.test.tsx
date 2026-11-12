import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import {
  AGENT_STEP,
  CODEX_STEP,
  FakeSocket,
  ManualClock,
  ORCHESTRATION_STEP,
  ROSTER,
  rosterReply,
  screenPage,
  stepsReply,
} from "./fake-socket";
import TIMELINE from "./fixtures/reports-timeline.json";
import ORCH from "./fixtures/orch-snapshot.json";

function renderActivity(dispatches: unknown = ROSTER) {
  window.location.hash = "#/agent-activity";
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
  const id = socket.request("steps.subscribe").id;
  act(() => socket.reply(rosterReply(id, true, dispatches)));
  act(() => socket.reply(stepsReply(id, [ORCHESTRATION_STEP, AGENT_STEP, CODEX_STEP])));
  return { socket, id };
}

const list = () => document.querySelector("#work-steps") as HTMLElement;
const rows = () => [...list().querySelectorAll(".work-event")].map((row) => row.querySelector("b")?.textContent);

describe("the agent activity route", () => {
  beforeEach(() => FakeSocket.reset());

  test("shows why an in-process worker has no steps, with its heartbeat, self-report and checkpoints", () => {
    const observation = {
      stream_reason: "in_process",
      heartbeat_at: "2026-11-05T10:20:00+00:00",
      self_report: { reported_model: "claude-opus-5-5", match: true, reported_at: "2026-11-05T10:01:00+00:00" },
      checkpoints: [{ checkpoint_id: "cp-1", commit_sha: "1111111aaaa2222", created_at: "2026-11-05T10:12:00+00:00" }],
      checkpoint_count: 1,
    };

    renderActivity([{ ...ROSTER[0], observation }, ROSTER[1]]);

    const panel = document.querySelector("#work-observation") as HTMLElement;
    expect(
      within(panel).getByText(
        "In-process воркер работает внутри сессии coordinator и не отдаёт поток событий. " +
          "Ход работы виден по heartbeat, self-report модели и чекпоинтам.",
      ),
    ).toBeTruthy();
    expect(within(panel).getByText("05.11.2026 10:20 UTC")).toBeTruthy();
    expect(within(panel).getByText("claude-opus-5-5")).toBeTruthy();
    expect(within(panel).getByText("совпадает с назначенной")).toBeTruthy();
    const checkpoint = panel.querySelector("[data-checkpoint='cp-1']") as HTMLElement;
    expect(within(checkpoint).getByText("1111111")).toBeTruthy();
    expect(within(checkpoint).getByText("05.11.2026 10:12 UTC")).toBeTruthy();
    expect(within(panel).queryByText(/Показаны последние/)).toBeNull();
  });

  test("tells an in-process worker without a self-report or checkpoints apart from a mismatched one", () => {
    const quiet = {
      stream_reason: "in_process",
      heartbeat_at: "",
      self_report: null,
      checkpoints: [],
      checkpoint_count: 0,
    };

    renderActivity([{ ...ROSTER[0], observation: quiet }, ROSTER[1]]);

    const panel = document.querySelector("#work-observation") as HTMLElement;
    expect(within(panel).getByText("—")).toBeTruthy();
    expect(within(panel).getByText("ещё не отправлен")).toBeTruthy();
    expect(within(panel).getByText("Чекпоинтов пока нет.")).toBeTruthy();
  });

  test("marks a self-report of another model and says how many checkpoints are left out", () => {
    const checkpoints = Array.from({ length: 20 }, (_, index) => ({
      checkpoint_id: `cp-${index + 6}`,
      commit_sha: "abcdef0123",
      created_at: "2026-11-05T10:12:00+00:00",
    }));
    const observation = {
      stream_reason: "in_process",
      heartbeat_at: "2026-11-05T10:20:00+00:00",
      self_report: { reported_model: "claude-sonnet-5-5", match: false, reported_at: "2026-11-05T10:01:00+00:00" },
      checkpoints,
      checkpoint_count: 25,
    };

    renderActivity([{ ...ROSTER[0], observation }, ROSTER[1]]);

    const panel = document.querySelector("#work-observation") as HTMLElement;
    expect(within(panel).getByText("не совпадает с назначенной")).toBeTruthy();
    expect(panel.querySelectorAll("[data-checkpoint]")).toHaveLength(20);
    expect(within(panel).getByText("Показаны последние 20 из 25.")).toBeTruthy();
  });

  test("shows a stream reason it has no text for as the server sent it", () => {
    const observation = {
      stream_reason: "future_reason",
      heartbeat_at: "",
      self_report: null,
      checkpoints: [],
      checkpoint_count: 0,
    };

    renderActivity([{ ...ROSTER[0], observation }, ROSTER[1]]);

    const panel = document.querySelector("#work-observation") as HTMLElement;
    expect(within(panel).getByText("future_reason")).toBeTruthy();
  });

  test("shows no in-process panel for a worker with an event stream", () => {
    renderActivity();

    expect(document.querySelector("#work-observation")).toBeNull();
  });

  test("shows agent and orchestration steps of one feed without a reload", () => {
    const { socket, id } = renderActivity();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Ход работы");
    expect(socket.sent.filter((body) => body.type === "steps.subscribe")).toHaveLength(1);
    expect(rows()).toEqual(["Dispatch dispatch-dev: dispatched → working", "Read", "Проверяю тесты"]);
    const codex = [...list().querySelectorAll(".work-event")][2] as HTMLElement;
    expect(within(codex).getByText("структура недоступна")).toBeTruthy();
    act(() => socket.reply(stepsReply(id, [{ ...AGENT_STEP, kind: "result", text: "Готово" }])));
    expect(rows().at(-1)).toBe("Готово");
    const sources = document.querySelector(".work-sources") as HTMLElement;
    expect(within(sources).getByText("структура доступна")).toBeTruthy();
    expect(within(sources).getByText("структура недоступна")).toBeTruthy();
  });

  test("the mockup summary, KPI row, status chips, session route and tabs", () => {
    renderActivity();
    expect(document.querySelector("#work-summary")!.textContent).toContain("Сессии2");
    expect(document.querySelector("#work-kpis")!.textContent).toContain("Последнее событие");
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Обзор", "Таймлайн", "Статистика"]);
    const chips = document.querySelector("#work-status-chips")!;
    act(() => fireEvent.click(within(chips as HTMLElement).getByRole("button", { name: /Выполняется/ })));
    expect(document.querySelectorAll(".work-sessions .work-row")).toHaveLength(2);
    const route = document.querySelector("#work-route")!;
    expect(route.textContent).toContain("Маршрут сессии #885");
    expect([...route.querySelectorAll(".work-flow-node b")].map((node) => node.textContent)).toEqual([
      "Architect",
      "Developer",
      "Review",
      "QA",
      "PR",
    ]);
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Статистика" })));
    expect(document.querySelector("#work-stats")!.textContent).toContain("События в минуту");
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Таймлайн" })));
    expect(document.querySelector("#work-timeline")).not.toBeNull();
  });

  test("sessions show role icons and localized statuses; the ticket picker narrows them", () => {
    const { socket, id } = renderActivity();
    const other = { ...ROSTER[0], dispatch_id: "dispatch-qa-9", batch_id: "batch-901", ticket: "#901", role: "qa", state: "failed" };
    act(() => socket.reply(rosterReply(id, true, [...ROSTER, other])));
    const sessions = document.querySelector(".work-sessions") as HTMLElement;
    const icons = [...sessions.querySelectorAll(".work-row .work-role [data-icon]")].map((icon) => icon.getAttribute("data-icon"));
    // Newest activity first: the developer and the QA dispatch were last seen at 10:20, the reviewer at 10:06.
    expect(icons).toEqual(["developer", "qa", "review"]);
    const statuses = [...sessions.querySelectorAll(".work-row .work-status")].map((status) => status.textContent?.trim());
    expect(statuses).toEqual(["Выполняется", "Заблокировано", "Выполняется · тишина"]);
    expect(sessions.textContent).not.toContain("working");
    const picker = screen.getByRole("combobox", { name: "Выбрать задачу" }) as HTMLSelectElement;
    expect([...picker.options].map((option) => option.value)).toEqual(["", "#901", "#885"]);
    act(() => fireEvent.change(picker, { target: { value: "#901" } }));
    expect([...sessions.querySelectorAll(".work-row")].map((row) => row.getAttribute("data-dispatch"))).toEqual(["dispatch-qa-9"]);
    expect(document.querySelector("#work-route")!.textContent).toContain("Маршрут сессии #901");
  });

  test("the session route carries role icons and localized step labels; session events come from the batch chronology", () => {
    const { socket } = renderActivity();
    const route = document.querySelector("#work-route")!;
    expect([...route.querySelectorAll(".work-flow-icon [data-icon]")].map((icon) => icon.getAttribute("data-icon"))).toEqual([
      "architect",
      "developer",
      "review",
      "qa",
      "pr",
    ]);
    expect(route.querySelector('[data-step="Developer"] small')!.textContent).toBe("Выполняется");
    const ask = socket.request("reports.timeline");
    expect(ask).toMatchObject({ batch_id: "batch-885" });
    act(() => socket.reply(screenPage(ask.id, "reports.timeline", JSON.stringify(TIMELINE))));
    const events = document.querySelector("#work-events-panel") as HTMLElement;
    expect(events.textContent).toContain("События сессии #885");
    const first = events.querySelector(".work-event") as HTMLElement;
    expect(first.querySelector("b")!.textContent).toBe(TIMELINE.events.at(-1)!.text);
    expect(events.querySelector('[data-kind="report"] small')!.textContent).toBe("отчёт");
  });

  test("statistics count the observed events of the last hour by type", () => {
    renderActivity();
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Статистика" })));
    const types = document.querySelector("#work-event-types") as HTMLElement;
    expect(types.textContent).toContain("за час");
    expect(document.querySelector("#work-rate svg")).not.toBeNull();
  });

  test("the rendered list never shows thinking, tool inputs or raw JSON", () => {
    const { socket, id } = renderActivity();
    act(() =>
      socket.reply(
        stepsReply(id, [{ ...AGENT_STEP, text: "visible", thinking: "THINK-SECRET", input: { path: "INPUT-SECRET" } }]),
      ),
    );
    const text = list().textContent ?? "";
    expect(text).not.toContain("THINK-SECRET");
    expect(text).not.toContain("INPUT-SECRET");
    expect(text).not.toContain("visible");
    expect(text).not.toMatch(/[{}]/);
    expect(text).not.toContain("thinking");
  });

  test("a dispatch row and the role select filter the list", () => {
    renderActivity();
    act(() => fireEvent.click(screen.getByRole("button", { name: /dispatch-rev/ })));
    expect(rows()).toEqual(["Проверяю тесты"]);
    expect(screen.getByRole("button", { name: /dispatch-rev/ }).getAttribute("aria-pressed")).toBe("true");
    // A second click on the pressed row clears the session filter (no separate «Все сессии» chip).
    act(() => fireEvent.click(screen.getByRole("button", { name: /dispatch-rev/ })));
    expect(rows()).toHaveLength(3);
    const select = screen.getByRole("combobox", { name: "Фильтр по роли" }) as HTMLSelectElement;
    expect([...select.options].map((option) => option.value)).toEqual(["", "developer", "review"]);
    act(() => fireEvent.change(select, { target: { value: "developer" } }));
    expect(rows()).toEqual(["Dispatch dispatch-dev: dispatched → working", "Read"]);
  });

  test("a reset roster empties the list and the English labels translate it", () => {
    const { socket, id } = renderActivity();
    act(() => fireEvent.click(screen.getByRole("button", { name: "EN · Английский язык" })));
    expect(rows()[0]).toBe("Dispatch dispatch-dev: dispatched to working");
    expect(within(list()).getByText("structure unavailable")).toBeTruthy();
    act(() => socket.reply(rosterReply(id, true)));
    expect(rows()).toEqual([]);
    expect(screen.getByText("No steps yet")).toBeTruthy();
  });

  test("sessions are one filter row and the 5 latest, with a toggle to show all", () => {
    const { socket, id } = renderActivity();
    const many = Array.from({ length: 7 }, (_, index) => ({
      ...ROSTER[0],
      dispatch_id: `dispatch-${index}`,
      batch_id: `batch-${900 + index}`,
      ticket: `#${900 + index}`,
      last_event_at: `2026-11-05T10:${String(10 + index).padStart(2, "0")}:00+00:00`,
    }));
    act(() => socket.reply(rosterReply(id, true, many)));
    const sessions = document.querySelector(".work-sessions") as HTMLElement;
    const shown = () => [...sessions.querySelectorAll(".work-row")].map((row) => row.getAttribute("data-dispatch"));
    expect(shown()).toEqual(["dispatch-6", "dispatch-5", "dispatch-4", "dispatch-3", "dispatch-2"]);
    expect(sessions.querySelector(".panel-head .small")?.textContent).toBe("5 из 7");
    expect(within(sessions).queryByRole("button", { name: "Все сессии" })).toBeNull();
    const filters = sessions.querySelector(".work-filters") as HTMLElement;
    expect(filters.querySelectorAll("select")).toHaveLength(2);
    expect(filters.querySelector(".chips")).not.toBeNull();
    act(() => fireEvent.click(within(sessions).getByRole("button", { name: "Показать все 7" })));
    expect(shown()).toHaveLength(7);
    expect(within(sessions).getByRole("button", { name: "Показать 5 последних" })).toBeTruthy();
  });

  test("the session route opens the task and the orchestration", () => {
    renderActivity();
    const actions = document.querySelector("#work-route .work-route-actions") as HTMLElement;
    expect([...actions.querySelectorAll("a")].map((link) => [link.textContent?.trim(), link.getAttribute("href")])).toEqual([
      ["Открыть задачу", "#/board?ticket=%23885"],
      ["Оркестрация", "#/orchestration"],
    ]);
  });

  test("steps and session events show the 10 latest in compact rows inside a scroll region", () => {
    const { socket, id } = renderActivity();
    const many = Array.from({ length: 14 }, (_, index) => ({ ...AGENT_STEP, text: `step ${index}`, observed_at: `2026-11-05T10:${String(30 + index)}:00+00:00` }));
    act(() => socket.reply(stepsReply(id, many)));
    expect(rows()).toEqual(Array.from({ length: 10 }, (_, index) => `step ${index + 4}`));
    expect(list().getAttribute("role")).toBe("region");
    expect(list().tabIndex).toBe(0);
    const ask = socket.request("reports.timeline");
    const events = Array.from({ length: 14 }, (_, index) => ({ at: `2026-11-08T09:${String(10 + index)}:00+00:00`, kind: "state", role: null, text: `event ${index}` }));
    act(() => socket.reply(screenPage(ask.id, "reports.timeline", JSON.stringify({ ...TIMELINE, events }))));
    const shown = [...document.querySelectorAll("#work-events .work-event b")].map((item) => item.textContent);
    expect(shown).toEqual(Array.from({ length: 10 }, (_, index) => `event ${13 - index}`));
    expect(document.querySelector("#work-events")?.getAttribute("role")).toBe("region");
  });

  test("the timeline has the time axis on top, the total and the last event at the side and the wait legend", () => {
    const { socket } = renderActivity();
    const ask = socket.request("orchestration.snapshot");
    act(() => socket.reply(screenPage(ask.id, "orchestration.snapshot", JSON.stringify(ORCH))));
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Таймлайн" })));
    const gantt = document.querySelector("#work-timeline .work-gantt") as HTMLElement;
    expect(gantt.firstElementChild?.classList.contains("work-gantt-axis")).toBe(true);
    const ticks = [...gantt.querySelectorAll(".work-gantt-ticks span")].map((tick) => tick.textContent);
    expect(ticks[0]).toMatch(/^0(м|ч)$/);
    const row = gantt.querySelector(".work-gantt-row") as HTMLElement;
    expect(row.querySelector(".work-gantt-name small")?.textContent).not.toMatch(/\d+[hm]\b/);
    expect(row.querySelector(".work-gantt-last")?.textContent).not.toBe("");
    expect(gantt.getAttribute("role")).toBe("region");
    expect([...document.querySelectorAll("#work-timeline .orch-legend span")].map((item) => item.textContent)).toEqual(["готово", "активно", "ожидание", "блок"]);
  });

  test("the statistics axis reads 0м … 60м like the mockup, the last label anchored at the end", () => {
    renderActivity();
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Статистика" })));
    const labels = [...document.querySelectorAll("#work-rate text.work-rate-axis")].filter((label) => label.getAttribute("text-anchor") !== "end" || /м$/.test(label.textContent ?? ""));
    const minutes = labels.map((label) => label.textContent).filter((text) => /м$/.test(text ?? ""));
    expect(minutes).toEqual(["0м", "15м", "30м", "45м", "60м"]);
    expect(labels.find((label) => label.textContent === "60м")?.getAttribute("text-anchor")).toBe("end");
  });
});
