import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { FakeSocket, ManualClock, screenPage } from "./fake-socket";
import SPECS from "./fixtures/task-board-specs.json";
import BOARD from "./fixtures/task-board.json";

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

const card = (id: string) => BOARD.tickets.find((ticket) => ticket.id === id)!;
const dialog = () => document.querySelector("#board-ticket") as HTMLElement;
const open = (id: string) =>
  act(() => fireEvent.click(document.querySelector(`[data-board-ticket="${id}"] h3`) as HTMLElement));

function stubClipboard(writeText: (text: string) => Promise<void>) {
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
}

describe("the ticket modal", () => {
  beforeEach(() => {
    FakeSocket.reset();
    window.localStorage.clear();
  });
  afterEach(() => {
    Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
  });

  test("shows the labels, story points, issue, PR, branch, the status and its select", () => {
    renderBoard();
    open("#514");
    const modal = dialog();
    expect(modal.querySelector("h2")?.textContent).toBe("Модальное окно тикета");
    expect(modal.querySelector(".eyebrow")?.textContent).toBe("#514 · Синтетическая спека доски");
    const labels = [...modal.querySelectorAll(".board-modal-labels em")].map((label) => label.textContent);
    expect(labels).toEqual(["hitl", "status::in-progress", "3 SP"]);
    const links = [...modal.querySelectorAll(".board-modal-links a")].map((link) => [link.textContent, link.getAttribute("href")]);
    expect(links).toEqual([
      ["issue #514", "https://tracker.example.test/acme/app/issues/514"],
      ["PR #520", "https://tracker.example.test/acme/app/pull/520"],
    ]);
    expect(modal.querySelector(".branch-inline")?.textContent).toBe("integration/board-fixture");
    expect(modal.querySelector("#board-status-label")?.textContent).toBe("Review / QA");
    // The status select offers the server's moves; a ticket in review has none.
    const select = modal.querySelector("#board-status") as HTMLSelectElement;
    expect(select.value).toBe("review");
    expect([...select.options].map((option) => option.dataset.allowed)).toEqual(["false", "false", "false", "false", "false"]);
    expect(modal.querySelector("input")).toBeNull();
  });

  test("the Context, Acceptance and Prompt tabs show the snapshot's text", () => {
    renderBoard();
    open("#511");
    const modal = dialog();
    expect([...modal.querySelectorAll('[role="tab"]')].map((tab) => tab.textContent)).toEqual([
      "Контекст",
      "Acceptance (2)",
      "Промпт",
    ]);
    expect(modal.querySelector(".board-blocker")?.textContent).toBe("#512нужен источникopen");
    expect(modal.querySelector(".board-file code")?.textContent).toBe("harness/console/");
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Acceptance (2)" })));
    expect([...modal.querySelectorAll(".board-acceptance li")].map((item) => item.textContent)).toEqual(
      card("#511").criteria,
    );
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Промпт" })));
    expect(modal.querySelector("pre.board-prompt")?.textContent).toBe(card("#511").prompt);
  });

  test("the Agent prompt button copies the prompt from every tab", async () => {
    const writeText = vi.fn(async () => undefined);
    stubClipboard(writeText);
    renderBoard();
    open("#512");
    const button = screen.getByRole("button", { name: "Промпт агента" });
    expect(button.id).toBe("board-copy");
    expect(button.classList.contains("board-agent-prompt")).toBe(true);
    expect(button.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");

    for (const tab of ["Контекст", "Acceptance (3)", "Промпт"]) {
      act(() => fireEvent.click(screen.getByRole("tab", { name: tab })));
      writeText.mockClear();
      await act(async () => fireEvent.click(screen.getByRole("button", { name: "Промпт агента" })));

      expect(writeText).toHaveBeenCalledExactlyOnceWith(card("#512").prompt);
      expect(dialog().querySelector('[role="status"]')?.textContent).toBe("Промпт скопирован");
    }
  });

  test("a refused copy leaves the text to copy by hand", async () => {
    stubClipboard(async () => {
      throw new Error("denied");
    });
    renderBoard();
    open("#512");
    await act(async () => fireEvent.click(document.querySelector("#board-copy") as HTMLElement));
    expect(dialog().querySelector('[role="status"]')?.textContent).toBe("Скопируйте текст вручную");
    expect(document.querySelector("#board-copy-text")?.textContent).toBe(card("#512").prompt);
  });

  test("ticket text stays plain text and a non-http issue link is not rendered", () => {
    renderBoard();
    open("#516");
    const modal = dialog();
    expect(modal.querySelector("h2")?.textContent).toBe("<script>alert(1)</script> Небезопасный заголовок");
    expect(modal.querySelector(".board-modal-links a")).toBeNull();
    expect(modal.querySelector(".board-blocker em")?.textContent).toBe("нет данных");
    expect(modal.querySelector("#board-sp")?.textContent).toBe("нет данных SP");
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Acceptance (2)" })));
    expect([...modal.querySelectorAll(".board-acceptance li")].map((item) => item.textContent)).toEqual([
      "<b>не HTML</b>",
      "`код` и [ссылка](javascript:alert(1))",
    ]);
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Промпт" })));
    expect(modal.querySelector("pre.board-prompt")?.textContent).toContain("<img src=x onerror=alert(1)>");
    expect(modal.querySelector("script, img, a, .board-acceptance b, .board-modal-head b")).toBeNull();
  });

  test("closes with the close button and opens from the keyboard", () => {
    renderBoard();
    const target = document.querySelector('[data-board-ticket="#513"]') as HTMLElement;
    act(() => fireEvent.keyDown(target, { key: "Enter" }));
    expect(dialog()).not.toBeNull();
    act(() => fireEvent.click(screen.getByRole("button", { name: "Закрыть" })));
    expect(dialog()).toBeNull();
  });

  test("modal labels follow the language", () => {
    renderBoard("?lang=en");
    open("#511");
    expect([...dialog().querySelectorAll('[role="tab"]')].map((tab) => tab.textContent)).toEqual([
      "Context",
      "Acceptance (2)",
      "Prompt",
    ]);
    expect(dialog().querySelector("#board-status-label")?.textContent).toBe("Backlog");
    expect(dialog().querySelector("#board-status")?.getAttribute("aria-label")).toBe("Change status");
    expect(screen.getByRole("button", { name: "Agent prompt" })).toBeTruthy();
  });
});
