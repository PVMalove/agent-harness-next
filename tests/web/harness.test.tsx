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
  // The Commands tab and the overview's quick command table each ask for the section catalog.
  for (const catalog of socket.sent.filter((body) => body.type === "job.catalog")) {
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
  }
  act(() => answerHarness(socket, overview));
  return { socket };
}

const kpis = () => document.querySelector("#harness-kpis") as HTMLElement;

describe("the Harness route", () => {
  beforeEach(() => FakeSocket.reset());

  test("shows the overview facts; the pipeline usage block of no mockup slot is gone", () => {
    const { socket } = renderHarness();
    expect(socket.request("harness.overview")).toMatchObject({ force: false });
    expect(screen.getByRole("tab", { name: "Обзор" }).getAttribute("aria-selected")).toBe("true");
    expect(document.querySelector("#harness-version")?.textContent).toBe("2.0.0 → 2.0.1");
    expect([...kpis().querySelectorAll(":scope > div > span:first-child")].map((label) => label.textContent)).toEqual([
      "Установлено",
      "Runtime store",
      "Audit chain",
      "Skills",
    ]);
    expect(within(kpis()).getByText("schema 3")).toBeTruthy();
    expect(kpis().textContent).toContain("cutover не выполнен");
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
      "Обзор",
      "Runtime",
      "Адаптеры",
      "Контейнеры",
      "Команды",
    ]);
    expect(document.querySelector("#harness-usage")).toBeNull();
    expect(within(document.querySelector("#harness-install") as HTMLElement).getByText("engineering-suite")).toBeTruthy();
  });

  test("overview in the mockup's order: facts, KPI captions, six installation rows, runtime, adapters, quick commands", () => {
    renderHarness({
      ...HARNESS_OVERVIEW,
      integrations: [
        { name: "Claude Code", kind: "runtime", status: "current", cli: true, detail: ".harness/adapters/claude_worker.py" },
        { name: "Codex", kind: "runtime", status: "outdated", cli: false, detail: ".harness/adapters/codex_worker.py" },
        { name: "GitHub", kind: "tracker", status: "current", cli: true, detail: "github.com/owner/repo" },
      ],
    });
    const facts = [...document.querySelectorAll(".harness-title .home-facts span")].map((item) => item.textContent);
    expect(facts.at(-1)).toMatch(/^\d{2}:\d{2}:\d{2}$/);
    expect(facts).not.toContain("→ 2.0.1");
    expect(kpis().querySelector("div small")?.textContent).toBe("доступно 2.0.1");
    const install = document.querySelector("#harness-install") as HTMLElement;
    const rows = [...install.querySelectorAll(".harness-component")];
    expect(rows.map((row) => row.querySelector("span")?.textContent)).toEqual([
      "Harness package",
      "Skills snapshot",
      "Managed files",
      "Hook policy",
      "Runtime store",
      "harness.lock",
    ]);
    expect(rows.every((row) => row.querySelector("em.orch-pill")?.textContent)).toBe(true);
    const overview = document.querySelector("#harness-tab-overview") as HTMLElement;
    expect(overview.querySelector("#harness-runtime .panel-head .orch-pill")?.textContent).toBe("file-ledger");
    expect(overview.querySelectorAll("#harness-adapters .harness-adapter")).toHaveLength(3);
    const quick = overview.querySelector("#harness-quick-commands") as HTMLElement;
    expect(quick.querySelectorAll(".harness-command-row").length).toBeGreaterThan(0);
    expect(quick.querySelectorAll(".harness-command-row").length).toBeLessThanOrEqual(3);
    expect(overview.querySelector("#harness-maintenance")).toBeNull();
    expect(document.querySelector("#harness-tab-commands #harness-maintenance")).not.toBeNull();
    act(() => fireEvent.click(within(quick).getAllByRole("button", { name: "Показать" })[0]!));
    expect(screen.getByRole("tab", { name: "Команды" }).getAttribute("aria-selected")).toBe("true");
  });

  test("the maintenance panel shows the server's plan, skips and worktree reasons", () => {
    renderHarness();
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Команды" })));
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
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Команды" })));
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
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Команды" })));
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
    expect(document.querySelectorAll("#harness-install .harness-component em")[1]?.textContent).toBe("Drift");
    expect(screen.getByText(/worktree has uncommitted changes/)).toBeTruthy();
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
    expect(within(adapters).getAllByText("нет данных").length).toBeGreaterThan(0);
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Контейнеры" })));
    const containers = document.querySelector("#harness-tab-containers") as HTMLElement;
    // Every probe failed: the engine is named, each fact says no data with the probe's reason.
    expect(within(containers).getByText("docker", { selector: "b" })).toBeTruthy();
    const daemon = containers.querySelector("#harness-engine .no-data") as HTMLElement;
    expect(daemon.title).toBe("docker info: код 1: Cannot connect to the Docker daemon");
    const counts = containers.querySelectorAll("[data-fact='images-volumes'] .no-data");
    expect([...counts].map((item) => (item as HTMLElement).title)).toEqual(["docker images: код 1", "docker volume ls: код 1"]);
    expect(within(containers).getAllByText("нет данных").length).toBeGreaterThan(4);
  });

  test("Runtime shows the runtime status probe, Adapters the Claude Code, Codex and GitHub adapters", () => {
    renderHarness({
      ...HARNESS_OVERVIEW,
      runtime: { state: "online", revision: 41, reason: "" },
      integrations: [
        { name: "Claude Code", kind: "runtime", status: "current", cli: true, detail: ".harness/adapters/claude_worker.py" },
        { name: "Codex", kind: "runtime", status: "outdated", cli: false, detail: ".harness/adapters/codex_worker.py" },
        { name: "GitHub", kind: "tracker", status: "current", cli: true, detail: "github.com/owner/repo" },
      ],
    });
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Runtime" })));
    const runtime = document.querySelector("#harness-tab-runtime #harness-runtime") as HTMLElement;
    expect(runtime.querySelector(".panel-head .orch-pill")?.textContent).toBe("работает");
    expect(within(runtime).getByText("41")).toBeTruthy();
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Адаптеры" })));
    const cards = [...document.querySelectorAll("#harness-tab-adapters .harness-adapter")];
    expect(cards.map((card) => card.querySelector("h3")?.textContent)).toEqual(["Claude Code", "Codex", "GitHub"]);
    expect(cards.map((card) => card.querySelector(".harness-adapter-head svg")?.getAttribute("data-icon"))).toEqual(["terminal", "command", "github-mark"]);
    expect(cards.map((card) => card.querySelector("em")?.textContent)).not.toContain("current");
  });

  test("a runtime that does not answer says why; maintenance actions carry icons", () => {
    renderHarness({ ...HARNESS_OVERVIEW, runtime: { state: "offline", revision: null, reason: "runtime не отвечает (runtime_unavailable)" } });
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Runtime" })));
    const runtime = document.querySelector("#harness-tab-runtime #harness-runtime") as HTMLElement;
    expect(runtime.querySelector(".panel-head .orch-pill")?.textContent).toBe("не отвечает");
    expect(runtime.textContent).toContain("runtime не отвечает (runtime_unavailable)");
    const buttons = [...document.querySelectorAll("#harness-maintenance button")];
    expect(buttons.length).toBeGreaterThan(2);
    expect(buttons.every((button) => button.querySelector("svg") !== null)).toBe(true);
  });

  test("the Containers tab shows the engine inventory the kernel probed", () => {
    renderHarness({
      ...HARNESS_OVERVIEW,
      containers: {
        engine: "podman", version: "5.2.0", cgroup_driver: "systemd", cgroup_version: "v2", selinux: true,
        rootless: true, info_problem: null, images: 3, images_problem: null, volumes: 2, volumes_problem: null,
      },
    });
    act(() => fireEvent.click(screen.getByRole("tab", { name: "Контейнеры" })));
    expect(document.querySelector("#harness-engine-line")?.textContent).toBe("podman · 5.2.0 · rootless · cgroup v2 · systemd");
    expect(document.querySelector("[data-fact='images-volumes']")?.textContent).toBe("3 / 2");
    const engine = document.querySelector("#harness-engine")?.textContent ?? "";
    expect(engine).toContain("daemon отвечает");
    expect(engine).toContain("SELinux включён");
    const blocks = [...document.querySelectorAll(".harness-container-grid > .harness-container-block")];
    expect(blocks.map((block) => block.querySelector("h3")?.textContent)).toEqual(["Images", "Networks / volumes"]);
    expect(blocks[0]?.querySelector(".harness-block-head > span")?.textContent).toBe("3");
    expect(blocks[1]?.querySelector(".harness-block-head > span")?.textContent).toContain("2");
    expect(blocks[1]?.querySelector(".harness-cleanup")).toBeTruthy();
  });

  test("in English the overview tab reads Overview, apart from folder browsing", () => {
    renderHarness(HARNESS_OVERVIEW, "?lang=en");
    expect(screen.getByRole("tab", { name: "Overview" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("tab", { name: "Commands" })).toBeTruthy();
    expect(translate("en", "Обзор папок")).toBe("Browse folders");
  });
});
