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

function renderActivity() {
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
  act(() => socket.reply(rosterReply(id)));
  act(() => socket.reply(stepsReply(id, [ORCHESTRATION_STEP, AGENT_STEP, CODEX_STEP])));
  return { socket, id };
}

const list = () => document.querySelector("#work-steps") as HTMLElement;
const rows = () => [...list().querySelectorAll(".work-event")].map((row) => row.querySelector("b")?.textContent);

describe("the agent activity route", () => {
  beforeEach(() => FakeSocket.reset());

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
    expect(icons).toEqual(["developer", "review", "qa"]);
    const statuses = [...sessions.querySelectorAll(".work-row .work-status")].map((status) => status.textContent?.trim());
    expect(statuses).toEqual(["Выполняется", "Выполняется · тишина", "Заблокировано"]);
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
    act(() => fireEvent.click(screen.getByRole("button", { name: "Все сессии" })));
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
});
