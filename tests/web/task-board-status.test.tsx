import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { FakeSocket, ManualClock, jobReply, screenPage } from "./fake-socket";
import SPECS from "./fixtures/task-board-specs.json";
import BOARD from "./fixtures/task-board.json";

/* The status change of the Task Board over the fixture board (#501): drag and drop and the status
   select show the server's moves, a refused move shows its reason without a job, an allowed one
   waits for the confirmation and runs `board-status`, and every command answer refreshes the board
   with force. */

function renderBoard(language = "") {
  window.location.hash = `#/board${language}`;
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
  for (const [type, value] of [["task_board.specs", SPECS], ["task_board.snapshot", BOARD]] as const) {
    const body = socket.request(type);
    act(() => socket.reply(screenPage(body.id, type, JSON.stringify(value))));
  }
  return socket;
}

const card = (id: string) => document.querySelector(`[data-board-ticket="${id}"]`) as HTMLElement;
const column = (id: string) => document.querySelector(`[data-board-col="${id}"]`) as HTMLElement;
const targets = () =>
  [...document.querySelectorAll("[data-board-col]")].map((col) => [
    col.getAttribute("data-board-col"),
    col.classList.contains("drop-ok") ? "ok" : col.classList.contains("drop-no") ? "no" : "",
  ]);
const notice = () => document.querySelector("#board-move-notice");
const starts = (socket: FakeSocket) => socket.sent.filter((body) => body.type === "job.start");
const boards = (socket: FakeSocket) => socket.sent.filter((body) => body.type === "task_board.snapshot");

function drop(ticket: string, to: string) {
  act(() => fireEvent.dragStart(card(ticket)));
  act(() => fireEvent.dragOver(column(to)));
  act(() => fireEvent.drop(column(to)));
  act(() => fireEvent.dragEnd(card(ticket)));
}

const result = (fields: Record<string, unknown>) =>
  JSON.stringify({ ticket: "#512", from: "ready", to: "progress", reason: null, blockers: [], batch: null, message: "", ...fields }) + "\n";

function finish(socket: FakeSocket, stdout: string, id = "job-9") {
  const start = socket.request("job.start");
  act(() =>
    socket.reply(
      jobReply(start.id, "job.start", {
        id,
        command_id: "board-status",
        phase: "completed",
        done: true,
        returncode: 0,
        cursor: 1,
        output: [{ channel: "stdout", text: stdout }],
      }),
    ),
  );
}

function confirmMove(socket: FakeSocket, ticket: string, to: string) {
  drop(ticket, to);
  const dialog = document.querySelector("#board-confirm") as HTMLElement;
  expect(dialog).toBeTruthy();
  act(() => fireEvent.click(dialog.querySelector("#board-confirm-ok") as HTMLElement));
  return socket.request("job.start");
}

describe("the Task Board status change", () => {
  beforeEach(() => {
    FakeSocket.reset();
    window.localStorage.clear();
  });

  test("dragging a card highlights the allowed and the refused columns", () => {
    renderBoard();
    expect(card("#512").getAttribute("draggable")).toBe("true");
    expect(card("#514").getAttribute("draggable")).toBe("true");
    act(() => fireEvent.dragStart(card("#512")));
    expect(targets()).toEqual([
      ["backlog", "ok"],
      ["ready", ""],
      ["progress", "ok"],
      ["review", "no"],
      ["done", "no"],
    ]);
    expect(column("review").dataset.reason).toBe("«Review / QA» вычисляют dispatch и PR; карточку туда не переносят");
    act(() => fireEvent.dragEnd(card("#512")));
    expect(targets().every(([, mark]) => mark === "")).toBe(true);
  });

  test("a refused drop shows its reason and starts no job", () => {
    const socket = renderBoard();
    drop("#511", "ready");
    expect(notice()?.textContent).toBe("#511 → «Готово к работе»: Открыты блокеры: #512");
    expect(notice()?.getAttribute("data-reason")).toBe("open_blockers");
    drop("#513", "ready");
    expect(notice()?.textContent).toBe("#513 → «Готово к работе»: Активный batch b-513");
    drop("#512", "done");
    expect(notice()?.textContent).toContain("«Готово» заполняет закрытие тикета после подтверждённого merge");
    expect(document.querySelector("#board-confirm")).toBeNull();
    expect(starts(socket)).toEqual([]);
  });

  test("an allowed drop asks for confirmation and cancel starts nothing", () => {
    const socket = renderBoard();
    drop("#512", "progress");
    const dialog = document.querySelector("#board-confirm") as HTMLElement;
    expect(dialog.querySelector(".eyebrow")?.textContent).toBe("СМЕНА СТАТУСА");
    expect(dialog.querySelector("h2")?.textContent).toBe("#512 → В работе");
    expect(dialog.querySelector(".board-confirm-diff")?.textContent).toBe("ready→progress");
    expect(dialog.querySelector(".board-confirm-note")?.textContent).toBe(
      "Сервер запустит смену метки в GitHub как мутирующий job и обновит доску.",
    );
    act(() => fireEvent.click(screen.getByRole("button", { name: "Отмена" })));
    expect(document.querySelector("#board-confirm")).toBeNull();
    expect(starts(socket)).toEqual([]);
  });

  test("a confirmed move runs board-status and refreshes the board with force", () => {
    const socket = renderBoard();
    const start = confirmMove(socket, "#512", "progress");
    expect(start).toMatchObject({
      command_id: "board-status",
      values: { spec: "#501", ticket: "#512", to: "progress" },
      confirmed: true,
    });
    expect(notice()?.getAttribute("data-reason")).toBe("running");
    const before = boards(socket).length;
    finish(socket, result({ result: "changed", message: "status::ready -> status::in-progress" }));
    expect(notice()?.textContent).toBe("#512: статус обновлён");
    expect(boards(socket)).toHaveLength(before + 1);
    expect(boards(socket).at(-1)).toMatchObject({ spec: "#501", force: true });
  });

  test("a busy server refuses the move with the running job", () => {
    const socket = renderBoard();
    const start = confirmMove(socket, "#512", "progress");
    act(() =>
      socket.reply({
        v: 1,
        id: start.id,
        type: "job.start",
        ok: false,
        error: { code: "busy", message: "Busy: job-7 (update)", job_id: "job-7" },
      }),
    );
    expect(notice()?.textContent).toBe("#512 → «В работе»: Занято: update");
    expect(notice()?.getAttribute("data-reason")).toBe("busy");
  });

  test("a write error and a refusal of the command are shown and the board is refreshed", () => {
    const socket = renderBoard();
    confirmMove(socket, "#512", "progress");
    const before = boards(socket).length;
    finish(socket, result({ result: "write_error", reason: "write_failed", message: "gh: label not found" }));
    expect(notice()?.textContent).toBe("#512 → «В работе»: Ошибка записи в трекер: изменение не сохранено");
    expect(boards(socket).length).toBe(before + 1);
    // The refreshed board answers; then a move the command itself refuses.
    const refreshed = socket.request("task_board.snapshot");
    act(() => socket.reply(screenPage(refreshed.id, "task_board.snapshot", JSON.stringify(BOARD))));
    confirmMove(socket, "#516", "ready");
    finish(socket, result({ ticket: "#516", result: "refused", reason: "open_blockers", blockers: ["#77"] }), "job-10");
    expect(notice()?.textContent).toBe("#516 → «Готово к работе»: Открыты блокеры: #77");
  });

  test("the status select of the modal offers the same moves and refusals", () => {
    const socket = renderBoard();
    act(() => fireEvent.click(card("#512").querySelector("h3") as HTMLElement));
    const modal = document.querySelector("#board-ticket") as HTMLElement;
    const select = modal.querySelector("#board-status") as HTMLSelectElement;
    expect(select.value).toBe("ready");
    expect([...select.options].map((option) => [option.value, option.dataset.allowed])).toEqual([
      ["backlog", "true"],
      ["ready", "false"],
      ["progress", "true"],
      ["review", "false"],
      ["done", "false"],
    ]);
    act(() => fireEvent.change(select, { target: { value: "review" } }));
    expect(modal.querySelector("#board-modal-notice")?.getAttribute("data-reason")).toBe("review_target");
    expect(select.value).toBe("ready");
    act(() => fireEvent.change(select, { target: { value: "backlog" } }));
    const dialog = document.querySelector("#board-confirm") as HTMLElement;
    expect(dialog.querySelector("h2")?.textContent).toBe("#512 → Бэклог");
    act(() => fireEvent.click(dialog.querySelector("#board-confirm-ok") as HTMLElement));
    expect(socket.request("job.start")).toMatchObject({ values: { spec: "#501", ticket: "#512", to: "backlog" } });
    expect(document.querySelector("#board-ticket")).toBeNull();
  });

  test("the captions and the confirmation follow the language", () => {
    renderBoard("?lang=en");
    drop("#511", "ready");
    expect(notice()?.textContent).toBe("#511 → “Ready”: Open blockers: #512");
    drop("#512", "progress");
    const dialog = document.querySelector("#board-confirm") as HTMLElement;
    expect(dialog.querySelector(".eyebrow")?.textContent).toBe("STATUS CHANGE");
    expect(dialog.querySelector("#board-confirm-ok")?.textContent).toBe("Change status");
  });
});
