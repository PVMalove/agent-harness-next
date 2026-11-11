import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { CommandPanel } from "../../harness/console/frontend/src/commands/CommandPanel";
import type { RunRequest } from "../../harness/console/frontend/src/commands/CommandPanel";
import { ConsoleProvider } from "../../harness/console/frontend/src/useConsole";
import type { LocalJob } from "../../harness/console/frontend/src/ws/jobs";
import { PHASE_LABELS } from "../../harness/console/frontend/src/commands/JobOutput";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import catalog from "../../harness/console/frontend/src/i18n/catalog.json";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { CANCEL_REASON, COMMANDS, FakeSocket, HARNESS_OVERVIEW, MAINTENANCE, ManualClock, answerHarness, jobReply, jobSnapshot } from "./fake-socket";
import served from "./fixtures/job-catalog.json";

const line = (n: number) => ({ channel: "stdout", text: `line ${n}\n` });

function renderHarness(
  commands: unknown[] = COMMANDS,
  cancelReason: string = CANCEL_REASON,
  maintenance: unknown = MAINTENANCE,
) {
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
  act(() =>
    socket.reply({ v: 1, id: catalogRequest.id, type: "job.catalog", ok: true, commands, cancel_reason: cancelReason }),
  );
  const list = socket.request("job.list");
  act(() => answerHarness(socket, HARNESS_OVERVIEW, maintenance));
  act(() => fireEvent.click(screen.getByRole("tab", { name: "Команды" })));
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
    expect(within(dialog).getByText("Команда удаляет локальные данные — восстановить их нельзя.")).toBeTruthy();
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

  test("the label and the reasons are the server's, not a client copy", () => {
    const { socket, list } = renderHarness(
      [{ ...COMMANDS[1], reversibility_label: "⚠ метка сервера", confirmation_reason: "Причина от сервера." }],
      "Предупреждение сервера об отмене.",
    );
    expect(within(row("uninstall-apply")).getByText("⚠ метка сервера")).toBeTruthy();
    act(() => fireEvent.click(screen.getByRole("button", { name: "Запустить uninstall-apply" })));
    expect(within(screen.getByRole("dialog")).getByText("Причина от сервера.")).toBeTruthy();
    act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Отмена" })));
    const { output: _output, ...summary } = jobSnapshot({ id: "job-7", command_id: "registry" });
    act(() => socket.reply({ v: 1, id: list.id, type: "job.list", ok: true, jobs: [summary] }));
    const bar = document.querySelector(".command-busy") as HTMLElement;
    act(() => fireEvent.click(within(bar).getByRole("button", { name: "Отменить job" })));
    expect(within(screen.getByRole("dialog")).getByText("Предупреждение сервера об отмене.")).toBeTruthy();
  });

  test("in English the server's label and reasons are translated", () => {
    const { socket, list } = renderHarness();
    act(() => fireEvent.click(screen.getByRole("button", { name: "EN · Английский язык" })));
    expect(within(row("uninstall-apply")).getByText(catalog.en["✖ удаление"])).toBeTruthy();
    act(() => fireEvent.click(screen.getByRole("button", { name: "Run uninstall-apply" })));
    expect(
      within(screen.getByRole("dialog")).getByText("The command deletes local data — it cannot be restored."),
    ).toBeTruthy();
    act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" })));
    const { output: _output, ...summary } = jobSnapshot({ id: "job-7", command_id: "registry" });
    act(() => socket.reply({ v: 1, id: list.id, type: "job.list", ok: true, jobs: [summary] }));
    const bar = document.querySelector(".command-busy") as HTMLElement;
    act(() => fireEvent.click(within(bar).getByRole("button", { name: "Cancel the job" })));
    expect(
      within(screen.getByRole("dialog")).getByText(
        "Cancelling stops the command; the changes it has already made are not rolled back.",
      ),
    ).toBeTruthy();
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

  test("an unavailable command, or a plan-bound one without a shown plan, cannot be started", () => {
    const blocked = [
      { ...COMMANDS[0], command_id: "verify", available: false },
      { ...COMMANDS[1], command_id: "cleanup-apply", typed_confirmation: null, plan_required: true },
    ];
    renderHarness(blocked, CANCEL_REASON, { maintenance: null, error: "Git unavailable" });
    for (const name of ["Запустить verify", "Запустить cleanup-apply"]) {
      expect((screen.getByRole("button", { name }) as HTMLButtonElement).disabled).toBe(true);
    }
    expect(within(row("verify")).getByText("Команда недоступна для выбранного проекта")).toBeTruthy();
  });

  test("every label the panel shows has its English translation", () => {
    const english: Record<string, string> = catalog.en;
    for (const label of [
      ...served.commands.flatMap((command) => [command.reversibility_label, command.confirmation_reason ?? []].flat()),
      served.cancel_reason,
      ...Object.values(PHASE_LABELS),
    ]) {
      expect(english[label], label).toBeTruthy();
    }
  });
});

const CLEANUP = {
  ...COMMANDS[1],
  command_id: "cleanup-apply",
  title: "Очистка .harness (soft): применить",
  typed_confirmation: null,
  plan_required: true,
};
const DIGEST = "c".repeat(64);

function renderPanel(props: {
  planDigests?: Record<string, string>;
  request?: RunRequest | null;
  onJobDone?: (job: LocalJob) => void;
  confirmAll?: boolean;
  listed?: boolean;
}) {
  const client = createConsoleClient({
    url: "ws://127.0.0.1:1/ws",
    WebSocket: FakeSocket,
    timers: new ManualClock(),
    probeHealth: async () => false,
  });
  const view = (next: typeof props) => (
    <LanguageProvider>
      <ConsoleProvider client={client}>
        <CommandPanel section="harness" {...next} />
      </ConsoleProvider>
    </LanguageProvider>
  );
  const rendered = render(view(props));
  const socket = FakeSocket.last;
  act(() => socket.open());
  const catalogRequest = socket.request("job.catalog");
  act(() =>
    socket.reply({
      v: 1,
      id: catalogRequest.id,
      type: "job.catalog",
      ok: true,
      commands: [...COMMANDS, CLEANUP],
      cancel_reason: CANCEL_REASON,
    }),
  );
  return { socket, rerender: (next: typeof props) => rendered.rerender(view(next)) };
}

describe("the command panel inside a page", () => {
  beforeEach(() => FakeSocket.reset());

  test("a server digest makes a plan-bound command runnable and travels with its start", () => {
    const { socket } = renderPanel({ planDigests: { "cleanup-apply": DIGEST } });
    act(() => fireEvent.click(screen.getByRole("button", { name: "Запустить cleanup-apply" })));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(CLEANUP.confirmation_reason!)).toBeTruthy();
    act(() => fireEvent.click(within(dialog).getByRole("button", { name: "Запустить" })));
    expect(socket.request("job.start")).toMatchObject({
      command_id: "cleanup-apply",
      confirmed: true,
      plan_digest: DIGEST,
    });
  });

  test("a page's run request opens the same server-driven dialog, once per nonce", () => {
    const request = { command_id: "uninstall-apply", values: {}, nonce: 1 };
    const { socket, rerender } = renderPanel({ request });
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(COMMANDS[1]!.confirmation_reason!)).toBeTruthy();
    act(() => fireEvent.click(within(dialog).getByRole("button", { name: "Отмена" })));
    rerender({ request });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(socket.sent.filter((body) => body.type === "job.start")).toEqual([]);
    rerender({ request: { command_id: "cleanup-apply", values: {}, nonce: 2 } });
    expect(screen.getByRole("alert").textContent).toBe("Нужно превью плана очистки: запустите команду из TUI");
  });

  test("confirmAll asks before a reversible command and shows the page's reason", () => {
    const request = { command_id: "diff", values: { json: "1" }, nonce: 1, reason: "Перечитать конфигурацию batch." };
    const { socket } = renderPanel({ request, confirmAll: true });
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("Перечитать конфигурацию batch.")).toBeTruthy();
    expect(socket.sent.filter((body) => body.type === "job.start")).toEqual([]);
    act(() => fireEvent.click(within(dialog).getByRole("button", { name: "Отмена" })));
    expect(socket.sent.filter((body) => body.type === "job.start")).toEqual([]);
    act(() => fireEvent.click(screen.getByRole("button", { name: "Запустить diff" })));
    act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Запустить" })));
    const starts = socket.sent.filter((body) => body.type === "job.start");
    expect(starts).toHaveLength(1);
    expect(starts[0]).toMatchObject({ command_id: "diff", confirmed: true });
  });

  test("the page learns once that the shown job finished", () => {
    const done = vi.fn();
    const { socket } = renderPanel({ onJobDone: done });
    act(() => fireEvent.click(screen.getByRole("button", { name: "Запустить diff" })));
    const start = socket.request("job.start");
    act(() => socket.reply(jobReply(start.id, "job.start", { command_id: "diff", mutating: false })));
    expect(done).not.toHaveBeenCalled();
    const follow = socket.request("job.subscribe");
    const final = { command_id: "diff", mutating: false, phase: "completed", done: true, returncode: 0 };
    act(() => socket.reply(jobReply(follow.id, "job.subscribe", final)));
    act(() => socket.reply(jobReply(follow.id, "job.subscribe", final)));
    expect(done).toHaveBeenCalledTimes(1);
    expect(done.mock.calls[0]![0]).toMatchObject({ id: "job-1", phase: "completed", returncode: 0 });
  });

  test("an unlisted panel shows no command table but still runs a page's request behind the dialog", () => {
    const request = { command_id: "diff", values: {}, nonce: 1 };
    const { socket } = renderPanel({ request, confirmAll: true, listed: false });
    expect(screen.queryByRole("button", { name: "Запустить diff" })).toBeNull();
    expect(screen.queryByText("Команды")).toBeNull();
    act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Запустить" })));
    expect(socket.request("job.start")).toMatchObject({ command_id: "diff", confirmed: true });
  });
});
