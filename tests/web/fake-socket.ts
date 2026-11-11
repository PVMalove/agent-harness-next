/* Deterministic seams for the console client: a scripted WebSocket and a manual clock. */
import type { SocketLike, Timers } from "../../harness/console/frontend/src/ws/client";

export class FakeSocket implements SocketLike {
  static instances: FakeSocket[] = [];
  readyState = 0;
  sent: Record<string, unknown>[] = [];
  onopen: ((event: unknown) => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onclose: ((event: unknown) => void) | null = null;
  onerror: ((event: unknown) => void) | null = null;

  constructor(readonly url: string) {
    FakeSocket.instances.push(this);
  }

  static reset(): void {
    FakeSocket.instances = [];
  }

  static get last(): FakeSocket {
    const socket = FakeSocket.instances.at(-1);
    if (!socket) throw new Error("no socket was opened");
    return socket;
  }

  send(data: string): void {
    this.sent.push(JSON.parse(data) as Record<string, unknown>);
  }

  close(): void {
    if (this.readyState === 3) return;
    this.readyState = 3;
    this.onclose?.({});
  }

  /** The server accepts the handshake. */
  open(): void {
    this.readyState = 1;
    this.onopen?.({});
  }

  /** The server sends one text frame. */
  reply(body: Record<string, unknown>): void {
    this.onmessage?.({ data: JSON.stringify(body) });
  }

  /** The last request of `type` this socket sent. */
  request(type: string): Record<string, unknown> {
    const found = this.sent.filter((body) => body.type === type).at(-1);
    if (!found) throw new Error(`no ${type} request was sent`);
    return found;
  }
}

interface Scheduled {
  at: number;
  callback: () => void;
}

export class ManualClock implements Timers {
  now = 0;
  private next = 1;
  private readonly tasks = new Map<number, Scheduled>();

  setTimeout(callback: () => void, ms: number): unknown {
    const handle = this.next++;
    this.tasks.set(handle, { at: this.now + ms, callback });
    return handle;
  }

  clearTimeout(handle: unknown): void {
    this.tasks.delete(handle as number);
  }

  /** Run every task due within `ms`, in time order. */
  advance(ms: number): void {
    const end = this.now + ms;
    for (;;) {
      const due = [...this.tasks.entries()]
        .filter(([, task]) => task.at <= end)
        .sort((a, b) => a[1].at - b[1].at || a[0] - b[0])[0];
      if (!due) break;
      this.tasks.delete(due[0]);
      this.now = due[1].at;
      due[1].callback();
    }
    this.now = end;
  }

  /** Delays of the pending tasks from now. */
  pending(): number[] {
    return [...this.tasks.values()].map((task) => task.at - this.now).sort((a, b) => a - b);
  }
}

export const SNAPSHOT = {
  version: 2,
  health: { ok: 3, warn: 1, fail: 1, skipped: 2 },
  problems: [
    { status: "fail", id: "skills.drift", message: "Skill drift", group: "skills" },
    { status: "warn", id: "hooks", message: "Hook missing", group: "hooks" },
  ],
  problems_total: 2,
  harness_version: "2.0.0",
  drift: "clean",
  active_batches: null,
  repo_map: { tier: null, message: "no cache", head_map: null, stale_map: null },
  memory: { state: null, policy: null },
  project: null,
  harness: null,
  store: null,
  drift_counts: null,
  areas: [],
  skipped_checks: [],
  recent_sessions: [],
};

export function snapshotReply(id: unknown, snapshot: unknown = SNAPSHOT): Record<string, unknown> {
  return { v: 1, id, type: "home.snapshot", ok: true, cached: false, age_seconds: 0, snapshot };
}

/* Job catalog descriptions and the cancel warning as job.catalog sends them
   (tests/web/fixtures/job-catalog.json for the Playwright mock). */
export const CANCEL_REASON = "Отмена останавливает команду; уже внесённые изменения не откатываются.";

export const COMMANDS = [
  {
    command_id: "diff",
    title: "Дрейф управляемых файлов",
    section: "harness",
    reversibility: "reversible",
    reversibility_label: "✔ обратимо",
    needs_confirmation: false,
    confirmation_reason: null,
    typed_confirmation: null,
    read_only: true,
    inputs: [],
    plan_required: false,
    available: true,
  },
  {
    command_id: "uninstall-apply",
    title: "Удалить харнесс из проекта (с резервной копией изменённых файлов)",
    section: "harness",
    reversibility: "deletes-local-data",
    reversibility_label: "✖ удаление",
    needs_confirmation: true,
    confirmation_reason: "Команда удаляет локальные данные — восстановить их нельзя.",
    typed_confirmation: "UNINSTALL",
    read_only: false,
    inputs: [],
    plan_required: false,
    available: true,
  },
];

/** A job snapshot of job-1 with `overrides`. */
export function jobSnapshot(overrides: Record<string, unknown> = {}): {
  id: string;
  command_id: string;
  mutating: boolean;
  phase: "running" | "completed" | "failed" | "cancelled";
  cursor: number;
  done: boolean;
  truncated: boolean;
  returncode: number | null;
  error: string | null;
  output: { channel: string; text: string }[];
} {
  return {
    id: "job-1",
    command_id: "uninstall-apply",
    mutating: true,
    phase: "running",
    cursor: 0,
    done: false,
    truncated: false,
    returncode: null,
    error: "",
    output: [],
    ...overrides,
  } as ReturnType<typeof jobSnapshot>;
}

export function jobReply(
  id: unknown,
  type: string,
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return { v: 1, id, type, ok: true, job: jobSnapshot(overrides) };
}

/* The live step feed as steps.subscribe sends it (tests/web/fixtures/live-steps.json for the
   Playwright mock): a Claude developer, a Codex reviewer and one orchestration event. */
export const ROSTER = [
  {
    dispatch_id: "dispatch-dev", batch_id: "batch-885", ticket: "#885", role: "developer", state: "working",
    batch_state: "active", branch: "feature/issue-885", started_at: "2026-11-05T10:00:00+00:00",
    last_event_at: "2026-11-05T10:20:00+00:00", silent: false,
  },
  {
    dispatch_id: "dispatch-rev", batch_id: "batch-885", ticket: "#885", role: "review", state: "working",
    batch_state: "active", branch: "feature/issue-885", started_at: "2026-11-05T10:05:00+00:00",
    last_event_at: "2026-11-05T10:06:00+00:00", silent: true,
  },
];

export const AGENT_STEP = {
  origin: "agent",
  dispatch_id: "dispatch-dev",
  batch_id: "batch-885",
  role: "developer",
  source: "structured",
  structure: "available",
  kind: "tool",
  text: "Read",
  observed_at: "2026-11-06T10:00:01+00:00",
} as const;

export const CODEX_STEP = {
  ...AGENT_STEP,
  dispatch_id: "dispatch-rev",
  role: "review",
  source: "plain",
  structure: "unavailable",
  kind: "log",
  text: "Проверяю тесты",
} as const;

export const ORCHESTRATION_STEP = {
  origin: "orchestration",
  seq: 3,
  observed_at: "2026-11-06T10:00:00+00:00",
  event: "dispatch.transition",
  batch_id: "batch-885",
  dispatch_id: "dispatch-dev",
  ticket: "#885",
  role: "developer",
  from_state: "dispatched",
  to_state: "working",
  decision: null,
  next_role: null,
  outcome: null,
  stage: null,
  message: "",
} as const;

export function rosterReply(id: unknown, reset = true, dispatches: unknown = ROSTER): Record<string, unknown> {
  return {
    v: 1,
    id,
    type: "steps.subscribe",
    ok: true,
    kind: "roster",
    reset,
    orchestration: "available",
    dispatches,
  };
}

export function stepsReply(id: unknown, steps: unknown[]): Record<string, unknown> {
  return { v: 1, id, type: "steps.subscribe", ok: true, kind: "steps", steps };
}

/* A health report as diagnostics.snapshot pages it (schema v1 of `harness health --json`). */
export const HEALTH_REPORT = {
  schema_version: 1,
  repo: "/work/project",
  online: false,
  summary: { ok: 2, warn: 1, fail: 1, skipped: 1 },
  checks: [
    { id: "files.lock", group: "files", status: "ok", message: "harness.lock на месте", fix: null },
    {
      id: "hooks.policy",
      group: "hooks",
      status: "fail",
      message: "Нет .harness/hook-policy.json",
      fix: { text: "Запустите обновление", command: "harness update ." },
    },
    {
      id: "environment.uv",
      group: "environment",
      status: "warn",
      message: "uv старше рекомендуемого",
      fix: { text: "Обновите uv", command: null },
    },
    { id: "tracker.online", group: "tracker", status: "skipped", message: "Онлайн-проверки не выполнялись", fix: null },
    { id: "directories.sandboxes", group: "directories", status: "ok", message: "Каталоги на месте", fix: null },
  ],
  fixes_applied: [],
};

/** The first page of a paged screen snapshot whose JSON text is `text`. */
export function screenPage(
  id: unknown,
  type: string,
  text: string,
  options: { snapshotId?: number; next?: number; done?: boolean; cached?: boolean; age?: number } = {},
): Record<string, unknown> {
  const done = options.done ?? true;
  return {
    v: 1,
    id,
    type,
    ok: true,
    snapshot_id: options.snapshotId ?? 7,
    text,
    next: options.next ?? text.length,
    done,
    cached: options.cached ?? false,
    age_seconds: options.age ?? 0,
  };
}

/** A further page of a snapshot (`snapshot.page`). */
export function nextPage(id: unknown, text: string, next: number, done: boolean): Record<string, unknown> {
  return { v: 1, id, type: "snapshot.page", ok: true, text, next, done };
}

/* The Harness facts as harness.overview and harness.maintenance send them. */
export const HARNESS_OVERVIEW = {
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
  drift: "drift",
  drift_files: 0,
  store: { authority: "file-ledger", schema: 3, generation: "generation-1", audit_records: 12, cutover_at: null, reason: "" },
  adapters: [{ path: ".harness/adapters/claude/settings.json", status: "current", problem: null }],
  // The sandbox has no Docker socket: every probe of the engine fails with its reason.
  containers: {
    engine: "docker",
    version: null,
    cgroup_driver: null,
    cgroup_version: null,
    selinux: null,
    rootless: null,
    info_problem: "docker info: код 1: Cannot connect to the Docker daemon",
    images: null,
    images_problem: "docker images: код 1",
    volumes: null,
    volumes_problem: "docker volume ls: код 1",
  },
  usage: { unavailable: null, batches: 4, tickets: 3, dispatches: 12, reports: 9 },
};

const cleanupSummary = (mode: string, digest: string, bytes: number) => ({
  plan: {
    mode,
    root: "/work/project/.harness",
    min_age_hours: 24,
    remove: [{ kind: "directory", path: "/work/project/.harness/.sandboxes/runs/tests/old" }],
    skipped: [{ path: "/work/project/.harness/.sandboxes/runs/qa/new", reason: "active or newer than minimum age" }],
  },
  categories: { "runs/tests": { bytes, files: 3 } },
  total: { bytes, files: 3 },
  items: 1,
  digest,
});

export const MAINTENANCE = {
  maintenance: {
    soft: cleanupSummary("soft", "a".repeat(64), 2048),
    hard: cleanupSummary("hard", "b".repeat(64), 4096),
    worktrees: [
      { path: "/work/project/.harness/.sandboxes/worktrees/issue-1-done", branch: "feature/issue-1-done", dirty: 0, reason: "" },
      {
        path: "/work/project/.harness/.sandboxes/worktrees/issue-2-live",
        branch: "feature/issue-2-live",
        dirty: 3,
        reason: "worktree has uncommitted changes",
      },
    ],
    worktree_error: "",
    tree_sizes: [{ path: "/work/project/.harness/.sandboxes/worktrees/issue-1-done", size: { bytes: 1536, files: 4 } }],
  },
  error: "",
};

/** Answer the open harness.overview and harness.maintenance requests of `socket`. */
export function answerHarness(socket: FakeSocket, overview: unknown = HARNESS_OVERVIEW, maintenance: unknown = MAINTENANCE): void {
  for (const body of socket.sent.filter((sent) => sent.type === "harness.overview")) {
    socket.reply({ v: 1, id: body.id, type: "harness.overview", ok: true, cached: false, age_seconds: 0, ...(overview as object) });
  }
  for (const body of socket.sent.filter((sent) => sent.type === "harness.maintenance")) {
    socket.reply(screenPage(body.id, "harness.maintenance", JSON.stringify(maintenance)));
  }
}
