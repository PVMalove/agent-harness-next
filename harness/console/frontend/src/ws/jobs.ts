/* Catalog commands and jobs of the job.* protocol. The server owns the catalog, the confirmation,
   the mutation slot and the cursor; the client checks the shapes and merges output batches.
   JobReply.job is typed as JsonValue in ws-schema.json, so its shape follows
   harness/console/backend/domain/jobs.py (Job.summary, Job.snapshot) by hand. */
import type { CommandDescriptor, JobSummary } from "./protocol.gen";

export type { CommandDescriptor, JobSummary };

export interface OutputFragment {
  channel: string;
  text: string;
}

/** One reply's view of a job: its summary and the batch that ends at `cursor`. */
export interface JobSnapshot extends JobSummary {
  output: OutputFragment[];
}

/** The client's copy of a job: every fragment before `cursor`, in order. */
export type LocalJob = JobSnapshot;

export const PHASES = ["running", "completed", "failed", "cancelled"] as const;
const REVERSIBILITY = [
  "reversible",
  "deletes-local-data",
  "terminal-coordinator-action",
  "external-change",
  "overwrites-managed-files",
  "downloads-files",
];

/** The Russian label the web console shows for a job refusal code (catalog.json translates it). */
export const JOB_ERROR_LABELS: Readonly<Record<string, string>> = {
  unknown_command: "Неизвестная команда каталога",
  confirmation_required: "Команда требует явного подтверждения",
  plan_required: "Сначала нужно превью плана очистки",
  unavailable_command: "Команда недоступна в этом проекте",
  start_failed: "Команду не удалось подготовить",
  busy: "Консоль занята",
  not_running: "Job уже не выполняется",
  unknown_job: "Неизвестная job",
  invalid_cursor: "Курсор вне вывода job",
  bad_request: "Некорректный запрос",
};

type Check = (value: unknown) => boolean;

const count: Check = (value) => Number.isSafeInteger(value) && (value as number) >= 0;
const string: Check = (value) => typeof value === "string";
const flag: Check = (value) => typeof value === "boolean";
const nullable =
  (check: Check): Check =>
  (value) =>
    value === null || check(value);
const oneOf =
  (values: readonly string[]): Check =>
  (value) =>
    typeof value === "string" && values.includes(value);
const list =
  (check: Check): Check =>
  (value) =>
    Array.isArray(value) && value.every(check);
const isObject = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
/** Every field of `schema` is present and valid; fields a newer server adds are ignored. */
const has =
  (schema: Record<string, Check>): Check =>
  (value) =>
    isObject(value) &&
    Object.entries(schema).every(([key, check]) => Object.hasOwn(value, key) && check(value[key]));

const SUMMARY: Record<string, Check> = {
  id: string,
  command_id: string,
  mutating: flag,
  phase: oneOf(PHASES),
  cursor: count,
  done: flag,
  truncated: flag,
  returncode: nullable(Number.isSafeInteger),
  error: nullable(string),
};
const isSummary = has(SUMMARY);
const isSnapshot = has({ ...SUMMARY, output: list(has({ channel: string, text: string })) });
const isCommand = has({
  command_id: string,
  title: string,
  section: string,
  reversibility: oneOf(REVERSIBILITY),
  reversibility_label: string,
  needs_confirmation: flag,
  confirmation_reason: nullable(string),
  typed_confirmation: nullable(string),
  read_only: flag,
  inputs: list(string),
  plan_required: flag,
  available: flag,
});

export function parseJobSummary(value: unknown): JobSummary | null {
  return isSummary(value) ? (value as unknown as JobSummary) : null;
}

export function parseJobSnapshot(value: unknown): JobSnapshot | null {
  if (!isSnapshot(value)) return null;
  const snapshot = value as unknown as JobSnapshot;
  return snapshot.output.length <= snapshot.cursor ? snapshot : null;
}

export function parseCommands(value: unknown): CommandDescriptor[] | null {
  return list(isCommand)(value) ? (value as CommandDescriptor[]) : null;
}

/** The local job after `snapshot`. Its batch starts at `snapshot.cursor - output.length`: a
    batch that starts at or before the held cursor adds only the fragments past it; one that
    starts after it is a gap, and the caller resubscribes from the held cursor. */
export function mergeOutput(
  local: LocalJob | null,
  snapshot: JobSnapshot,
): { job: LocalJob; gap: boolean } {
  if (local === null) {
    if (snapshot.cursor === snapshot.output.length) return { job: snapshot, gap: false };
    return { job: { ...snapshot, output: [], cursor: 0, done: false }, gap: true };
  }
  const start = snapshot.cursor - snapshot.output.length;
  if (start > local.cursor) return { job: local, gap: true };
  // Nothing new: an older reply keeps the local job, one at the same cursor brings its phase.
  if (snapshot.cursor < local.cursor) return { job: local, gap: false };
  if (snapshot.cursor === local.cursor) return { job: { ...snapshot, output: local.output }, gap: false };
  return {
    job: {
      ...snapshot,
      output: [...local.output, ...snapshot.output.slice(local.cursor - start)],
    },
    gap: false,
  };
}
