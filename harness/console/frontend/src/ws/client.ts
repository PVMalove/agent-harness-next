/* One WebSocket to the console server with reconnects, an orchestration cursor, the cursors
   of the followed jobs and the one live step feed. Every effect (socket, timers, the /health/live probe) is injected, so
   tests drive it deterministically. */
import { mergeOutput, parseCommands, parseJobSnapshot, parseJobSummary } from "./jobs";
import type { CommandDescriptor, JobSummary, LocalJob } from "./jobs";
import type {
  ErrorReply,
  HomeSnapshotReply,
  HomeSnapshotRequest,
  JobCancelRequest,
  JobCatalogRequest,
  JobStartRequest,
  JobSubscribeRequest,
  OrchestrationEventsReply,
  OrchestrationSourceReply,
  OrchestrationSubscribeRequest,
  StepsSubscribeRequest,
} from "./protocol.gen";
import { parseStepsReply } from "./steps";
import type { StepsEvent } from "./steps";
import { parseHomeSnapshot } from "./types";
import type { HomeSnapshot } from "./types";
import { repoMapReader } from "./repoMap";
import type { RepoMapEvent } from "./repoMap";

export const FIRST_DELAY_MS = 500;
export const MAX_DELAY_MS = 8000;
export const REQUEST_TIMEOUT_MS = 30000;

/** The part of the browser WebSocket the client uses. */
export interface SocketLike {
  readonly readyState: number;
  onopen: ((event: unknown) => void) | null;
  onmessage: ((event: { data: unknown }) => void) | null;
  onclose: ((event: unknown) => void) | null;
  onerror: ((event: unknown) => void) | null;
  send(data: string): void;
  close(): void;
}

export type SocketFactory = new (url: string) => SocketLike;

export interface Timers {
  setTimeout(callback: () => void, ms: number): unknown;
  clearTimeout(handle: unknown): void;
}

export type ClientEvent =
  | { type: "connecting"; attempt: number }
  | { type: "open" }
  | { type: "closed"; wasOpen: boolean; attempt: number; delayMs: number }
  | { type: "health"; reachable: boolean }
  | { type: "snapshot"; snapshot: HomeSnapshot; cached: boolean; ageSeconds: number }
  | { type: "invalid" }
  | { type: "error"; code: string; message: string }
  | { type: "events"; cursor: string; events: unknown[] }
  | { type: "source"; cursor: string | null };

export type JobRequestType = "job.catalog" | "job.list" | "job.start" | "job.cancel" | "job.subscribe";

/** What the job requests bring: a section's commands, the job list, a followed job with its
    merged output, or a refusal with its code (and the running job of `busy`). */
export type JobEvent =
  | { type: "commands"; section: string; commands: CommandDescriptor[]; cancelReason: string }
  | { type: "jobs"; jobs: JobSummary[] }
  | { type: "job"; job: LocalJob }
  | { type: "job-error"; request: JobRequestType; code: string; message: string; jobId: string | null };

export interface StartJob {
  command_id: string;
  values?: Record<string, string>;
  confirmed?: boolean;
  /** The typed word of a command whose description asks for one; the server checks it. */
  confirmation?: string;
}

export interface ClientOptions {
  url: string;
  WebSocket: SocketFactory;
  timers: Timers;
  /** True when GET /health/live answered at all, false on a network failure. */
  probeHealth: () => Promise<boolean>;
  requestTimeoutMs?: number;
}

export interface HomeRequest {
  force?: boolean;
  online?: boolean;
}

export interface ConsoleClient {
  requestRepoMap(force?: boolean): boolean;
  subscribeRepoMap(listener: (event: RepoMapEvent) => void): () => void;
  start(): void;
  stop(): void;
  /** Reconnect now instead of waiting for the backoff timer. */
  retryNow(): void;
  /** Ask for the Home snapshot; false when no socket is open. */
  requestHome(request?: HomeRequest): boolean;
  subscribe(listener: (event: ClientEvent) => void): () => void;
  /** The cursor of the last received orchestration reply. */
  readonly cursor: string | null;
  /** Ask for the catalog commands of a console section; false when no socket is open. */
  requestCommands(section: JobCatalogRequest["section"]): boolean;
  /** Ask for the job summaries; asked again after every reconnect once asked. */
  listJobs(): boolean;
  /** Start a catalog command as the browser; its output is then followed. */
  startJob(request: StartJob): boolean;
  /** Ask to cancel a job; the server refuses without `confirmed`. */
  cancelJob(jobId: string, confirmed: boolean): boolean;
  /** Follow a job's output from the held cursor, again after every reconnect until it is done. */
  followJob(jobId: string): boolean;
  /** The held copy of a followed job. */
  job(jobId: string): LocalJob | undefined;
  subscribeJobs(listener: (event: JobEvent) => void): () => void;
  /** Follow the live step feed: one steps.subscribe per connection, sent again after a
      reconnect; a second call on the same connection sends nothing. */
  followSteps(): boolean;
  subscribeSteps(listener: (event: StepsEvent) => void): () => void;
}

const OPEN = 1;

/** 0.5 s doubling to 8 s: the delay before reconnect attempt `attempt` (1-based). */
export const backoff = (attempt: number): number =>
  Math.min(MAX_DELAY_MS, FIRST_DELAY_MS * 2 ** Math.max(0, attempt - 1));

const isObject = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);

export function createConsoleClient(options: ClientOptions): ConsoleClient {
  const { url, timers, probeHealth } = options;
  const timeoutMs = options.requestTimeoutMs ?? REQUEST_TIMEOUT_MS;
  const listeners = new Set<(event: ClientEvent) => void>();
  const jobListeners = new Set<(event: JobEvent) => void>();
  const mapListeners = new Set<(event: RepoMapEvent) => void>();
  // The followed jobs by id: the held output and cursor survive reconnects.
  const followed = new Map<string, LocalJob | null>();
  // Open job requests of the current socket by request id.
  const jobRequests = new Map<string, { type: JobRequestType; key: string }>();
  let jobsWanted = false;
  const stepListeners = new Set<(event: StepsEvent) => void>();
  let stepsWanted = false;
  let stepsSubscription: string | null = null;
  const pending = new Map<string, unknown>();
  let socket: SocketLike | null = null;
  let generation = 0;
  let sequence = 0;
  let attempt = 0;
  let stopped = true;
  let reconnectTimer: unknown = null;
  let cursor: string | null = null;
  let subscription: string | null = null;
  let latestHome: string | null = null;

  const emit = (event: ClientEvent) => {
    for (const listener of [...listeners]) listener(event);
  };

  const emitJob = (event: JobEvent) => {
    for (const listener of [...jobListeners]) listener(event);
  };

  const emitSteps = (event: StepsEvent) => {
    for (const listener of [...stepListeners]) listener(event);
  };

  const subscribeSteps = (): boolean => {
    if (stepsSubscription !== null) return true;
    const request: StepsSubscribeRequest = { type: "steps.subscribe" };
    stepsSubscription = send({ ...request });
    return stepsSubscription !== null;
  };

  const clearPending = () => {
    for (const timer of pending.values()) timers.clearTimeout(timer);
    pending.clear();
    jobRequests.clear();
  };

  const send = (body: Record<string, unknown>): string | null => {
    if (!socket || socket.readyState !== OPEN) return null;
    const id = `${generation}-${++sequence}`;
    const current = socket;
    pending.set(
      id,
      timers.setTimeout(() => current.close(), timeoutMs),
    );
    current.send(JSON.stringify({ id, ...body }));
    return id;
  };

  const settle = (id: string) => {
    const timer = pending.get(id);
    if (timer !== undefined) timers.clearTimeout(timer);
    pending.delete(id);
  };

  const mapReader = repoMapReader(send, settle, (event) => {
    for (const listener of [...mapListeners]) listener(event);
  });

  const subscribeOrchestration = () => {
    const request: OrchestrationSubscribeRequest =
      cursor === null
        ? { type: "orchestration.subscribe" }
        : { type: "orchestration.subscribe", cursor };
    subscription = send({ ...request });
  };

  const requestHome = (request: HomeRequest = {}): boolean => {
    const body: HomeSnapshotRequest = {
      type: "home.snapshot",
      force: request.force ?? false,
      online: request.online ?? false,
    };
    const id = send({ ...body });
    if (id === null) return false;
    if (latestHome !== null) settle(latestHome);
    latestHome = id;
    return true;
  };

  const sendJob = (type: JobRequestType, key: string, body: Record<string, unknown>): boolean => {
    const id = send({ type, ...body });
    if (id === null) return false;
    jobRequests.set(id, { type, key });
    return true;
  };

  const subscribeJob = (jobId: string): boolean => {
    for (const [id, open] of jobRequests) {
      if (open.type === "job.subscribe" && open.key === jobId) {
        settle(id);
        jobRequests.delete(id);
      }
    }
    const request: JobSubscribeRequest = {
      type: "job.subscribe",
      job_id: jobId,
      cursor: followed.get(jobId)?.cursor ?? 0,
    };
    return sendJob("job.subscribe", jobId, { ...request });
  };

  /** Merge a job snapshot into the followed copy; a gap resubscribes from the held cursor. */
  const onJob = (value: unknown, request: JobRequestType, follow: boolean) => {
    const snapshot = parseJobSnapshot(value);
    if (!snapshot) {
      emitJob({ type: "job-error", request, code: "invalid", message: "", jobId: null });
      return;
    }
    if (!followed.has(snapshot.id)) followed.set(snapshot.id, null);
    const { job, gap } = mergeOutput(followed.get(snapshot.id) ?? null, snapshot);
    followed.set(snapshot.id, job);
    emitJob({ type: "job", job });
    if (gap || (follow && !job.done)) subscribeJob(snapshot.id);
  };

  const onJobReply = (id: string, reply: Record<string, unknown>) => {
    const open = jobRequests.get(id);
    if (!open || reply.type !== open.type) return;
    // A subscription streams on one id: its first reply clears the timeout, the stream stays.
    settle(id);
    if (reply.ok !== true) {
      jobRequests.delete(id);
      const error = (reply as unknown as ErrorReply).error;
      const code = error?.code ?? "unknown";
      if (open.type === "job.subscribe" && code === "unknown_job") followed.delete(open.key);
      emitJob({
        type: "job-error",
        request: open.type,
        code,
        message: error?.message ?? "",
        jobId: error?.job_id ?? (open.type === "job.subscribe" || open.type === "job.cancel" ? open.key : null),
      });
      return;
    }
    if (open.type !== "job.subscribe") jobRequests.delete(id);
    if (open.type === "job.catalog") {
      const commands = parseCommands(reply.commands);
      const cancelReason = reply.cancel_reason;
      if (commands && typeof cancelReason === "string") {
        emitJob({ type: "commands", section: open.key, commands, cancelReason });
      } else emitJob({ type: "job-error", request: open.type, code: "invalid", message: "", jobId: null });
    } else if (open.type === "job.list") {
      const jobs = Array.isArray(reply.jobs) ? reply.jobs.map(parseJobSummary) : null;
      if (jobs && jobs.every((job) => job !== null)) emitJob({ type: "jobs", jobs: jobs as JobSummary[] });
      else emitJob({ type: "job-error", request: open.type, code: "invalid", message: "", jobId: null });
    } else if (open.type === "job.subscribe") {
      onJob(reply.job, open.type, false);
      // The stream of a finished job ends; a gap already replaced it with a new subscription.
      if (followed.get(open.key)?.done) jobRequests.delete(id);
    } else {
      onJob(reply.job, open.type, true);
    }
  };

  const onReply = (reply: Record<string, unknown>) => {
    const id = reply.id;
    if (typeof id !== "string" || !id.startsWith(`${generation}-`)) return;
    if (mapReader.reply(reply)) return;
    if (jobRequests.has(id)) {
      onJobReply(id, reply);
      return;
    }
    if (reply.type === "home.snapshot") {
      if (id !== latestHome) return;
      settle(id);
      latestHome = null;
      if (reply.ok === true) {
        const ok = reply as unknown as HomeSnapshotReply;
        const snapshot = parseHomeSnapshot(ok.snapshot);
        if (snapshot && typeof ok.cached === "boolean" && typeof ok.age_seconds === "number") {
          emit({ type: "snapshot", snapshot, cached: ok.cached, ageSeconds: ok.age_seconds });
        } else {
          emit({ type: "invalid" });
        }
      } else {
        const error = (reply as unknown as ErrorReply).error;
        emit({ type: "error", code: error?.code ?? "unknown", message: error?.message ?? "" });
      }
      return;
    }
    if (reply.type === "steps.subscribe" && id === stepsSubscription) {
      // The stream stays on its id: its first reply clears the timeout.
      settle(id);
      if (reply.ok !== true) {
        stepsSubscription = null;
        const error = (reply as unknown as ErrorReply).error;
        emitSteps({ type: "steps-error", code: error?.code ?? "unknown", message: error?.message ?? "" });
        return;
      }
      const event = parseStepsReply(reply);
      emitSteps(event ?? { type: "steps-error", code: "invalid", message: "" });
      return;
    }
    if (reply.type === "orchestration.subscribe" && id === subscription) {
      settle(id);
      if (reply.ok !== true) {
        const error = (reply as unknown as ErrorReply).error;
        if (error?.code === "cursor_expired") {
          // The journal no longer holds our position: restart from the head, refetch Home.
          cursor = null;
          subscribeOrchestration();
          requestHome();
        } else {
          emit({ type: "error", code: error?.code ?? "unknown", message: error?.message ?? "" });
        }
        return;
      }
      if (reply.kind === "events") {
        const events = reply as unknown as OrchestrationEventsReply;
        cursor = events.cursor;
        emit({
          type: "events",
          cursor: events.cursor,
          events: Array.isArray(events.events) ? events.events : [],
        });
      } else if (reply.kind === "source") {
        const source = reply as unknown as OrchestrationSourceReply;
        if (source.cursor !== null) cursor = source.cursor;
        emit({ type: "source", cursor: source.cursor });
      }
    }
  };

  const scheduleReconnect = () => {
    timers.clearTimeout(reconnectTimer);
    reconnectTimer = timers.setTimeout(connect, backoff(attempt));
  };

  function connect() {
    if (stopped) return;
    timers.clearTimeout(reconnectTimer);
    reconnectTimer = null;
    clearPending();
    mapReader.reset();
    latestHome = null;
    subscription = null;
    stepsSubscription = null;
    const current = ++generation;
    sequence = 0;
    const previous = socket;
    const next = new options.WebSocket(url);
    socket = next;
    if (previous) previous.close();
    let wasOpen = false;
    emit({ type: "connecting", attempt });
    next.onopen = () => {
      if (current !== generation || stopped) return;
      wasOpen = true;
      attempt = 0;
      emit({ type: "open" });
      subscribeOrchestration();
      requestHome();
      for (const [jobId, job] of followed) if (!job?.done) subscribeJob(jobId);
      if (jobsWanted) sendJob("job.list", "", {});
      if (stepsWanted) subscribeSteps();
    };
    next.onmessage = (event) => {
      if (current !== generation || stopped) return;
      let reply: unknown;
      try {
        reply = JSON.parse(String(event.data));
      } catch {
        return;
      }
      if (isObject(reply)) onReply(reply);
    };
    next.onerror = () => next.close();
    next.onclose = () => {
      if (current !== generation || stopped) return;
      clearPending();
      mapReader.reset();
      socket = null;
      stepsSubscription = null;
      attempt += 1;
      emit({ type: "closed", wasOpen, attempt, delayMs: backoff(attempt) });
      scheduleReconnect();
      if (!wasOpen) {
        void probeHealth().then(
          (reachable) => {
            if (current === generation && !stopped) emit({ type: "health", reachable });
          },
          () => {
            if (current === generation && !stopped) emit({ type: "health", reachable: false });
          },
        );
      }
    };
  }

  return {
    requestRepoMap: mapReader.request,
    subscribeRepoMap(listener) {
      mapListeners.add(listener);
      return () => mapListeners.delete(listener);
    },
    start() {
      if (!stopped) return;
      stopped = false;
      connect();
    },
    stop() {
      stopped = true;
      generation += 1;
      timers.clearTimeout(reconnectTimer);
      clearPending();
      socket?.close();
      socket = null;
    },
    retryNow() {
      if (stopped) return;
      connect();
    },
    requestHome,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    get cursor() {
      return cursor;
    },
    requestCommands(section) {
      const request: JobCatalogRequest = { type: "job.catalog", section };
      return sendJob("job.catalog", section, { ...request });
    },
    listJobs() {
      jobsWanted = true;
      return sendJob("job.list", "", {});
    },
    startJob(request) {
      const body: JobStartRequest = {
        type: "job.start",
        command_id: request.command_id,
        values: request.values ?? {},
        confirmed: request.confirmed ?? false,
        ...(request.confirmation === undefined ? {} : { confirmation: request.confirmation }),
        client: "browser",
      };
      return sendJob("job.start", request.command_id, { ...body });
    },
    cancelJob(jobId, confirmed) {
      const body: JobCancelRequest = { type: "job.cancel", job_id: jobId, confirmed };
      return sendJob("job.cancel", jobId, { ...body });
    },
    followJob(jobId) {
      if (!followed.has(jobId)) followed.set(jobId, null);
      const held = followed.get(jobId);
      if (held?.done) {
        emitJob({ type: "job", job: held });
        return true;
      }
      return subscribeJob(jobId);
    },
    job(jobId) {
      return followed.get(jobId) ?? undefined;
    },
    subscribeJobs(listener) {
      jobListeners.add(listener);
      return () => jobListeners.delete(listener);
    },
    followSteps() {
      stepsWanted = true;
      return subscribeSteps();
    },
    subscribeSteps(listener) {
      stepListeners.add(listener);
      return () => stepListeners.delete(listener);
    },
  };
}

