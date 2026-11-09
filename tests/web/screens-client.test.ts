import { beforeEach, describe, expect, test } from "vitest";
import { createConsoleClient, screenKey } from "../../harness/console/frontend/src/ws/client";
import type { ScreenEvent } from "../../harness/console/frontend/src/ws/client";
import {
  checkTotal,
  parseHarnessOverview,
  parseHealthReport,
  parseMaintenance,
} from "../../harness/console/frontend/src/ws/screens";
import {
  parseOrchestration,
  parseReport,
  parseReports,
  parseTimeline,
} from "../../harness/console/frontend/src/ws/ledger";
import { groupRows, parseRecoveryView, parseRouteView } from "../../harness/console/frontend/src/ws/views";
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
  drift_files: 0,
  store: { authority: "file-ledger", schema: 3, generation: "generation-1", audit_records: 12 },
  adapters: [{ path: ".harness/adapters/claude/settings.json", status: "current", problem: null }],
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

const BATCH = {
  batch_id: "b-1",
  ticket: "#1",
  state: "active",
  created_at: "2026-11-01T10:00:00+00:00",
  branch: "feature/x",
  pr_created_at: "",
  pr_url: "",
  pr_state: "unknown",
};
const LEDGER = {
  version: 1,
  batches: [BATCH],
  reports: [{ dispatch_id: "d-1", batch_id: "b-1", ticket: "#1", role: "developer", outcome: "completed", reported_at: "t1" }],
  stages: [{ dispatch_id: "d-1", batch_id: "b-1", ticket: "#1", role: "developer", state: "reported", at: "t1", report: "d-1" }],
  qa_runs: [],
  qa_attempts: [],
  unavailable: null,
  dispatches: { "d-1": { role: "developer" } },
  reports_kpi: {
    reports: 1, evidence_complete: 1, latency_p50_seconds: null, latency_p95_seconds: null,
    qa_first_pass: 0, qa_tickets: 0, attention: 0, blocked: 0,
  },
};
const KPI = {
  wip: 1, oldest_wip_seconds: 60, awaiting_approval: 0, oldest_approval_seconds: null, blocked: 0, stale: 0,
  rework: 0, qa_first_pass: 0, qa_tickets: 0, cycle_p50_seconds: null, cycle_p95_seconds: null,
  throughput_7d: 0, failed: 0,
};
const ANALYTICS = { flow: { by_state: { active: 1 }, pr_per_day: [0, 1] }, quality: {}, runtime: { unfinished: 1 }, gates: { approval_p50_seconds: null } };
const ROW = { label: "Причина", value: "удержание", state: "warn", mark: "⚠ внимание", group: "Причина и граница" };
const ACTION = { key: "status", label: "Проверить состояние", enabled: true, reason: "", effect: "observe", needs_confirmation: false };
const STAGE = { rows: [ROW], actions: [ACTION], blockers: [], notes: [] };

describe("Reports, Orchestration, Recovery and Container route reads", () => {
  beforeEach(() => FakeSocket.reset());

  test("parameters are sent, keyed in a stable order and a new value is a new key", () => {
    const { client, socket } = setup();
    client.requestScreen({ type: "recovery.view", params: { skip: ["a1"], batch: "b-1" } });
    expect(socket.request("recovery.view")).toMatchObject({ batch: "b-1", skip: ["a1"], force: false });
    client.requestScreen({ type: "container_route.view", params: { batch: "b-1", role: "qa", runtime: "" } });
    expect(socket.request("container_route.view")).not.toHaveProperty("force");
    expect(screenKey({ type: "recovery.view", params: { batch: "b-1", skip: [] } })).toBe(
      screenKey({ type: "recovery.view", params: { skip: [], batch: "b-1" } }),
    );
    expect(screenKey({ type: "recovery.view", params: { batch: "b-1" } })).not.toBe(
      screenKey({ type: "recovery.view", params: { batch: "b-2" } }),
    );
  });

  test("a report body and a chronology come without cache facts; other replies still need them", () => {
    const { events, client, socket } = setup();
    client.requestScreen({ type: "reports.report", params: { dispatch_id: "d-1" } });
    const report = socket.request("reports.report");
    expect(report).not.toHaveProperty("force");
    const body = JSON.stringify({ output: "готово" });
    socket.reply({ v: 1, id: report.id, type: "reports.report", ok: true, snapshot_id: 3, text: body, next: body.length, done: true });
    const key = screenKey({ type: "reports.report", params: { dispatch_id: "d-1" } });
    expect(events).toEqual([{ type: "screen", key, value: { output: "готово" }, cached: false, ageSeconds: 0 }]);
    client.requestScreen({ type: "recovery.view" });
    const view = socket.request("recovery.view");
    socket.reply({ v: 1, id: view.id, type: "recovery.view", ok: true, snapshot_id: 4, text: "{}", next: 2, done: true });
    expect(events.at(-1)).toEqual({ type: "screen-error", key: "recovery.view", code: "invalid", message: "" });
    client.requestScreen({ type: "reports.timeline", params: { batch_id: "b-1" } });
    const timeline = socket.request("reports.timeline");
    socket.reply({ ...screenPage(timeline.id, "reports.timeline", "{}"), cached: "no" });
    expect(events.at(-1)).toMatchObject({ type: "screen-error", code: "invalid" });
  });

  test("the parsers accept the server shapes and refuse an extra or missing field", () => {
    expect(parseReports(LEDGER)).toEqual(LEDGER);
    expect(parseReports({ ...LEDGER, reports_kpi: { ...LEDGER.reports_kpi, extra: 1 } })).toBeNull();
    expect(parseReports({ ...LEDGER, version: 2 })).toBeNull();
    const orchestration = { ledger: LEDGER, lock: { lock: null, error: "занят" }, kpi: KPI, analytics: ANALYTICS };
    expect(parseOrchestration(orchestration)).toEqual(orchestration);
    expect(parseOrchestration({ ...orchestration, kpi: { ...KPI, wip: -1 } })).toBeNull();
    const timeline = { batch: BATCH, role_flow: ["developer"], events: [{ at: "t", kind: "dispatch", text: "x", role: null }] };
    expect(parseTimeline(timeline)).toEqual(timeline);
    expect(parseTimeline({ ...timeline, batch: { ...BATCH, pr_url: 1 } })).toBeNull();
    expect(parseReport({ output: "<b>x</b>" })).toEqual({ output: "<b>x</b>" });
    expect(parseReport([])).toBeNull();
    const recovery = {
      history: [{ batch_id: "b-1", label: "#1 · active · b-1" }],
      history_unavailable: "",
      entry: { batch_id: "b-1", enabled: true, state: "warn", mark: "⚠ внимание", reason: "удержание" },
      view: { batch: "b-1", unknown_outcome: false, rows: [ROW], blockers: [], notes: [], actions: [ACTION] },
      resume_plan: { command: "coordinator.py recovery resume", checks: [["config", "passed"]], approval_required: false, next_step: "—" },
    };
    expect(parseRecoveryView(recovery)).toEqual(recovery);
    expect(parseRecoveryView({ ...recovery, view: { ...recovery.view, rows: [{ ...ROW, mark: 1 }] } })).toBeNull();
    const stages = Object.fromEntries(
      ["setup", "preflight", "plan", "worker", "qa", "cleanup"].map((stage) => [stage, { stage, ...STAGE }]),
    );
    const route = {
      selection: { batch: "", role: "developer", runtime: "" },
      context: [["Worker", "не создан"]],
      tabs: [{ stage: "setup", title: "Setup", state: "info", mark: "·", reason: "" }],
      stages,
    };
    expect(parseRouteView(route)).toEqual(route);
    expect(parseRouteView({ ...route, stages: { ...stages, deploy: stages.setup } })).toBeNull();
    expect(groupRows([ROW, { ...ROW, label: "b" }, { ...ROW, group: "Проверки" }]).map((item) => item.rows.length)).toEqual([2, 1]);
  });
});

describe("Open Project, Update Harness, Configuration and Help reads", () => {
  beforeEach(() => FakeSocket.reset());

  test("help is asked by language without force; each language is its own key", () => {
    const { events, client, socket } = setup();
    client.requestScreen({ type: "help.snapshot", params: { language: "en" } });
    const request = socket.request("help.snapshot");
    expect(request).toEqual({ id: request.id, type: "help.snapshot", language: "en" });
    expect(screenKey({ type: "help.snapshot", params: { language: "en" } })).not.toBe(
      screenKey({ type: "help.snapshot", params: { language: "ru" } }),
    );
    const body = JSON.stringify({ language: "en", intro: "# Guide", sections: [] });
    socket.reply(screenPage(request.id, "help.snapshot", body, { cached: false, age: 0 }));
    const key = screenKey({ type: "help.snapshot", params: { language: "en" } });
    expect(events).toEqual([{ type: "screen", key, value: { language: "en", intro: "# Guide", sections: [] }, cached: false, ageSeconds: 0 }]);
  });

  test("the snapshots take force; a file diff takes none and comes without cache facts", () => {
    const { events, client, socket } = setup();
    for (const type of ["open_project.snapshot", "update_harness.snapshot", "configuration.snapshot"] as const) {
      client.requestScreen({ type, force: true });
      expect(socket.request(type)).toMatchObject({ type, force: true });
    }
    client.requestScreen({ type: "update_harness.diff", params: { path: "AGENTS.md" } });
    const diff = socket.request("update_harness.diff");
    expect(diff).toEqual({ id: diff.id, type: "update_harness.diff", path: "AGENTS.md" });
    const text = JSON.stringify({ path: "AGENTS.md", text: "+x" });
    socket.reply({ v: 1, id: diff.id, type: "update_harness.diff", ok: true, snapshot_id: 9, text, next: text.length, done: true });
    const key = screenKey({ type: "update_harness.diff", params: { path: "AGENTS.md" } });
    expect(events.at(-1)).toEqual({ type: "screen", key, value: { path: "AGENTS.md", text: "+x" }, cached: false, ageSeconds: 0 });
  });
});

