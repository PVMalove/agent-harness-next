import { beforeEach, describe, expect, test } from "vitest";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import type { JobEvent } from "../../harness/console/frontend/src/ws/client";
import {
  JOB_ERROR_LABELS,
  mergeOutput,
  parseCommands,
  parseJobSnapshot,
  parseJobSummary,
} from "../../harness/console/frontend/src/ws/jobs";
import type { LocalJob } from "../../harness/console/frontend/src/ws/jobs";
import catalog from "../../harness/console/frontend/src/i18n/catalog.json";
import { CANCEL_REASON, COMMANDS, FakeSocket, ManualClock, jobReply, jobSnapshot } from "./fake-socket";

const fragment = (n: number) => ({ channel: "stdout", text: `line ${n}\n` });
const lines = (from: number, to: number) =>
  Array.from({ length: to - from }, (_, index) => fragment(from + index));

function setup() {
  const clock = new ManualClock();
  const events: JobEvent[] = [];
  const client = createConsoleClient({
    url: "ws://127.0.0.1:4242/ws",
    WebSocket: FakeSocket,
    timers: clock,
    probeHealth: async () => false,
  });
  client.subscribeJobs((event) => events.push(event));
  client.start();
  FakeSocket.last.open();
  return { clock, events, client };
}

const jobEvents = (events: JobEvent[]) =>
  events.flatMap((event) => (event.type === "job" ? [event.job] : []));

describe("job snapshots", () => {
  test("parse the summary, the snapshot and the command descriptions of the server", () => {
    const snapshot = jobSnapshot({ output: lines(0, 2), cursor: 2 });
    expect(parseJobSnapshot(snapshot)).toEqual(snapshot);
    expect(parseJobSnapshot({ ...snapshot, cursor: -1 })).toBeNull();
    expect(parseJobSnapshot({ ...snapshot, phase: "paused" })).toBeNull();
    expect(parseJobSnapshot({ ...snapshot, output: [{ channel: "stdout" }] })).toBeNull();
    const { output: _output, ...summary } = snapshot;
    expect(parseJobSummary(summary)).toEqual(summary);
    expect(parseJobSummary({ ...summary, mutating: "yes" })).toBeNull();
    expect(parseCommands(COMMANDS)).toEqual(COMMANDS);
    expect(parseCommands([{ ...COMMANDS[0], inputs: "x" }])).toBeNull();
    expect(parseCommands([{ ...COMMANDS[1], confirmation_reason: 1 }])).toBeNull();
    const { reversibility_label: _label, ...unlabelled } = COMMANDS[0]!;
    expect(parseCommands([unlabelled])).toBeNull();
  });

  test("merge appends a contiguous batch and keeps only the tail of an overlap", () => {
    const local: LocalJob = { ...jobSnapshot({ output: lines(0, 3), cursor: 3 }) };
    const contiguous = mergeOutput(local, jobSnapshot({ output: lines(3, 5), cursor: 5 }));
    expect(contiguous.gap).toBe(false);
    expect(contiguous.job.output).toEqual(lines(0, 5));
    expect(contiguous.job.cursor).toBe(5);
    // The server replays from 1: fragments 1 and 2 are already held, 3 is new.
    const overlap = mergeOutput(local, jobSnapshot({ output: lines(1, 4), cursor: 4 }));
    expect(overlap.gap).toBe(false);
    expect(overlap.job.output).toEqual(lines(0, 4));
    const stale = mergeOutput(local, jobSnapshot({ output: lines(0, 2), cursor: 2 }));
    expect(stale.job.output).toEqual(lines(0, 3));
    expect(stale.job.cursor).toBe(3);
  });

  test("merge reports a gap and keeps the local output when a batch starts past it", () => {
    const local: LocalJob = { ...jobSnapshot({ output: lines(0, 2), cursor: 2 }) };
    const result = mergeOutput(local, jobSnapshot({ output: lines(4, 6), cursor: 6 }));
    expect(result.gap).toBe(true);
    expect(result.job.output).toEqual(lines(0, 2));
    expect(result.job.cursor).toBe(2);
    const first = mergeOutput(null, jobSnapshot({ output: lines(0, 1), cursor: 1 }));
    expect(first).toEqual({ gap: false, job: jobSnapshot({ output: lines(0, 1), cursor: 1 }) });
  });

  test("every refusal code has a label translated in the catalog", () => {
    const english: Record<string, string> = catalog.en;
    for (const label of Object.values(JOB_ERROR_LABELS)) {
      expect(english[label], label).toBeTruthy();
    }
    expect(Object.keys(JOB_ERROR_LABELS).sort()).toEqual(
      [
        "bad_request",
        "busy",
        "confirmation_required",
        "invalid_cursor",
        "not_running",
        "plan_required",
        "start_failed",
        "unavailable_command",
        "unknown_command",
        "unknown_job",
      ].sort(),
    );
  });
});

describe("the console client's jobs", () => {
  beforeEach(() => FakeSocket.reset());

  test("asks for a section's commands and reports them", () => {
    const { client, events } = setup();
    const socket = FakeSocket.last;
    expect(client.requestCommands("harness")).toBe(true);
    const request = socket.request("job.catalog");
    expect(request).toEqual({ id: request.id, type: "job.catalog", section: "harness" });
    socket.reply({ v: 1, id: request.id, type: "job.catalog", ok: true, commands: COMMANDS, cancel_reason: CANCEL_REASON });
    expect(events.at(-1)).toEqual({ type: "commands", section: "harness", commands: COMMANDS, cancelReason: CANCEL_REASON });
  });

  test("starts a job as the browser, then follows its output from the returned cursor", () => {
    const { client, events } = setup();
    const socket = FakeSocket.last;
    client.startJob({ command_id: "uninstall-apply", confirmed: true, confirmation: "UNINSTALL" });
    const start = socket.request("job.start");
    expect(start).toEqual({
      id: start.id,
      type: "job.start",
      command_id: "uninstall-apply",
      values: {},
      confirmed: true,
      confirmation: "UNINSTALL",
      client: "browser",
    });
    socket.reply(jobReply(start.id, "job.start", { output: lines(0, 1), cursor: 1 }));
    const follow = socket.request("job.subscribe");
    expect(follow).toEqual({ id: follow.id, type: "job.subscribe", job_id: "job-1", cursor: 1 });
    socket.reply(jobReply(follow.id, "job.subscribe", { output: lines(1, 3), cursor: 3 }));
    socket.reply(
      jobReply(follow.id, "job.subscribe", {
        output: lines(3, 4),
        cursor: 4,
        phase: "completed",
        done: true,
        returncode: 0,
      }),
    );
    const last = jobEvents(events).at(-1);
    expect(last?.output).toEqual(lines(0, 4));
    expect(last?.phase).toBe("completed");
    expect(client.job("job-1")?.cursor).toBe(4);
  });

  test("a refused start reports its code and the running job of busy", () => {
    const { client, events } = setup();
    const socket = FakeSocket.last;
    client.startJob({ command_id: "registry" });
    const start = socket.request("job.start");
    expect(start.confirmed).toBe(false);
    socket.reply({
      v: 1,
      id: start.id,
      type: "job.start",
      ok: false,
      error: { code: "busy", message: "Busy: job-7 (verify)", job_id: "job-7" },
    });
    expect(events.at(-1)).toEqual({
      type: "job-error",
      request: "job.start",
      code: "busy",
      message: "Busy: job-7 (verify)",
      jobId: "job-7",
    });
  });

  test("a cancel is sent only with the confirmation flag it is given", () => {
    const { client } = setup();
    const socket = FakeSocket.last;
    client.followJob("job-1");
    client.cancelJob("job-1", true);
    expect(socket.request("job.cancel")).toMatchObject({ job_id: "job-1", confirmed: true });
    client.cancelJob("job-1", false);
    expect(socket.request("job.cancel")).toMatchObject({ job_id: "job-1", confirmed: false });
  });

  test("lists the jobs and asks again after a reconnect", () => {
    const { client, clock, events } = setup();
    client.listJobs();
    const socket = FakeSocket.last;
    const list = socket.request("job.list");
    const { output: _output, ...summary } = jobSnapshot({ mutating: true });
    socket.reply({ v: 1, id: list.id, type: "job.list", ok: true, jobs: [summary] });
    expect(events.at(-1)).toEqual({ type: "jobs", jobs: [summary] });
    socket.close();
    clock.advance(500);
    FakeSocket.last.open();
    expect(FakeSocket.last.request("job.list").type).toBe("job.list");
  });

  test("a dropped socket resumes the output from the held cursor without loss or repeats", () => {
    const { client, clock, events } = setup();
    const first = FakeSocket.last;
    client.followJob("job-1");
    const follow = first.request("job.subscribe");
    expect(follow.cursor).toBe(0);
    first.reply(jobReply(follow.id, "job.subscribe", { output: lines(0, 3), cursor: 3 }));
    first.close();
    clock.advance(500);
    const second = FakeSocket.last;
    second.open();
    const resume = second.request("job.subscribe");
    expect(resume).toEqual({ id: resume.id, type: "job.subscribe", job_id: "job-1", cursor: 3 });
    // A late frame of the old socket is dropped.
    first.onmessage?.({ data: JSON.stringify(jobReply(follow.id, "job.subscribe", { output: lines(3, 5), cursor: 5 })) });
    second.reply(jobReply(resume.id, "job.subscribe", { output: lines(3, 6), cursor: 6 }));
    second.reply(
      jobReply(resume.id, "job.subscribe", { output: lines(6, 7), cursor: 7, phase: "completed", done: true, returncode: 0 }),
    );
    expect(jobEvents(events).at(-1)?.output).toEqual(lines(0, 7));
    second.close();
    clock.advance(500);
    FakeSocket.last.open();
    // A finished job is not followed again.
    expect(FakeSocket.last.sent.filter((body) => body.type === "job.subscribe")).toEqual([]);
  });

  test("a batch past the held cursor resubscribes from it", () => {
    const { client } = setup();
    const socket = FakeSocket.last;
    client.followJob("job-1");
    const follow = socket.request("job.subscribe");
    socket.reply(jobReply(follow.id, "job.subscribe", { output: lines(0, 2), cursor: 2 }));
    socket.reply(jobReply(follow.id, "job.subscribe", { output: lines(5, 6), cursor: 6 }));
    const again = socket.request("job.subscribe");
    expect(again.id).not.toBe(follow.id);
    expect(again.cursor).toBe(2);
    expect(client.job("job-1")?.output).toEqual(lines(0, 2));
  });

  test("an unknown job stops being followed", () => {
    const { client, events, clock } = setup();
    const socket = FakeSocket.last;
    client.followJob("job-9");
    const follow = socket.request("job.subscribe");
    socket.reply({ v: 1, id: follow.id, type: "job.subscribe", ok: false, error: { code: "unknown_job", message: "Unknown job." } });
    expect(events.at(-1)).toMatchObject({ type: "job-error", request: "job.subscribe", code: "unknown_job", jobId: "job-9" });
    socket.close();
    clock.advance(500);
    FakeSocket.last.open();
    expect(FakeSocket.last.sent.filter((body) => body.type === "job.subscribe")).toEqual([]);
  });
});
