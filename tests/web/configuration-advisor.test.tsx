import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { AdvisorPanel } from "../../harness/console/frontend/src/configuration/AdvisorPanel";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { ConsoleProvider } from "../../harness/console/frontend/src/useConsole";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { FakeSocket, ManualClock, screenPage } from "./fake-socket";
import CONFIGURATION from "./fixtures/configuration.json";

const WIZARD = [
  { group: "project", file: "project.json", path: ["language"], label: "Язык отчётов", type: "enum", choices: ["ru", "en"], default: null, minimum: null,
    description: "", recommendation: { value: "ru", reason: "Сохранить текущую настройку проекта." } },
  { group: "hooks", file: "project.json", path: ["branch_pattern"], label: "Шаблон имени ветки", type: "string", choices: [], default: null, minimum: null,
    description: "", recommendation: null },
];
const STATUS = { provider: "codex", found: true, version_supported: true, authorized: false, ready: false, message: "Нет действующей авторизации Codex CLI." };

function renderParameters() {
  window.location.hash = "#/configuration";
  const clock = new ManualClock();
  const client = createConsoleClient({ url: "ws://127.0.0.1:1/ws", WebSocket: FakeSocket, timers: clock, probeHealth: async () => false });
  render(
    <LanguageProvider>
      <App client={client} />
    </LanguageProvider>,
  );
  const socket = FakeSocket.last;
  act(() => socket.open());
  const request = socket.request("configuration.snapshot");
  act(() => socket.reply(screenPage(request.id, "configuration.snapshot", JSON.stringify({ ...CONFIGURATION, wizard: WIZARD }))));
  act(() => fireEvent.click(screen.getByRole("tab", { name: /Параметры$/ })));
  return { socket, panel: () => document.querySelector("#configuration-advisor") as HTMLElement };
}

const advisorFrames = (socket: FakeSocket) => socket.sent.filter((body) => String(body.type).startsWith("advisor."));
const starts = (socket: FakeSocket) => socket.sent.filter((body) => body.type === "job.start");
const press = (panel: HTMLElement, name: string) => act(() => fireEvent.click(within(panel).getByRole("button", { name })));
const pick = (panel: HTMLElement, name: string) => act(() => fireEvent.click(within(panel).getByRole("radio", { name })));
const changes = () => {
  act(() => fireEvent.click(screen.getByRole("tab", { name: /Изменения$/ })));
  return [...document.querySelectorAll("#configuration-changes li")].map((item) => item.textContent);
};

describe("the AI hints of the Parameters tab", () => {
  beforeEach(() => FakeSocket.reset());

  test("offer No AI, Codex CLI and Claude Code CLI and send nothing before a press", () => {
    const { socket, panel } = renderParameters();
    expect(within(panel()).getAllByRole("radio").map((item) => (item as HTMLInputElement).value)).toEqual(["none", "codex", "claude"]);
    expect((within(panel()).getByRole("radio", { name: "Без ИИ" }) as HTMLInputElement).checked).toBe(true);
    expect(within(panel()).getByRole("button", { name: "Спросить ИИ" })).toHaveProperty("disabled", true);
    pick(panel(), "Codex CLI");
    expect(advisorFrames(socket)).toEqual([]);
  });

  test("Check CLI sends only advisor.check and shows presence, version and authorization", () => {
    const { socket, panel } = renderParameters();
    pick(panel(), "Codex CLI");
    press(panel(), "Проверить CLI");
    expect(advisorFrames(socket).map((body) => body.type)).toEqual(["advisor.check"]);
    const check = socket.request("advisor.check");
    expect(check).toEqual({ id: check.id, type: "advisor.check", provider: "codex" });
    act(() => socket.reply({ v: 1, id: check.id, type: "advisor.check", ok: true, status: STATUS }));
    const rows = [...document.querySelectorAll("#configuration-advisor-status dd")].map((item) => item.textContent);
    expect(rows).toEqual(["да", "да", "нет", STATUS.message]);
  });

  test("a late status of the previously selected CLI is not shown after a switch", () => {
    const { socket, panel } = renderParameters();
    pick(panel(), "Codex CLI");
    press(panel(), "Проверить CLI");
    const first = socket.request("advisor.check");
    pick(panel(), "Claude Code CLI");
    act(() => socket.reply({ v: 1, id: first.id, type: "advisor.check", ok: true, status: STATUS }));
    expect(document.querySelector("#configuration-advisor-status")).toBeNull();
    press(panel(), "Проверить CLI");
    const second = socket.request("advisor.check");
    expect(second.provider).toBe("claude");
    act(() => socket.reply({ v: 1, id: second.id, type: "advisor.check", ok: true, status: { ...STATUS, provider: "claude", message: "Claude готов." } }));
    expect(document.querySelector("#configuration-advisor-status")?.textContent).toContain("Claude готов.");
  });

  test("switching the CLI while a check is pending re-enables Check CLI", () => {
    const { panel } = renderParameters();
    pick(panel(), "Codex CLI");
    press(panel(), "Проверить CLI");
    expect(within(panel()).getByRole("button", { name: "Проверить CLI" })).toHaveProperty("disabled", true);
    pick(panel(), "Claude Code CLI");
    expect(within(panel()).getByRole("button", { name: "Проверить CLI" })).toHaveProperty("disabled", false);
  });

  test("a connection drop during a check re-enables Check CLI", () => {
    const { socket, panel } = renderParameters();
    pick(panel(), "Codex CLI");
    press(panel(), "Проверить CLI");
    expect(within(panel()).getByRole("button", { name: "Проверить CLI" })).toHaveProperty("disabled", true);
    act(() => socket.close());
    expect(within(panel()).getByRole("button", { name: "Проверить CLI" })).toHaveProperty("disabled", false);
    expect(document.querySelector("#configuration-advisor-status")).toBeNull();
  });

  test("Ask AI names the parameter only, and an accepted advice changes the draft only", () => {
    const { socket, panel } = renderParameters();
    pick(panel(), "Claude Code CLI");
    press(panel(), "Спросить ИИ");
    const ask = socket.request("advisor.ask");
    expect(ask).toEqual({ id: ask.id, type: "advisor.ask", provider: "claude", file: "project.json", path: ["language"] });
    act(() =>
      socket.reply({
        v: 1, id: ask.id, type: "advisor.ask", ok: true, outcome: "advice",
        advice: { value: "en", why: "Команда пишет по-английски", impact: "Отчёты на английском", comparison: [{ option: "ru", tradeoff: "Русские отчёты" }] },
      }),
    );
    expect(document.querySelector("#configuration-advice")?.textContent).toContain("Команда пишет по-английски");
    press(panel(), "Принять совет ИИ");
    expect(starts(socket)).toEqual([]);
    expect(changes()).toEqual(['project.json → language "en"']);
    expect(starts(socket)).toEqual([]);
  });

  test("with broken draft JSON Accept AI advice is disabled with the reason and the draft stays unchanged", () => {
    const { socket, panel } = renderParameters();
    act(() => fireEvent.click(screen.getByRole("tab", { name: /JSON$/ })));
    act(() => fireEvent.change(screen.getByRole("textbox", { name: "project.json" }), { target: { value: "{" } }));
    act(() => fireEvent.click(screen.getByRole("tab", { name: /Параметры$/ })));
    pick(panel(), "Codex CLI");
    press(panel(), "Спросить ИИ");
    const ask = socket.request("advisor.ask");
    act(() => socket.reply({ v: 1, id: ask.id, type: "advisor.ask", ok: true, outcome: "advice", advice: { value: "en", why: "w", impact: "i", comparison: [] } }));
    const accept = within(panel()).getByRole("button", { name: "Принять совет ИИ" }) as HTMLButtonElement;
    expect(accept.disabled).toBe(true);
    const reason = document.getElementById(accept.getAttribute("aria-describedby") ?? "");
    expect(reason?.textContent).toContain("Черновик файла не разобран");
    act(() => fireEvent.click(screen.getByRole("tab", { name: /JSON$/ })));
    expect((screen.getByRole("textbox", { name: "project.json" }) as HTMLTextAreaElement).value).toBe("{");
  });

  test("a refused accept shows the reason and keeps the advice", () => {
    const clock = new ManualClock();
    const client = createConsoleClient({ url: "ws://127.0.0.1:1/ws", WebSocket: FakeSocket, timers: clock, probeHealth: async () => false });
    const accepted: unknown[] = [];
    render(
      <LanguageProvider>
        <ConsoleProvider client={client}>
          <AdvisorPanel param={WIZARD[0] as never} refusal={null} onAccept={(value) => (accepted.push(value), false)} />
        </ConsoleProvider>
      </LanguageProvider>,
    );
    const socket = FakeSocket.last;
    act(() => socket.open());
    const panel = document.querySelector("#configuration-advisor") as HTMLElement;
    pick(panel, "Codex CLI");
    press(panel, "Спросить ИИ");
    const ask = socket.request("advisor.ask");
    act(() => socket.reply({ v: 1, id: ask.id, type: "advisor.ask", ok: true, outcome: "advice", advice: { value: "en", why: "w", impact: "i", comparison: [] } }));
    press(panel, "Принять совет ИИ");
    expect(accepted).toEqual(["en"]);
    expect(within(panel).getByRole("alert").textContent).toContain("Черновик файла не разобран");
    expect(document.querySelector("#configuration-advice")).not.toBeNull();
  });

  test("a fallback shows the reason and the console recommendation and keeps the draft", () => {
    const { socket, panel } = renderParameters();
    pick(panel(), "Codex CLI");
    press(panel(), "Спросить ИИ");
    const ask = socket.request("advisor.ask");
    act(() => socket.reply({ v: 1, id: ask.id, type: "advisor.ask", ok: true, outcome: "fallback", cause: "timeout", reason: "CLI не ответил вовремя." }));
    const fallback = document.querySelector("#configuration-advice-fallback")?.textContent ?? "";
    expect(fallback).toContain("ИИ не ответил за 90 с");
    expect(fallback).toContain("CLI не ответил вовремя.");
    expect(fallback).toContain("Рекомендация консоли: ru");
    expect(document.querySelector("#configuration-advice")).toBeNull();
    expect(changes()).toEqual(["Изменений нет"]);
  });

  test("Cancel, another parameter and another provider cancel the pending ask", () => {
    const { socket, panel } = renderParameters();
    pick(panel(), "Codex CLI");
    press(panel(), "Спросить ИИ");
    const first = socket.request("advisor.ask");
    press(panel(), "Отменить");
    expect(socket.request("advisor.cancel")).toMatchObject({ type: "advisor.cancel", request_id: first.id });
    press(panel(), "Спросить ИИ");
    const second = socket.request("advisor.ask");
    act(() => fireEvent.change(screen.getByLabelText("Выбрать параметр"), { target: { value: "1" } }));
    expect(socket.request("advisor.cancel")).toMatchObject({ request_id: second.id });
    expect(socket.request("advisor.ask")).toBe(second);
    press(panel(), "Спросить ИИ");
    const third = socket.request("advisor.ask");
    expect(third.path).toEqual(["branch_pattern"]);
    pick(panel(), "Claude Code CLI");
    expect(socket.request("advisor.cancel")).toMatchObject({ request_id: third.id });
    // A late answer of a cancelled ask is not shown.
    act(() => socket.reply({ v: 1, id: third.id, type: "advisor.ask", ok: true, outcome: "advice", advice: { value: "x", why: "w", impact: "i", comparison: [] } }));
    expect(document.querySelector("#configuration-advice")).toBeNull();
  });
});
