/* The connection state the shell shows, as a pure reducer over client events. */
import type { ClientEvent } from "./ws/client";
import type { HomeSnapshot } from "./ws/types";
import { healthTotal } from "./ws/types";

export type ConnectionStatus = "connected" | "reconnecting" | "no_server" | "error" | "empty";

/** After this many failed attempts a kept snapshot no longer hides a dead server. */
export const STALE_ATTEMPTS = 5;

export interface ConnectionState {
  status: ConnectionStatus;
  /** Failed attempts since the last open socket. */
  attempt: number;
  /** Delay before the next attempt, in milliseconds. */
  nextDelayMs: number;
  /** The last valid snapshot; kept while reconnecting and marked stale. */
  snapshot: HomeSnapshot | null;
  cached: boolean;
  ageSeconds: number | null;
  stale: boolean;
  /** Why the state is `error`: a server error code, `invalid_snapshot` or `session_rejected`. */
  errorCode: string | null;
}

export const INITIAL: ConnectionState = {
  status: "reconnecting",
  attempt: 0,
  nextDelayMs: 0,
  snapshot: null,
  cached: false,
  ageSeconds: null,
  stale: false,
  errorCode: null,
};

/** A valid snapshot without any check and without problems: nothing to show, not a failure. */
export const isEmpty = (snapshot: HomeSnapshot): boolean =>
  healthTotal(snapshot.health) === 0 && snapshot.problems_total === 0;

export function reduce(state: ConnectionState, event: ClientEvent): ConnectionState {
  switch (event.type) {
    case "snapshot":
      return {
        ...state,
        status: isEmpty(event.snapshot) ? "empty" : "connected",
        attempt: 0,
        nextDelayMs: 0,
        snapshot: event.snapshot,
        cached: event.cached,
        ageSeconds: event.ageSeconds,
        stale: false,
        errorCode: null,
      };
    case "closed":
      return {
        ...state,
        // A socket that was open dropped: keep the snapshot and reconnect.
        status: event.wasOpen ? "reconnecting" : state.status,
        attempt: event.attempt,
        nextDelayMs: event.delayMs,
        stale: state.snapshot !== null,
      };
    case "health": {
      // A socket never opened. With a recent snapshot keep reconnecting for a few attempts.
      if (state.snapshot !== null && state.attempt < STALE_ATTEMPTS) {
        return { ...state, status: "reconnecting" };
      }
      return event.reachable
        ? { ...state, status: "error", errorCode: "session_rejected" }
        : { ...state, status: "no_server", errorCode: null };
    }
    case "invalid":
      return { ...state, status: "error", errorCode: "invalid_snapshot" };
    case "error":
      return { ...state, status: "error", errorCode: event.code };
    case "open":
    case "connecting":
    case "events":
    case "source":
      return state;
  }
}
