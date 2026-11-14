import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { menuCounter, preRelease } from "../../harness/console/frontend/src/AppShell";
import { NAV_ITEMS } from "../../harness/console/frontend/src/navigation";
import type { HomeSnapshot } from "../../harness/console/frontend/src/ws/types";
import fixture from "./fixtures/home-snapshot.json";
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

describe("the shell header and menu counters", () => {
  test("a pre-release badge only for a semver pre-release suffix", () => {
    expect(preRelease("2.1.0-rc.1")).toBe("rc.1");
    expect(preRelease("2.0.0-pre")).toBe("pre");
    expect(preRelease("v2.0.0-beta.2+build.5")).toBe("beta.2");
    expect(preRelease("2.0.0")).toBeNull();
    expect(preRelease("unknown")).toBeNull();
  });

  test("counters come from the Home snapshot and stay hidden without data", () => {
    const snapshot = {
      ...(fixture as unknown as HomeSnapshot),
      health: { ok: 1, warn: 1, fail: 2, skipped: 0 },
      drift_counts: { total: 3, added: 1, missing: 0, package_changed: 2, local_changed: 0, conflict: 0, retired: 0 },
      repo_map: { tier: "full", message: "", head_map: null, stale_map: null },
    };
    expect(menuCounter("diagnostics", snapshot)).toEqual({ text: "2", css: "err" });
    expect(menuCounter("update-harness", snapshot)).toEqual({ text: "3", css: "warn" });
    expect(menuCounter("harness", snapshot)).toEqual({ text: "3", css: "warn" });
    expect(menuCounter("repo-map", snapshot)).toEqual({ text: "full", css: "full" });
    expect(menuCounter("board", snapshot)).toBeNull();
    expect(menuCounter("diagnostics", null)).toBeNull();
    expect(menuCounter("update-harness", { ...snapshot, drift_counts: null })).toBeNull();
  });
});

describe("the shell", () => {
  beforeEach(() => {
    window.location.hash = "#/";
  });

  test("the header branch carries the branch icon, not a text glyph", () => {
    FakeSocket.reset();
    renderApp();
    const socket = FakeSocket.last;
    act(() => socket.open());
    act(() => socket.reply({ v: 1, id: socket.request("home.snapshot").id, type: "home.snapshot", ok: true,
      cached: false, age_seconds: 0, snapshot: fixture }));
    const branch = document.querySelector("#branch") as HTMLElement;
    expect(branch.querySelector("svg")?.getAttribute("data-icon")).toBe("branch");
    expect(branch.textContent).toBe("feature/issue-7");
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

  test("a section route moves aria-current and shows its page", async () => {
    renderApp();
    await act(async () => {
      window.location.hash = "#/board";
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    const current = within(navigation()).getByRole("link", { name: "Доска задач" });
    expect(current.getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Доска задач");
    expect(document.title).toBe("Harness Console · Доска задач");
    expect(screen.queryByText("Этот раздел ещё недоступен в веб-консоли")).toBeNull();
  });

  test("the hidden Recovery and Container routes have no menu item and highlight Orchestration", async () => {
    renderApp();
    for (const hash of ["#/recovery?batch=b-1", "#/container-route?batch=b-1&role=qa"]) {
      await act(async () => {
        window.location.hash = hash;
        window.dispatchEvent(new PopStateEvent("popstate"));
      });
      const links = within(navigation()).getAllByRole("link");
      expect(links).toHaveLength(13);
      expect(links.some((link) => /recovery|container-route/.test(link.getAttribute("href") ?? ""))).toBe(false);
      expect(links.filter((link) => link.getAttribute("aria-current") === "page")).toEqual([
        within(navigation()).getByRole("link", { name: "Оркестрация" }),
      ]);
    }
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
    // The command panel lives in the "Команды" tab, mounted even while another tab is shown.
    expect(screen.getAllByRole("heading", { level: 2, name: "Команды", hidden: true }).length).toBeGreaterThan(0);
    expect(document.querySelector(".command-panel")?.closest("main")).toBeTruthy();
    expect(screen.queryByText("Этот раздел ещё недоступен в веб-консоли")).toBeNull();
  });

  test("the Diagnostics route renders the health report inside the shell, not a placeholder", async () => {
    renderApp();
    await act(async () => {
      window.location.hash = "#/diagnostics";
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    const current = within(navigation()).getByRole("link", { name: "Диагностика" });
    expect(current.getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Диагностика");
    expect(screen.getByRole("heading", { level: 2, name: "Сводка здоровья" }).closest("main")).toBeTruthy();
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
    act(() => fireEvent.click(screen.getByRole("button", { name: "EN · Английский язык" })));
    const nav = screen.getByRole("navigation", { name: "Console sections" });
    expect(within(nav).getByRole("link", { name: "Home" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("button", { name: "EN · English language" }).getAttribute("aria-pressed")).toBe(
      "true",
    );
  });

  test("a skip link comes first and moves focus to the page without touching the route", async () => {
    renderApp();
    window.location.hash = "#/diagnostics";
    const skip = screen.getByRole("link", { name: "Перейти к содержимому" });
    const focusable = document.querySelectorAll("a[href], button, input, select, textarea, [tabindex]");
    expect(focusable[0]).toBe(skip);
    await act(async () => fireEvent.click(skip));
    expect(document.activeElement).toBe(document.getElementById("content"));
    expect(window.location.hash).toBe("#/diagnostics");
  });

  test("every page title equals its menu item (Home keeps the mockup's «Состояние харнесса»)", () => {
    for (const item of NAV_ITEMS.filter((entry) => entry.route !== "")) {
      window.location.hash = `#/${item.route}`;
      const { unmount } = renderApp();
      const link = within(navigation()).getAllByRole("link").find((node) => node.getAttribute("href") === `#/${item.route}`);
      const heading = document.querySelector("main#content h1");
      expect(heading?.textContent?.trim(), item.route).toBe(link?.textContent?.trim());
      unmount();
    }
  });
});

describe("the runtime indicator", () => {
  const command = "harness-runtime serve --repo /work/repo";
  const store = (start_command: string, authority = "runtime-store") => ({
    ...(fixture as unknown as HomeSnapshot),
    store: {
      authority,
      schema: 4,
      generation: "generation-ff01",
      audit_records: start_command ? null : 7,
      cutover_at: null,
      reason: start_command ? "runtime не отвечает (runtime_unavailable)" : "",
      start_command,
    },
  });

  async function showAt(hash: string, snapshot: unknown) {
    FakeSocket.reset();
    window.location.hash = hash;
    const view = renderApp();
    const socket = FakeSocket.last;
    act(() => socket.open());
    act(() => socket.reply({ v: 1, id: socket.request("home.snapshot").id, type: "home.snapshot", ok: true,
      cached: false, age_seconds: 0, snapshot }));
    return view;
  }

  test("a runtime that does not answer is shown with its start command on the pages that need it", async () => {
    for (const hash of ["#/", "#/orchestration", "#/recovery?batch=b-1", "#/container-route?batch=b-1&role=qa"]) {
      const { unmount } = await showAt(hash, store(command));
      expect(screen.getByText("Runtime: не отвечает"), hash).toBeTruthy();
      expect(screen.getByText(command), hash).toBeTruthy();
      unmount();
    }
  });

  test("the copy button puts the command on the clipboard and says so", async () => {
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    const { unmount } = await showAt("#/", store(command));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Скопировать команду" }));
    });
    expect(writeText).toHaveBeenCalledWith(command);
    expect(screen.getByText("Команда скопирована")).toBeTruthy();
    unmount();
    Object.defineProperty(navigator, "clipboard", { value: undefined, configurable: true });
  });

  test("other pages show the state without the command", async () => {
    const { unmount } = await showAt("#/board", store(command));
    expect(screen.getByText("Runtime: не отвечает")).toBeTruthy();
    expect(screen.queryByText(command)).toBeNull();
    unmount();
  });

  test("an answering runtime is shown as working and a file ledger shows no indicator", async () => {
    const first = await showAt("#/", store(""));
    expect(screen.getByText("Runtime: работает")).toBeTruthy();
    first.unmount();
    const second = await showAt("#/", store("", "file-ledger"));
    expect(screen.queryByText(/^Runtime:/)).toBeNull();
    second.unmount();
  });
});
