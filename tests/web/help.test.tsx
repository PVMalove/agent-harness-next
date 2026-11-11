import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { blocks } from "../../harness/console/frontend/src/help/Markdown";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { FakeSocket, ManualClock, screenPage } from "./fake-socket";
import EN from "./fixtures/help-en.json";
import FACTS from "./fixtures/help-facts.json";
import RU from "./fixtures/help-ru.json";

function answer(socket: FakeSocket, value: unknown) {
  const request = socket.request("help.snapshot");
  act(() => socket.reply(screenPage(request.id, "help.snapshot", JSON.stringify(value))));
  return request;
}

function renderPage() {
  window.localStorage.clear();
  window.location.hash = "#/help";
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
  return { socket, request: answer(socket, RU) };
}

const tabs = () => screen.getAllByRole("tab").map((item) => item.textContent);
const content = () => document.querySelector("main#content")?.textContent ?? "";

describe("the Help route", () => {
  beforeEach(() => FakeSocket.reset());

  test("asks for the guide in the UI language and shows its sections as tabs", () => {
    const { request } = renderPage();
    expect(request).toEqual({ id: request.id, type: "help.snapshot", language: "ru" });
    expect(tabs()).toEqual(FACTS.ru);
    expect(content()).toContain("Справка по пульту");
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Клавиши" })));
    expect(document.querySelector("#help-section h2")?.textContent).toBe("Клавиши");
    const sent = RU.sections.find((item) => item.title === "Клавиши")!.markdown;
    expect(sent).toContain("|");
    expect(document.querySelector("#help-section table")).not.toBeNull();
  });

  test("follows the ru/en switch with a new request", () => {
    const { socket } = renderPage();
    act(() => fireEvent.click(screen.getByRole("button", { name: "EN · Английский язык" })));
    const request = answer(socket, EN);
    expect(request).toMatchObject({ type: "help.snapshot", language: "en" });
    expect(tabs()).toEqual(FACTS.en);
  });

  test("the renderer makes elements, never markup or an external link", () => {
    renderPage();
    expect(document.querySelector("#help-intro a, #help-section a")).toBeNull();
    expect(blocks("# T\n\n- a `b`\n  c\n\n| x | y |\n| --- | --- |\n| 1 | 2 |\n\n<b>x</b> [doc](https://example.org)")).toEqual([
      { kind: "heading", level: 1, text: "T" },
      { kind: "list", items: ["a `b` c"] },
      { kind: "table", rows: [["x", "y"], ["1", "2"]] },
      { kind: "paragraph", lines: ["<b>x</b> [doc](https://example.org)"] },
    ]);
  });
});
