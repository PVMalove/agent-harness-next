/* The Reports and Orchestration snapshots. ws-schema.json types the paged snapshot text as a
   string, so the shapes follow harness/console/kernel/reports.py (`ledger_payload`,
   `timeline_payload`) and kernel/pipeline_kpi.py (`to_payload`) by hand, as ws/screens.ts does
   for Diagnostics. The parsers only check shapes: every KPI and analytics figure is the
   server's and is never recomputed here. A report body is untrusted text. */

/* Shape checks, as in ws/screens.ts; ws/views.ts shares them. */
export type Check = (value: unknown) => boolean;
export const isObject = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
export const count: Check = (value) => Number.isSafeInteger(value) && (value as number) >= 0;
export const string: Check = (value) => typeof value === "string";
export const flag: Check = (value) => typeof value === "boolean";
export const nullable =
  (check: Check): Check =>
  (value) =>
    value === null || check(value);
export const list =
  (check: Check): Check =>
  (value) =>
    Array.isArray(value) && value.every(check);
/** Exactly the keys of `schema`, each valid: the server's decoders refuse any other key too. */
export const exact =
  (schema: Record<string, Check>): Check =>
  (value) =>
    isObject(value) &&
    Object.keys(value).length === Object.keys(schema).length &&
    Object.entries(schema).every(([key, check]) => Object.hasOwn(value, key) && check(value[key]));

export interface BatchSummary {
  batch_id: string;
  ticket: string;
  state: string;
  created_at: string;
  branch: string;
  pr_created_at: string;
  pr_url: string;
  pr_state: string;
}

export interface ReportHead {
  dispatch_id: string;
  batch_id: string;
  ticket: string;
  role: string;
  outcome: string;
  reported_at: string;
  /** Whether the body records a risk, and a blocker. */
  has_risks: boolean;
  has_blockers: boolean;
}

export interface StageHead {
  dispatch_id: string;
  batch_id: string;
  ticket: string;
  role: string;
  state: string;
  at: string;
  /** The dispatch id of the stage's report, or null while none is recorded. */
  report: string | null;
  /** When the dispatch was created and its worker last sent a heartbeat; "" when unknown. */
  started_at: string;
  heartbeat_at: string;
}

export interface QaRun {
  artifact: string;
  logged_at: string;
  dispatch_id: string | null;
  ticket: string;
  outcome: string;
  commands: [string, number][];
  tail: string[];
  total_lines: number;
}

export interface QaAttempt {
  dispatch_id: string;
  stage: string;
  failed_at: string;
  message: string;
}

export interface Ledger {
  version: 2;
  batches: BatchSummary[];
  reports: ReportHead[];
  stages: StageHead[];
  qa_runs: QaRun[];
  qa_attempts: QaAttempt[];
  unavailable: string | null;
  dispatches: Record<string, { role?: string }>;
}

export type Figures = Record<string, number | null>;

export interface ReportRef {
  dispatch_id: string;
  outcome: string;
  has_blockers: boolean;
}

/** One batch of the read-only publication view (kernel/publish_view.py); unread facts are null. */
export interface PublishEntry {
  batch_id: string;
  ticket: string;
  state: string;
  branch: string;
  candidate: string | null;
  target: string | null;
  integration_ref: string | null;
  /** The local remote-tracking ref of the branch: as old as the last fetch. */
  head: string | null;
  head_matches: boolean | null;
  target_in_history: boolean | null;
  refusals: string[];
  review: ReportRef | null;
  qa: ReportRef | null;
  pr_url: string;
  pr_state: string;
}

export interface ReportsSnapshot extends Ledger {
  reports_kpi: Figures;
  publish: PublishEntry[];
}

export type Figure = number | null | number[] | Record<string, number>;
export type AnalyticsSection = "flow" | "quality" | "runtime" | "gates";
export type Analytics = Record<AnalyticsSection, Record<string, Figure>>;

export interface LockState {
  lock: Record<string, unknown> | null;
  error: string | null;
}

export interface OrchestrationSnapshot {
  ledger: ReportsSnapshot;
  lock: LockState;
  kpi: Figures;
  analytics: Analytics;
}

export interface TimelineEvent {
  at: string;
  kind: string;
  text: string;
  role: string | null;
}

export interface BatchTimeline {
  batch: BatchSummary;
  role_flow: string[];
  events: TimelineEvent[];
}

/** A completion report body: any JSON object; its fields are read defensively. */
export type ReportBody = Record<string, unknown>;

export const KPI_KEYS = [
  "wip",
  "oldest_wip_seconds",
  "awaiting_approval",
  "oldest_approval_seconds",
  "blocked",
  "stale",
  "rework",
  "qa_first_pass",
  "qa_tickets",
  "cycle_p50_seconds",
  "cycle_p95_seconds",
  "throughput_7d",
  "failed",
  "unknown",
  "batches",
  "rework_batches",
  "flow_efficiency_pct",
] as const;
export const REPORTS_KPI_KEYS = [
  "reports",
  "evidence_complete",
  "latency_p50_seconds",
  "latency_p95_seconds",
  "qa_first_pass",
  "qa_tickets",
  "attention",
  "blocked",
  "stale_evidence",
] as const;
export const ANALYTICS_SECTIONS: readonly AnalyticsSection[] = ["flow", "quality", "runtime", "gates"];

const figures =
  (keys: readonly string[]): Check =>
  (value) =>
    exact(Object.fromEntries(keys.map((key) => [key, nullable(count)])))(value);

const batch = exact({
  batch_id: string,
  ticket: string,
  state: string,
  created_at: string,
  branch: string,
  pr_created_at: string,
  pr_url: string,
  pr_state: string,
});
const reportHead = exact({
  dispatch_id: string,
  batch_id: string,
  ticket: string,
  role: string,
  outcome: string,
  reported_at: string,
  has_risks: flag,
  has_blockers: flag,
});
const stage = exact({
  dispatch_id: string,
  batch_id: string,
  ticket: string,
  role: string,
  state: string,
  at: string,
  report: nullable(string),
  started_at: string,
  heartbeat_at: string,
});
const command: Check = (value) =>
  Array.isArray(value) && value.length === 2 && string(value[0]) && Number.isSafeInteger(value[1]);
const qaRun = exact({
  artifact: string,
  logged_at: string,
  dispatch_id: nullable(string),
  ticket: string,
  outcome: string,
  commands: list(command),
  tail: list(string),
  total_lines: count,
});
const qaAttempt = exact({ dispatch_id: string, stage: string, failed_at: string, message: string });
const dispatches: Check = (value) =>
  isObject(value) &&
  Object.values(value).every(
    (record) => isObject(record) && Object.entries(record).every(([key, role]) => key === "role" && string(role)),
  );
const ledgerFields = {
  version: (value: unknown) => value === 2,
  batches: list(batch),
  reports: list(reportHead),
  stages: list(stage),
  qa_runs: list(qaRun),
  qa_attempts: list(qaAttempt),
  unavailable: nullable(string),
  dispatches,
};
const reportRef = exact({ dispatch_id: string, outcome: string, has_blockers: flag });
const publishEntry = exact({
  batch_id: string,
  ticket: string,
  state: string,
  branch: string,
  candidate: nullable(string),
  target: nullable(string),
  integration_ref: nullable(string),
  head: nullable(string),
  head_matches: nullable(flag),
  target_in_history: nullable(flag),
  refusals: list(string),
  review: nullable(reportRef),
  qa: nullable(reportRef),
  pr_url: string,
  pr_state: string,
});
const reportsSnapshot = exact({
  ...ledgerFields,
  reports_kpi: figures(REPORTS_KPI_KEYS),
  publish: list(publishEntry),
});

const figure: Check = (value) =>
  value === null ||
  count(value) ||
  list(count)(value) ||
  (isObject(value) && Object.values(value).every(count));
const section: Check = (value) => isObject(value) && Object.values(value).every(figure);
const analytics = exact(Object.fromEntries(ANALYTICS_SECTIONS.map((name) => [name, section])));
const lock = exact({ lock: nullable(isObject), error: nullable(string) });
const orchestration = exact({ ledger: reportsSnapshot, lock, kpi: figures(KPI_KEYS), analytics });

const event = exact({ at: string, kind: string, text: string, role: nullable(string) });
const timeline = exact({ batch, role_flow: list(string), events: list(event) });

/** The reports.snapshot payload (the ledger with the Reports KPIs), or null for another shape. */
export function parseReports(value: unknown): ReportsSnapshot | null {
  return reportsSnapshot(value) ? (value as ReportsSnapshot) : null;
}

/** The orchestration.snapshot payload, or null for any other shape. */
export function parseOrchestration(value: unknown): OrchestrationSnapshot | null {
  return orchestration(value) ? (value as unknown as OrchestrationSnapshot) : null;
}

/** The reports.timeline payload, or null for any other shape. */
export function parseTimeline(value: unknown): BatchTimeline | null {
  return timeline(value) ? (value as unknown as BatchTimeline) : null;
}

/** The reports.report payload: any JSON object. */
export function parseReport(value: unknown): ReportBody | null {
  return isObject(value) ? value : null;
}
