/* Presentation of the Reports page, ported from the TUI: harness/console/kernel/reports.py
   (`stage_status`, `batch_status`, `batch_start_text`, `batch_timing_text`, `select_stages`,
   `report_section_lines`, `qa_log_text`, `role_flow_text`), harness/console/kernel/status.py
   (`Status`) and harness/console/tui/stats.py (`reports_kpi_tiles`). The figures are the
   server's; these functions only word, filter and order them. tests/web/fixtures/reports-facts.json
   pins every text to the one the TUI shows for the same snapshot. */
import type { Language } from "../i18n";
import type { BatchSummary, BatchTimeline, Figures, Ledger, ReportBody, ReportHead, StageHead } from "../ws/ledger";

export type StatusKind = "accepted" | "running" | "paused" | "not_started" | "error" | "warning";

/** kernel/status.py KINDS: every status is a symbol plus text, never colour alone. */
export const SYMBOLS: Readonly<Record<StatusKind, string>> = {
  accepted: "✔",
  running: "▶",
  paused: "Ⅱ",
  not_started: "○",
  error: "✖",
  warning: "⚠",
};

export interface Status {
  kind: StatusKind;
  ru: string;
  en: string;
}

export const renderStatus = (status: Status, language: Language): string =>
  `${SYMBOLS[status.kind]} ${language === "en" ? status.en : status.ru}`;

const OUTCOMES: Readonly<Record<string, [StatusKind, string, string]>> = {
  completed: ["accepted", "завершено", "completed"],
  blocked: ["warning", "заблокировано", "blocked"],
  failed: ["error", "ошибка", "failed"],
};

const BATCH_STATES: Readonly<Record<string, [StatusKind, string, string]>> = {
  planned: ["not_started", "запланирован", "planned"],
  "awaiting-approval": ["not_started", "ждёт подтверждения", "awaiting approval"],
  active: ["running", "в работе", "in progress"],
  blocked: ["warning", "заблокирован", "blocked"],
  completed: ["accepted", "завершён", "completed"],
  failed: ["error", "провален", "failed"],
  "not-required": ["not_started", "не требуется", "not required"],
  abandoned: ["paused", "отменён", "abandoned"],
};

/** The reports of a ledger by dispatch id. */
export const reportsById = (ledger: Ledger): Map<string, ReportHead> =>
  new Map(ledger.reports.map((report) => [report.dispatch_id, report]));

/** A stage row's status: `✔ отчёт получен · завершено`, or `⚠ в работе · отчёта ещё нет`. */
export function stageStatus(stage: StageHead, report: ReportHead | undefined, narrow = false): Status {
  if (report === undefined) {
    const [ru, en] = stage.state === "working" ? ["в работе", "in progress"] : [stage.state, stage.state];
    return { kind: "warning", ru: `${ru} · отчёта ещё нет`, en: `${en} · no report yet` };
  }
  const [kind, ru, en] = OUTCOMES[report.outcome] ?? ["warning", report.outcome, report.outcome];
  const [wordRu, wordEn] = narrow ? ["отчёт", "report"] : ["отчёт получен", "report received"];
  return { kind, ru: `${wordRu} · ${ru}`, en: `${wordEn} · ${en}` };
}

export function batchStatus(batch: BatchSummary): Status {
  const [kind, ru, en] = BATCH_STATES[batch.state] ?? ["warning", batch.state, batch.state];
  return { kind, ru, en };
}

const ZONED = /(Z|[+-]\d{2}:?\d{2})$/i;

/** A recorded, timezone-aware time; a missing or invalid one stays unknown. */
export function timestamp(value: string): Date | null {
  if (!ZONED.test(value.trim())) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

const two = (value: number) => String(value).padStart(2, "0");

export function batchStartText(batch: BatchSummary): string {
  const start = timestamp(batch.created_at);
  if (!start) return "начало: неизвестно";
  return `${two(start.getUTCDate())}.${two(start.getUTCMonth() + 1)}.${start.getUTCFullYear()} ${two(start.getUTCHours())}:${two(start.getUTCMinutes())} UTC`;
}

/** Elapsed wall time to PR creation, never inferred from publish or merge. */
export function batchTimingText(batch: BatchSummary, language: Language): string {
  const en = language === "en";
  if (batch.pr_state === "missing") return en ? "PR has not been created" : "PR ещё не создан";
  const unknown = en ? "to PR: unknown" : "до PR: неизвестно";
  if (batch.pr_state !== "found") return unknown;
  const start = timestamp(batch.created_at);
  const end = timestamp(batch.pr_created_at);
  if (!start || !end || end < start) return unknown;
  const seconds = Math.floor((end.getTime() - start.getTime()) / 1000);
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const units = en ? ["d", "h", "min", "s"] : ["д", "ч", "мин", "с"];
  const parts = [
    [days, units[0]],
    [hours, units[1]],
    [minutes, units[2]],
  ]
    .filter(([count]) => count)
    .map(([count, unit]) => `${count} ${unit}`);
  return (en ? "to PR: " : "до PR: ") + (parts.length ? parts.join(" ") : `${seconds} ${units[3]}`);
}

export interface StageFilters {
  ticket: string;
  role: string;
  outcome: string;
  date: string;
  state: string;
  completion: "all" | "open" | "finished";
  sortBy: "time" | "ticket" | "role" | "state";
  descending: boolean;
}

export const NO_FILTERS: StageFilters = {
  ticket: "",
  role: "",
  outcome: "",
  date: "",
  state: "",
  completion: "all",
  sortBy: "time",
  descending: true,
};

const FINISHED_STATES = new Set(["reported", "cancelled", "failed", "abandoned"]);
const finished = (stage: StageHead) => stage.report !== null || FINISHED_STATES.has(stage.state);
const byText = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

/** Combined filters and a stable order; unknown times always go last (`select_stages`). */
export function selectStages(
  stages: readonly StageHead[],
  reports: Map<string, ReportHead>,
  filters: StageFilters,
): StageHead[] {
  const ticket = filters.ticket.trim().toLowerCase();
  const role = filters.role.trim().toLowerCase();
  const state = filters.state.trim().toLowerCase();
  const outcome = filters.outcome.trim().toLowerCase();
  const date = filters.date.trim();
  const shown = stages.filter((stage) => {
    const report = stage.report === null ? undefined : reports.get(stage.report);
    return (
      (!ticket || stage.ticket.toLowerCase().includes(ticket)) &&
      (!role || stage.role.toLowerCase().includes(role)) &&
      (!state || state === stage.state.toLowerCase()) &&
      (!outcome || (report !== undefined && outcome === report.outcome.toLowerCase())) &&
      (!date || stage.at.startsWith(date)) &&
      (filters.completion !== "open" || !finished(stage)) &&
      (filters.completion !== "finished" || finished(stage))
    );
  });
  shown.sort((a, b) => byText(a.dispatch_id, b.dispatch_id));
  const sign = filters.descending ? -1 : 1;
  if (filters.sortBy === "time") {
    const known = shown.filter((stage) => timestamp(stage.at) !== null);
    const unknown = shown.filter((stage) => timestamp(stage.at) === null);
    known.sort((a, b) => sign * (timestamp(a.at)!.getTime() - timestamp(b.at)!.getTime()));
    return [...known, ...unknown];
  }
  if (filters.sortBy === "ticket") {
    const key = (stage: StageHead): [number, number, string] => {
      const match = /^#?(\d+)$/.exec(stage.ticket);
      return match ? [0, Number(match[1]), ""] : [1, 0, stage.ticket.toLowerCase()];
    };
    return shown.sort((a, b) => {
      const [x, y] = [key(a), key(b)];
      return sign * (x[0] - y[0] || x[1] - y[1] || byText(x[2], y[2]));
    });
  }
  const field = (stage: StageHead) => (filters.sortBy === "role" ? stage.role : stage.state).toLowerCase();
  return shown.sort((a, b) => sign * byText(field(a), field(b)));
}

/* -- report sections -------------------------------------------------------------------------- */

export type ReportLine = [Status | null, string];

const text = (value: unknown, fallback = ""): string => (typeof value === "string" ? value : fallback);
const objects = (value: unknown): Record<string, unknown>[] =>
  Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => item !== null && typeof item === "object" && !Array.isArray(item))
    : [];
const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);

const REVIEW_SEVERITIES: Readonly<Record<string, StatusKind>> = {
  none: "accepted",
  clean: "accepted",
  warning: "warning",
  blocker: "error",
};
const CHECK_RESULTS: Readonly<Record<string, StatusKind>> = { pass: "accepted", fail: "error", not_run: "not_started" };

function checksText(report: ReportBody): string {
  const checks = objects(report.checks_run);
  if (!checks.length) return "проверки не запускались";
  return checks
    .map((check) => `• ${text(check.command, "?")} — ${text(check.result, "?")}: ${text(check.evidence)}`)
    .join("\n");
}

function reviewText(review: Record<string, unknown>): string {
  const lines = [`candidate: ${text(review.candidate_commit, "?")}`];
  for (const axis of ["standards", "spec"]) {
    const evidence = review[axis];
    if (!isRecord(evidence)) continue;
    const findings = objects(evidence.findings);
    lines.push(`${axis}: ${text(evidence.severity, "?")}, находок: ${findings.length}`);
    for (const item of findings) {
      lines.push(`  [${text(item.severity, "?")}] ${text(item.summary)}: ${text(item.evidence)}`);
    }
  }
  return lines.join("\n");
}

function evidenceSummary(value: unknown): string {
  if (isRecord(value) && Object.keys(value).length === 2 && value.status === "none" && value.details === "") {
    return "none";
  }
  if (isRecord(value) && value.status === "present") return text(value.details);
  return "";
}

/** `report_sections`: the named sections of a report body in reading order. */
export function reportSections(report: ReportBody): [string, string][] {
  const sections: [string, string][] = [
    ["Output", text(report.output)],
    ["Checks", checksText(report)],
  ];
  if (isRecord(report.review)) sections.push(["Review", reviewText(report.review)]);
  sections.push(
    ["Risks", evidenceSummary(report.risks)],
    ["Blockers", evidenceSummary(report.blockers)],
    ["Next action", text(report.next_coordinator_action)],
  );
  return sections;
}

function checkLines(report: ReportBody): ReportLine[] {
  const lines: ReportLine[] = objects(report.checks_run).map((check) => {
    const result = text(check.result, "?");
    const evidence = text(check.evidence);
    const command = text(check.command, "?");
    return [
      { kind: CHECK_RESULTS[result] ?? "warning", ru: result, en: result },
      evidence ? `${command} — ${evidence}` : command,
    ];
  });
  return lines.length ? lines : [[null, checksText(report)]];
}

function reviewLines(review: Record<string, unknown>): ReportLine[] {
  const lines: ReportLine[] = [[null, `candidate: ${text(review.candidate_commit, "?")}`]];
  for (const axis of ["standards", "spec"]) {
    const evidence = review[axis];
    if (!isRecord(evidence)) continue;
    const findings = objects(evidence.findings);
    const severity = text(evidence.severity, "?");
    lines.push([
      { kind: REVIEW_SEVERITIES[severity] ?? "warning", ru: severity, en: severity },
      `${axis} · находок: ${findings.length}`,
    ]);
    for (const item of findings) {
      lines.push([null, `  [${text(item.severity, "?")}] ${text(item.summary)}: ${text(item.evidence)}`]);
    }
  }
  return lines;
}

function evidenceLine(body: string): ReportLine {
  if (body === "none") return [{ kind: "accepted", ru: "нет", en: "none" }, ""];
  if (body) return [{ kind: "warning", ru: "есть", en: "present" }, body];
  return [{ kind: "not_started", ru: "не указано", en: "not stated" }, ""];
}

/** `report_section_lines`: every section as lines; a check, a review axis, a risk and a blocker
    line carry a status. */
export function reportSectionLines(report: ReportBody): [string, ReportLine[]][] {
  return reportSections(report).map(([title, body]) => {
    if (title === "Checks") return [title, checkLines(report)];
    if (title === "Review" && isRecord(report.review)) return [title, reviewLines(report.review)];
    if (title === "Risks" || title === "Blockers") return [title, [evidenceLine(body)]];
    return [title, [[null, body || "—"]]];
  });
}

/* -- QA log and chronology -------------------------------------------------------------------- */

/** `qa_log_text`: the failed qa-lane attempts and every QA gate run of a dispatch, or "". */
export function qaLogText(ledger: Ledger, dispatchId: string): string {
  const runs = ledger.qa_runs.filter((run) => run.dispatch_id === dispatchId);
  const attempts = ledger.qa_attempts.filter((item) => item.dispatch_id === dispatchId);
  if (!runs.length && !attempts.length) return "";
  const attemptsText = [
    `попытки qa-lane: ${attempts.length}`,
    ...attempts.map(
      (attempt) => `  ${attempt.failed_at || "время ?"} · ${attempt.dispatch_id} · ${attempt.stage}: ${attempt.message}`,
    ),
  ].join("\n");
  const runTexts = runs.map((run) => {
    const failed = run.commands.filter(([, code]) => code !== 0);
    let summary = `итог: ${failed.length ? "failed" : "passed"} — команд ${run.commands.length}, с ошибкой ${failed.length}`;
    if (failed.length) summary += ` (${failed.map(([command, code]) => `${command}: exit ${code}`).join(", ")})`;
    return [
      `${run.artifact} · ${run.logged_at || "время ?"} · ${run.dispatch_id || "без отчёта"} · ${run.ticket} · отчёт: ${run.outcome}`,
      summary,
      `хвост лога (последние ${run.tail.length} из ${run.total_lines} строк):`,
      ...run.tail.map((line) => `  ${line}`),
    ].join("\n");
  });
  return [attemptsText, ...runTexts].join("\n\n");
}

export const roleFlowText = (timeline: BatchTimeline): string =>
  timeline.role_flow.join(" → ") || "диспатчей ещё не было";

/* -- KPI tiles -------------------------------------------------------------------------------- */

/** `duration_text`: `3 ч 20 мин`, `2 дн 4 ч`; `—` without a figure. */
export function durationText(seconds: number | null | undefined, language: Language): string {
  if (seconds === null || seconds === undefined) return "—";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const [day, hour, minute] = language === "ru" ? ["дн", "ч", "мин"] : ["d", "h", "min"];
  if (days) return `${days} ${day} ${hours} ${hour}`;
  if (hours) return `${hours} ${hour} ${minutes} ${minute}`;
  return `${minutes} ${minute}`;
}

/** Python's `round`: halves go to the even neighbour, so `round(2.5)` is 2. */
export function pyRound(value: number): number {
  const floor = Math.floor(value);
  const diff = value - floor;
  if (Math.abs(diff - 0.5) < 1e-9) return floor % 2 === 0 ? floor : floor + 1;
  return Math.round(value);
}

export interface Tile {
  label: string;
  figure: string;
  hint: string;
  tone: "" | "warning" | "error";
}

const figure = (figures: Figures, key: string): number => figures[key] ?? 0;

/** `reports_kpi_tiles`: a figure that needs attention starts with its status symbol. */
export function reportsKpiTiles(kpi: Figures, t: (text: string) => string, language: Language): Tile[] {
  const share = (part: number, total: number) => (total ? `${part} / ${total}  (${pyRound((100 * part) / total)}%)` : "—");
  const flagged = (count: number): [string, Tile["tone"]] => (count ? [`⚠ ${count}`, "warning"] : [String(count), ""]);
  const reports = figure(kpi, "reports");
  const [risks, risksTone] = flagged(figure(kpi, "attention"));
  const [blockers, blockersTone] = flagged(figure(kpi, "blocked"));
  const latency = `${durationText(kpi.latency_p50_seconds, language)} / ${durationText(kpi.latency_p95_seconds, language)}`;
  return [
    { label: t("Отчётов"), figure: String(reports), hint: "", tone: "" },
    { label: t("Evidence полно"), figure: share(figure(kpi, "evidence_complete"), reports), hint: t("output, risks, blockers"), tone: "" },
    { label: t("Задержка отчёта"), figure: latency, hint: "p50 / p95", tone: "" },
    { label: t("QA с первого раза"), figure: share(figure(kpi, "qa_first_pass"), figure(kpi, "qa_tickets")), hint: t("по тикетам"), tone: "" },
    { label: t("С рисками"), figure: risks, hint: t("отчёты с записанным риском"), tone: risksTone },
    { label: t("С блокерами"), figure: blockers, hint: t("отчёты с блокером"), tone: blockersTone },
  ];
}

/** A dispatch or batch id without its common prefix, as the TUI lists it. */
export const shortId = (value: string, prefix: string): string =>
  (value.startsWith(prefix) ? value.slice(prefix.length) : value).slice(0, 8);
