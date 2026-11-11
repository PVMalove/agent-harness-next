/* The mockup's Agent activity blocks over the live roster and the ledger snapshot: the summary,
   the KPI row, the session route, the timeline and the statistics. Counts come from the roster
   or the server's analytics; a figure without a source shows an explicit no-data state. */
import { Icon } from "../icons";
import { compactDuration, useI18n } from "../i18n";
import type { Language } from "../i18n";
import { href } from "../navigation";
import type { Analytics, Ledger, StageHead } from "../ws/ledger";
import type { HeldStep, RosterDispatch } from "../ws/steps";

export type SessionStatus = "running" | "blocked" | "awaiting" | "other";

/** The mockup's status of one roster entry. */
export function sessionStatus(entry: RosterDispatch): SessionStatus {
  if (entry.state === "failed" || entry.state === "blocked" || entry.batch_state === "blocked") return "blocked";
  if (entry.state === "working" || entry.state === "dispatched") return "running";
  if (entry.batch_state === "awaiting_approval" || entry.state === "reported" || entry.state === "approved") {
    return "awaiting";
  }
  return "other";
}

export const STATUS_TONE: Record<SessionStatus, string> = { running: "ok", blocked: "err", awaiting: "warn", other: "" };

/** The mockup's status icons and labels of a session; "other" keeps the state's own label. */
export const STATUS_ICON: Record<SessionStatus, string> = { running: "play", blocked: "blocked", awaiting: "awaiting", other: "completed" };
export const STATUS_LABEL: Record<Exclude<SessionStatus, "other">, string> = {
  running: "Выполняется",
  blocked: "Заблокировано",
  awaiting: "Ждёт решения",
};

/** The mockup's role names and icons; a role without one keeps its own name and the activity glyph. */
export const ROLE_NAMES: Record<string, string> = {
  architect: "Architect",
  developer: "Developer",
  "code-review": "Review",
  review: "Review",
  qa: "QA",
};
export const ROLE_ICON: Record<string, string> = {
  architect: "architect",
  developer: "developer",
  "code-review": "review",
  review: "review",
  qa: "qa",
};
export const roleName = (role: string): string => ROLE_NAMES[role] ?? role;
export const roleIcon = (role: string): string => ROLE_ICON[role] ?? "activity";

export function statusCounts(dispatches: readonly RosterDispatch[]): Record<"all" | SessionStatus, number> {
  const counts = { all: dispatches.length, running: 0, blocked: 0, awaiting: 0, other: 0 };
  for (const entry of dispatches) counts[sessionStatus(entry)] += 1;
  return counts;
}

/** The mockup's list limits: the latest sessions, session events and steps shown at once. */
export const SESSION_LIMIT = 5;
export const EVENT_LIMIT = 10;
export const STEP_LIMIT = 10;

/** Whole minutes between an ISO time and `now`; null for an unknown time. */
export function ageMinutes(iso: string, now: number): number | null {
  const at = Date.parse(iso);
  return iso && !Number.isNaN(at) ? Math.max(0, Math.round((now - at) / 60000)) : null;
}

/** Whole minutes in the console's duration wording (`2 ч 7 мин`), `—` when unknown. */
export const formatMinutes = (minutes: number | null, language: Language): string =>
  minutes === null ? "—" : compactDuration(minutes * 60, language);

/** The mockup's bar: the share of `value` in `max`, at least 3% when not zero. */
export function Bar({ value, max, tone = "cyan" }: { value: number; max: number; tone?: string }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <span className="orch-bar">
      <i className={tone} style={{ width: `${value ? Math.max(3, pct) : 0}%` }} />
    </span>
  );
}

export function NoData({ why }: { why?: string }) {
  const { t } = useI18n();
  return (
    <span className="muted no-data" title={why ?? t("Недоступно в текущем снимке")}>
      {t("нет данных")}
    </span>
  );
}

export function WorkSummary({ dispatches }: { dispatches: readonly RosterDispatch[] }) {
  const { t } = useI18n();
  const counts = statusCounts(dispatches);
  return (
    <div className="work-summary" id="work-summary">
      <div>
        <span>{t("Сессии")}</span>
        <b>{counts.all}</b>
        <small>{t("в наблюдении")}</small>
      </div>
      <div>
        <span>{t("Выполняется")}</span>
        <b className="ok">{counts.running}</b>
        <small>{t("живой шаг")}</small>
      </div>
      <div>
        <span>{t("Заблокировано")}</span>
        <b className="err">{counts.blocked}</b>
        <small>{t("нужно решение")}</small>
      </div>
      <div>
        <span>{t("Ждёт решения")}</span>
        <b className="warn">{counts.awaiting}</b>
        <small>{t("не начат следующий шаг")}</small>
      </div>
    </div>
  );
}

const sum = (figure: unknown): number | null =>
  figure && typeof figure === "object" && !Array.isArray(figure)
    ? Object.values(figure as Record<string, number>).reduce((total, value) => total + value, 0)
    : null;

export function WorkKpis({
  dispatches,
  analytics,
  now,
}: {
  dispatches: readonly RosterDispatch[];
  analytics: Analytics | null;
  now: number;
}) {
  const { t, language } = useI18n();
  const times = dispatches.map((entry) => entry.last_event_at).filter(Boolean).sort();
  const last = times.length ? times[times.length - 1]! : "";
  const silent = dispatches.filter((entry) => entry.silent).length;
  const running = dispatches.filter((entry) => sessionStatus(entry) === "running" && entry.started_at);
  const oldest = running.reduce<RosterDispatch | null>(
    (found, entry) => (found === null || entry.started_at < found.started_at ? entry : found),
    null,
  );
  const retries = analytics ? sum(analytics.quality.rework_by_role) : null;
  return (
    <div className="work-kpis" id="work-kpis">
      <div>
        <span>{t("Последнее событие")}</span>
        <b className="cyan">{last ? last.slice(11, 19) : <NoData />}</b>
        <small>{t("наблюдаемый факт")}</small>
      </div>
      <div>
        <span>{t("Тишина")}</span>
        <b className="violet">{silent}</b>
        <small>{t("сессий молчит")}</small>
      </div>
      <div>
        <span>{t("Возраст шага")}</span>
        <b className="blue">{oldest ? formatMinutes(ageMinutes(oldest.started_at, now), language) : <NoData />}</b>
        <small>{oldest ? `${oldest.role} · ${oldest.ticket || oldest.batch_id}` : t("нет живого шага")}</small>
      </div>
      <div>
        <span>{t("Повторы")}</span>
        <b className="lavender">{retries === null ? <NoData /> : retries}</b>
        <small>{t("по данным ledger")}</small>
      </div>
    </div>
  );
}

const ROUTE: [string, string[], string][] = [
  ["Architect", ["architect"], "architect"],
  ["Developer", ["developer"], "developer"],
  ["Review", ["review", "code-review"], "review"],
  ["QA", ["qa"], "qa"],
];

/** The route of the selected session's batch: Architect -> Developer -> Review -> QA -> PR. */
export function SessionRoute({
  session,
  dispatches,
  prState,
  now,
}: {
  session: RosterDispatch | null;
  dispatches: readonly RosterDispatch[];
  prState: string | null;
  now: number;
}) {
  const { t, language, section, state: stateText } = useI18n();
  if (!session) {
    return (
      <section className="panel work-route-panel" id="work-route">
        <div className="work-empty">{t("Выберите сессию слева.")}</div>
      </section>
    );
  }
  const batch = dispatches.filter((entry) => entry.batch_id === session.batch_id);
  const tone = STATUS_TONE[sessionStatus(session)];
  const steps = ROUTE.map(([name, roles, icon]) => {
    const entry = batch.filter((item) => roles.includes(item.role)).at(-1);
    const state = !entry ? "pending" : sessionStatus(entry) === "running" ? "current" : "done";
    return { name, state, icon, label: entry ? stateText(entry.state) : t("Не начат") };
  });
  steps.push({ name: "PR", state: prState ? "done" : "pending", icon: "pr", label: prState ? stateText(prState) : t("нет данных") });
  const current = steps.find((step) => step.state === "current") ?? null;
  return (
    <section className="panel work-route-panel" id="work-route">
      <div className="panel-head">
        <h2>{t("Маршрут сессии {id}", { id: session.ticket || session.batch_id })}</h2>
        <span className={`work-status ${tone}`}>{stateText(session.state)}</span>
      </div>
      <div className="work-route-body">
        <div className="work-task-meta">
          <span>
            <Icon name={roleIcon(session.role)} /> {roleName(session.role)}
          </span>
          <span className="branch-inline">
            <Icon name="branch" />
            <b>{session.branch || "—"}</b>
          </span>
          <span>
            <Icon name="clock" /> {formatMinutes(ageMinutes(session.started_at, now), language)}
            {session.started_at ? ` · ${t("старт")} ${session.started_at.slice(11, 16)}` : ""}
          </span>
        </div>
        <div className="work-flow-scroll" tabIndex={0} role="region" aria-label={t("Маршрут сессии")}>
          <div className="work-flow">
            {steps.map((step, index) => (
              <span key={step.name} style={{ display: "contents" }}>
                <div
                  // A new key on a step change replays the mockup's step transition (off under reduced motion).
                  key={`${step.name}-${step.state}`}
                  className={`work-flow-node ${step.state} ${step.state === "current" ? tone : ""}`}
                  data-step={step.name}
                >
                  <span className="work-flow-icon">
                    <Icon name={step.icon} />
                  </span>
                  <b>{step.name}</b>
                  <small>{step.label}</small>
                </div>
                {index < steps.length - 1 ? (
                  <div
                    className={`work-flow-edge ${steps[index + 1]!.state === "current" ? `active ${tone}` : step.state === "done" && steps[index + 1]!.state === "done" ? "done" : ""}`}
                  />
                ) : null}
              </span>
            ))}
          </div>
        </div>
        <div className={`work-current ${tone}`}>
          <span>{t("Текущий шаг")}</span>
          <b>{current ? current.name : "—"}</b>
          <small>{current ? current.label : t("нет живого шага")}</small>
        </div>
        <div className="work-route-actions">
          {session.ticket && (
            <a className="btn" href={`${href("board")}?ticket=${encodeURIComponent(session.ticket)}`}>
              <Icon name="board" /> {t("Открыть задачу")}
            </a>
          )}
          <a className="btn" href={href("orchestration")}>
            {section("Orchestration")} <Icon name="chevron" />
          </a>
        </div>
      </div>
    </section>
  );
}

interface Segment {
  role: string;
  from: number;
  to: number;
  tone: string;
}

/** The ledger states that wait for a start or a decision (the mockup's blue «ожидание»). */
const WAITING = new Set(["approved", "awaiting_approval", "queued"]);
/** A live stage whose worker has not sent a heartbeat for this long is shown as silent. */
const SILENT_MINUTES = 15;

export interface TimelineRow {
  batch: string;
  ticket: string;
  /** Minutes from the batch's first stage to its last end (or now). */
  total: number;
  segments: Segment[];
  /** Minutes since the last recorded event or heartbeat; null when none is known. */
  last: number | null;
  silent: boolean;
}

/** The timeline rows of the ledger stages, one row per batch, minutes from its first stage. */
export function timelineRows(stages: readonly StageHead[], now: number): TimelineRow[] {
  const byBatch = new Map<string, StageHead[]>();
  for (const stage of stages) {
    if (!stage.started_at) continue;
    byBatch.set(stage.batch_id, [...(byBatch.get(stage.batch_id) ?? []), stage]);
  }
  return [...byBatch.entries()].map(([batch, items]) => {
    const start = Math.min(...items.map((item) => Date.parse(item.started_at)));
    const segments = items.map((item) => {
      const open = item.state === "working" || item.state === "dispatched";
      const end = open ? now : Date.parse(item.at) || now;
      const from = Math.round((Date.parse(item.started_at) - start) / 60000);
      return {
        role: item.role,
        from,
        to: Math.max(from + 1, Math.round((end - start) / 60000)),
        tone: open ? "cyan" : item.state === "failed" || item.state === "blocked" ? "violet" : WAITING.has(item.state) ? "blue" : "mint",
      };
    });
    const times = items.flatMap((item) => [Date.parse(item.at), Date.parse(item.heartbeat_at)]).filter((time) => !Number.isNaN(time));
    const last = times.length ? Math.max(0, Math.round((now - Math.max(...times)) / 60000)) : null;
    const live = items.filter((item) => item.state === "working" || item.state === "dispatched");
    const silent = live.some((item) => {
      const beat = Date.parse(item.heartbeat_at || item.started_at);
      return !Number.isNaN(beat) && now - beat > SILENT_MINUTES * 60000;
    });
    return { batch, ticket: items[0]!.ticket, total: Math.max(...segments.map((segment) => segment.to)), segments, last, silent };
  });
}

const AXIS_STEPS = [5, 10, 15, 30, 60, 120, 240, 480, 720, 1440, 2880, 10080];

/** The time axis of the timeline: a tick step from 5 minutes to a week so that at most six steps
    cover the longest row, and its labels in minutes or hours. */
export function timelineAxis(longest: number, language: Language): { span: number; ticks: { at: number; label: string }[] } {
  const step = AXIS_STEPS.find((candidate) => longest / candidate <= 6) ?? AXIS_STEPS.at(-1)!;
  const span = Math.max(step, Math.ceil(longest / step) * step);
  const [minute, hour] = language === "ru" ? ["м", "ч"] : ["m", "h"];
  const ticks = [];
  for (let at = 0; at <= span; at += step) ticks.push({ at, label: step < 60 ? `${at}${minute}` : `${at / 60}${hour}` });
  return { span, ticks };
}

export function ActivityTimeline({ ledger, now }: { ledger: Ledger | null; now: number }) {
  const { t, language } = useI18n();
  const rows = ledger ? timelineRows(ledger.stages, now) : [];
  const axis = timelineAxis(Math.max(1, ...rows.map((row) => row.total)), language);
  const max = axis.span;
  return (
    <section className="panel work-analytics" id="work-timeline">
      <div className="panel-head">
        <h2>{t("Таймлайн")}</h2>
        <span className="small muted">{t("прошлое и текущий шаг · без внутренних рассуждений")}</span>
      </div>
      {rows.length === 0 ? (
        <div className="work-empty">{ledger ? t("Этапов с временем начала нет") : t("нет данных")}</div>
      ) : (
        <div className="work-gantt" tabIndex={0} role="region" aria-label={t("Таймлайн")}>
          <div className="work-gantt-axis">
            <span />
            <div className="work-gantt-ticks">
              {axis.ticks.map((tick) => (
                <span key={tick.at} style={{ left: `${(tick.at / max) * 100}%` }}>
                  {tick.label}
                </span>
              ))}
            </div>
            <span>{t("последнее")}</span>
          </div>
          {rows.map((row) => (
            <div className="work-gantt-row" key={row.batch}>
              <div className="work-gantt-name">
                <b>{row.ticket || row.batch}</b>
                <small>{formatMinutes(row.total, language)}</small>
              </div>
              <div className="work-gantt-track">
                {row.segments.map((segment, index) => (
                  <div
                    key={index}
                    className={`work-gantt-seg ${segment.tone}`}
                    style={{ left: `${(segment.from / max) * 100}%`, width: `${((segment.to - segment.from) / max) * 100}%` }}
                    title={`${segment.role} · ${segment.from}–${segment.to} ${t("мин")}`}
                  >
                    <span>{segment.role}</span>
                  </div>
                ))}
              </div>
              <div className={`work-gantt-last${row.silent ? " silent" : ""}`} title={row.last === null ? undefined : `${row.silent ? `${t("тишина")} ` : ""}${formatMinutes(row.last, language)}`}>
                {row.last === null ? "—" : `${row.silent ? `${t("тишина")} ` : ""}${formatMinutes(row.last, language)}`}
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="orch-legend">
        <span>
          <i className="mint" />
          {t("готово")}
        </span>
        <span>
          <i className="cyan" />
          {t("активно")}
        </span>
        <span>
          <i className="blue" />
          {t("ожидание")}
        </span>
        <span>
          <i className="violet" />
          {t("блок")}
        </span>
      </div>
    </section>
  );
}

const record = (figure: unknown): Record<string, number> =>
  figure && typeof figure === "object" && !Array.isArray(figure) ? (figure as Record<string, number>) : {};

function Rows({ values, tone, name = (key) => key }: { values: Record<string, number>; tone: string; name?: (key: string) => string }) {
  const { t } = useI18n();
  const entries = Object.entries(values);
  if (!entries.length) return <p className="orch-note">{t("нет данных")}</p>;
  const max = Math.max(...entries.map(([, value]) => value));
  return (
    <>
      {entries.map(([label, value]) => (
        <div className="work-stat-row" key={label}>
          <span>{name(label)}</span>
          <Bar value={value} max={max} tone={tone} />
          <b>{value}</b>
        </div>
      ))}
    </>
  );
}

const HOUR_MS = 3600000;
const RATE_BINS = 12;

/** The observed step feed of the last hour: events per minute in 5-minute bins and counts by type. */
export function eventFigures(steps: readonly HeldStep[], now: number): { rate: number[]; types: Record<string, number>; total: number } {
  const rate = new Array<number>(RATE_BINS).fill(0);
  const types: Record<string, number> = {};
  let total = 0;
  for (const { step } of steps) {
    const at = Date.parse(step.observed_at);
    if (Number.isNaN(at) || at > now || now - at >= HOUR_MS) continue;
    const bin = RATE_BINS - 1 - Math.floor((now - at) / (HOUR_MS / RATE_BINS));
    rate[bin] = (rate[bin] ?? 0) + 1;
    const type = step.origin === "agent" ? "agent" : step.event;
    types[type] = (types[type] ?? 0) + 1;
    total += 1;
  }
  const perMinute = HOUR_MS / RATE_BINS / 60000;
  return { rate: rate.map((count) => Math.round((count / perMinute) * 10) / 10), types, total };
}

const EVENT_TYPES: Record<string, string> = {
  agent: "шаги агента",
  "batch.transition": "переходы batch",
  "dispatch.transition": "переходы dispatch",
  "gate.decision": "решения гейтов",
  "qa.run": "QA-прогоны",
  "qa.attempt": "попытки QA",
};

/** The mockup's events-per-minute line over the last hour; a flat chart when nothing was seen. */
function RateChart({ rate }: { rate: readonly number[] }) {
  const { t, language } = useI18n();
  const W = 760;
  const H = 170;
  const L = 28;
  const R = 10;
  const T = 12;
  const B = 24;
  const max = Math.max(1, ...rate);
  const x = (i: number) => L + (i * (W - L - R)) / Math.max(1, rate.length - 1);
  const y = (v: number) => T + ((max - v) / max) * (H - T - B);
  const points = rate.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  return (
    <div className="work-rate-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t("События в минуту за последний час")}>
        {[0, max / 2, max].map((v) => (
          <g key={v}>
            <line x1={L} y1={y(v)} x2={W - R} y2={y(v)} className="work-rate-grid" />
            <text x={L - 5} y={y(v) + 3} textAnchor="end" className="work-rate-axis">
              {Math.round(v * 10) / 10}
            </text>
          </g>
        ))}
        {[0, 15, 30, 45, 60].map((m) => (
          <text key={m} x={L + (m / 60) * (W - L - R)} y={H - 7} textAnchor={m === 0 ? "start" : m === 60 ? "end" : "middle"} className="work-rate-axis">
            {`${m}${language === "ru" ? "м" : "m"}`}
          </text>
        ))}
        <polyline points={points} className="work-rate-line" />
      </svg>
    </div>
  );
}

export function ActivityStats({
  analytics,
  steps = [],
  now = Date.now(),
}: {
  analytics: Analytics | null;
  steps?: readonly HeldStep[];
  now?: number;
}) {
  const { t } = useI18n();
  const why = t("Журнал событий не агрегируется сервером");
  const events = eventFigures(steps, now);
  const typeRows = Object.fromEntries(
    Object.entries(events.types).map(([type, count]) => [t(EVENT_TYPES[type] ?? type), count]),
  );
  const open = record(analytics?.runtime.open_age_by_role);
  const p50 = record(analytics?.flow.stage_p50_by_role);
  const p95 = record(analytics?.flow.stage_p95_by_role);
  const roles = [...new Set([...Object.keys(open), ...Object.keys(p50)])];
  const minutes = (seconds: number | undefined) => (seconds === undefined ? 0 : Math.round(seconds / 60));
  const maxAge = Math.max(1, ...roles.flatMap((role) => [minutes(open[role]), minutes(p95[role])]));
  return (
    <section className="panel work-analytics" id="work-stats">
      <div className="panel-head">
        <h2>{t("Статистика")}</h2>
        <span className="small muted">{t("срез последнего часа · только события")}</span>
      </div>
      <div className="orch-analytics-grid">
        <article className="orch-chart wide" id="work-rate">
          <div className="orch-chart-head">
            <h3>{t("События в минуту")}</h3>
            <span>{t("{count} событий за час", { count: events.total })}</span>
          </div>
          <RateChart rate={events.rate} />
          <p className="orch-note">{t("Шаги наблюдаются с открытия страницы; события до этого не учитываются.")}</p>
        </article>
        <article className="orch-chart" id="work-event-types">
          <div className="orch-chart-head">
            <h3>{t("Типы событий")}</h3>
            <span>{t("за час")}</span>
          </div>
          <Rows values={typeRows} tone="cyan" />
        </article>
        <article className="orch-chart">
          <div className="orch-chart-head">
            <h3>{t("Загрузка ролей")}</h3>
            <span>{t("активные сессии")}</span>
          </div>
          {analytics ? <Rows values={record(analytics.flow.current_by_role)} tone="cyan" name={roleName} /> : <NoData />}
        </article>
        <article className="orch-chart wide">
          <div className="orch-chart-head">
            <h3>{t("Возраст шага vs p50/p95")}</h3>
            <span>{t("минуты")}</span>
          </div>
          {roles.length === 0 ? (
            <p className="orch-note">{t("нет данных")}</p>
          ) : (
            roles.map((role) => (
              <div className="work-stage-age" key={role}>
                <span>{roleName(role)}</span>
                <div className="work-age-bars">
                  {(
                    [
                      [open[role], "blue"],
                      [p50[role], "cyan"],
                      [p95[role], "violet"],
                    ] as const
                  ).map(([seconds, tone]) => (
                    <div key={tone}>
                      <Bar value={minutes(seconds)} max={maxAge} tone={tone} />
                      <small>{seconds === undefined ? "—" : minutes(seconds)}</small>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
          <div className="orch-legend">
            <span>
              <i className="blue" />
              current
            </span>
            <span>
              <i className="cyan" />
              p50
            </span>
            <span>
              <i className="violet" />
              p95
            </span>
          </div>
        </article>
        <article className="orch-chart wide">
          <div className="orch-chart-head">
            <h3>Retry</h3>
            <span>{t("по ролям")}</span>
          </div>
          {analytics ? <Rows values={record(analytics.quality.rework_by_role)} tone="violet" name={roleName} /> : <NoData />}
          <p className="orch-note">
            {t("Причины повтора")}: <NoData why={why} />
          </p>
        </article>
      </div>
    </section>
  );
}
