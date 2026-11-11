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
    expect(headings(2).map((text) => text!.replace(/\s+\d+$/, ""))).toEqual([
      "Требует внимания",
      "Контекст",
      "Последние задачи",
      "Здоровье",
      "Контур Harness",
    ]);
    expect(headings(3).map((text) => text!.trim())).toEqual([
      "Проект",
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
    expect(document.getElementById("home-facts")!.textContent).toBe("42 пройдено · 1 внимание · 2 ошибки · 11 пропущено");
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
    expect(document.getElementById("problem-count")!.textContent).toBe("2 ошибки · 1 предупреждение · 3 / 5");
  });

  test("facts without a source show an explicit no-data state, never a demo value", () => {
    renderHome({ ...fixture, project: null, recent_sessions: [], store: { ...fixture.store, authority: "runtime-store", cutover_at: null } });
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
    act(() => fireEvent.click(screen.getByRole("button", { name: "EN · Английский язык" })));
    expect(headings(2).map((text) => text!.replace(/\s+\d+$/, ""))).toEqual([
      "Requires attention",
      "Context",
      "Recent tasks",
      "Health",
      "Harness outline",
    ]);
    expect(document.getElementById("problems-limit")!.textContent).toBe(
      "Showing 3 of 5 · Full check catalog unavailable",
    );
    expect(document.getElementById("home-facts")!.textContent).toBe("42 passed · 1 warnings · 2 errors · 11 skipped");
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

describe("Home after the owner's review", () => {
  beforeEach(() => {
    FakeSocket.reset();
    window.location.hash = "#/";
  });

  const icons = (root: Element) => [...root.querySelectorAll("svg[data-icon]")].map((svg) => svg.getAttribute("data-icon"));

  test("health areas carry their own icons and the mockup's compact counters", () => {
    renderHome();
    const rows = [...document.querySelectorAll("#home-health .health-row")];
    expect(rows.map((row) => icons(row.querySelector(".health-name")!)[0])).toEqual(["github", "skills", "shield", "harness"]);
    const counts = rows[0].querySelector(".health-count")!;
    expect(counts.querySelectorAll("span").length).toBe(4);
    expect(counts.textContent).toBe("5✓ 0⚠ 1✖ 2–");
  });

  test("attention and checks show the localized check title, the id only as a hint", () => {
    renderHome({
      ...fixture,
      problems: [{ status: "fail", id: "files.skill_snapshot", message: "differs", group: "files" }],
      problems_total: 1,
    });
    const attention = document.getElementById("attention-list")!;
    expect(within(attention).getByText("Снимок навыков")).toBeTruthy();
    expect(attention.querySelector("b")!.textContent).not.toContain("files.skill_snapshot");
    expect(document.getElementById("problem-count")!.textContent).toContain("1 ошибка");
  });

  test("the project card shows the hosting icon without a tracker capsule and capability names", () => {
    renderHome();
    const context = document.getElementById("home-context")!;
    const project = context.querySelector(".context-section h3")!;
    expect(icons(project)).toEqual(["github-mark"]);
    expect(context.querySelector(".provider")).toBeNull();
    expect(within(context).getByText("backend-orchestration · engineering-suite")).toBeTruthy();
    expect(within(context).getByText("не выполнен")).toBeTruthy();
  });

  test("a map of another commit is shown as stale for HEAD with a Rebuild action", () => {
    renderHome({
      ...fixture,
      repo_map: {
        ...fixture.repo_map,
        head_map: null,
        stale_map: { origin: "кэш", commit: "7ff379f", files: 35, edges: 80, estimated_tokens: 16000 },
      },
    });
    const context = document.getElementById("home-context")!;
    expect(within(context).getByText(/устарела для HEAD/)).toBeTruthy();
    expect(within(context).getByRole("link", { name: /Перестроить/ }).getAttribute("href")).toBe("#/repo-map");
  });

  test("recent tasks: number search, role and status icons, localized status and duration", () => {
    renderHome();
    const tasks = document.getElementById("home-tasks")!;
    const rows = () => [...tasks.querySelectorAll(".task-row")];
    expect(icons(rows()[0].querySelector(".task-role")!)).toEqual(["developer"]);
    expect(icons(rows()[1].querySelector(".task-role")!)).toEqual(["qa"]);
    expect(rows()[0].querySelector(".task-status")!.textContent).toContain("Активен");
    expect(icons(rows()[0].querySelector(".task-status")!)).toEqual(["play"]);
    expect(rows()[0].querySelector(".task-time")!.textContent).toBe("2 мин");
    expect(rows()[1].querySelector(".task-time")!.textContent).toBe("31 мин");
    act(() => fireEvent.change(within(tasks).getByRole("searchbox"), { target: { value: "6" } }));
    expect(rows().map((row) => row.querySelector(".task-id")!.textContent)).toEqual(["#6"]);
    act(() => fireEvent.change(within(tasks).getByRole("searchbox"), { target: { value: "#99" } }));
    expect(rows()).toEqual([]);
    expect(within(tasks).getByText(/не найдена/)).toBeTruthy();
  });

  test("the session route spans the panel with localized steps and marks the running step", () => {
    renderHome();
    const steps = [...document.querySelectorAll("#home-tasks .route-step")];
    expect(steps.map((step) => step.querySelector("small")!.textContent)).toEqual(["Отчёт сдан", "Выполняется"]);
    expect(steps[1].className).toContain("current");
    expect(icons(steps[0])).toEqual(["architect"]);
  });
});
