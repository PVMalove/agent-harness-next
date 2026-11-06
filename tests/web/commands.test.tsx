import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import {
  CONFIRMATION_REASONS,
  REVERSIBILITY_LABELS,
} from "../../harness/console/frontend/src/commands/CommandPanel";
import { PHASE_LABELS } from "../../harness/console/frontend/src/commands/JobOutput";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import catalog from "../../harness/console/frontend/src/i18n/catalog.json";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { COMMANDS, FakeSocket, ManualClock, jobReply, jobSnapshot } from "./fake-socket";

const line = (n: number) => ({ channel: "stdout", text: `line ${n}\n` });

function renderHarness(commands: unknown[] = COMMANDS) {
  window.location.hash = "#/harness";
  const clock = new ManualClock();
  const client = createConsoleClient({
    url: "ws://127.0.0.1:1/ws",
    WebSocket: FakeSocket,
    timers: clock,
    probeHealth: async () => false,
  });
  render(
    <LanguageProvider>
      <App client={client} />
    </LanguageProvider>,
  );
  const socket = FakeSocket.last;
  act(() => socket.open());
  const catalogRequest = socket.request("job.catalog");
  act(() => socket.reply({ v: 1, id: catalogRequest.id, type: "job.catalog", ok: true, commands }));
  const list = socket.request("job.list");
  return { client, clock, socket, list };
}

const row = (commandId: string) => document.querySelector(`[data-command="${commandId}"]`) as HTMLElement;
const output = () => document.querySelector(".command-output pre")?.textContent;

describe("the Harness commands panel", () => {
  beforeEach(() => FakeSocket.reset());

  test("lists the server's commands with their class labels inside the shell", () => {
    const { socket, list } = renderHarness();
    act(() => socket.reply({ v: 1, id: list.id, type: "job.list", ok: true, jobs: [] }));
    expect(socket.request("job.catalog")).toMatchObject({ section: "harness" });
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Harness");
    expect(within(row("diff")).getByText("✔ обратимо")).toBeTruthy();
    expect(within(row("uninstall-apply")).getByText("✖ удаление")).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Команды" }).getAttribute("aria-selected")).toBe("true");
  });

  test("a reversible command starts at once and its output grows with the subscription", () => {
    const { socket } = renderHarness();
    act(() => fireEvent.click(screen.getByRole("button", { name: "Запустить diff" })));
    const start = socket.request("job.start");
    expect(start).toMatchObject({ command_id: "diff", confirmed: false, client: "browser" });
    expect(screen.queryByRole("dialog")).toBeNull();
    act(() =>
      socket.reply(jobReply(start.id, "job.start", { command_id: "diff", mutating: false, output: [line(1)], cursor: 1 })),
    );
    expect(output()).toBe("line 1\n");
    const follow = socket.request("job.subscribe");
    expect(follow).toMatchObject({ job_id: "job-1", cursor: 1 });
    act(() =>
      socket.reply(
        jobReply(follow.id, "job.subscribe", {
          command_id: "diff",
          mutating: false,
          output: [line(2)],
          cursor: 2,
          phase: "completed",
          done: true,
          returncode: 0,
        }),
      ),
    );
    expect(output()).toBe("line 1\nline 2\n");
    expect(screen.getByText("Завершена")).toBeTruthy();
    expect(screen.getByText("Код возврата: 0")).toBeTruthy();
  });

  test("an irreversible command asks first and sends only the typed word it was given", () => {
    const { socket } = renderHarness();
    act(() => fireEvent.click(screen.getByRole("button", { name: "Запустить uninstall-apply" })));
    expect(socket.sent.filter((body) => body.type === "job.start")).toEqual([]);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(CONFIRMATION_REASONS["deletes-local-data"]!)).toBeTruthy();
    const submit = within(dialog).getByRole("button", { name: "Запустить" }) as HTMLButtonElement;
    expect(submit.disabled).toBe(true);
    const typed = within(dialog).getByLabelText("Введите UNINSTALL, чтобы подтвердить");
    act(() => fireEvent.change(typed, { target: { value: "uninstall" } }));
    expect(submit.disabled).toBe(true);
    act(() => fireEvent.change(typed, { target: { value: "UNINSTALL" } }));
    act(() => fireEvent.click(submit));
    expect(socket.request("job.start")).toMatchObject({
      command_id: "uninstall-apply",
      confirmed: true,
      confirmation: "UNINSTALL",
    });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  test("closing the dialog starts nothing", () => {
    const { socket } = renderHarness();
    act(() => fireEvent.click(screen.getByRole("button", { name: "Запустить uninstall-apply" })));
    act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Отмена" })));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(socket.sent.filter((body) => body.type === "job.start")).toEqual([]);
  });

  test("a busy console shows the running mutation and cancels it only after a confirmation", () => {
    const { socket, list } = renderHarness();
    const { output: _output, ...summary } = jobSnapshot({ id: "job-7", command_id: "registry", cursor: 3 });
    act(() => socket.reply({ v: 1, id: list.id, type: "job.list", ok: true, jobs: [summary] }));
    const busy = screen.getByText("Занято: registry");
    expect(busy).toBeTruthy();
    const follow = socket.request("job.subscribe");
    expect(follow).toMatchObject({ job_id: "job-7", cursor: 0 });
    act(() =>
      socket.reply(jobReply(follow.id, "job.subscribe", { id: "job-7", command_id: "registry", output: [line(1)], cursor: 1 })),
    );
    expect(output()).toBe("line 1\n");
    const bar = document.querySelector(".command-busy") as HTMLElement;
    act(() => fireEvent.click(within(bar).getByRole("button", { name: "Отменить job" })));
    expect(socket.sent.filter((body) => body.type === "job.cancel")).toEqual([]);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Отмена останавливает команду; уже внесённые изменения не откатываются.")).toBeTruthy();
    act(() => fireEvent.click(within(dialog).getByRole("button", { name: "Отменить job" })));
    expect(socket.request("job.cancel")).toMatchObject({ job_id: "job-7", confirmed: true });
  });

  test("a busy refusal of a start shows the job that holds the console", () => {
    const { socket } = renderHarness();
    act(() => fireEvent.click(screen.getByRole("button", { name: "Запустить diff" })));
    const start = socket.request("job.start");
    act(() =>
      socket.reply({
        v: 1,
        id: start.id,
        type: "job.start",
        ok: false,
        error: { code: "busy", message: "Busy: job-7 (registry)", job_id: "job-7" },
      }),
    );
    expect(screen.getByRole("alert").textContent).toBe("Консоль занята");
    expect(socket.request("job.subscribe")).toMatchObject({ job_id: "job-7", cursor: 0 });
  });

  test("an unavailable or plan-bound command cannot be started from the web", () => {
    const blocked = [
      { ...COMMANDS[0], command_id: "verify", available: false },
      { ...COMMANDS[1], command_id: "cleanup-apply", typed_confirmation: null, plan_required: true },
    ];
    renderHarness(blocked);
    for (const name of ["Запустить verify", "Запустить cleanup-apply"]) {
      expect((screen.getByRole("button", { name }) as HTMLButtonElement).disabled).toBe(true);
    }
    expect(within(row("verify")).getByText("Команда недоступна для выбранного проекта")).toBeTruthy();
  });

  test("every label the panel shows has its English translation", () => {
    const english: Record<string, string> = catalog.en;
    for (const label of [
      ...Object.values(REVERSIBILITY_LABELS),
      ...Object.values(CONFIRMATION_REASONS),
      ...Object.values(PHASE_LABELS),
    ]) {
      expect(english[label], label).toBeTruthy();
    }
  });
});
