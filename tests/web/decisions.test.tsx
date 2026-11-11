import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { CANCEL_REASON, FakeSocket, ManualClock } from "./fake-socket";
import { jobReply } from "./fake-socket";
import fixture from "./fixtures/decisions.json";

const permission = {
  kind: "native-permission", batch_id: "batch-884", dispatch_id: "dispatch-aaaa",
  ticket: "#884", role: "developer", reversibility: "external-change",
  command_ids: ["native-permission-allow", "native-permission-deny"],
  values: { dispatch: "dispatch-aaaa", request_id: "request-7", request_sha256: "a".repeat(64) },
  details: { tool_name: "Read", input_preview: '{"file_path":"example.py"}' },
};
const commands = ["allow", "deny"].map((answer) => ({
  command_id: `native-permission-${answer}`, title: answer === "allow" ? "Разрешить запрос native permission" : "Отклонить запрос native permission",
  section: "decisions", reversibility: "external-change", reversibility_label: "↗ внешнее действие",
  needs_confirmation: true, confirmation_reason: "Решение достигает работающего runtime.",
  typed_confirmation: null, read_only: false,
  inputs: ["dispatch", "request_id", "request_sha256"], available: true, plan_required: false,
}));

function open(route = "orchestration") {
  window.location.hash = `#/${route}`;
  const clock = new ManualClock();
  const client = createConsoleClient({ url: "ws://127.0.0.1:1/ws", WebSocket: FakeSocket,
    timers: clock, probeHealth: async () => false });
  render(<LanguageProvider><App client={client} /></LanguageProvider>);
  const socket = FakeSocket.last;
  act(() => socket.open());
  return { socket, clock };
}

beforeEach(() => FakeSocket.reset());

function answer(socket: FakeSocket, items: unknown[] = [permission]) {
  act(() => socket.reply({ v: 1, id: socket.request("decisions.snapshot").id,
    type: "decisions.snapshot", ok: true,
    snapshot: { version: 1, items, total: items.length, unavailable: false } }));
  act(() => socket.reply({ v: 1, id: socket.request("job.catalog").id,
    type: "job.catalog", ok: true, commands: fixture.commands, cancel_reason: CANCEL_REASON }));
}

test("a native choice shows its context and sends the bound request only after confirmation", () => {
  const { socket } = open();
  // The missing screen must request the existing public snapshot before it can offer a choice.
  expect(socket.sent.some((body) => body.type === "decisions.snapshot")).toBe(true);
  act(() => socket.reply({ v: 1, id: socket.request("decisions.snapshot").id,
    type: "decisions.snapshot", ok: true,
    snapshot: { version: 1, items: [permission], total: 1, unavailable: false } }));
  act(() => socket.reply({ v: 1, id: socket.request("job.catalog").id, type: "job.catalog",
    ok: true, commands, cancel_reason: CANCEL_REASON }));
  expect(screen.getByText("#884")).toBeTruthy();
  expect(screen.getByText("dispatch-aaaa")).toBeTruthy();
  expect(screen.getByText('{"file_path":"example.py"}')).toBeTruthy();
  act(() => fireEvent.click(screen.getByRole("button", { name: commands[0].title })));
  expect(socket.sent.filter((body) => body.type === "job.start")).toEqual([]);
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText("Решение достигает работающего runtime.")).toBeTruthy();
  act(() => fireEvent.click(within(dialog).getByRole("button", { name: "Подтвердить" })));
  expect(socket.request("job.start")).toMatchObject({ command_id: "native-permission-allow",
    client: "browser", confirmed: true, values: permission.values });
});

test("the same choice cannot be submitted again while its start reply is pending", () => {
  const { socket } = open();
  answer(socket);
  const allow = screen.getByRole("button", { name: "Разрешить запрос native permission" }) as HTMLButtonElement;
  act(() => fireEvent.click(allow));
  act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Подтвердить" })));
  expect(allow.disabled).toBe(true);
  expect(socket.sent.filter((body) => body.type === "job.start")).toHaveLength(1);
});

test("a terminal report decision uses server choices and the operator's own approval fields", () => {
  const { socket } = open("publish");
  answer(socket, fixture.snapshot.items);
  expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Публикация");
  const run = screen.getByRole("button", { name: "Решение по batch" }) as HTMLButtonElement;
  expect(run.disabled).toBe(true);
  act(() => fireEvent.change(screen.getByLabelText("batch-decide decision"), { target: { value: "block" } }));
  act(() => fireEvent.change(screen.getByLabelText("batch-decide approved_by"), { target: { value: "operator" } }));
  act(() => fireEvent.change(screen.getByLabelText("batch-decide approved_at"), { target: { value: "2026-11-06T12:00:00Z" } }));
  act(() => fireEvent.click(run));
  expect(socket.sent.filter((body) => body.type === "job.start")).toHaveLength(0);
  expect(screen.getByRole("dialog").textContent).toContain('"decision": "block"');
  act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Подтвердить" })));
  expect(socket.request("job.start")).toMatchObject({ command_id: "batch-decide", confirmed: true,
    values: { batch: "batch-report", decision: "block", approved_by: "operator", approved_at: "2026-11-06T12:00:00Z" } });
});

test("dispatch proposal output precedes a separately confirmed approval bound to its digest", () => {
  const { socket } = open();
  answer(socket, fixture.snapshot.items.filter((item) => item.kind === "dispatch-approval"));
  act(() => fireEvent.click(screen.getByRole("button", { name: "Предложить dispatch" })));
  const proposal = socket.request("job.start");
  expect(proposal).toMatchObject({ command_id: "dispatch-propose", confirmed: false, values: { batch: "batch-proposal" } });
  act(() => socket.reply(jobReply(proposal.id, "job.start", { command_id: "dispatch-propose", done: true,
    phase: "completed", returncode: 0, output: [{ channel: "stdout", text: '{"transition_digest":"abc123"}' }], cursor: 1 })));
  answer(socket, fixture.snapshot.items.filter((item) => item.kind === "dispatch-approval"));
  expect(screen.getByText('{"transition_digest":"abc123"}')).toBeTruthy();
  const approve = screen.getByRole("button", { name: "Создать dispatch" }) as HTMLButtonElement;
  expect(approve.disabled).toBe(true);
  act(() => fireEvent.change(screen.getByLabelText("dispatch-create transition_digest"), { target: { value: "abc123" } }));
  act(() => fireEvent.click(approve));
  act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Подтвердить" })));
  expect(socket.request("job.start")).toMatchObject({ command_id: "dispatch-create", confirmed: true,
    values: { batch: "batch-proposal", transition_digest: "abc123" } });
});

test("closing the confirmation sends nothing and a changed request invalidates it", () => {
  const { socket } = open();
  answer(socket);
  const allow = () => screen.getByRole("button", { name: "Разрешить запрос native permission" });
  act(() => fireEvent.click(allow()));
  act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Отмена" })));
  expect(screen.queryByRole("dialog")).toBeNull();
  act(() => fireEvent.click(allow()));
  act(() => fireEvent.click(screen.getByRole("button", { name: "Обновить" })));
  answer(socket, [{ ...permission, values: { ...permission.values, request_sha256: "b".repeat(64) } }]);
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(socket.sent.filter((body) => body.type === "job.start")).toEqual([]);
});

test("a disconnect invalidates the choice and reconnect refreshes without replaying it", () => {
  const { socket, clock } = open();
  answer(socket);
  act(() => fireEvent.click(screen.getByRole("button", { name: "Разрешить запрос native permission" })));
  act(() => socket.close());
  expect(screen.queryByRole("dialog")).toBeNull();
  act(() => clock.advance(500));
  const next = FakeSocket.last;
  act(() => next.open());
  expect(next.sent.some((body) => body.type === "decisions.snapshot")).toBe(true);
  expect(next.sent.filter((body) => body.type === "job.start")).toEqual([]);
});

test("the work view includes native requests and translates the decision context to English", () => {
  const { socket } = open("agent-activity");
  answer(socket, fixture.snapshot.items);
  expect(screen.queryByText("Approval dispatch")).toBeNull();
  act(() => fireEvent.click(screen.getByRole("button", { name: "EN · Английский язык" })));
  expect(screen.getByRole("heading", { name: "Pending decisions" })).toBeTruthy();
  expect(screen.getByRole("heading", { name: "Native permission request" })).toBeTruthy();
});

test("the work view keeps the decision job result after its last native request disappears", () => {
  const { socket } = open("agent-activity");
  answer(socket);
  act(() => fireEvent.click(screen.getByRole("button", { name: "Отклонить запрос native permission" })));
  act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Подтвердить" })));
  act(() => socket.reply(jobReply(socket.request("job.start").id, "job.start", {
    command_id: "native-permission-deny", done: true, phase: "completed", returncode: 0,
    output: [{ channel: "stdout", text: "Choice queued" }], cursor: 1,
  })));
  answer(socket, []);
  expect(screen.queryByText("Choice queued")).not.toBeNull();
  expect(screen.getByText("Код возврата: 0")).toBeTruthy();
});
