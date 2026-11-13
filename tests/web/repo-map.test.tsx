import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import FACTS from "./fixtures/repo-map.json";
import { FakeSocket, ManualClock, snapshotReply, jobReply } from "./fake-socket";

beforeEach(() => FakeSocket.reset());

// Without a cached map the kernel derives no symbol kinds and no coverage.
const NO_MAP = { ...FACTS, map: null, symbol_kinds: null, coverage: null };

function open() {
  window.location.hash = "#/repo-map";
  const clock = new ManualClock();
  const client = createConsoleClient({ url: "ws://127.0.0.1:1/ws", WebSocket: FakeSocket,
    timers: clock, probeHealth: async () => false });
  render(<LanguageProvider><App client={client} /></LanguageProvider>);
  const socket = FakeSocket.last;
  act(() => socket.open());
  act(() => socket.reply(snapshotReply(socket.request("home.snapshot").id)));
  return { socket, clock };
}

function facts(socket: FakeSocket, value: unknown = FACTS) {
  act(() => socket.reply({ v: 1, id: socket.request("repo_map.snapshot").id,
    type: "repo_map.snapshot", ok: true, snapshot_id: 1, text: JSON.stringify(value),
    next: 1000, done: true, cached: true, age_seconds: 2 }));
}

test("Repo Map shows the whole-snapshot summary and the signatures of the selected file", () => {
  const { socket } = open();
  facts(socket);
  expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Repo Map");
  const summary = screen.getByLabelText("Сводка Repo Map");
  expect(within(summary).getByText("≈512")).toBeTruthy();
  expect(summary.querySelectorAll(".ds-stat-value")).toHaveLength(4);
  expect(summary.id).toBe("repo-facts");
  expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["1Файлы", "2Символы", "3Связи"]);
  act(() => fireEvent.click(screen.getByRole("button", { name: "pkg/core.py" })));
  expect(screen.getByText("def load_config(path)")).toBeTruthy();
  expect(screen.getByText(/Счётчики сверху — весь снимок/).textContent).toContain("4 файлов, 3 символов и 4 связей");
});

test("the file filter narrows the tree and Reset restores it", () => {
  const { socket } = open();
  facts(socket);
  act(() => fireEvent.change(screen.getByRole("searchbox", { name: "Поиск файла или пути" }), { target: { value: "cli" } }));
  expect(screen.queryByRole("button", { name: "pkg/core.py" })).toBeNull();
  expect(screen.getByRole("button", { name: "pkg/cli.py" })).toBeTruthy();
  act(() => fireEvent.click(screen.getByRole("button", { name: "Сбросить" })));
  expect(screen.getByRole("button", { name: "pkg/core.py" })).toBeTruthy();
});

test("symbol kinds are the kernel's; a kind the map cannot give says no data", () => {
  const { socket } = open();
  facts(socket);
  act(() => fireEvent.click(screen.getByRole("tab", { name: /Символы/ })));
  const chips = [...document.querySelectorAll("#repo-kind-chips button")].map((chip) => chip.textContent);
  expect(chips).toEqual(["Все 3", "Functions 2", "Modules 1"]);
  act(() => fireEvent.click(screen.getByRole("button", { name: "Modules 1" })));
  const kinds = [...document.querySelectorAll(".ds-symbol-row .ds-kind")].map((kind) => kind.textContent);
  expect(kinds).toEqual(["class"]);
  expect(screen.getByText("Строка").nextElementSibling!.textContent).toBe("нет данных");
});

test("building requires confirmation, pins the displayed HEAD and displays an uncached degraded result", () => {
  const { socket } = open();
  facts(socket, NO_MAP);
  act(() => fireEvent.click(screen.getAllByRole("button", { name: "Перестроить" })[0]));
  expect(socket.sent.filter((r) => r.type === "job.start")).toHaveLength(0);
  act(() => fireEvent.click(screen.getByRole("button", { name: "Отмена" })));
  expect(socket.sent.filter((r) => r.type === "job.start")).toHaveLength(0);
  act(() => fireEvent.click(screen.getAllByRole("button", { name: "Перестроить" })[0]));
  act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Собрать" })));
  const request = socket.request("job.start");
  expect(request).toMatchObject({ command_id: "repo-map-build", values: { commit: "a".repeat(40) }, client: "browser" });
  const built = { ...FACTS.map, tier: "minimal", parser: "path-only", files: [{ path: "new.py" }], edges: [], diagnostics: [], estimated_tokens: 8 };
  act(() => socket.reply(jobReply(request.id, "job.start", { command_id: "repo-map-build", done: true,
    phase: "completed", returncode: 0, output: [{ channel: "stdout", text: JSON.stringify(built) }], cursor: 1 })));
  facts(socket, NO_MAP);
  expect(screen.getByRole("button", { name: "new.py" })).toBeTruthy();
  expect(screen.getByText("minimal")).toBeTruthy();
});

test("a paged snapshot is assembled before display and an expired page is an explicit error", () => {
  const { socket } = open();
  const text = JSON.stringify(FACTS);
  act(() => socket.reply({ v: 1, id: socket.request("repo_map.snapshot").id, type: "repo_map.snapshot", ok: true,
    snapshot_id: 42, text: text.slice(0, 100), next: 100, done: false, cached: false, age_seconds: 0 }));
  expect(socket.request("snapshot.page")).toMatchObject({ snapshot_id: 42, offset: 100 });
  expect(screen.queryByRole("button", { name: "pkg/core.py" })).toBeNull();
  act(() => socket.reply({ v: 1, id: socket.request("snapshot.page").id, type: "snapshot.page", ok: true,
    text: text.slice(100), next: text.length, done: true }));
  expect(screen.getByRole("button", { name: "pkg/core.py" })).toBeTruthy();
  act(() => fireEvent.click(screen.getByRole("button", { name: "Обновить" })));
  act(() => socket.reply({ v: 1, id: socket.request("repo_map.snapshot").id, type: "repo_map.snapshot", ok: false,
    error: { code: "snapshot_expired", message: "expired" } }));
  expect(screen.getByRole("alert").getAttribute("data-code")).toBe("snapshot_expired");
});

test("reconnect discards an incomplete snapshot and never replays a build", () => {
  const { socket, clock } = open();
  facts(socket);
  act(() => socket.close());
  act(() => clock.advance(500));
  const next = FakeSocket.last;
  act(() => next.open());
  expect(next.request("repo_map.snapshot")).toMatchObject({ force: false });
  expect(next.sent.filter((r) => r.type === "job.start")).toHaveLength(0);
  facts(next, { ...NO_MAP, head: "b".repeat(40) });
  expect(screen.queryByRole("button", { name: "pkg/core.py" })).toBeNull();
  expect(screen.getByText("Кэша карты для HEAD нет")).toBeTruthy();
});

test("a changed HEAD invalidates an open build confirmation", () => {
  const { socket } = open();
  facts(socket);
  act(() => fireEvent.click(screen.getByRole("button", { name: "Обновить" })));
  act(() => fireEvent.click(screen.getAllByRole("button", { name: "Перестроить" })[0]));
  facts(socket, { ...NO_MAP, head: "b".repeat(40) });
  act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Собрать" })));
  expect(socket.sent.filter((r) => r.type === "job.start")).toHaveLength(0);
});

test("truncated build output cannot become a map and its failure survives a snapshot refresh", () => {
  const { socket } = open();
  facts(socket, NO_MAP);
  act(() => fireEvent.click(screen.getAllByRole("button", { name: "Перестроить" })[0]));
  act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Собрать" })));
  act(() => socket.reply(jobReply(socket.request("job.start").id, "job.start", {
    command_id: "repo-map-build", done: true, phase: "completed", returncode: 0, truncated: true,
    output: [{ channel: "stdout", text: JSON.stringify(FACTS.map) }], cursor: 1,
  })));
  facts(socket, NO_MAP);
  expect(screen.getByRole("alert").getAttribute("data-code")).toBe("truncated");
  expect(screen.queryByRole("button", { name: "pkg/core.py" })).toBeNull();
});

test("hubs count unique incoming files like TUI and graph selection filters symbols", () => {
  const { socket } = open();
  facts(socket);
  act(() => fireEvent.click(screen.getByRole("tab", { name: /Связи/ })));
  const hubs = screen.getByRole("heading", { name: "Хабы" }).closest("section")!;
  expect(within(hubs).getByText("pkg/core.py").parentElement?.textContent).toBe("pkg/core.py2");
  act(() => fireEvent.click(screen.getByRole("button", { name: "pkg/cli.py" })));
  expect(screen.getByRole("tab", { name: /Символы/ }).getAttribute("aria-selected")).toBe("true");
  expect(document.querySelectorAll(".ds-symbol-row")).toHaveLength(1);
  expect(screen.getAllByText("def main(argv)").length).toBeGreaterThan(0);
});

test("a lost start acknowledgement reconciles the running job without replaying the command", () => {
  const { socket, clock } = open();
  facts(socket);
  act(() => fireEvent.click(screen.getAllByRole("button", { name: "Перестроить" })[0]));
  act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Собрать" })));
  act(() => socket.close());
  act(() => clock.advance(500));
  const next = FakeSocket.last;
  act(() => next.open());
  act(() => next.reply(snapshotReply(next.request("home.snapshot").id)));
  facts(next);
  act(() => next.reply({ v: 1, id: next.request("job.list").id, type: "job.list", ok: true, jobs: [{
    id: "recovered", command_id: "repo-map-build", mutating: true, phase: "running", cursor: 0,
    done: false, truncated: false, returncode: null, error: "",
  }] }));
  expect(next.request("job.subscribe")).toMatchObject({ job_id: "recovered", cursor: 0 });
  expect(next.sent.filter((r) => r.type === "job.start")).toHaveLength(0);
  act(() => next.reply(jobReply(next.request("job.subscribe").id, "job.subscribe", { id: "recovered",
    command_id: "repo-map-build", done: true, phase: "completed", returncode: 0, cursor: 1,
    output: [{ channel: "stdout", text: JSON.stringify(FACTS.map) }],
  })));
  expect((screen.getAllByRole("button", { name: "Перестроить" })[0] as HTMLButtonElement).disabled).toBe(false);
});

test("a nonzero CLI exit reports a build error and its diagnostic stderr", () => {
  const { socket } = open();
  facts(socket);
  act(() => fireEvent.click(screen.getAllByRole("button", { name: "Перестроить" })[0]));
  act(() => fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Собрать" })));
  act(() => socket.reply(jobReply(socket.request("job.start").id, "job.start", {
    command_id: "repo-map-build", done: true, phase: "completed", returncode: 2, cursor: 1,
    output: [{ channel: "stderr", text: "error: bad commit\nremedy: pass HEAD" }],
  })));
  expect(screen.getByRole("alert").getAttribute("data-code")).toBe("build_failed");
  expect(screen.getByText(/error: bad commit/)).toBeTruthy();
});

test("the file tree is a hierarchy: indented folder rows that fold, file rows with their status", () => {
  const { socket } = open();
  facts(socket);
  const rows = () => [...document.querySelectorAll(".ds-tree .ds-tree-dir, .ds-tree .ds-tree-file")];
  const name = (row: Element) => row.querySelector("b, .ds-tree-name")?.textContent;
  const shape = () => rows().map((row) => [row.className.split(" ")[1], name(row), (row.querySelector(".ds-tree-indent") as HTMLElement).style.width]);
  expect(shape()).toEqual([
    ["ds-tree-dir", "pkg/", "0px"],
    ["ds-tree-file", "core.py", "16px"],
    ["ds-tree-file", "cli.py", "16px"],
    ["ds-tree-file", "broken.py", "16px"],
    ["ds-tree-file", "README.md", "0px"],
  ]);
  expect(rows()[0].querySelector("svg[data-icon='folder']")).not.toBeNull();
  expect(rows()[1].querySelector(".ds-tree-status")?.textContent).toBeTruthy();
  act(() => fireEvent.click(rows()[0]));
  expect(rows()[0].getAttribute("aria-expanded")).toBe("false");
  expect(shape().map(([, label]) => label)).toEqual(["pkg/", "README.md"]);
});

test("without a map for HEAD the latest cached map shows marked stale for HEAD, with Rebuild", () => {
  const { socket } = open();
  const stale = { ...FACTS.map, commit: "0123456789abcdef0123456789abcdef01234567" };
  facts(socket, { ...NO_MAP, stale_map: stale });
  const banner = document.querySelector("#repo-stale") as HTMLElement;
  expect(banner.textContent).toContain("устарела для HEAD");
  expect(banner.textContent).toContain("0123456789ab");
  expect(within(banner).getByRole("button", { name: /Перестроить/ })).toBeTruthy();
  expect(screen.getByRole("button", { name: "pkg/core.py" })).toBeTruthy();
});

test("the empty state names the reason and offers Rebuild in place", () => {
  const { socket } = open();
  facts(socket, NO_MAP);
  const empty = document.querySelector("#repo-empty") as HTMLElement;
  expect(empty.textContent).toContain("Кэша карты для HEAD нет");
  act(() => fireEvent.click(within(empty).getByRole("button", { name: /Перестроить/ })));
  expect(screen.getByRole("dialog")).toBeTruthy();
});

test("the summary separates the whole snapshot from the fragment and keeps the header actions", () => {
  const { socket } = open();
  facts(socket);
  const actions = [...document.querySelectorAll(".ds-head-actions > button")];
  expect(actions.map((button) => button.textContent?.trim())).toEqual(["", "Перестроить", "Экспорт"]);
  expect(actions[0]?.getAttribute("aria-label")).toBe("Обновить");
  expect(actions[2]?.querySelector("svg")).toBeTruthy();
  const stats = [...document.querySelectorAll("#repo-facts .ds-stat")].map((card) =>
    [card.querySelector(".ds-stat-label")?.textContent, card.querySelector(".ds-stat-value")?.textContent, card.querySelector(".ds-stat-caption")?.textContent ?? null]);
  expect(stats).toEqual([["Файлы", "4", null], ["Символы", "3", null], ["Связи", "4", null], ["Токены", "≈512", "бюджет 4000"]]);
  const facts_ = document.querySelector("#repo-facts .ds-facts-main")!.textContent!;
  expect(facts_).toContain("Уровень full");
  expect(facts_).toContain("Парсер bundle");
  expect(facts_).toContain("Python 3.14 · linux_x86_64");
  expect(facts_).toContain("HEAD индекса aaaaaaaa");
  expect(document.querySelector("#repo-facts .ds-facts-end")?.textContent).toMatch(/\d\d:\d\d:\d\d$/);
  // The Settings tab is gone: parser, memory and policy facts are no longer a page of their own.
  expect(screen.queryByRole("tab", { name: /Настройки/ })).toBeNull();
});
