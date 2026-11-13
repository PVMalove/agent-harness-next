/* The Home snapshot body of a home.snapshot reply. ws-schema.json types it as JsonValue, so its
   shape follows harness/console/kernel/home_snapshot.py (HomeSnapshot.to_payload) by hand. */
import type { HomeActivityPayload, LinkActivityPayload } from "./protocol.gen";

/** The per-link counters of the Home contour: a key of the reply beside the snapshot, counted
    for that reply from the events the console observed (kernel/home_activity.py). */
export type HomeActivity = HomeActivityPayload;
export type LinkActivity = LinkActivityPayload;

export interface HealthCounters {
  ok: number;
  warn: number;
  fail: number;
  skipped: number;
}

export interface Problem {
  status: string;
  id: string;
  message: string;
  /** The health area of the check; "" when unknown. */
  group: string;
}

export interface ProjectFacts {
  name: string;
  branch: string | null;
  commit: string | null;
  /** The resolved tracker type; "" when unknown. */
  tracker: string;
}

export interface HarnessInstall {
  installed: boolean;
  installed_version: string;
  capabilities: number;
  skills: number;
  managed_files: number;
  /** Installed capability names in lock order; `uncatalogued` lacks a catalog entry. */
  capability_names: string[];
  uncatalogued: string[];
}

export interface StoreFacts {
  /** "file-ledger", "runtime-store" or "none". */
  authority: string;
  schema: number | null;
  generation: string | null;
  audit_records: number | null;
  /** `AUTHORITY.json` cutover time; null before a cutover. */
  cutover_at: string | null;
  /** Why a fact is null; "" when every fact was read. */
  reason: string;
}

export interface DriftCounts {
  total: number;
  added: number;
  missing: number;
  package_changed: number;
  local_changed: number;
  conflict: number;
  retired: number;
}

export interface AreaCounters {
  area: string;
  ok: number;
  warn: number;
  fail: number;
  skipped: number;
}

export interface RouteStep {
  role: string;
  state: string;
}

export interface RecentSession {
  batch_id: string;
  ticket: string;
  state: string;
  branch: string;
  created_at: string;
  route: RouteStep[];
  /** The latest dispatch time (the creation when there is none). */
  updated_at: string;
}

export interface HeadMap {
  origin: string;
  commit: string;
  files: number;
  edges: number;
  estimated_tokens: number;
}

export interface RepoMapCard {
  tier: string | null;
  message: string;
  /** null: there is no map for HEAD. */
  head_map: HeadMap | null;
  /** The latest cached map of another commit when HEAD has none ("stale for HEAD"). */
  stale_map: HeadMap | null;
}

export interface MemoryState {
  status: string;
  message: string;
}

export interface MemoryPolicy {
  enabled: boolean;
  active: boolean;
  source_types: string[];
  indexed: number | null;
  problem: string;
  inactive: string;
  top_k: number | null;
  max_tokens: number | null;
}

export interface MemoryCard {
  state: MemoryState | null;
  policy: MemoryPolicy | null;
}

export interface HomeSnapshot {
  version: 2;
  health: HealthCounters;
  problems: Problem[];
  problems_total: number;
  harness_version: string;
  drift: string;
  /** null: orchestration is not connected; never read as 0. */
  active_batches: number | null;
  repo_map: RepoMapCard;
  memory: MemoryCard;
  project: ProjectFacts | null;
  harness: HarnessInstall | null;
  store: StoreFacts | null;
  /** null: `harness diff --json` could not be read. */
  drift_counts: DriftCounts | null;
  areas: AreaCounters[];
  skipped_checks: Problem[];
  recent_sessions: RecentSession[];
}

type Check = (value: unknown) => boolean;

const count: Check = (value) => Number.isSafeInteger(value) && (value as number) >= 0;
const string: Check = (value) => typeof value === "string";
const flag: Check = (value) => typeof value === "boolean";
const nullable =
  (check: Check): Check =>
  (value) =>
    value === null || check(value);
const isObject = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const fields =
  (schema: Record<string, Check>): Check =>
  (value) =>
    isObject(value) &&
    Object.keys(value).length === Object.keys(schema).length &&
    Object.entries(schema).every(([key, check]) => Object.hasOwn(value, key) && check(value[key]));
const list =
  (check: Check): Check =>
  (value) =>
    Array.isArray(value) && value.every(check);

const PROBLEM = fields({ status: string, id: string, message: string, group: string });
const COUNTS = { ok: count, warn: count, fail: count, skipped: count };

const SNAPSHOT = fields({
  version: (value) => value === 2,
  health: fields(COUNTS),
  problems: list(PROBLEM),
  problems_total: count,
  harness_version: string,
  drift: string,
  active_batches: nullable(count),
  repo_map: fields({
    tier: nullable(string),
    message: string,
    head_map: nullable(
      fields({ origin: string, commit: string, files: count, edges: count, estimated_tokens: count }),
    ),
    stale_map: nullable(
      fields({ origin: string, commit: string, files: count, edges: count, estimated_tokens: count }),
    ),
  }),
  memory: fields({
    state: nullable(fields({ status: string, message: string })),
    policy: nullable(
      fields({
        enabled: flag,
        active: flag,
        source_types: list(string),
        indexed: nullable(count),
        problem: string,
        inactive: string,
        top_k: nullable(count),
        max_tokens: nullable(count),
      }),
    ),
  }),
  project: nullable(fields({ name: string, branch: nullable(string), commit: nullable(string), tracker: string })),
  harness: nullable(
    fields({
      installed: flag,
      installed_version: string,
      capabilities: count,
      skills: count,
      managed_files: count,
      capability_names: list(string),
      uncatalogued: list(string),
    }),
  ),
  store: nullable(
    fields({
      authority: string,
      schema: nullable(count),
      generation: nullable(string),
      audit_records: nullable(count),
      cutover_at: nullable(string),
      reason: string,
    }),
  ),
  drift_counts: nullable(
    fields({
      total: count,
      added: count,
      missing: count,
      package_changed: count,
      local_changed: count,
      conflict: count,
      retired: count,
    }),
  ),
  areas: list(fields({ area: string, ...COUNTS })),
  skipped_checks: list(PROBLEM),
  recent_sessions: list(
    fields({
      batch_id: string,
      ticket: string,
      state: string,
      branch: string,
      created_at: string,
      route: list(fields({ role: string, state: string })),
      updated_at: string,
    }),
  ),
});

/** The snapshot when `value` has exactly its shape, otherwise null. */
export function parseHomeSnapshot(value: unknown): HomeSnapshot | null {
  if (!SNAPSHOT(value)) return null;
  const snapshot = value as unknown as HomeSnapshot;
  return snapshot.problems.length <= snapshot.problems_total ? snapshot : null;
}

const rate: Check = (value) => typeof value === "number" && Number.isFinite(value) && value >= 0;
const ACTIVITY = fields({
  window_seconds: count,
  links: list(
    fields({ link: string, events_per_minute: rate, last_event_age_seconds: nullable(rate) }),
  ),
  last_event_age_seconds: nullable(rate),
  events_total_window: count,
});

/** The activity when `value` has exactly its shape, otherwise null: a reply with a broken
    activity still carries a usable snapshot, so the contour just has no data. */
export function parseHomeActivity(value: unknown): HomeActivity | null {
  return ACTIVITY(value) ? (value as HomeActivity) : null;
}

export const healthTotal = (health: HealthCounters): number =>
  health.ok + health.warn + health.fail + health.skipped;
