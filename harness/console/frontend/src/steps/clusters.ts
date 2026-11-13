/* The step list as a timeline: adjacent steps of one source that follow each other closely are
   one cluster, and each cluster shows how long it lasted. Pure functions over the held steps. */
import type { HeldStep, Step } from "../ws/steps";

/** Adjacent steps of one source at most this many seconds apart belong to one cluster. */
export const CLUSTER_WINDOW_SECONDS = 30;

export interface StepCluster {
  /** The key of the first member: stable while the cluster grows at its end. */
  key: number;
  members: HeldStep[];
  /** The newest member; its text names the cluster. */
  last: HeldStep;
  /** Seconds between the first and the last member. */
  spanSeconds: number;
  /** Seconds from the first member to the first step of the next cluster of the same source; null
      for the newest cluster of a source, whose end is not known. */
  durationSeconds: number | null;
}

/** The source of a step: an agent log is one per dispatch, orchestration events one per batch. */
export function sourceOf(step: Step): string {
  return step.origin === "agent"
    ? `agent:${step.dispatch_id}:${step.source}`
    : `orchestration:${step.batch_id ?? ""}`;
}

const seconds = (step: Step): number => Date.parse(step.observed_at) / 1000;

export function clusterSteps(steps: readonly HeldStep[]): StepCluster[] {
  const clusters: { members: HeldStep[]; source: string }[] = [];
  for (const held of steps) {
    const source = sourceOf(held.step);
    const open = clusters.at(-1);
    const previous = open?.members.at(-1);
    const gap = previous ? seconds(held.step) - seconds(previous.step) : Number.NaN;
    if (open && open.source === source && Number.isFinite(gap) && gap >= 0 && gap <= CLUSTER_WINDOW_SECONDS) {
      open.members.push(held);
    } else {
      clusters.push({ members: [held], source });
    }
  }
  return clusters.map((cluster, index) => {
    const first = cluster.members[0]!;
    const last = cluster.members.at(-1)!;
    const next = clusters.slice(index + 1).find((later) => later.source === cluster.source);
    const start = seconds(first.step);
    const end = next ? seconds(next.members[0]!.step) : Number.NaN;
    const span = seconds(last.step) - start;
    return {
      key: first.key,
      members: cluster.members,
      last,
      spanSeconds: Number.isFinite(span) ? Math.max(0, Math.round(span)) : 0,
      durationSeconds: Number.isFinite(end - start) ? Math.max(0, Math.round(end - start)) : null,
    };
  });
}

/** "45 с", "2 мин 5 с", "1 ч 1 мин"; a dash for an unknown duration. */
export function durationText(value: number | null, language: string): string {
  if (value === null) return "—";
  const [s, m, h] = language === "en" ? ["s", "min", "h"] : ["с", "мин", "ч"];
  if (value < 60) return `${value} ${s}`;
  if (value < 3600) return `${Math.floor(value / 60)} ${m} ${value % 60} ${s}`;
  return `${Math.floor(value / 3600)} ${h} ${Math.floor((value % 3600) / 60)} ${m}`;
}
