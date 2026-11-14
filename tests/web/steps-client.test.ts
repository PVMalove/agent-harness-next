import { beforeEach, describe, expect, test } from "vitest";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import {
  EMPTY_STEPS,
  EVENT_LABELS,
  MAX_STEPS,
  STRUCTURE_LABELS,
  eventText,
  filterSteps,
  parseStepsReply,
  reduceSteps,
  rosterRoles,
} from "../../harness/console/frontend/src/ws/steps";
import type { OrchestrationStep, StepsEvent } from "../../harness/console/frontend/src/ws/steps";
import catalog from "../../harness/console/frontend/src/i18n/catalog.json";
import { translate } from "../../harness/console/frontend/src/i18n";
import {
  AGENT_STEP,
  CODEX_STEP,
  FakeSocket,
  ManualClock,
  ORCHESTRATION_STEP,
  ROSTER,
  rosterReply,
  stepsReply,
} from "./fake-socket";

function setup() {
  const clock = new ManualClock();
  const events: StepsEvent[] = [];
  const client = createConsoleClient({
    url: "ws://127.0.0.1:4242/ws",
    WebSocket: FakeSocket,
    timers: clock,
    probeHealth: async () => false,
  });
  client.subscribeSteps((event) => events.push(event));
  client.start();
  FakeSocket.last.open();
  return { clock, events, client };
}

const stepRequests = (socket: FakeSocket) => socket.sent.filter((body) => body.type === "steps.subscribe");

beforeEach(() => FakeSocket.reset());

describe("the step feed of the client", () => {
  test("one steps.subscribe per connection, sent again after a reconnect", () => {
    const { clock, events, client } = setup();
    const first = FakeSocket.last;
    expect(stepRequests(first)).toEqual([]);
    expect(client.followSteps()).toBe(true);
    expect(client.followSteps()).toBe(true);
    expect(stepRequests(first)).toHaveLength(1);
    const id = first.request("steps.subscribe").id;
    expect(first.request("steps.subscribe")).toEqual({ id, type: "steps.subscribe" });
    first.reply(rosterReply(id));
    first.reply(stepsReply(id, [ORCHESTRATION_STEP, AGENT_STEP]));
    expect(events.map((event) => event.type)).toEqual(["roster", "steps"]);

    first.close();
    clock.advance(10000);
    const second = FakeSocket.last;
    expect(second).not.toBe(first);
    second.open();
    expect(stepRequests(second)).toHaveLength(1);
    // A reply on the old id of the closed connection is ignored.
    second.reply(stepsReply(id, [AGENT_STEP]));
    expect(events).toHaveLength(2);
  });

  test("a refusal frees the slot and a malformed step is refused as a whole", () => {
    const { events, client } = setup();
    client.followSteps();
    const socket = FakeSocket.last;
    const id = socket.request("steps.subscribe").id;
    socket.reply(stepsReply(id, [{ ...AGENT_STEP, thinking: "secret" }]));
    socket.reply(stepsReply(id, [{ ...AGENT_STEP, input: { path: "x" } }]));
    expect(events).toEqual([
      { type: "steps-error", code: "invalid", message: "" },
      { type: "steps-error", code: "invalid", message: "" },
    ]);
    socket.reply({ v: 1, id, type: "steps.subscribe", ok: false, error: { code: "busy", message: "Busy" } });
    expect(events.at(-1)).toEqual({ type: "steps-error", code: "busy", message: "Busy" });
    client.followSteps();
    expect(stepRequests(socket)).toHaveLength(2);
  });
});

describe("the steps reducer", () => {
  const roster = parseStepsReply(rosterReply(1)) as StepsEvent;
  const steps = parseStepsReply(stepsReply(1, [ORCHESTRATION_STEP, AGENT_STEP, CODEX_STEP])) as StepsEvent;

  test("a reset roster drops the held steps, a plain roster keeps them", () => {
    let state = reduceSteps(reduceSteps(EMPTY_STEPS, roster), steps);
    expect(state.steps.map((held) => held.step)).toEqual([ORCHESTRATION_STEP, AGENT_STEP, CODEX_STEP]);
    expect(state.orchestration).toBe("available");
    state = reduceSteps(state, parseStepsReply(rosterReply(1, false, ROSTER.slice(0, 1))) as StepsEvent);
    expect(state.steps).toHaveLength(3);
    expect(state.dispatches).toEqual(ROSTER.slice(0, 1));
    state = reduceSteps(state, roster);
    expect(state.steps).toEqual([]);
  });

  test("a roster entry's observation keeps exactly its allowlisted fields", () => {
    const observation = {
      stream_reason: "in_process",
      heartbeat_at: "2026-11-05T10:20:00+00:00",
      self_report: { reported_model: "claude-opus-5-5", match: true, reported_at: "2026-11-05T10:01:00+00:00" },
      checkpoints: [{ checkpoint_id: "cp-1", commit_sha: "1111111aaaa", created_at: "2026-11-05T10:12:00+00:00" }],
      checkpoint_count: 1,
    };
    const roster = (value: unknown) => parseStepsReply(rosterReply(1, true, [{ ...ROSTER[0], observation: value }]));

    expect(roster(observation)).toEqual({
      type: "roster",
      reset: true,
      orchestration: "available",
      dispatches: [{ ...ROSTER[0], observation }],
    });
    expect(roster({ ...observation, extra: 1 })).toBeNull();
    expect(roster({ ...observation, checkpoint_count: 0 })).toBeNull();
    expect(roster({ ...observation, self_report: { reported_model: "x", match: "yes", reported_at: "" } })).toBeNull();
    expect(roster({ ...observation, checkpoints: [{ checkpoint_id: "cp-1" }] })).toBeNull();
  });

  test("the list keeps the newest steps with unique keys", () => {
    const many = Array.from({ length: MAX_STEPS + 20 }, (_, index) => ({ ...AGENT_STEP, text: `s${index}` }));
    const state = reduceSteps(EMPTY_STEPS, { type: "steps", steps: many });
    expect(state.steps).toHaveLength(MAX_STEPS);
    expect(state.steps.at(-1)?.step).toEqual({ ...AGENT_STEP, text: `s${MAX_STEPS + 19}` });
    expect(new Set(state.steps.map((held) => held.key)).size).toBe(MAX_STEPS);
  });

  test("filters narrow the list by dispatch and by role", () => {
    const state = reduceSteps(EMPTY_STEPS, steps);
    const by = (dispatch: string | null, role: string | null) =>
      filterSteps(state.steps, { dispatch, role }).map((held) => held.step);
    expect(by(null, null)).toHaveLength(3);
    expect(by("dispatch-dev", null)).toEqual([ORCHESTRATION_STEP, AGENT_STEP]);
    expect(by(null, "review")).toEqual([CODEX_STEP]);
    expect(by("dispatch-dev", "review")).toEqual([]);
    expect(rosterRoles(ROSTER)).toEqual(["developer", "review"]);
  });

  test("event texts fill their fields and every label has its English text", () => {
    const step = ORCHESTRATION_STEP as unknown as OrchestrationStep;
    expect(eventText(step, (text, values) => translate("ru", text, values))).toBe(
      "Dispatch dispatch-dev: dispatched → working",
    );
    expect(eventText({ ...step, event: "batch.transition", from_state: null }, (text, values) =>
      translate("en", text, values),
    )).toBe("Batch batch-885: — → working");
    const english: Record<string, string> = catalog.en;
    for (const label of [...Object.values(EVENT_LABELS), ...Object.values(STRUCTURE_LABELS)]) {
      expect(english[label], label).toBeTruthy();
    }
    expect(translate("en", STRUCTURE_LABELS.unavailable)).toBe("structure unavailable");
  });
});
