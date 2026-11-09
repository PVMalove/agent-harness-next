/* Presentation of the Orchestration page, ported from harness/console/tui/stats.py (`kpi_tiles`,
   `analytics_rows`, `pipeline_stats_fields`, `state_filter_items`, `batch_label`),
   harness/console/kernel/pipeline_stats.py (`pipeline_stats`) and harness/console/tui/ledger_lock.py
   (`lock_text`). Every KPI and analytics figure is the server's; these functions only word and
   count the served ledger lists, as the TUI does. tests/web/fixtures/orchestration-facts.json
   pins every text to the one the TUI shows for the same snapshot. */
import type { Language } from "../i18n";
import { durationText, pyRound } from "../reports/format";
import type { Tile } from "../reports/format";
import type { Analytics, AnalyticsSection, BatchSummary, Figure, Figures, Ledger } from "../ws/ledger";

type Translate = (text: string) => string;

/** The batch lifecycle in order: planned → awaiting-approval ↔ active → a terminal state. */
export const BATCH_STATES = [
  "planned",
  "awaiting-approval",
  "active",
  "blocked",
  "completed",
  "failed",
  "not-required",
  "abandoned",
] as const;
export const STATE_LABELS: Readonly<Record<string, string>> = {
  planned: "запланирован",
  "awaiting-approval": "ждёт подтверждения",
  active: "в работе",
  blocked: "заблокирован",
  completed: "завершён",
  failed: "провален",
  "not-required": "не требуется",
  abandoned: "отменён",
};
export const ALL_STATES = "all";

const byText = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);

/** An ISO timestamp as `YYYY-MM-DD HH:MM`; anything else unchanged. */
export const shortTime = (value: string): string =>
  value.length >= 16 && value[10] === "T" ? value.slice(0, 16).replace("T", " ") : value;

/* -- KPI tiles -------------------------------------------------------------------------------- */

/** `kpi_tiles`: a figure that needs attention starts with its status symbol. */
export function kpiTiles(kpi: Figures, t: Translate, language: Language): Tile[] {
  const value = (key: string) => kpi[key] ?? 0;
  const flagged = (count: number): [string, Tile["tone"]] => (count ? [`⚠ ${count}`, "warning"] : [String(count), ""]);
  const duration = (key: string) => durationText(kpi[key], language);
  const [stale, staleTone] = flagged(value("stale"));
  const [blocked, blockedTone] = flagged(value("blocked"));
  const tickets = value("qa_tickets");
  const firstPass = tickets
    ? `${value("qa_first_pass")} / ${tickets}  (${pyRound((100 * value("qa_first_pass")) / tickets)}%)`
    : "—";
  return [
    { label: t("В работе (WIP)"), figure: String(value("wip")), hint: `${t("старейший")} ${duration("oldest_wip_seconds")}`, tone: "" },
    {
      label: t("Ждёт подтверждения"),
      figure: String(value("awaiting_approval")),
      hint: `${t("старейший")} ${duration("oldest_approval_seconds")}`,
      tone: "",
    },
    { label: t("Заблокировано"), figure: blocked, hint: "", tone: blockedTone },
    { label: t("Без движения"), figure: stale, hint: t("активные > 6 ч"), tone: staleTone },
    { label: t("QA с первого раза"), figure: firstPass, hint: t("по тикетам"), tone: "" },
    { label: t("Доработки"), figure: String(value("rework")), hint: t("повторные диспатчи"), tone: "" },
    { label: t("Цикл до PR"), figure: `${duration("cycle_p50_seconds")} / ${duration("cycle_p95_seconds")}`, hint: "p50 / p95", tone: "" },
    {
      label: t("PR за 7 дней"),
      figure: String(value("throughput_7d")),
      hint: value("failed") ? `✖ ${t("провалено")} ${value("failed")}` : "",
      tone: "",
    },
  ];
}

/* -- analytics -------------------------------------------------------------------------------- */

export const ANALYTICS_TABS: readonly [AnalyticsSection, string][] = [
  ["flow", "Поток работ"],
  ["quality", "Качество"],
  ["runtime", "Runtime"],
  ["gates", "Гейты"],
];

const AGING_BUCKETS = ["lt_1d", "d1_3", "d3_7", "gt_7d"] as const;
const AGING: Readonly<Record<Language, Readonly<Record<string, string>>>> = {
  ru: { lt_1d: "< 1 дн", d1_3: "1–3 дн", d3_7: "3–7 дн", gt_7d: "> 7 дн" },
  en: { lt_1d: "< 1 d", d1_3: "1–3 d", d3_7: "3–7 d", gt_7d: "> 7 d" },
};
const SPARK = "▁▂▃▄▅▆▇█";

const isCounts = (value: Figure | undefined): value is Record<string, number> =>
  value !== null && value !== undefined && typeof value === "object" && !Array.isArray(value);

/** `name 3 · other 1`, the largest first; `—` for none. */
function countText(counts: Figure | undefined, labels: Readonly<Record<string, string>> = {}): string {
  if (!isCounts(counts) || !Object.keys(counts).length) return "—";
  return Object.entries(counts)
    .sort(([a, x], [b, y]) => y - x || byText(a, b))
    .map(([name, count]) => `${labels[name] ?? name} ${count}`)
    .join(" · ");
}

/** The seven daily counts as bars and numbers; `—` without any. */
function spark(values: Figure | undefined): string {
  if (!Array.isArray(values) || !values.some(Boolean)) return "—";
  const peak = Math.max(...values);
  const bars = values.map((value) => (value ? SPARK[pyRound(((SPARK.length - 1) * value) / peak)] : " ")).join("");
  return `${bars}  (${values.join(" ")})`;
}

const seconds = (value: Figure | undefined, language: Language) =>
  durationText(typeof value === "number" ? value : null, language);
const number = (value: Figure | undefined) => String(typeof value === "number" ? value : 0);

/** `analytics_rows`: (label, value) rows of one analytics tab; an empty section says so. */
export function analyticsRows(
  section: AnalyticsSection,
  analytics: Analytics,
  t: Translate,
  language: Language,
): [string, string][] {
  const figures = analytics[section];
  if (!Object.keys(figures).length) return [[t("Данные"), t("в ledger нет данных")]];
  if (section === "flow") {
    const buckets = figures.aging;
    const states = Object.fromEntries(Object.entries(STATE_LABELS).map(([key, label]) => [key, t(label)]));
    return [
      [t("Батчи по состояниям"), countText(figures.by_state, states)],
      [
        t("Возраст незавершённых"),
        isCounts(buckets) || buckets === undefined
          ? AGING_BUCKETS.map((name) => `${AGING[language][name]} ${(isCounts(buckets) ? buckets[name] : 0) ?? 0}`).join(" · ")
          : "—",
      ],
      [t("PR по дням, 7 дней"), spark(figures.pr_per_day)],
      [
        t("Цикл до PR p50 / p95"),
        `${seconds(figures.cycle_p50_seconds, language)} / ${seconds(figures.cycle_p95_seconds, language)}`,
      ],
    ];
  }
  if (section === "quality") {
    const passed = typeof figures.qa_first_pass === "number" ? figures.qa_first_pass : 0;
    const total = typeof figures.qa_tickets === "number" ? figures.qa_tickets : 0;
    return [
      [t("Доработки по ролям"), countText(figures.rework_by_role)],
      [t("Отчёты по ролям"), countText(figures.reports_by_role)],
      [t("Итоги отчётов"), countText(figures.outcomes)],
      [t("Неудачные попытки QA"), number(figures.qa_attempts_failed)],
      [t("QA с первого раза"), total ? `${passed} / ${total}` : "—"],
    ];
  }
  if (section === "runtime") {
    return [
      [t("Состояния стадий"), countText(figures.stage_states)],
      [t("Не завершено"), number(figures.unfinished)],
      [t("Старейшая не завершённая"), seconds(figures.oldest_unfinished_seconds, language)],
      [t("Без движения"), number(figures.stale)],
    ];
  }
  return [
    [t("Ждут подтверждения"), number(figures.awaiting)],
    [
      t("Ожидание p50 / p95"),
      `${seconds(figures.approval_p50_seconds, language)} / ${seconds(figures.approval_p95_seconds, language)}`,
    ],
    [t("Старейшее ожидание"), seconds(figures.approval_oldest_seconds, language)],
    [t("PR по состояниям"), countText(figures.pr_states)],
  ];
}

/* -- state and statistics --------------------------------------------------------------------- */

export interface PipelineStats {
  batches: number;
  tickets: number;
  byState: Map<string, number>;
  dispatchesByRole: Map<string, number>;
  reportsByOutcome: Map<string, number>;
  qaRuns: number;
  qaAttemptsFailed: number;
  firstAt: string;
  lastAt: string;
}

const counter = (values: readonly string[]): Map<string, number> => {
  const counts = new Map<string, number>();
  for (const value of values) counts.set(value, (counts.get(value) ?? 0) + 1);
  return counts;
};

/** `pipeline_stats`: how much the pipeline has been used, counted from the served lists. */
export function pipelineStats(ledger: Ledger): PipelineStats {
  const dates = ledger.batches.map((batch) => batch.created_at).filter(Boolean).sort(byText);
  return {
    batches: ledger.batches.length,
    tickets: new Set(ledger.batches.map((batch) => batch.ticket)).size,
    byState: counter(ledger.batches.map((batch) => batch.state)),
    dispatchesByRole: counter(Object.values(ledger.dispatches).map((record) => record.role ?? "?")),
    reportsByOutcome: counter(ledger.reports.map((report) => report.outcome)),
    qaRuns: ledger.qa_runs.length,
    qaAttemptsFailed: ledger.qa_attempts.length,
    firstAt: dates[0] ?? "",
    lastAt: dates.at(-1) ?? "",
  };
}

const counts = (values: Map<string, number>) =>
  [...values.entries()]
    .sort(([a], [b]) => byText(a, b))
    .map(([name, count]) => `${name} ${count}`)
    .join(", ") || "нет";

/** Known lifecycle states in lifecycle order, then any unknown state the ledger holds. */
const stateOrder = (byState: Map<string, number>): string[] => [
  ...BATCH_STATES.filter((state) => byState.get(state)),
  ...[...byState.keys()].filter((state) => !(BATCH_STATES as readonly string[]).includes(state)).sort(byText),
];

/** `pipeline_stats_fields`: (label, value) of each statistics line; none without a batch. */
export function pipelineStatsFields(stats: PipelineStats): [string, string][] {
  if (!stats.batches) return [];
  const states = stateOrder(stats.byState)
    .map((state) => `${STATE_LABELS[state] ?? state} ${stats.byState.get(state)}`)
    .join(", ");
  const period = `${shortTime(stats.firstAt) || "?"} — ${shortTime(stats.lastAt) || "?"}`;
  return [
    ["Запусков (batch)", `${stats.batches}, тикетов: ${stats.tickets}`],
    ["По состояниям", states],
    ["Диспатчи по ролям", counts(stats.dispatchesByRole)],
    ["Отчёты по итогам", counts(stats.reportsByOutcome)],
    ["QA-прогонов", `${stats.qaRuns}, неудачных попыток qa-lane: ${stats.qaAttemptsFailed}`],
    ["Период", period],
  ];
}

/** `state_filter_items`: every lifecycle state with its count, "all" first. */
export function stateFilterItems(ledger: Ledger): [string, string][] {
  const found = counter(ledger.batches.map((batch) => batch.state));
  const states = [
    ...BATCH_STATES,
    ...[...found.keys()].filter((state) => !(BATCH_STATES as readonly string[]).includes(state)).sort(byText),
  ];
  return [
    [ALL_STATES, `все (${ledger.batches.length})`],
    ...states.map((state): [string, string] => [state, `${STATE_LABELS[state] ?? state} (${found.get(state) ?? 0})`]),
  ];
}

export const batchesInState = (ledger: Ledger, state: string): BatchSummary[] =>
  state === ALL_STATES ? [...ledger.batches] : ledger.batches.filter((batch) => batch.state === state);

/** `batch_label`: the ticket, state and start, then the batch id. */
export const batchLabel = (batch: BatchSummary): [string, string] => [
  `${batch.ticket} · ${STATE_LABELS[batch.state] ?? batch.state} · ${shortTime(batch.created_at) || "дата неизвестна"}`,
  batch.batch_id,
];

/* -- ledger lock ------------------------------------------------------------------------------ */

interface LockWords {
  free: string;
  held: string;
  noOperation: string;
  owner: string;
  ownerUnreadable: string;
  age: string;
  available: string;
  aliveTimeout: string;
  hostTimeout: string;
  verdict: string;
  unknownVerdict: string;
  release: string;
  unavailable: string;
  units: [string, string, string];
  lease: string;
  leaseFree: string;
  leaseStale: string;
  leaseUnavailable: string;
  verdicts: Readonly<Record<string, string>>;
}

const LOCK_WORDS: Readonly<Record<Language, LockWords>> = {
  ru: {
    free: "Lock ledger свободен.",
    held: "Lock ledger занят: {operation}",
    noOperation: "операция не записана",
    owner: "Владелец: pid {pid} · {host}{where}",
    ownerUnreadable: "Владелец: запись не читается",
    age: "Держится: {held} · до снятия по таймауту: {timeout}",
    available: "доступно",
    aliveTimeout: "{remaining} (таймаут не снимает живого владельца)",
    hostTimeout: "не применяется (владелец на другом хосте)",
    verdict: "Вердикт: {verdict}, {meaning}",
    unknownVerdict: "неизвестный вердикт",
    release:
      "Снять: «Снять lock ledger» (ledger release-lock; --force только с одобрением оператора и причиной)",
    unavailable: "Lock ledger: состояние недоступно: {error}",
    units: ["ч", "мин", "с"],
    lease: "Lease QA-lane: {owner} · fencing {token} · срок до {expires}{stale}",
    leaseFree: "Lease QA-lane свободен.",
    leaseStale: " · heartbeat пропущен",
    leaseUnavailable: "Lease QA-lane: состояние недоступно: {error}",
    verdicts: {
      "owner-alive": "владелец жив; живой владелец не снимается",
      "owner-dead": "владелец завершился; ledger release-lock снимет lock",
      "owner-in-other-environment":
        "владелец из другого PID-пространства или загрузки; pid не проверить, снятие по таймауту",
      "owner-on-another-host": "владелец на другом хосте; проверить его можно только там",
      "owner-unknown-recent": "запись владельца не читается; снятие по таймауту",
      "owner-unknown-stale": "владелец неизвестен, таймаут прошёл; ledger release-lock снимет lock",
      "owner-pid-reused": "pid владельца занят другим процессом; это не доказывает смерть, lease не снимается",
      "owner-unknown": "идентичность владельца неизвестна; снять может только оператор",
    },
  },
  en: {
    free: "The ledger lock is free.",
    held: "Ledger lock held: {operation}",
    noOperation: "operation not recorded",
    owner: "Owner: pid {pid} · {host}{where}",
    ownerUnreadable: "Owner: record cannot be read",
    age: "Held for: {held} · until the timeout release: {timeout}",
    available: "available",
    aliveTimeout: "{remaining} (the timeout never releases a live owner)",
    hostTimeout: "not applicable (owner on another host)",
    verdict: "Verdict: {verdict}, {meaning}",
    unknownVerdict: "unknown verdict",
    release:
      "Release: “Release the ledger lock” (ledger release-lock; --force only with an operator's approval and a reason)",
    unavailable: "Ledger lock: state unavailable: {error}",
    units: ["h", "min", "s"],
    lease: "QA lease: {owner} · fencing {token} · expires at {expires}{stale}",
    leaseFree: "The QA lease is free.",
    leaseStale: " · heartbeat missed",
    leaseUnavailable: "QA lease: state unavailable: {error}",
    verdicts: {
      "owner-alive": "the owner is alive; a live owner is never released",
      "owner-dead": "the owner has exited; ledger release-lock releases the lock",
      "owner-in-other-environment":
        "the owner is in another PID namespace or boot; its pid cannot be checked, released by the timeout",
      "owner-on-another-host": "the owner is on another host; only there can it be checked",
      "owner-unknown-recent": "the owner record cannot be read; released by the timeout",
      "owner-unknown-stale": "the owner is unknown and the timeout has passed; ledger release-lock releases it",
      "owner-pid-reused": "another process holds the owner's pid; that never proves death, so the lease stays",
      "owner-unknown": "the owner's identity is unknown; only an operator can release it",
    },
  },
};

const fill = (template: string, values: Readonly<Record<string, unknown>>) =>
  template.replace(/\{(\w+)\}/g, (_, name: string) => String(values[name] ?? "None"));
const pyText = (value: unknown) => (value === null || value === undefined ? "None" : String(value));
const asInt = (value: unknown) => (typeof value === "number" ? Math.trunc(value) : 0);

/** `duration` of ledger_lock.py: «1 ч 05 мин», «3 мин 20 с», «45 с». */
function lockDuration(total: number, language: Language): string {
  const [h, m, s] = LOCK_WORDS[language].units;
  const value = Math.max(0, total);
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const secs = value % 60;
  const two = (n: number) => String(n).padStart(2, "0");
  if (hours) return `${hours} ${h} ${two(minutes)} ${m}`;
  if (minutes) return `${minutes} ${m} ${two(secs)} ${s}`;
  return `${secs} ${s}`;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);

function leaseLines(lease: unknown, words: LockWords): string[] {
  if (lease === null) return [words.leaseFree];
  if (!isRecord(lease)) return [];
  if ("error" in lease) return [fill(words.leaseUnavailable, { error: pyText(lease.error) })];
  const owner = lease.owner;
  const who = isRecord(owner) ? `${pyText(owner.owner_kind)} ${pyText(owner.owner_id)}` : words.noOperation;
  const verdict = pyText(lease.verdict);
  return [
    fill(words.lease, {
      owner: who,
      token: pyText(lease.fencing_token),
      expires: pyText(lease.expires_at),
      stale: lease.stale_heartbeat ? words.leaseStale : "",
    }),
    fill(words.verdict, { verdict, meaning: words.verdicts[verdict] ?? words.unknownVerdict }),
  ];
}

/** `lock_text`: who holds the ledger lock, for how long, when and how it may be released; the
    error of a lock that could not be read. */
export function lockLines(lock: Record<string, unknown> | null, error: string | null, language: Language): string[] {
  const words = LOCK_WORDS[language];
  if (lock === null) return [fill(words.unavailable, { error: error ?? "состояние не сообщается" })];
  const lease = "qa_lease" in lock ? leaseLines(lock.qa_lease, words) : [];
  if (!lock.locked) return [words.free, ...lease];
  const held = asInt(lock.held_seconds);
  const remaining = asInt(lock.remaining_seconds);
  const verdict = pyText(lock.verdict);
  const timeout = lock.release_available
    ? words.available
    : verdict === "owner-alive"
      ? fill(words.aliveTimeout, { remaining: lockDuration(remaining, language) })
      : verdict === "owner-on-another-host"
        ? words.hostTimeout
        : lockDuration(remaining, language);
  const owner = lock.owner;
  const ownerLine = isRecord(owner)
    ? fill(words.owner, {
        pid: pyText(owner.pid),
        host: pyText(owner.host),
        where: typeof owner.pid_namespace === "string" ? ` · ${owner.pid_namespace}` : "",
      })
    : words.ownerUnreadable;
  return [
    fill(words.held, { operation: lock.operation || words.noOperation }),
    ownerLine,
    fill(words.age, { held: lockDuration(held, language), timeout }),
    fill(words.verdict, { verdict, meaning: words.verdicts[verdict] ?? words.unknownVerdict }),
    words.release,
    ...lease,
  ];
}
