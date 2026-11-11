import { beforeEach, expect, test } from "vitest";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import type { DecisionsEvent } from "../../harness/console/frontend/src/ws/decisions";
import { FakeSocket, ManualClock } from "./fake-socket";
import fixture from "./fixtures/decisions.json";

beforeEach(() => FakeSocket.reset());

function setup() {
  const clock = new ManualClock();
  const client = createConsoleClient({ url: "ws://127.0.0.1:1/ws", WebSocket: FakeSocket,
    timers: clock, probeHealth: async () => false });
  const events: DecisionsEvent[] = [];
  client.subscribeDecisions((event) => events.push(event));
  client.start();
  FakeSocket.last.open();
  return { clock, client, events, socket: FakeSocket.last };
}

test("polling coalesces a pending read instead of replacing it with overlapping reads", () => {
  const { client, events, socket } = setup();
  client.requestDecisions();
  client.requestDecisions();
  expect(socket.sent.filter((body) => body.type === "decisions.snapshot")).toHaveLength(1);
  socket.reply({ v: 1, id: socket.request("decisions.snapshot").id, type: "decisions.snapshot", ok: true, snapshot: fixture.snapshot });
  expect(events).toEqual([{ type: "decisions", snapshot: fixture.snapshot }]);
  client.requestDecisions();
  expect(socket.sent.filter((body) => body.type === "decisions.snapshot")).toHaveLength(2);
});

test.each([
  { ...fixture.snapshot, version: 2 },
  { ...fixture.snapshot, total: -1 },
  { ...fixture.snapshot, items: [{ ...fixture.snapshot.items[0], values: { batch: 7 } }] },
])("a malformed snapshot reports a typed error", (snapshot) => {
  const { client, events, socket } = setup();
  client.requestDecisions();
  socket.reply({ v: 1, id: socket.request("decisions.snapshot").id, type: "decisions.snapshot", ok: true, snapshot });
  expect(events).toEqual([{ type: "decisions-error", code: "invalid" }]);
});

test("a reply of a dropped connection cannot replace the fresh decision context", () => {
  const { client, events, socket, clock } = setup();
  client.requestDecisions();
  const old = socket.request("decisions.snapshot");
  socket.close();
  clock.advance(500);
  const next = FakeSocket.last;
  next.open();
  client.requestDecisions();
  next.reply({ v: 1, id: old.id, type: "decisions.snapshot", ok: true, snapshot: fixture.snapshot });
  expect(events).toEqual([]);
  next.reply({ v: 1, id: next.request("decisions.snapshot").id, type: "decisions.snapshot", ok: true,
    snapshot: { version: 1, items: [], total: 0, unavailable: true } });
  expect(events).toEqual([{ type: "decisions", snapshot: { version: 1, items: [], total: 0, unavailable: true } }]);
});
