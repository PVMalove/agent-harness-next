import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { FakeSocket, ManualClock } from "./fake-socket";

function renderApp() {
  return render(
    <LanguageProvider>
      <App
        client={createConsoleClient({
          url: "ws://127.0.0.1:1/ws",
          WebSocket: FakeSocket,
          timers: new ManualClock(),
          probeHealth: async () => false,
        })}
      />
    </LanguageProvider>,
  );
}

const navigation = () => screen.getByRole("navigation", { name: "Разделы консоли" });

describe("the shell", () => {
  beforeEach(() => {
    window.location.hash = "#/";
  });

  test("lists 13 sections in three groups and marks the current one", () => {
    renderApp();
    const nav = navigation();
    const groups = nav.querySelectorAll(".nav-group");
    expect([...groups].map((group) => group.querySelector(".nav-group-label")?.textContent)).toEqual([
      "Обзор",
      "Работа",
      "Контекст",
    ]);
    expect([...groups].map((group) => group.querySelectorAll("a").length)).toEqual([4, 5, 4]);
    const links = within(nav).getAllByRole("link");
    expect(links).toHaveLength(13);
    expect(links.filter((link) => link.getAttribute("aria-current") === "page")).toEqual([
      within(nav).getByRole("link", { name: "Главная" }),
    ]);
  });

  test("a section route moves aria-current and shows its placeholder", async () => {
    renderApp();
    await act(async () => {
      window.location.hash = "#/diagnostics";
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    const current = within(navigation()).getByRole("link", { name: "Диагностика" });
    expect(current.getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Диагностика");
    expect(document.title).toBe("Harness Console · Диагностика");
  });

  test("the Harness route renders its commands inside the shell, not a placeholder", async () => {
    renderApp();
    await act(async () => {
      window.location.hash = "#/harness";
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    const current = within(navigation()).getByRole("link", { name: "Harness" });
    expect(current.getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Harness");
    expect(screen.getByRole("heading", { level: 2, name: "Команды" })).toBeTruthy();
    expect(document.querySelector(".command-panel")?.closest("main")).toBeTruthy();
    expect(screen.queryByText("Этот раздел ещё недоступен в веб-консоли")).toBeNull();
  });

  test("the agent activity route renders its step list inside the shell, not a placeholder", async () => {
    renderApp();
    await act(async () => {
      window.location.hash = "#/agent-activity";
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    const current = within(navigation()).getByRole("link", { name: "Ход работы" });
    expect(current.getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Ход работы");
    expect(screen.getByRole("heading", { level: 2, name: "Шаги и события" })).toBeTruthy();
    expect(document.querySelector(".work-events")?.closest("main")).toBeTruthy();
    expect(screen.queryByText("Этот раздел ещё недоступен в веб-консоли")).toBeNull();
  });

  test("collapse is remembered and the drawer closes on the scrim and Esc", () => {
    renderApp();
    const collapse = screen.getByRole("button", { name: "Свернуть меню" });
    act(() => fireEvent.click(collapse));
    expect(document.body.classList.contains("nav-collapsed")).toBe(true);
    expect(localStorage.getItem("harness-nav-collapsed")).toBe("1");
    expect(collapse.getAttribute("aria-expanded")).toBe("false");
    expect(screen.getByRole("button", { name: "Развернуть меню" })).toBe(collapse);

    const toggle = screen.getByRole("button", { name: "Открыть меню" });
    const scrim = document.getElementById("nav-scrim")!;
    expect(scrim.hidden).toBe(true);
    act(() => fireEvent.click(toggle));
    expect(document.body.classList.contains("nav-open")).toBe(true);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(scrim.hidden).toBe(false);
    act(() => fireEvent.click(scrim));
    expect(document.body.classList.contains("nav-open")).toBe(false);

    act(() => fireEvent.click(toggle));
    act(() => fireEvent.keyDown(document, { key: "Escape" }));
    expect(document.body.classList.contains("nav-open")).toBe(false);
    expect(scrim.hidden).toBe(true);
  });

  test("a remembered collapse is restored on start", () => {
    localStorage.setItem("harness-nav-collapsed", "1");
    renderApp();
    expect(document.body.classList.contains("nav-collapsed")).toBe(true);
  });

  test("g, d, o and ? navigate outside inputs only", async () => {
    renderApp();
    await act(async () => fireEvent.keyDown(document, { key: "d" }));
    expect(window.location.hash).toBe("#/diagnostics");
    await act(async () => fireEvent.keyDown(document, { key: "o" }));
    expect(window.location.hash).toBe("#/orchestration");
    await act(async () => fireEvent.keyDown(document, { key: "?" }));
    expect(window.location.hash).toBe("#/help");
    const input = document.createElement("input");
    document.body.append(input);
    await act(async () => fireEvent.keyDown(input, { key: "g" }));
    expect(window.location.hash).toBe("#/help");
    input.remove();
    await act(async () => fireEvent.keyDown(document, { key: "g" }));
    expect(window.location.hash).toBe("#/");
  });

  test("the language switch translates the shell in place", () => {
    renderApp();
    act(() => fireEvent.click(screen.getByRole("button", { name: "Английский язык" })));
    const nav = screen.getByRole("navigation", { name: "Console sections" });
    expect(within(nav).getByRole("link", { name: "Home" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("button", { name: "English language" }).getAttribute("aria-pressed")).toBe(
      "true",
    );
  });
});
