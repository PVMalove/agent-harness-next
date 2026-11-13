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

  test("asks for the guide in the UI language; the seven tabs carry counts computed from the data", () => {
    const { request } = renderPage();
    expect(request).toEqual({ id: request.id, type: "help.snapshot", language: "ru" });
    expect(tabs()).toEqual(["1Начало", "13Разделы", "4Клавиши", "6Статусы", "12Безопасность", "4Вопросы", "3Документация"]);
    expect([...document.querySelectorAll("#help-kpis .ds-stat-label")].map((item) => item.textContent)).toEqual([
      "Разделов", "Сочетаний клавиш", "Правил безопасности", "Вопросов",
    ]);
    expect(document.querySelectorAll(".ds-pillars > div")).toHaveLength(3);
    expect(content()).toContain("Справка по пульту");
    // Every guide section is shown in one of the tabs.
    const seen = new Set<string>();
    for (const name of tabs()) {
      act(() => fireEvent.click(screen.getByRole("tab", { name: new RegExp(name!.replace(/^\d+/, "")) })));
      for (const heading of document.querySelectorAll("#help-tab-start .ds-panel-title, [id^='help-section-'] .ds-panel-title, #help-faq .ds-panel-title, .ds-md h2")) seen.add(heading.textContent ?? "");
    }
    for (const title of FACTS.ru) expect([...seen], title).toContain(title);
  });

  test("Sections lists every menu section, Keys the web shortcuts as keycaps with the TUI keys table", () => {
    renderPage();
    act(() => fireEvent.click(screen.getByRole("tab", { name: /Разделы/ })));
    expect(document.querySelectorAll(".ds-grid-3 a")).toHaveLength(13);
    act(() => fireEvent.click(screen.getByRole("tab", { name: /Клавиши/ })));
    expect([...document.querySelectorAll(".ds-key-grid kbd")].map((item) => item.textContent)).toEqual(["g", "d", "o", "?"]);
    expect(document.querySelector("#help-section-2 table")).not.toBeNull();
  });

  test("Start: README action, quick links, the Read next tiles that switch the tab, FAQ in its own tab", () => {
    renderPage();
    const actions = [...document.querySelectorAll(".ds-head-actions > *")].map((item) => item.textContent?.trim());
    expect(actions).toEqual(["README", "Диагностика"]);
    const cards = [...document.querySelectorAll("#help-tab-start a.ds-quick")];
    expect(cards.map((card) => card.querySelector(".ds-row-title")?.textContent)).toEqual([
      "Проверить здоровье", "Открыть обновление", "Изучить Repo Map", "Настроить Harness",
    ]);
    const next = document.querySelector("#help-next") as HTMLElement;
    expect(next.querySelectorAll("button.ds-tile")).toHaveLength(6);
    act(() => fireEvent.click(next.querySelectorAll("button.ds-tile")[4]!));
    expect(screen.getByRole("tab", { name: /Вопросы/ }).getAttribute("aria-selected")).toBe("true");
    const faq = document.querySelectorAll("#help-faq details");
    expect(faq).toHaveLength(4);
    expect(faq[0]?.querySelector("summary")?.textContent).toBe("Почему «пропущено» не считается успехом?");
  });

  test("one search filters the blocks of every tab and shows its matches instead of the tab", () => {
    renderPage();
    const search = screen.getByRole("searchbox", { name: "Поиск по справке" });
    act(() => fireEvent.change(search, { target: { value: "heartbeat" } }));
    const results = document.querySelector("#help-search-results") as HTMLElement;
    expect(results).not.toBeNull();
    expect(results.textContent?.toLowerCase()).toContain("heartbeat");
    act(() => fireEvent.change(search, { target: { value: "zzzzzz-no-such-text" } }));
    expect(document.querySelector("#help-search-results")?.textContent).toContain("Ничего не найдено");
    act(() => fireEvent.click(screen.getByRole("button", { name: "Сбросить" })));
    expect(document.querySelector("#help-search-results")).toBeNull();
    expect(document.querySelector("#help-intro")).not.toBeNull();
  });

  test("follows the ru/en switch with a new request", () => {
    const { socket } = renderPage();
    act(() => fireEvent.click(screen.getByRole("button", { name: "EN · Английский язык" })));
    const request = answer(socket, EN);
    expect(request).toMatchObject({ type: "help.snapshot", language: "en" });
    expect(tabs().map((label) => label!.replace(/^\d+/, ""))).toEqual(["Start", "Sections", "Keys", "Statuses", "Safety", "Questions", "Documentation"]);
  });

  test("the renderer makes elements, never markup or an external link", () => {
    renderPage();
    expect(document.querySelector("#help-intro a, [id^='help-section-'] a")).toBeNull();
    expect(blocks("# T\n\n- a `b`\n  c\n\n| x | y |\n| --- | --- |\n| 1 | 2 |\n\n<b>x</b> [doc](https://example.org)")).toEqual([
      { kind: "heading", level: 1, text: "T" },
      { kind: "list", items: ["a `b` c"] },
      { kind: "table", rows: [["x", "y"], ["1", "2"]] },
      { kind: "paragraph", lines: ["<b>x</b> [doc](https://example.org)"] },
    ]);
  });
});
