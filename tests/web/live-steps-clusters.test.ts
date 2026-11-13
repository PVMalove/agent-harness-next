import { describe, expect, test } from "vitest";
import {
  CLUSTER_WINDOW_SECONDS,
  clusterSteps,
  durationText,
} from "../../harness/console/frontend/src/steps/clusters";
import type { HeldStep, Step } from "../../harness/console/frontend/src/ws/steps";
import { AGENT_STEP, CODEX_STEP, ORCHESTRATION_STEP } from "./fake-socket";

let key = 0;
const held = (step: Step): HeldStep => ({ key: key++, step });
const at = (seconds: number) => `2026-11-06T10:00:${String(seconds).padStart(2, "0")}+00:00`;
const agent = (seconds: number, extra: Partial<Step> = {}) =>
  held({ ...AGENT_STEP, observed_at: at(seconds), ...extra } as Step);

describe("clustering the steps of one source", () => {
  test("no steps, no clusters", () => {
    expect(clusterSteps([])).toEqual([]);
  });

  test("adjacent steps of one source inside the window make one cluster with a span", () => {
    const steps = [agent(0), agent(5), agent(CLUSTER_WINDOW_SECONDS + 5)];
    const [cluster, ...rest] = clusterSteps(steps);
    expect(rest).toEqual([]);
    expect(cluster!.members.map((member) => member.key)).toEqual(steps.map((step) => step.key));
    expect(cluster!.spanSeconds).toBe(CLUSTER_WINDOW_SECONDS + 5);
    expect(cluster!.last).toBe(steps[2]);
  });

  test("a gap longer than the window starts a new cluster", () => {
    const clusters = clusterSteps([agent(0), agent(CLUSTER_WINDOW_SECONDS + 1)]);
    expect(clusters).toHaveLength(2);
  });

  test("another source in between splits the run; sources are dispatch (agent) and batch (orchestration)", () => {
    const steps = [
      agent(0),
      held({ ...CODEX_STEP, observed_at: at(2) } as Step),
      agent(4),
      held({ ...ORCHESTRATION_STEP, observed_at: at(6) } as Step),
      held({ ...ORCHESTRATION_STEP, observed_at: at(8), seq: 4 } as Step),
    ];
    expect(clusterSteps(steps).map((cluster) => cluster.members.length)).toEqual([1, 1, 1, 2]);
  });

  test("a step with an unreadable time is never merged", () => {
    const clusters = clusterSteps([agent(0), agent(1, { observed_at: "later" } as Partial<Step>), agent(2)]);
    expect(clusters.map((cluster) => cluster.members.length)).toEqual([1, 1, 1]);
  });

  test("the duration of a cluster runs to the next cluster of the same source; the newest has none", () => {
    const steps = [agent(0), agent(1), held({ ...CODEX_STEP, observed_at: at(3) } as Step), agent(CLUSTER_WINDOW_SECONDS + 10)];
    const clusters = clusterSteps(steps);
    expect(clusters.map((cluster) => cluster.durationSeconds)).toEqual([CLUSTER_WINDOW_SECONDS + 10, null, null]);
  });
});

describe("the duration text", () => {
  test("seconds, minutes with seconds, hours; no value is a dash", () => {
    expect(durationText(null, "ru")).toBe("—");
    expect(durationText(0, "ru")).toBe("0 с");
    expect(durationText(45, "ru")).toBe("45 с");
    expect(durationText(125, "ru")).toBe("2 мин 5 с");
    expect(durationText(125, "en")).toBe("2 min 5 s");
    expect(durationText(3700, "ru")).toBe("1 ч 1 мин");
  });
});
