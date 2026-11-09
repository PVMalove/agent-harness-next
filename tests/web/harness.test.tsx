import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { LanguageProvider, translate } from "../../harness/console/frontend/src/i18n";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import {
  CANCEL_REASON,
  COMMANDS,
  FakeSocket,
  HARNESS_OVERVIEW,
  MAINTENANCE,
  ManualClock,
  answerHarness,
  jobReply,
} from "./fake-socket";

const CLEANUP = {
  ...COMMANDS[1],
  command_id: "cleanup-apply",
  title: "Очистка .harness (soft): применить",
  typed_confirmation: null,
  plan_required: true,
};
const REMOVE = {
  ...COMMANDS[1],
  command_id: "worktree-remove",
  title: "Удалить worktree",
  typed_confirmation: null,
  inputs: ["worktree"],
};

function renderHarness(overview: unknown = HARNESS_OVERVIEW, language = "") {
  window.location.hash = `#/harness${language}`;
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
  const catalog = socket.request("job.catalog");
  act(() =>
    socket.reply({
      v: 1,
      id: catalog.id,
      type: "job.catalog",
      ok: true,
      commands: [...COMMANDS, CLEANUP, REMOVE],
      cancel_reason: CANCEL_REASON,
    }),
  );
  act(() => answerHarness(socket, overview));
  return { socket };
}

const kpis = () => document.querySelector("#harness-kpis") as HTMLElement;

describe("the Harness route", () => {
  beforeEach(() => FakeSocket.reset());

  test("shows the overview facts and the server's pipeline usage counts", () => {
    const { socket } = renderHarness();
    expect(socket.request("harness.overview")).toMatchObject({ force: false });
    expect(screen.getByRole("tab", { name: "Обзор" }).getAttribute("aria-selected")).toBe("true");
    expect(document.querySelector("#harness-version")?.textContent).toBe("2.0.0");
    expect(document.querySelector("#harness-drift")?.textContent).toBe("⚠ дрейф есть");
    expect([...kpis().querySelectorAll(":scope > div > span:first-child")].map((label) => label.textContent)).toEqual([
      "Установлено",
      "Runtime store",
      "Audit chain",
      "Skills",
    ]);
    expect(within(kpis()).getByText("schema 3")).toBeTruthy();
    expect(within(kpis()).getAllByText("нет данных").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
      "Обзор",
      "Runtime",
      "Адаптеры",
      "Контейнеры",
      "Команды",
    ]);
    const usage = document.querySelector("#harness-usage") as HTMLElement;
    for (const value of ["4", "3", "12", "9"]) expect(within(usage).getByText(value)).toBeTruthy();
    expect(within(document.querySelector("#harness-install") as HTMLElement).getByText("engineering-suite")).toBeTruthy();
  });

  test("an unavailable ledger shows its reason instead of counts", () => {
    renderHarness({
      ...HARNESS_OVERVIEW,
      usage: { unavailable: "Леджер не найден", batches: 0, tickets: 0, dispatches: 0, reports: 0 },
    });
    expect(within(document.querySelector("#harness-usage") as HTMLElement).getByText(/Леджер не найден/)).toBeTruthy();
  });

  test("the maintenance panel shows the server's plan, skips and worktree reasons", () => {
    renderHarness();
    const panel = document.querySelector("#harness-maintenance") as HTMLElement;
    expect(within(panel).getByText("runs/tests: 2.0 KiB · 3")).toBeTruthy();
    expect(within(panel).getByText("Жёсткий режим: +2.0 KiB")).toBeTruthy();
    expect(document.querySelector("#worktree-count")?.textContent).toBe("Worktree: 2 · можно удалить: 1");
    expect(within(panel).getByText(/есть незакоммиченные изменения/)).toBeTruthy();
    act(() => fireEvent.click(within(panel).getByRole("button", { name: "План" })));
    expect(within(panel).getByText(/активные данные или моложе 24 ч/)).toBeTruthy();
    const remove = (name: string) => within(panel).getByRole("button", { name: `Удалить… ${name}` }) as HTMLButtonElement;
    expect(remove("issue-1-done").disabled).toBe(false);
    expect(remove("issue-2-live").disabled).toBe(true);
  });

  test("Очистить… switches to Commands and opens the server confirmation bound to the soft plan", () => {
    const { socket } = renderHarness();
    act(() => fireEvent.click(screen.getByRole("button", { name: "Очистить…" })));
    expect(screen.getByRole("tab", { name: "Команды" }).getAttribute("aria-selected")).toBe("true");
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(CLEANUP.confirmation_reason!)).toBeTruthy();
    act(() => fireEvent.click(within(dialog).getByRole("button", { name: "Запустить" })));
    expect(socket.request("job.start")).toMatchObject({
      command_id: "cleanup-apply",
      confirmed: true,
      plan_digest: MAINTENANCE.maintenance.soft.digest,
    });
  });

  test("a worktree removal asks with the worktree path, and a finished job refreshes the facts", () => {
    const { socket } = renderHarness();
    act(() => fireEvent.click(screen.getByRole("button", { name: "Удалить… issue-1-done" })));
    act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Запустить" })));
    const start = socket.request("job.start");
    expect(start).toMatchObject({
      command_id: "worktree-remove",
      values: { worktree: MAINTENANCE.maintenance.worktrees[0]!.path },
    });
    const before = socket.sent.filter((body) => body.type === "harness.overview").length;
    act(() =>
      socket.reply(
        jobReply(start.id, "job.start", { command_id: "worktree-remove", phase: "completed", done: true, returncode: 0 }),
      ),
    );
    const overviews = socket.sent.filter((body) => body.type === "harness.overview");
    expect(overviews.length).toBe(before + 1);
    expect(overviews.at(-1)).toMatchObject({ force: true });
    expect(socket.request("harness.maintenance")).toMatchObject({ force: true });
  });

  test("in English the page labels and the reasons are translated", () => {
    renderHarness(HARNESS_OVERVIEW, "?lang=en");
    expect(screen.getByRole("heading", { level: 2, name: "Installation" })).toBeTruthy();
    expect(document.querySelector("#harness-drift")?.textContent).toBe("⚠ drift detected");
    expect(screen.getByText(/worktree has uncommitted changes/)).toBeTruthy();
  });

  test("in English the server's ledger reason is translated through the catalog", () => {
    const reason = "леджер оркестрации не найден или не инициализирован";
    renderHarness(
      { ...HARNESS_OVERVIEW, usage: { unavailable: reason, batches: 0, tickets: 0, dispatches: 0, reports: 0 } },
      "?lang=en",
    );
    const english = "the orchestration ledger is not found or not initialized";
    expect(within(document.querySelector("#harness-usage") as HTMLElement).getByText(`Pipeline usage: ${english}`)).toBeTruthy();
    expect(screen.queryByText(new RegExp(reason))).toBeNull();
  });

  test("Runtime, Adapters and Containers show the overview facts and say what has no source", () => {
    renderHarness();
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Runtime" })));
    const runtime = document.querySelector("#harness-tab-runtime") as HTMLElement;
    expect(within(runtime).getByText("generation-1")).toBeTruthy();
    expect(within(runtime).getByRole("heading", { level: 2, name: "Audit chain" })).toBeTruthy();
    expect(within(runtime).getAllByText("нет данных").length).toBeGreaterThan(0);
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Адаптеры" })));
    const adapters = document.querySelector("#harness-tab-adapters") as HTMLElement;
    expect(within(adapters).getByText("current")).toBeTruthy();
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Контейнеры" })));
    const containers = document.querySelector("#harness-tab-containers") as HTMLElement;
    expect(within(containers).getAllByText("нет данных")).toHaveLength(4);
  });

  test("in English the overview tab reads Overview, apart from folder browsing", () => {
    renderHarness(HARNESS_OVERVIEW, "?lang=en");
    expect(screen.getByRole("tab", { name: "Overview" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("tab", { name: "Commands" })).toBeTruthy();
    expect(translate("en", "Обзор папок")).toBe("Browse folders");
  });
});
