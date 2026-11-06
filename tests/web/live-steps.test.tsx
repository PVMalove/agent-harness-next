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
  rosterReply,
  stepsReply,
} from "./fake-socket";

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

const list = () => document.querySelector(".work-events") as HTMLElement;
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
    act(() => fireEvent.click(screen.getByRole("button", { name: "Английский язык" })));
    expect(rows()[0]).toBe("Dispatch dispatch-dev: dispatched to working");
    expect(within(list()).getByText("structure unavailable")).toBeTruthy();
    act(() => socket.reply(rosterReply(id, true)));
    expect(rows()).toEqual([]);
    expect(screen.getByText("No steps yet")).toBeTruthy();
  });
});
