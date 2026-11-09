/* Read models of task_board.specs and task_board.snapshot (#913). The server builds the columns,
   the card order and the prompt; the page only checks the shape of the fields it shows. */

/** The server's snapshot TTL (`BOARD_TTL_SECONDS` in backend/domain/task_board.py). */
export const BOARD_TTL_MS = 60000;

export const BOARD_COLUMNS = ["backlog", "ready", "progress", "review", "done"] as const;
export type BoardColumn = (typeof BOARD_COLUMNS)[number];

/** Why the tracker could not be read; the last good snapshot is shown with its age. */
export interface BoardStale {
  reason: string;
  message: string;
}

export interface BoardSpec {
  id: string;
  n: number | null;
  title: string;
  url: string | null;
  branch: string | null;
  tickets_total: number | null;
  tickets_open: number | null;
}

export interface BoardSpecs {
  tracker: string;
  stale: BoardStale | null;
  age_seconds: number | null;
  specs: BoardSpec[];
  truncated: boolean;
}

export interface BoardBlocker {
  id: string;
  n: number | null;
  why: string;
  state: "open" | "closed" | "unknown";
}

export interface BoardCard {
  id: string;
  n: number | null;
  title: string;
  url: string | null;
  closed: boolean;
  column: BoardColumn;
  labels: string[];
  priority: string | null;
  sp: number | null;
  command: string;
  branch: string | null;
  what: string;
  criteria: string[];
  files: { path: string; why: string }[];
  blockers: BoardBlocker[];
  open_blockers: number;
  pr: { ref: string; url: string | null } | null;
  batch: string | null;
  batch_state: string | null;
  dispatch: string | null;
  dispatch_state: string | null;
  prompt: string;
  truncated: boolean;
}

export interface TaskBoard {
  tracker: string;
  stale: BoardStale | null;
  age_seconds: number | null;
  ledger: "ok" | "unavailable";
  spec: { id: string; n: number | null; title: string; url: string | null; branch: string | null };
  columns: { id: BoardColumn; count: number }[];
  kpis: { open: number; total: number; with_open_blockers: number; active_batch: number };
  tickets: BoardCard[];
  truncated: boolean;
}

const object = (v: unknown): v is Record<string, unknown> =>
  v !== null && typeof v === "object" && !Array.isArray(v);
const text = (v: unknown): v is string => typeof v === "string";
const count = (v: unknown): v is number => Number.isSafeInteger(v) && Number(v) >= 0;
const optionalText = (v: unknown) => v === null || text(v);
const optionalCount = (v: unknown) => v === null || count(v);
const optionalAge = (v: unknown) => v === null || (typeof v === "number" && Number.isFinite(v) && v >= 0);
const texts = (v: unknown): v is string[] => Array.isArray(v) && v.every(text);
const column = (v: unknown): v is BoardColumn => BOARD_COLUMNS.includes(v as BoardColumn);

const stale = (v: unknown) => v === null || (object(v) && text(v.reason) && text(v.message));

const facts = (v: Record<string, unknown>) =>
  text(v.tracker) && stale(v.stale) && optionalAge(v.age_seconds) && typeof v.truncated === "boolean";

const spec = (v: unknown) =>
  object(v) && text(v.id) && optionalCount(v.n) && text(v.title) && optionalText(v.url) && optionalText(v.branch);

const blocker = (v: unknown) =>
  object(v) && text(v.id) && optionalCount(v.n) && text(v.why) && ["open", "closed", "unknown"].includes(String(v.state));

const card = (v: unknown) =>
  object(v) && text(v.id) && optionalCount(v.n) && text(v.title) && optionalText(v.url) &&
  typeof v.closed === "boolean" && column(v.column) && texts(v.labels) && optionalText(v.priority) &&
  optionalCount(v.sp) && text(v.command) && optionalText(v.branch) && text(v.what) && texts(v.criteria) &&
  Array.isArray(v.files) && v.files.every((f) => object(f) && text(f.path) && text(f.why)) &&
  Array.isArray(v.blockers) && v.blockers.every(blocker) && count(v.open_blockers) &&
  (v.pr === null || (object(v.pr) && text(v.pr.ref) && optionalText(v.pr.url))) &&
  optionalText(v.batch) && optionalText(v.batch_state) && optionalText(v.dispatch) &&
  optionalText(v.dispatch_state) && text(v.prompt) && typeof v.truncated === "boolean";

/** The open specs, or null for another shape. */
export function parseSpecs(v: unknown): BoardSpecs | null {
  if (!object(v) || !facts(v) || !Array.isArray(v.specs)) return null;
  const valid = v.specs.every(
    (s) => spec(s) && optionalCount((s as Record<string, unknown>).tickets_total) &&
      optionalCount((s as Record<string, unknown>).tickets_open),
  );
  return valid ? (v as unknown as BoardSpecs) : null;
}

/** The board of one spec, or null for another shape. */
export function parseBoard(v: unknown): TaskBoard | null {
  if (!object(v) || !facts(v) || !["ok", "unavailable"].includes(String(v.ledger)) || !spec(v.spec)) return null;
  const columns = v.columns;
  if (!Array.isArray(columns) || columns.length !== BOARD_COLUMNS.length ||
      !columns.every((c, i) => object(c) && c.id === BOARD_COLUMNS[i] && count(c.count))) return null;
  const k = v.kpis;
  if (!object(k) || !count(k.open) || !count(k.total) || !count(k.with_open_blockers) ||
      !count(k.active_batch)) return null;
  if (!Array.isArray(v.tickets) || !v.tickets.every(card)) return null;
  return v as unknown as TaskBoard;
}
