import { beforeEach, describe, expect, test } from "vitest";
import { createConsoleClient, screenKey } from "../../harness/console/frontend/src/ws/client";
import type { ScreenEvent } from "../../harness/console/frontend/src/ws/client";
import {
  checkTotal,
  parseHarnessOverview,
  parseHealthReport,
  parseMaintenance,
} from "../../harness/console/frontend/src/ws/screens";
import { FakeSocket, HEALTH_REPORT, ManualClock, nextPage, screenPage } from "./fake-socket";

function setup() {
  const clock = new ManualClock();
  const events: ScreenEvent[] = [];
  const client = createConsoleClient({
    url: "ws://127.0.0.1:4242/ws",
    WebSocket: FakeSocket,
    timers: clock,
    probeHealth: async () => false,
  });
  client.subscribeScreens((event) => events.push(event));
  client.start();
  FakeSocket.last.open();
  return { clock, events, client, socket: FakeSocket.last };
}

const OVERVIEW = {
  state: {
    installed: true,
    installed_version: "2.0.0",
    capabilities: ["engineering-suite"],
    skills: 32,
    managed_files: 259,
    updated_at: "2026-11-05 10:00 UTC",
    orchestration: true,
  },
  package_version: "2.0.1",
  drift: "clean",
  usage: { unavailable: null, batches: 4, tickets: 3, dispatches: 12, reports: 9 },
};

const SUMMARY = {
  plan: { mode: "soft", root: "/work/project/.harness", min_age_hours: 24, remove: [], skipped: [] },
  categories: {},
  total: { bytes: 0, files: 0 },
  items: 0,
  digest: "a".repeat(64),
};

describe("screen snapshots", () => {
  beforeEach(() => FakeSocket.reset());

  test("a paged snapshot is completed with snapshot.page and parsed once done", () => {
    const { events, client, socket } = setup();
    expect(client.requestScreen({ type: "diagnostics.snapshot" })).toBe(true);
    const request = socket.request("diagnostics.snapshot");
    expect(request).toMatchObject({ force: false, online: false });
    const text = JSON.stringify(HEALTH_REPORT);
    const cut = Math.floor(text.length / 2);
    socket.reply(screenPage(request.id, "diagnostics.snapshot", text.slice(0, cut), { next: cut, done: false, cached: true, age: 4 }));
    expect(events).toEqual([]);
    const page = socket.request("snapshot.page");
    expect(page).toMatchObject({ snapshot_id: 7, offset: cut });
    socket.reply(nextPage(page.id, text.slice(cut), text.length, true));
    expect(events).toEqual([
      { type: "screen", key: "diagnostics.snapshot", value: HEALTH_REPORT, cached: true, ageSeconds: 4 },
    ]);
  });

  test("a newer request of the same key supersedes the older one", () => {
    const { events, client, socket } = setup();
    client.requestScreen({ type: "harness.maintenance" });
    const older = socket.request("harness.maintenance");
    client.requestScreen({ type: "harness.maintenance", force: true });
    const newer = socket.request("harness.maintenance");
    expect(newer.force).toBe(true);
    const text = JSON.stringify({ maintenance: null, error: "Git unavailable" });
    socket.reply(screenPage(older.id, "harness.maintenance", text));
    expect(events).toEqual([]);
    socket.reply(screenPage(newer.id, "harness.maintenance", text));
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ type: "screen", key: "harness.maintenance" });
  });

  test("the online report has its own key and the overview arrives typed without its envelope", () => {
    const { events, client, socket } = setup();
    expect(screenKey({ type: "diagnostics.snapshot", online: true })).toBe("diagnostics.snapshot:online");
    client.requestScreen({ type: "harness.overview" });
    const request = socket.request("harness.overview");
    expect(request).toEqual({ id: request.id, type: "harness.overview", force: false });
    socket.reply({ v: 1, id: request.id, type: "harness.overview", ok: true, cached: false, age_seconds: 0.5, ...OVERVIEW });
    expect(events).toEqual([{ type: "screen", key: "harness.overview", value: OVERVIEW, cached: false, ageSeconds: 0.5 }]);
    expect(parseHarnessOverview(events[0]!.type === "screen" ? events[0]!.value : null)).toEqual(OVERVIEW);
  });

  test("a refusal, malformed JSON and a reconnect each end the read", () => {
    const { events, client, socket } = setup();
    client.requestScreen({ type: "diagnostics.snapshot", online: true });
    const refused = socket.request("diagnostics.snapshot");
    socket.reply({
      v: 1,
      id: refused.id,
      type: "diagnostics.snapshot",
      ok: false,
      error: { code: "collect_failed", message: "RuntimeError" },
    });
    client.requestScreen({ type: "harness.maintenance" });
    socket.reply(screenPage(socket.request("harness.maintenance").id, "harness.maintenance", "{broken"));
    expect(events).toEqual([
      { type: "screen-error", key: "diagnostics.snapshot:online", code: "collect_failed", message: "RuntimeError" },
      { type: "screen-error", key: "harness.maintenance", code: "invalid", message: "" },
    ]);
    client.requestScreen({ type: "harness.overview" });
    const stale = socket.request("harness.overview");
    socket.close();
    socket.reply({ v: 1, id: stale.id, type: "harness.overview", ok: true, cached: false, age_seconds: 0, ...OVERVIEW });
    expect(events).toHaveLength(2);
  });
});

describe("screen parsers", () => {
  test("accept the server shapes and refuse anything else without recomputing", () => {
    expect(parseHealthReport(HEALTH_REPORT)).toEqual(HEALTH_REPORT);
    expect(checkTotal(HEALTH_REPORT.summary)).toBe(5);
    expect(parseHealthReport({ ...HEALTH_REPORT, schema_version: 2 })).toBeNull();
    expect(parseHealthReport({ ...HEALTH_REPORT, extra: 1 })).toBeNull();
    expect(parseHealthReport({ ...HEALTH_REPORT, checks: [{ ...HEALTH_REPORT.checks[0], status: "bad" }] })).toBeNull();
    const view = {
      soft: SUMMARY,
      hard: { ...SUMMARY, plan: { ...SUMMARY.plan, mode: "hard" } },
      worktrees: [{ path: "/w/a", branch: "feature/x", dirty: 0, reason: "" }],
      worktree_error: "",
      tree_sizes: [{ path: "/w/a", size: { bytes: 10, files: 1 } }],
    };
    expect(parseMaintenance({ maintenance: view, error: "" })).toEqual({ maintenance: view, error: "" });
    expect(parseMaintenance({ maintenance: null, error: "boom" })).toEqual({ maintenance: null, error: "boom" });
    expect(parseMaintenance({ maintenance: { ...view, soft: { ...SUMMARY, items: -1 } }, error: "" })).toBeNull();
    expect(parseHarnessOverview({ ...OVERVIEW, usage: { ...OVERVIEW.usage, batches: "4" } })).toBeNull();
  });
});
