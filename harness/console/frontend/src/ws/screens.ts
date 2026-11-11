/* The screen snapshots of Diagnostics and Harness. ws-schema.json types the paged snapshot text as
   a string, so the shapes of the health report and of the maintenance facts follow
   harness/console/kernel/health_report.py (schema v1) and harness/console/kernel/maintenance.py
   (MaintenanceView.to_payload) by hand, as ws/types.ts does for Home. The parsers only check
   shapes: every count, total and digest is the server's and is never recomputed here. */
import type { HarnessOverviewReply } from "./protocol.gen";
import type { HealthCounters } from "./types";

export type CheckStatus = "ok" | "warn" | "fail" | "skipped";
export const CHECK_STATUSES: readonly CheckStatus[] = ["ok", "warn", "fail", "skipped"];

export interface CheckFix {
  text: string;
  command: string | null;
}

export interface HealthCheck {
  id: string;
  group: string;
  status: CheckStatus;
  message: string;
  fix: CheckFix | null;
}

export interface HealthReport {
  schema_version: 1;
  repo: string;
  online: boolean;
  summary: HealthCounters;
  checks: HealthCheck[];
  fixes_applied: string[];
}

export interface Size {
  bytes: number;
  files: number;
}

export interface CleanupItem {
  kind: string;
  path: string;
  branch?: string | null;
}

export interface CleanupSkip {
  path: string;
  reason: string;
}

export interface CleanupPlan {
  mode: string;
  root: string;
  min_age_hours: number;
  remove: CleanupItem[];
  skipped: CleanupSkip[];
}

export interface CleanupSummary {
  plan: CleanupPlan;
  categories: Record<string, Size>;
  total: Size;
  items: number;
  digest: string;
}

export interface WorktreeFact {
  path: string;
  branch: string | null;
  dirty: number | null;
  reason: string;
}

export interface MaintenanceView {
  soft: CleanupSummary;
  hard: CleanupSummary;
  worktrees: WorktreeFact[];
  worktree_error: string;
  tree_sizes: { path: string; size: Size }[];
}

/** The harness.maintenance snapshot: the facts, or none with the text of why. */
export interface MaintenanceFacts {
  maintenance: MaintenanceView | null;
  error: string;
}

/** The harness.overview reply without its envelope. */
export type HarnessOverview = Pick<
  HarnessOverviewReply,
  "state" | "package_version" | "drift" | "drift_files" | "store" | "adapters" | "containers" | "usage"
>;

type Check = (value: unknown) => boolean;

const isObject = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const count: Check = (value) => Number.isSafeInteger(value) && (value as number) >= 0;
const string: Check = (value) => typeof value === "string";
const flag: Check = (value) => typeof value === "boolean";
const number: Check = (value) => typeof value === "number" && Number.isFinite(value);
const nullable =
  (check: Check): Check =>
  (value) =>
    value === null || check(value);
const list =
  (check: Check): Check =>
  (value) =>
    Array.isArray(value) && value.every(check);
/** Exactly the keys of `schema`, each valid: the server's decoders refuse any other key too. */
const exact =
  (schema: Record<string, Check>): Check =>
  (value) =>
    isObject(value) &&
    Object.keys(value).length === Object.keys(schema).length &&
    Object.entries(schema).every(([key, check]) => Object.hasOwn(value, key) && check(value[key]));
/** The keys of `schema` are present and valid; others are allowed. */
const has =
  (schema: Record<string, Check>): Check =>
  (value) =>
    isObject(value) && Object.entries(schema).every(([key, check]) => Object.hasOwn(value, key) && check(value[key]));

const counters = exact({ ok: count, warn: count, fail: count, skipped: count });
const status: Check = (value) => typeof value === "string" && (CHECK_STATUSES as readonly string[]).includes(value);
const check = exact({
  id: string,
  group: string,
  status,
  message: string,
  fix: nullable(exact({ text: string, command: nullable(string) })),
});
const report = exact({
  schema_version: (value) => value === 1,
  repo: string,
  online: flag,
  summary: counters,
  checks: list(check),
  fixes_applied: list(string),
});

const size = exact({ bytes: count, files: count });
const plan = exact({
  mode: string,
  root: string,
  min_age_hours: number,
  remove: list(has({ kind: string, path: string })),
  skipped: list(has({ path: string, reason: string })),
});
const summary = exact({
  plan,
  categories: (value) => isObject(value) && Object.values(value).every(size),
  total: size,
  items: count,
  digest: string,
});
const view = exact({
  soft: summary,
  hard: summary,
  worktrees: list(exact({ path: string, branch: nullable(string), dirty: nullable(count), reason: string })),
  worktree_error: string,
  tree_sizes: list(exact({ path: string, size })),
});
const maintenance = exact({ maintenance: nullable(view), error: string });

/** The `HarnessState` payload of harness/console/kernel/harness_facts.py. */
export const harnessState = exact({
  installed: flag,
  installed_version: string,
  capabilities: list(string),
  skills: count,
  managed_files: count,
  updated_at: string,
  orchestration: flag,
});
const usage = exact({
  unavailable: nullable(string),
  batches: count,
  tickets: count,
  dispatches: count,
  reports: count,
});
const store = exact({
  authority: (value) => value === "file-ledger" || value === "runtime-store" || value === "none",
  schema: nullable(count),
  generation: nullable(string),
  audit_records: nullable(count),
});
const adapter = exact({
  path: string,
  status: (value) => value === "current" || value === "outdated" || value === "missing",
  problem: nullable(string),
});
/** The container engine inventory of harness/console/kernel/container_inventory.py. */
const containers = exact({
  engine: string,
  version: nullable(string),
  cgroup_driver: nullable(string),
  cgroup_version: nullable(string),
  selinux: nullable(flag),
  rootless: nullable(flag),
  info_problem: nullable(string),
  images: nullable(count),
  images_problem: nullable(string),
  volumes: nullable(count),
  volumes_problem: nullable(string),
});
const overview = has({
  state: harnessState,
  package_version: string,
  drift: string,
  drift_files: nullable(count),
  store: nullable(store),
  adapters: nullable(list(adapter)),
  containers: nullable(containers),
  usage,
});

/** The `harness health --json` report (schema v1), or null for any other shape. */
export function parseHealthReport(value: unknown): HealthReport | null {
  return report(value) ? (value as HealthReport) : null;
}

/** The maintenance facts of harness.maintenance, or null for any other shape. */
export function parseMaintenance(value: unknown): MaintenanceFacts | null {
  return maintenance(value) ? (value as MaintenanceFacts) : null;
}

/** The facts of a harness.overview reply, or null for any other shape. */
export function parseHarnessOverview(value: unknown): HarnessOverview | null {
  if (!overview(value)) return null;
  const found = value as unknown as HarnessOverview;
  return {
    state: found.state,
    package_version: found.package_version,
    drift: found.drift,
    drift_files: found.drift_files,
    store: found.store,
    adapters: found.adapters,
    containers: found.containers,
    usage: found.usage,
  };
}

/** The total number of checks the report's summary counts. */
export const checkTotal = (counts: HealthCounters): number => counts.ok + counts.warn + counts.fail + counts.skipped;
