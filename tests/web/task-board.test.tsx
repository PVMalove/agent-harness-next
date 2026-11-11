import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { SPEC_KEY } from "../../harness/console/frontend/src/board/format";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { FakeSocket, ManualClock, screenPage } from "./fake-socket";
import SPECS from "./fixtures/task-board-specs.json";
import STALE from "./fixtures/task-board-stale.json";
import BOARD from "./fixtures/task-board.json";

const answered = new Set<unknown>();

/** Answer every open request of `type` with `value` as a paged snapshot. */
function answer(socket: FakeSocket, type: string, value: unknown) {
  for (const body of socket.sent.filter((sent) => sent.type === type && !answered.has(sent.id))) {
    answered.add(body.id);
    act(() => socket.reply(screenPage(body.id, type, JSON.stringify(value), { cached: false, age: 0 })));
  }
}

function renderBoard(options: { specs?: unknown; board?: unknown; language?: string } = {}) {
  window.location.hash = `#/board${options.language ?? ""}`;
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
  answer(socket, "task_board.specs", options.specs ?? SPECS);
  if (options.board !== null) answer(socket, "task_board.snapshot", options.board ?? BOARD);
  return socket;
}

const boards = (socket: FakeSocket) => socket.sent.filter((body) => body.type === "task_board.snapshot");
const content = () => document.querySelector("main#content")?.textContent ?? "";
const cards = () => [...document.querySelectorAll("[data-board-ticket]")].map((card) => card.getAttribute("data-board-ticket"));
const counters = () => [...document.querySelectorAll(".board-col-count")].map((count) => count.textContent);

function events(socket: FakeSocket, list: unknown[]) {
  const subscription = socket.request("orchestration.subscribe").id;
  act(() =>
    socket.reply({ v: 1, id: subscription, type: "orchestration.subscribe", ok: true, kind: "events", cursor: "j-1", events: list }),
  );
}

describe("the Task Board route", () => {
  beforeEach(() => {
    FakeSocket.reset();
    answered.clear();
    window.localStorage.clear();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  test("shows the spec switcher, KPIs and five columns with their card counters", () => {
    const socket = renderBoard();
    expect(socket.request("task_board.specs")).toMatchObject({ force: false });
    expect(socket.request("task_board.snapshot")).toMatchObject({ spec: "#501", force: false });
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Доска задач");
    const columns = [...document.querySelectorAll("[data-board-col]")].map((column) => column.getAttribute("data-board-col"));
    expect(columns).toEqual(["backlog", "ready", "progress", "review", "done"]);
    expect(counters()).toEqual(["2", "2", "1", "1", "1"]);
    expect(cards()).toEqual(["#511", "#516", "#512", "#517", "#513", "#514", "#515"]);
    const facts = document.querySelector("#board-facts")?.textContent ?? "";
    for (const fact of ["Синтетическая спека доски", "integration/board-fixture", "7 задач"]) expect(facts).toContain(fact);
    const options = [...document.querySelectorAll("#board-spec option")].map((option) => option.textContent);
    expect(options).toEqual(["#501 · Синтетическая спека доски — 7 задач", "#502 · Вторая синтетическая спека — нет данных"]);
    expect(document.querySelector(".board-spec-meta")?.textContent).toBe("7 задач · 6 открыто");
    expect(document.querySelector("#board-kpis")?.textContent).toContain("из 7 задач");
    expect(content()).toContain("dispatch: developer");
    expect(content()).toContain("блокеров: 1");
  });

  test("remembers the chosen spec in this browser", () => {
    window.localStorage.setItem(SPEC_KEY, "#502");
    const socket = renderBoard({ board: null });
    expect(socket.request("task_board.snapshot")).toMatchObject({ spec: "#502" });
    answer(socket, "task_board.snapshot", BOARD);
    act(() => fireEvent.change(document.querySelector("#board-spec") as HTMLElement, { target: { value: "#501" } }));
    expect(window.localStorage.getItem(SPEC_KEY)).toBe("#501");
    expect(socket.request("task_board.snapshot")).toMatchObject({ spec: "#501" });
  });

  test("a remembered spec the tracker no longer lists falls back to the first", () => {
    window.localStorage.setItem(SPEC_KEY, "#999");
    const socket = renderBoard();
    // The remembered spec is asked in parallel with the specs; the listing then picks the first.
    expect(boards(socket).map((body) => body.spec)).toEqual(["#999", "#501"]);
  });

  test("the remembered spec's board is asked before the specs answer, over the drawn frame", () => {
    window.localStorage.setItem(SPEC_KEY, "#502");
    window.location.hash = "#/board";
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
    expect(socket.sent.some((body) => body.type === "task_board.specs")).toBe(true);
    expect(boards(socket).map((body) => body.spec)).toEqual(["#502"]);
    expect(document.querySelectorAll("[data-board-frame] [data-board-col]")).toHaveLength(5);
    expect(document.querySelector("#board-updating .board-mascot")).not.toBeNull();
    answer(socket, "task_board.snapshot", BOARD);
    expect(cards()).toHaveLength(7);
    expect(document.querySelector("#board-updating")).toBeNull();
  });

  test("the spec row finds a spec by its number and names a number it does not know", () => {
    const socket = renderBoard();
    const field = screen.getByRole("searchbox", { name: "Найти спеку по номеру" });
    act(() => fireEvent.change(field, { target: { value: "#502" } }));
    expect((document.querySelector("#board-spec") as HTMLSelectElement).value).toBe("#502");
    expect(boards(socket).at(-1)).toMatchObject({ spec: "#502" });
    expect(window.localStorage.getItem(SPEC_KEY)).toBe("#502");
    act(() => fireEvent.change(screen.getByRole("searchbox", { name: "Найти спеку по номеру" }), { target: { value: "77" } }));
    expect(document.querySelector(".board-spec-missing")?.textContent).toBe("Спека #77 не найдена");
  });

  test("search, priority and only-without-blockers narrow the cards and the column counters", () => {
    renderBoard();
    expect(counters()).toEqual(["2", "2", "1", "1", "1"]);
    const search = document.querySelector("#board-search") as HTMLElement;
    act(() => fireEvent.change(search, { target: { value: "фильтры" } }));
    expect(cards()).toEqual(["#513"]);
    expect(document.querySelector("#board-count")?.textContent).toBe("1 из 7");
    expect(counters()).toEqual(["0", "0", "1", "0", "0"]);
    act(() => fireEvent.change(search, { target: { value: "docs/board.md" } }));
    expect(cards()).toEqual(["#512"]);
    act(() => fireEvent.change(search, { target: { value: "нужен источник" } }));
    expect(cards()).toEqual(["#511"]);
    act(() => fireEvent.click(document.querySelector("#board-reset") as HTMLElement));
    expect(cards()).toHaveLength(7);
    expect(counters()).toEqual(["2", "2", "1", "1", "1"]);
    act(() => fireEvent.change(document.querySelector("#board-priority") as HTMLElement, { target: { value: "priority::p1" } }));
    expect(cards()).toEqual(["#511", "#517"]);
    expect(counters()).toEqual(["1", "1", "0", "0", "0"]);
    act(() => fireEvent.click(document.querySelector("#board-free") as HTMLElement));
    expect(cards()).toEqual(["#517"]);
    expect(counters()).toEqual(["0", "1", "0", "0", "0"]);
    expect(document.querySelectorAll(".board-empty")).toHaveLength(4);
  });

  test("the search field shows a magnifier hidden from screen readers", () => {
    renderBoard();
    const search = document.querySelector(".board-toolbar .board-search") as HTMLElement;
    const icon = search.querySelector("svg.hi") as SVGElement;

    expect(icon).not.toBeNull();
    expect(icon.getAttribute("aria-hidden")).toBe("true");
    expect(icon.nextElementSibling).toBe(search.querySelector("input#board-search"));
    expect(screen.getByRole("searchbox", { name: "Поиск задач" })).toBe(search.querySelector("input"));
  });

  test("Refresh asks for the specs and the board with force and shows the refreshing state", () => {
    const socket = renderBoard();
    act(() => fireEvent.click(document.querySelector("#board-refresh") as HTMLElement));
    expect(socket.request("task_board.specs")).toMatchObject({ force: true });
    expect(socket.request("task_board.snapshot")).toMatchObject({ spec: "#501", force: true });
    expect(document.querySelector('[data-board-state="loading"]')).toBeNull();
    expect(document.querySelectorAll("[data-board-frame] [data-board-col]")).toHaveLength(5);
    expect(document.querySelector("#board-updating .board-mascot")).not.toBeNull();
    answer(socket, "task_board.specs", SPECS);
    answer(socket, "task_board.snapshot", BOARD);
    expect(document.querySelector("#board-updating")).toBeNull();
    expect(cards()).toHaveLength(7);
  });

  test("a ledger event of a board ticket or batch asks for the board once, with force", () => {
    const socket = renderBoard();
    expect(boards(socket)).toHaveLength(1);
    events(socket, [
      { event: "batch.transition", batch_id: "b-new", ticket: "#511", from: null, to: "active" },
      { event: "dispatch.transition", batch_id: "b-513", dispatch_id: "d-9", role: "qa", from: null, to: "working" },
    ]);
    expect(boards(socket)).toHaveLength(2);
    expect(boards(socket)[1]).toMatchObject({ spec: "#501", force: true });
    answer(socket, "task_board.snapshot", BOARD);
    events(socket, [{ event: "dispatch.transition", batch_id: "b-513", dispatch_id: "d-9", role: "qa", from: "working", to: "reported" }]);
    expect(boards(socket)).toHaveLength(3);
    answer(socket, "task_board.snapshot", BOARD);
    events(socket, [{ event: "batch.transition", batch_id: "b-x", ticket: "#777", from: null, to: "active" }, {}]);
    expect(boards(socket)).toHaveLength(3);
    // Background refreshes keep the columns on screen.
    expect(document.querySelector('[data-board-state="loading"]')).toBeNull();
  });

  test("without events the board is asked again after the snapshot TTL", () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const socket = renderBoard();
    act(() => vi.advanceTimersByTime(59000));
    expect(boards(socket)).toHaveLength(1);
    act(() => vi.advanceTimersByTime(1000));
    expect(boards(socket)).toHaveLength(2);
    expect(boards(socket)[1]).toMatchObject({ spec: "#501", force: false });
  });

  test("an unavailable tracker shows the last snapshot, its age and the reason", () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const socket = renderBoard({ board: STALE });
    const banner = document.querySelector(".board-banner.down")?.textContent ?? "";
    expect(banner).toContain("Трекер недоступен.");
    expect(banner).toContain("Нет доступа к трекеру: tracker login required");
    expect(banner).toContain("Показан снимок 1 мин назад.");
    expect(cards()).toHaveLength(7);
    expect(document.querySelector("#board-age")?.textContent).toBe("1 мин");
    expect(document.querySelector("#board-kpis")?.textContent).toContain("трекер недоступен");
    // A stale answer is asked again after a whole TTL, never at once.
    act(() => vi.advanceTimersByTime(59000));
    expect(boards(socket)).toHaveLength(1);
    act(() => vi.advanceTimersByTime(1000));
    expect(boards(socket)).toHaveLength(2);
  });

  test("a tracker that never answered shows the reason without a false empty state", () => {
    const empty = { ...SPECS, specs: [], stale: { reason: "timeout", message: "" }, age_seconds: null };
    renderBoard({ specs: empty, board: null });
    expect(content()).toContain("Трекер не ответил вовремя");
    expect(content()).toContain("Снимка доски ещё нет");
    expect(content()).not.toContain("Спек пока нет");
  });

  test("the no-specs, empty-board and first-load states", () => {
    const socket = renderBoard({ specs: { ...SPECS, specs: [] }, board: null });
    expect(document.querySelector('[data-board-state="nospecs"]')?.textContent).toContain("Спек пока нет");
    expect(boards(socket)).toHaveLength(0);
    FakeSocket.reset();
    answered.clear();
    document.body.innerHTML = "";
    const next = renderBoard({ board: null });
    expect(document.querySelectorAll("[data-board-frame] [data-board-col]")).toHaveLength(5);
    expect(document.querySelector("#board-updating .board-mascot")).not.toBeNull();
    answer(next, "task_board.snapshot", {
      ...BOARD,
      tickets: [],
      columns: BOARD.columns.map((column) => ({ ...column, count: 0 })),
      kpis: { open: 0, total: 0, with_open_blockers: 0, active_batch: 0 },
    });
    expect(document.querySelector('[data-board-state="empty"]')?.textContent).toContain("На доске нет задач");
  });

  test("ticket text stays plain text and a non-http link is not rendered", () => {
    renderBoard();
    const card = document.querySelector('[data-board-ticket="#516"]') as HTMLElement;
    expect(card.querySelector("h3")?.textContent).toBe("<script>alert(1)</script> Небезопасный заголовок");
    expect(card.querySelector("p")?.textContent).toBe("<img src=x onerror=alert(1)> **жирный** текст");
    expect(document.querySelector("main#content script, main#content img, main#content strong")).toBeNull();
    expect(card.querySelector("a")).toBeNull();
    expect(card.querySelector(".board-card-foot")?.textContent).toContain("нет данных");
    const safe = document.querySelector('[data-board-ticket="#511"] a') as HTMLAnchorElement;
    expect(safe.getAttribute("href")).toBe("https://tracker.example.test/acme/app/issues/511");
    expect(safe.getAttribute("rel")).toBe("noopener noreferrer");
  });

  test("labels follow the language", () => {
    renderBoard({ language: "?lang=en" });
    const names = [...document.querySelectorAll(".board-col header b")].map((name) => name.textContent);
    expect(names).toEqual(["Backlog", "Ready", "In progress", "Review / QA", "Done"]);
    expect(document.querySelector("#board-count")?.textContent).toBe("7 of 7");
    expect(content()).toContain("criteria: 2");
    expect(content()).toContain("no data");
  });
});
