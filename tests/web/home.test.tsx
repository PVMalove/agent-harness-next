import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { OFFLINE_REFRESH_MS } from "../../harness/console/frontend/src/routes/Home";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import fixture from "./fixtures/home-snapshot.json";
import { FakeSocket, ManualClock, snapshotReply } from "./fake-socket";

function renderHome(snapshot: unknown = fixture) {
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
  act(() => socket.reply(snapshotReply(socket.request("home.snapshot").id, snapshot)));
  return { client, socket };
}

const headings = (level: number) =>
  screen.getAllByRole("heading", { level }).map((heading) => heading.textContent);

describe("Home", () => {
  beforeEach(() => {
    FakeSocket.reset();
    window.location.hash = "#/";
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "Date"] });
  });
  afterEach(() => vi.useRealTimers());

  test("shows the mockup blocks in order with the snapshot facts in Russian", () => {
    renderHome();
    expect(headings(1)).toEqual(["Состояние харнесса"]);
    expect(headings(2).map((text) => text!.replace(/\s*\d+$/, ""))).toEqual([
      "Требует внимания",
      "Контекст",
      "Последние задачи",
      "Здоровье",
      "Контур Harness",
    ]);
    expect(headings(3).map((text) => text!.trim())).toEqual([
      "Проектgithub",
      "Harness",
      "Runtime store",
      "Repo Map",
      "Память",
      "Маршрут сессии #7",
      "По областям",
      "Проверки",
    ]);
    const health = document.getElementById("home-health")!;
    expect(within(health).getByText("42").className).toBe("ok");
    expect(document.getElementById("health-fail")!.textContent).toBe("2");
    expect(document.getElementById("home-facts")!.textContent).toBe("42 ok · 1 warn · 2 fail · 11 skip");
    const chips = document.getElementById("home-chips")!.textContent!;
    expect(chips).toContain("установлено 1.5.1");
    expect(chips).toContain("file-ledger");
    expect(chips).toContain("32 навыков");
    expect(chips).not.toContain("2.0.0");
    const attention = document.getElementById("attention-list")!;
    expect(within(attention).getByText("skills.drift")).toBeTruthy();
    expect(within(attention).getAllByRole("img").map((icon) => icon.getAttribute("aria-label"))).toEqual([
      "ошибки",
      "ошибки",
      "внимание",
    ]);
    expect(within(attention).getAllByRole("link", { name: "Открыть →" }).map((link) => link.getAttribute("href"))).toEqual([
      "#/diagnostics",
      "#/update-harness",
      "#/diagnostics",
    ]);
    expect(screen.getByText("local · b3e4d28")).toBeTruthy();
    const context = document.getElementById("home-context")!;
    expect(within(context).getByText("feature/issue-7")).toBeTruthy();
    expect(within(context).getByText("generation-1a2b3c4d")).toBeTruthy();
    expect(context.compareDocumentPosition(document.getElementById("home-tasks")!)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
  });

  test("recent sessions, areas and the check filters come from the snapshot", () => {
    renderHome();
    const tasks = document.getElementById("home-tasks")!;
    expect([...tasks.querySelectorAll(".task-id")].map((cell) => cell.textContent)).toEqual(["#7", "#6"]);
    expect([...tasks.querySelectorAll(".route-step")].map((step) => step.className)).toEqual([
      "route-step done",
      "route-step current",
    ]);
    expect(document.querySelectorAll("#home-areas .health-row")).toHaveLength(4);
    const checks = () => [...document.querySelectorAll("#home-checks .check-main b")].map((cell) => cell.textContent);
    expect(checks()).toEqual(["integration.config", "skills.drift", "hooks.bash", "tracker.online"]);
    act(() => fireEvent.click(screen.getByRole("button", { name: "Пропущено" })));
    expect(checks()).toEqual(["tracker.online"]);
    act(() => fireEvent.click(screen.getByRole("button", { name: "Проблемы" })));
    expect(checks()).toEqual(["integration.config", "skills.drift", "hooks.bash"]);
  });

  test("says how many problems are listed of how many", () => {
    renderHome();
    expect(document.getElementById("problems-limit")!.textContent).toBe(
      "Показано 3 из 5 · Полный каталог проверок недоступен",
    );
    expect(document.getElementById("problem-count")!.textContent).toBe("2 ошибки · 1 предупреждения · 3 / 5");
  });

  test("facts without a source show an explicit no-data state, never a demo value", () => {
    renderHome({ ...fixture, project: null, recent_sessions: [] });
    const tasks = document.getElementById("home-tasks")!;
    expect(within(tasks).getByText("Сессий в ledger нет")).toBeTruthy();
    const context = document.getElementById("home-context")!;
    const branch = within(context).getByText("Ветка").parentElement!;
    expect(branch.querySelector("dd")!.textContent).toBe("нет данных");
    expect(branch.querySelector("dd")!.getAttribute("title")).toBe("Недоступно в текущем снимке");
    const cutover = within(context).getByText("Cutover").parentElement!;
    expect(cutover.querySelector("dd")!.textContent).toBe("нет данных");
    const limit = within(context).getByText("Лимит").parentElement!;
    expect(limit.querySelector("dd")!.textContent).toBe("нет данных");
    expect(document.getElementById("home-contour")!.textContent).not.toContain("2.0.0");
  });

  test("switches to English in place", () => {
    renderHome();
    act(() => fireEvent.click(screen.getByRole("button", { name: "Английский язык" })));
    expect(headings(2).map((text) => text!.replace(/\s*\d+$/, ""))).toEqual([
      "Requires attention",
      "Context",
      "Recent tasks",
      "Health",
      "Harness outline",
    ]);
    expect(document.getElementById("problems-limit")!.textContent).toBe(
      "Showing 3 of 5 · Full check catalog unavailable",
    );
    expect(document.documentElement.lang).toBe("en");
  });

  test("offline mode asks again 15 s after a reply; online asks only on request", () => {
    const { socket } = renderHome();
    const count = () => socket.sent.filter((body) => body.type === "home.snapshot").length;
    expect(count()).toBe(1);
    act(() => vi.advanceTimersByTime(OFFLINE_REFRESH_MS));
    expect(count()).toBe(2);
    act(() => fireEvent.click(screen.getByRole("button", { name: "Онлайн" })));
    expect(socket.request("home.snapshot")).toMatchObject({ force: true, online: true });
    act(() => socket.reply(snapshotReply(socket.request("home.snapshot").id)));
    act(() => vi.advanceTimersByTime(OFFLINE_REFRESH_MS * 2));
    expect(count()).toBe(3);
    act(() => fireEvent.click(screen.getByRole("button", { name: /Проверить/ })));
    expect(count()).toBe(4);
    expect(socket.request("home.snapshot")).toMatchObject({ force: true, online: true });
  });

  test("orchestration events refresh Home without a reload", () => {
    const { socket } = renderHome();
    const subscription = socket.request("orchestration.subscribe").id;
    act(() =>
      socket.reply({ v: 1, id: subscription, type: "orchestration.subscribe", ok: true, kind: "events", cursor: "j-1", events: [{}] }),
    );
    act(() =>
      socket.reply({ v: 1, id: subscription, type: "orchestration.subscribe", ok: true, kind: "events", cursor: "j-2", events: [{}] }),
    );
    act(() => vi.advanceTimersByTime(1000));
    const requests = socket.sent.filter((body) => body.type === "home.snapshot");
    expect(requests).toHaveLength(2);
    expect(requests[1]).toMatchObject({ force: false });
    const changed = { ...fixture, health: { ...fixture.health, ok: 43 } };
    act(() => socket.reply(snapshotReply(requests[1]!.id, changed)));
    expect(document.getElementById("health-ok")!.textContent).toBe("43");
  });
});
