import { beforeEach, describe, expect, test } from "vitest";
import { backoff, createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import type { ClientEvent } from "../../harness/console/frontend/src/ws/client";
import { FakeSocket, ManualClock, SNAPSHOT, snapshotReply } from "./fake-socket";

function setup(probe: () => Promise<boolean> = async () => false) {
  const clock = new ManualClock();
  const events: ClientEvent[] = [];
  const client = createConsoleClient({
    url: "ws://127.0.0.1:4242/ws",
    WebSocket: FakeSocket,
    timers: clock,
    probeHealth: probe,
  });
  client.subscribe((event) => events.push(event));
  client.start();
  return { clock, events, client };
}

const types = (events: ClientEvent[]) => events.map((event) => event.type);

describe("the console client", () => {
  beforeEach(() => FakeSocket.reset());

  test("subscribes without a cursor, then asks for Home with generation ids", () => {
    const { events } = setup();
    const socket = FakeSocket.last;
    expect(socket.url).toBe("ws://127.0.0.1:4242/ws");
    socket.open();
    expect(socket.sent).toEqual([
      { id: "1-1", type: "orchestration.subscribe" },
      { id: "1-2", type: "home.snapshot", force: false, online: false },
    ]);
    socket.reply(snapshotReply("1-2"));
    expect(events.at(-1)).toEqual({
      type: "snapshot",
      snapshot: SNAPSHOT,
      cached: false,
      ageSeconds: 0,
      activity: null,
    });
  });

  test("a reply with the contour activity passes it on; a malformed one is dropped, not the snapshot", () => {
    const { events, client } = setup();
    const socket = FakeSocket.last;
    socket.open();
    const activity = {
      window_seconds: 300,
      events_per_minute: 1.2,
      links: [{ link: "typed", events_per_minute: 1.2, last_event_age_seconds: 4.5 }],
      last_event_age_seconds: 4.5,
      events_total_window: 6,
    };
    socket.reply({ ...snapshotReply("1-2"), activity });
    expect(events.at(-1)).toMatchObject({ type: "snapshot", activity });
    expect(client.requestHome({ force: true })).toBe(true);
    socket.reply({ ...snapshotReply("1-3"), activity: { ...activity, links: "x" } });
    expect(events.at(-1)).toMatchObject({ type: "snapshot", activity: null });
  });

  test("reconnects with a backoff of 0.5 s doubling to 8 s", () => {
    const { clock, events } = setup();
    FakeSocket.last.open();
    const delays: number[] = [];
    for (let attempt = 1; attempt <= 6; attempt += 1) {
      FakeSocket.last.close();
      const closed = events.at(-1);
      expect(closed?.type).toBe("closed");
      delays.push(clock.pending()[0]!);
      clock.advance(clock.pending()[0]!);
    }
    expect(delays).toEqual([500, 1000, 2000, 4000, 8000, 8000]);
    expect([1, 2, 5, 9].map(backoff)).toEqual([500, 1000, 8000, 8000]);
    expect(FakeSocket.instances).toHaveLength(7);
  });

  test("an open socket resets the backoff", () => {
    const { clock } = setup();
    FakeSocket.last.close();
    clock.advance(500);
    FakeSocket.last.close();
    expect(clock.pending()).toEqual([1000]);
    clock.advance(1000);
    FakeSocket.last.open();
    FakeSocket.last.close();
    expect(clock.pending()).toEqual([500]);
  });

  test("resubscribes from the last cursor after a reconnect; missed events arrive once", () => {
    const { clock, events } = setup();
    const first = FakeSocket.last;
    first.open();
    first.reply({ v: 1, id: "1-1", type: "orchestration.subscribe", ok: true, kind: "source", cursor: "j-3", source: {} });
    first.reply({ v: 1, id: "1-1", type: "orchestration.subscribe", ok: true, kind: "events", cursor: "j-5", events: [{ n: 4 }, { n: 5 }] });
    first.close();
    clock.advance(500);
    const second = FakeSocket.last;
    second.open();
    expect(second.request("orchestration.subscribe")).toEqual({
      id: "2-1",
      type: "orchestration.subscribe",
      cursor: "j-5",
    });
    second.reply({ v: 1, id: "2-1", type: "orchestration.subscribe", ok: true, kind: "events", cursor: "j-7", events: [{ n: 6 }, { n: 7 }] });
    const received = events.flatMap((event) => (event.type === "events" ? event.events : []));
    expect(received).toEqual([{ n: 4 }, { n: 5 }, { n: 6 }, { n: 7 }]);
  });

  test("cursor_expired resubscribes from the head and asks for a fresh Home", () => {
    const { clock, client } = setup();
    FakeSocket.last.open();
    FakeSocket.last.reply({ v: 1, id: "1-1", type: "orchestration.subscribe", ok: true, kind: "events", cursor: "j-9", events: [{}] });
    FakeSocket.last.close();
    clock.advance(500);
    const socket = FakeSocket.last;
    socket.open();
    const resume = socket.request("orchestration.subscribe");
    expect(resume.cursor).toBe("j-9");
    socket.reply({ v: 1, id: resume.id, type: "orchestration.subscribe", ok: false, error: { code: "cursor_expired", message: "gone" } });
    expect(client.cursor).toBeNull();
    const fresh = socket.sent.slice(2);
    expect(fresh).toEqual([
      { id: "2-3", type: "orchestration.subscribe" },
      { id: "2-4", type: "home.snapshot", force: false, online: false },
    ]);
  });

  test("a reply of an older socket generation or an older request is dropped", () => {
    const { clock, events, client } = setup();
    const first = FakeSocket.last;
    first.open();
    first.close();
    clock.advance(500);
    const second = FakeSocket.last;
    second.open();
    first.onmessage?.({ data: JSON.stringify(snapshotReply("2-2")) });
    second.reply(snapshotReply("1-2"));
    expect(client.requestHome({ force: true })).toBe(true);
    second.reply(snapshotReply("2-2"));
    expect(types(events)).not.toContain("snapshot");
    second.reply(snapshotReply("2-3"));
    expect(types(events).filter((type) => type === "snapshot")).toHaveLength(1);
    expect(second.request("home.snapshot")).toEqual({ id: "2-3", type: "home.snapshot", force: true, online: false });
  });

  test("an unanswered request times out by closing the socket", () => {
    const { clock, events } = setup();
    const socket = FakeSocket.last;
    socket.open();
    socket.reply({ v: 1, id: "1-1", type: "orchestration.subscribe", ok: true, kind: "source", cursor: null, source: null });
    clock.advance(29999);
    expect(socket.readyState).toBe(1);
    clock.advance(1);
    expect(socket.readyState).toBe(3);
    expect(events.at(-1)).toEqual({ type: "closed", wasOpen: true, attempt: 1, delayMs: 500 });
  });

  test("an ok:false reply and an invalid snapshot are reported", () => {
    const { events, client } = setup();
    const socket = FakeSocket.last;
    socket.open();
    socket.reply({ v: 1, id: "1-2", type: "home.snapshot", ok: false, error: { code: "busy", message: "later" } });
    expect(events.at(-1)).toEqual({ type: "error", code: "busy", message: "later" });
    client.requestHome();
    socket.reply(snapshotReply("1-3", { ...SNAPSHOT, active_batches: "0" }));
    expect(events.at(-1)).toEqual({ type: "invalid" });
  });

  test("a socket that never opened probes /health/live", async () => {
    const { events } = setup(async () => true);
    FakeSocket.last.close();
    await Promise.resolve();
    await Promise.resolve();
    expect(events.slice(-2)).toEqual([
      { type: "closed", wasOpen: false, attempt: 1, delayMs: 500 },
      { type: "health", reachable: true },
    ]);
  });

  test("stop closes the socket and cancels the reconnect", () => {
    const { clock, client } = setup();
    FakeSocket.last.open();
    client.stop();
    expect(FakeSocket.last.readyState).toBe(3);
    clock.advance(60000);
    expect(FakeSocket.instances).toHaveLength(1);
  });
});
