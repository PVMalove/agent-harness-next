/* The Home snapshot body of a home.snapshot reply. ws-schema.json types it as JsonValue, so its
   shape follows harness/console/kernel/home_snapshot.py (HomeSnapshot.to_payload) by hand. */

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
  version: 1;
  health: HealthCounters;
  problems: Problem[];
  problems_total: number;
  harness_version: string;
  drift: string;
  /** null: orchestration is not connected; never read as 0. */
  active_batches: number | null;
  repo_map: RepoMapCard;
  memory: MemoryCard;
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

const SNAPSHOT = fields({
  version: (value) => value === 1,
  health: fields({ ok: count, warn: count, fail: count, skipped: count }),
  problems: list(fields({ status: string, id: string, message: string })),
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
});

/** The snapshot when `value` has exactly its shape, otherwise null. */
export function parseHomeSnapshot(value: unknown): HomeSnapshot | null {
  if (!SNAPSHOT(value)) return null;
  const snapshot = value as unknown as HomeSnapshot;
  return snapshot.problems.length <= snapshot.problems_total ? snapshot : null;
}

export const healthTotal = (health: HealthCounters): number =>
  health.ok + health.warn + health.fail + health.skipped;
