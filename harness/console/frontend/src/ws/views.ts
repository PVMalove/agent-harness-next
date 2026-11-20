/* The Recovery and Container route views: harness/console/kernel/screen_views.py serialises the
   very rows, actions, blockers, tabs and stage views the TUI draws, so this module only checks
   their shapes. No availability, state or mark is decided here. */
import { exact, flag, list, nullable, string } from "./ledger";
import type { Check } from "./ledger";

export interface ViewRow {
  label: string;
  value: string;
  state: string | null;
  /** `✔ ок`, `○ не проверено`; empty for a row without a status. */
  mark: string;
  group: string;
}

export interface ViewAction {
  key: string;
  label: string;
  enabled: boolean;
  reason: string;
  effect: string;
  needs_confirmation: boolean;
}

export interface RecoveryEntry {
  batch_id: string;
  enabled: boolean;
  state: string;
  mark: string;
  reason: string;
}

export interface RecoveryBody {
  batch: string;
  unknown_outcome: boolean;
  rows: ViewRow[];
  blockers: string[];
  notes: string[];
  actions: ViewAction[];
}

export interface ResumePlan {
  command: string;
  checks: [string, string][];
  approval_required: boolean;
  next_step: string;
}

export interface RecoveryView {
  history: { batch_id: string; label: string }[];
  history_unavailable: string;
  entry: RecoveryEntry | null;
  view: RecoveryBody | null;
  resume_plan: ResumePlan | null;
}

export const STAGES = ["setup", "preflight", "plan", "worker", "qa", "cleanup"] as const;
export type Stage = (typeof STAGES)[number];

export interface StageView {
  stage: Stage;
  rows: ViewRow[];
  actions: ViewAction[];
  blockers: string[];
  notes: string[];
}

export interface RouteTab {
  stage: Stage;
  title: string;
  state: string;
  mark: string;
  reason: string;
}

export interface RouteView {
  selection: { batch: string; role: string; runtime: string };
  context: [string, string][];
  tabs: RouteTab[];
  stages: Record<Stage, StageView>;
}

const stageName: Check = (value) => typeof value === "string" && (STAGES as readonly string[]).includes(value);
const pair: Check = (value) => Array.isArray(value) && value.length === 2 && value.every(string);
const row = exact({ label: string, value: string, state: nullable(string), mark: string, group: string });
const action = exact({
  key: string,
  label: string,
  enabled: flag,
  reason: string,
  effect: string,
  needs_confirmation: flag,
});
const body = exact({
  batch: string,
  unknown_outcome: flag,
  rows: list(row),
  blockers: list(string),
  notes: list(string),
  actions: list(action),
});
const recovery = exact({
  history: list(exact({ batch_id: string, label: string })),
  history_unavailable: string,
  entry: nullable(exact({ batch_id: string, enabled: flag, state: string, mark: string, reason: string })),
  view: nullable(body),
  resume_plan: nullable(
    exact({ command: string, checks: list(pair), approval_required: flag, next_step: string }),
  ),
});
const stageView = exact({
  stage: stageName,
  rows: list(row),
  actions: list(action),
  blockers: list(string),
  notes: list(string),
});
const route = exact({
  selection: exact({ batch: string, role: string, runtime: string }),
  context: list(pair),
  tabs: list(exact({ stage: stageName, title: string, state: string, mark: string, reason: string })),
  stages: exact(Object.fromEntries(STAGES.map((name) => [name, stageView]))),
});

/** The recovery.view payload, or null for any other shape. */
export function parseRecoveryView(value: unknown): RecoveryView | null {
  return recovery(value) ? (value as unknown as RecoveryView) : null;
}

/** The container_route.view payload, or null for any other shape. */
export function parseRouteView(value: unknown): RouteView | null {
  return route(value) ? (value as unknown as RouteView) : null;
}

/** Rows grouped in order: a new group starts where the group name changes, as the TUI draws. */
export function groupRows(rows: readonly ViewRow[]): { group: string; rows: ViewRow[] }[] {
  const groups: { group: string; rows: ViewRow[] }[] = [];
  for (const item of rows) {
    const last = groups.at(-1);
    if (last && last.group === item.group) last.rows.push(item);
    else groups.push({ group: item.group, rows: [item] });
  }
  return groups;
}
