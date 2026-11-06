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
  version: 1,
  health: { ok: 3, warn: 1, fail: 1, skipped: 2 },
  problems: [
    { status: "fail", id: "skills.drift", message: "Skill drift" },
    { status: "warn", id: "hooks", message: "Hook missing" },
  ],
  problems_total: 2,
  harness_version: "2.0.0",
  drift: "clean",
  active_batches: null,
  repo_map: { tier: null, message: "no cache", head_map: null },
  memory: { state: null, policy: null },
};

export function snapshotReply(id: unknown, snapshot: unknown = SNAPSHOT): Record<string, unknown> {
  return { v: 1, id, type: "home.snapshot", ok: true, cached: false, age_seconds: 0, snapshot };
}

/* Job catalog descriptions as job.catalog sends them (tests/web/fixtures/job-catalog.json for
   the Playwright mock). */
export const COMMANDS = [
  {
    command_id: "diff",
    title: "Дрейф управляемых файлов",
    section: "harness",
    reversibility: "reversible",
    needs_confirmation: false,
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
    needs_confirmation: true,
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
