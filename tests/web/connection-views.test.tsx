import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import fixture from "./fixtures/home-snapshot.json";
import { FakeSocket, ManualClock, snapshotReply } from "./fake-socket";

function setup(reachable = false) {
  const clock = new ManualClock();
  const client = createConsoleClient({
    url: "ws://127.0.0.1:1/ws",
    WebSocket: FakeSocket,
    timers: clock,
    probeHealth: async () => reachable,
  });
  render(
    <LanguageProvider>
      <App client={client} />
    </LanguageProvider>,
  );
  return { client, clock };
}

const chip = () => document.getElementById("connection-state")!;
const banner = () => document.getElementById("connection-banner");
const page = () => document.querySelector(".connection-page");
const reply = (snapshot: unknown = fixture) => {
  const socket = FakeSocket.last;
  act(() => socket.reply(snapshotReply(socket.request("home.snapshot").id, snapshot)));
};
const flush = async () => {
  await act(async () => {
    await Promise.resolve();
  });
};

describe("connection views", () => {
  beforeEach(() => {
    FakeSocket.reset();
    window.location.hash = "#/";
  });

  test("connected: online chip, no banner, Home content", () => {
    setup();
    act(() => FakeSocket.last.open());
    reply();
    expect(chip().className).toBe("ds-conn ds-conn-connected");
    expect(chip().textContent).toBe("online");
    expect(banner()).toBeNull();
    expect(page()).toBeNull();
    expect(document.getElementById("home")).not.toBeNull();
  });

  test("reconnecting: banner with attempt, delay and a stale snapshot; retry reconnects now", () => {
    const { client } = setup();
    act(() => FakeSocket.last.open());
    reply();
    act(() => FakeSocket.last.close());
    expect(chip().className).toBe("ds-conn ds-conn-reconnecting");
    expect(banner()!.textContent).toContain("Попытка 1 · следующая через 0.5 с · Последний снимок устарел");
    expect(document.getElementById("health-ok")!.textContent).toBe("42");
    const retry = vi.spyOn(client, "retryNow");
    act(() => fireEvent.click(screen.getByRole("button", { name: "Повторить сейчас" })));
    expect(retry).toHaveBeenCalledTimes(1);
    expect(FakeSocket.instances).toHaveLength(2);
  });

  test("no server: the page replaces the content and retries", async () => {
    const { client } = setup(false);
    act(() => FakeSocket.last.close());
    await flush();
    expect(chip().className).toBe("ds-conn ds-conn-offline");
    expect(page()!.getAttribute("data-status")).toBe("no_server");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Нет связи с сервером консоли");
    expect(page()!.textContent).toContain("ws://127.0.0.1:1/ws");
    expect(page()!.textContent).toContain("последний снимок");
    expect(document.getElementById("home")).toBeNull();
    const retry = vi.spyOn(client, "retryNow");
    act(() => fireEvent.click(screen.getByRole("button", { name: "Повторить подключение" })));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  test("error: a rejected session", async () => {
    setup(true);
    act(() => FakeSocket.last.close());
    await flush();
    expect(chip().className).toBe("ds-conn ds-conn-error");
    expect(page()!.textContent).toContain("Сервер отклонил сессию");
  });

  test("error: ok:false and an invalid snapshot", () => {
    const { client } = setup();
    act(() => FakeSocket.last.open());
    const socket = FakeSocket.last;
    act(() =>
      socket.reply({ v: 1, id: socket.request("home.snapshot").id, type: "home.snapshot", ok: false, error: { code: "busy", message: "later" } }),
    );
    expect(page()!.getAttribute("data-status")).toBe("error");
    expect(page()!.textContent).toContain("busy");
    act(() => {
      client.requestHome();
    });
    reply({ ...fixture, problems_total: 1 });
    expect(page()!.textContent).toContain("снимок не прошёл проверку");
    const retry = vi.spyOn(client, "retryNow");
    act(() => fireEvent.click(screen.getByRole("button", { name: "Загрузить заново" })));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  test("empty: a valid snapshot without checks; refresh forces a new one", () => {
    const { client } = setup();
    act(() => FakeSocket.last.open());
    reply({ ...fixture, health: { ok: 0, warn: 0, fail: 0, skipped: 0 }, problems: [], problems_total: 0 });
    expect(chip().className).toBe("ds-conn ds-conn-empty");
    expect(chip().textContent).toBe("пусто");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Данных пока нет");
    const refresh = vi.spyOn(client, "requestHome");
    act(() => fireEvent.click(screen.getByRole("button", { name: "Обновить" })));
    expect(refresh).toHaveBeenCalledWith({ force: true });
  });

  test("empty: a page with its own data keeps its content; the empty page is Home's", async () => {
    setup();
    act(() => FakeSocket.last.open());
    reply({ ...fixture, health: { ok: 0, warn: 0, fail: 0, skipped: 0 }, problems: [], problems_total: 0 });
    await act(async () => {
      window.location.hash = "#/board";
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(page()).toBeNull();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Доска задач");
  });
});
