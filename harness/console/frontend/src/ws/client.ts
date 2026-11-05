/* One WebSocket to the console server with reconnects and an orchestration cursor. Every effect
   (socket, timers, the /health/live probe) is injected, so tests drive it deterministically. */
import type {
  ErrorReply,
  HomeSnapshotReply,
  HomeSnapshotRequest,
  OrchestrationEventsReply,
  OrchestrationSourceReply,
  OrchestrationSubscribeRequest,
} from "./protocol.gen";
import { parseHomeSnapshot } from "./types";
import type { HomeSnapshot } from "./types";

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
  start(): void;
  stop(): void;
  /** Reconnect now instead of waiting for the backoff timer. */
  retryNow(): void;
  /** Ask for the Home snapshot; false when no socket is open. */
  requestHome(request?: HomeRequest): boolean;
  subscribe(listener: (event: ClientEvent) => void): () => void;
  /** The cursor of the last received orchestration reply. */
  readonly cursor: string | null;
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

  const clearPending = () => {
    for (const timer of pending.values()) timers.clearTimeout(timer);
    pending.clear();
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

  const onReply = (reply: Record<string, unknown>) => {
    const id = reply.id;
    if (typeof id !== "string" || !id.startsWith(`${generation}-`)) return;
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
    latestHome = null;
    subscription = null;
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
      socket = null;
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
  };
}

