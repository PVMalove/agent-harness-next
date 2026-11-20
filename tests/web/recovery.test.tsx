import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { ABORT_REASON } from "../../harness/console/frontend/src/routes/Recovery";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { FakeSocket, ManualClock, jobReply, screenPage } from "./fake-socket";
import CATALOG from "./fixtures/recovery-catalog.json";
import FACTS from "./fixtures/recovery-facts.json";
import RECOVERY from "./fixtures/recovery.json";

function answerView(socket: FakeSocket, value: unknown = RECOVERY) {
  const request = socket.request("recovery.view");
  act(() => socket.reply(screenPage(request.id, "recovery.view", JSON.stringify(value), { cached: true, age: 1 })));
  return request;
}

function renderRecovery(route = "#/recovery?batch=b-887") {
  window.location.hash = route;
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
  const request = answerView(socket);
  const catalog = socket.sent.find((body) => body.type === "job.catalog");
  if (catalog) act(() => socket.reply({ v: 1, id: catalog.id, type: "job.catalog", ok: true, ...CATALOG }));
  return { socket, request };
}

const starts = (socket: FakeSocket) => socket.sent.filter((body) => body.type === "job.start");
const action = (key: string) =>
  within(document.querySelector(`#view-actions [data-action="${key}"]`) as HTMLElement).getByRole("button");
const content = () => document.querySelector("main#content")?.textContent ?? "";

describe("the Recovery route", () => {
  beforeEach(() => FakeSocket.reset());

  test("is hidden, opens the batch from the URL and shows every fact the TUI shows", () => {
    const { request } = renderRecovery();
    expect(request).toMatchObject({ batch: "b-887", skip: [], force: false });
    expect((FACTS as string[]).filter((fact) => !content().includes(fact))).toEqual([]);
    const current = document.querySelector('#navigation a[aria-current="page"]');
    expect(current?.getAttribute("href")).toBe("#/orchestration");
  });

  test("a disabled action shows its reason and cannot be clicked", () => {
    const { socket } = renderRecovery();
    const resume = action("resume") as HTMLButtonElement;
    expect(resume.disabled).toBe(true);
    expect(content()).toContain("ядро: проверка не пройдена");
    act(() => fireEvent.click(resume));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(starts(socket)).toEqual([]);
  });

  test("cancelling the confirmation starts nothing; confirming starts exactly one confirmed job", () => {
    const { socket } = renderRecovery();
    act(() => fireEvent.click(action("reload")));
    let dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("recovery-reload")).toBeTruthy();
    act(() => fireEvent.click(within(dialog).getByRole("button", { name: "Отмена" })));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(starts(socket)).toEqual([]);

    act(() => fireEvent.click(action("abort")));
    dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(ABORT_REASON)).toBeTruthy();
    act(() => {
      dialog.dispatchEvent(new Event("cancel", { cancelable: true }));
    });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(starts(socket)).toEqual([]);

    act(() => fireEvent.click(action("reload")));
    act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Запустить" })));
    expect(starts(socket)).toHaveLength(1);
    expect(starts(socket)[0]).toMatchObject({
      command_id: "recovery-reload",
      values: { batch: "b-887", json: "1" },
      confirmed: true,
    });
  });

  test("status and skip only read the view again; a finished job re-reads it", () => {
    const { socket } = renderRecovery();
    const before = socket.sent.filter((body) => body.type === "recovery.view").length;
    act(() => fireEvent.click(action("status")));
    expect(socket.sent.filter((body) => body.type === "recovery.view")).toHaveLength(before + 1);
    expect(socket.request("recovery.view")).toMatchObject({ force: true });
    answerView(socket);
    act(() => fireEvent.change(screen.getByLabelText("ID диагностики"), { target: { value: "a1a1a1a1a1a1a1a1" } }));
    act(() => fireEvent.click(action("skip")));
    expect(socket.request("recovery.view")).toMatchObject({ batch: "b-887", skip: ["a1a1a1a1a1a1a1a1"] });
    answerView(socket);
    expect(starts(socket)).toEqual([]);

    act(() => fireEvent.click(action("fix")));
    act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Запустить" })));
    const start = socket.request("job.start");
    act(() => socket.reply(jobReply(start.id, "job.start", { command_id: "recovery-fix", mutating: true })));
    const follow = socket.request("job.subscribe");
    const reads = socket.sent.filter((body) => body.type === "recovery.view").length;
    act(() =>
      socket.reply(
        jobReply(follow.id, "job.subscribe", { command_id: "recovery-fix", mutating: true, phase: "completed", done: true, returncode: 0 }),
      ),
    );
    expect(socket.sent.filter((body) => body.type === "recovery.view")).toHaveLength(reads + 1);
    answerView(socket);
    expect(action("fix-apply")).toBeTruthy();
  });

  test("the gate: a chosen batch is opened only through «Открыть recovery»", () => {
    const { socket } = renderRecovery("#/recovery");
    expect(document.querySelector("#recovery-view")).toBeNull();
    act(() => fireEvent.click(document.querySelector('#recovery-history [data-batch="b-887"]') as HTMLElement));
    answerView(socket);
    expect(document.querySelector("#recovery-entry")?.textContent).toBe("⚠ внимание  runtime удерживает batch после сбоя worker");
    expect(document.querySelector("#recovery-view")).toBeNull();
    act(() => fireEvent.click(screen.getByRole("button", { name: "Открыть recovery" })));
    expect(window.location.hash).toBe("#/recovery?batch=b-887");
  });
});
