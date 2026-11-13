import { describe, expect, test } from "vitest";
import {
  INITIAL,
  STALE_ATTEMPTS,
  reduce,
} from "../../harness/console/frontend/src/connection";
import type { ConnectionState } from "../../harness/console/frontend/src/connection";
import type { ClientEvent } from "../../harness/console/frontend/src/ws/client";
import type { HomeSnapshot } from "../../harness/console/frontend/src/ws/types";
import { SNAPSHOT } from "./fake-socket";

const snapshot = SNAPSHOT as HomeSnapshot;
const emptySnapshot: HomeSnapshot = {
  ...snapshot,
  health: { ok: 0, warn: 0, fail: 0, skipped: 0 },
  problems: [],
  problems_total: 0,
};

const run = (events: ClientEvent[], from: ConnectionState = INITIAL) => events.reduce(reduce, from);
const got = (value: HomeSnapshot): ClientEvent => ({
  type: "snapshot",
  snapshot: value,
  cached: true,
  ageSeconds: 4,
});

describe("the connection state", () => {
  test("starts as reconnecting without a snapshot", () => {
    expect(INITIAL.status).toBe("reconnecting");
    expect(INITIAL.snapshot).toBeNull();
  });

  test("a valid snapshot is connected", () => {
    const state = run([{ type: "open" }, got(snapshot)]);
    expect(state).toMatchObject({ status: "connected", snapshot, cached: true, ageSeconds: 4, stale: false });
  });

  test("a valid snapshot without checks or problems is empty", () => {
    expect(run([got(emptySnapshot)]).status).toBe("empty");
  });

  test("a dropped open socket reconnects and keeps the stale snapshot", () => {
    const state = run([got(snapshot), { type: "closed", wasOpen: true, attempt: 1, delayMs: 500 }]);
    expect(state).toMatchObject({
      status: "reconnecting",
      snapshot,
      stale: true,
      attempt: 1,
      nextDelayMs: 500,
    });
    expect(run([got(snapshot)], state)).toMatchObject({ status: "connected", stale: false, attempt: 0 });
  });

  test("a socket that never opened and a dead /health/live is no server", () => {
    const state = run([
      { type: "closed", wasOpen: false, attempt: 1, delayMs: 500 },
      { type: "health", reachable: false },
    ]);
    expect(state).toMatchObject({ status: "no_server", attempt: 1, errorCode: null });
  });

  test("a socket that never opened while /health/live answers is a rejected session", () => {
    const state = run([
      { type: "closed", wasOpen: false, attempt: 1, delayMs: 500 },
      { type: "health", reachable: true },
    ]);
    expect(state).toMatchObject({ status: "error", errorCode: "session_rejected" });
  });

  test("a kept snapshot rides out a few failed attempts, then the probe decides", () => {
    let state = run([got(snapshot), { type: "closed", wasOpen: true, attempt: 1, delayMs: 500 }]);
    state = run([{ type: "closed", wasOpen: false, attempt: 2, delayMs: 1000 }, { type: "health", reachable: false }], state);
    expect(state).toMatchObject({ status: "reconnecting", stale: true });
    state = run(
      [{ type: "closed", wasOpen: false, attempt: STALE_ATTEMPTS, delayMs: 8000 }, { type: "health", reachable: false }],
      state,
    );
    expect(state).toMatchObject({ status: "no_server", snapshot });
  });

  test("an ok:false reply or an invalid snapshot is an error", () => {
    expect(run([{ type: "error", code: "busy", message: "" }])).toMatchObject({ status: "error", errorCode: "busy" });
    expect(run([got(snapshot), { type: "invalid" }])).toMatchObject({
      status: "error",
      errorCode: "invalid_snapshot",
      snapshot,
    });
  });

  test("orchestration replies and socket progress change nothing by themselves", () => {
    const state = run([got(snapshot)]);
    for (const event of [
      { type: "open" },
      { type: "connecting", attempt: 0 },
      { type: "source", cursor: null },
      { type: "events", cursor: "j-1", events: [] },
    ] satisfies ClientEvent[]) {
      expect(reduce(state, event)).toBe(state);
    }
  });
});

describe("the contour activity of the connection state", () => {
  const activity = {
    window_seconds: 300,
    links: [{ link: "typed" as const, events_per_minute: 1.2, last_event_age_seconds: 4.5 }],
    last_event_age_seconds: 4.5,
    events_total_window: 6,
  };

  test("a snapshot reply sets it and a reply without it clears it", () => {
    const withActivity = run([{ ...(got(snapshot) as object), activity } as ClientEvent]);
    expect(withActivity.activity).toEqual(activity);
    expect(run([got(snapshot)], withActivity).activity).toBeNull();
    expect(INITIAL.activity).toBeNull();
  });

  test("a dropped socket takes it away while the snapshot stays", () => {
    const live = run([{ ...(got(snapshot) as object), activity } as ClientEvent]);
    const dropped = run([{ type: "closed", wasOpen: true, attempt: 1, delayMs: 500 }], live);
    expect(dropped).toMatchObject({ activity: null, snapshot, stale: true });
  });
});
