/* The mockup's Agent activity blocks over the live roster and the ledger snapshot: the summary,
   the KPI row, the session route, the timeline and the statistics. Counts come from the roster
   or the server's analytics; a figure without a source shows an explicit no-data state. */
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import type { Analytics, Ledger, StageHead } from "../ws/ledger";
import type { RosterDispatch } from "../ws/steps";

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

export function statusCounts(dispatches: readonly RosterDispatch[]): Record<"all" | SessionStatus, number> {
  const counts = { all: dispatches.length, running: 0, blocked: 0, awaiting: 0, other: 0 };
  for (const entry of dispatches) counts[sessionStatus(entry)] += 1;
  return counts;
}

/** Whole minutes between an ISO time and `now`; null for an unknown time. */
export function ageMinutes(iso: string, now: number): number | null {
  const at = Date.parse(iso);
  return iso && !Number.isNaN(at) ? Math.max(0, Math.round((now - at) / 60000)) : null;
}

export const formatMinutes = (minutes: number | null): string =>
  minutes === null ? "—" : minutes >= 60 ? `${Math.floor(minutes / 60)}h ${minutes % 60}m` : `${minutes}m`;

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
  const { t } = useI18n();
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
        <b className="blue">{oldest ? formatMinutes(ageMinutes(oldest.started_at, now)) : <NoData />}</b>
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

const ROUTE: [string, string[]][] = [
  ["Architect", ["architect"]],
  ["Developer", ["developer"]],
  ["Review", ["review", "code-review"]],
  ["QA", ["qa"]],
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
  const { t, section } = useI18n();
  if (!session) {
    return (
      <section className="panel work-route-panel" id="work-route">
        <div className="work-empty">{t("Выберите сессию слева.")}</div>
      </section>
    );
  }
  const batch = dispatches.filter((entry) => entry.batch_id === session.batch_id);
  const tone = STATUS_TONE[sessionStatus(session)];
  const steps = ROUTE.map(([name, roles]) => {
    const entry = batch.filter((item) => roles.includes(item.role)).at(-1);
    const state = !entry ? "pending" : sessionStatus(entry) === "running" ? "current" : "done";
    return { name, state, label: entry ? entry.state : t("Не начат") };
  });
  steps.push({ name: "PR", state: prState ? "done" : "pending", label: prState || t("нет данных") });
  const current = steps.find((step) => step.state === "current") ?? null;
  return (
    <section className="panel work-route-panel" id="work-route">
      <div className="panel-head">
        <h2>{t("Маршрут сессии {id}", { id: session.ticket || session.batch_id })}</h2>
        <span className={`work-status ${tone}`}>{session.state}</span>
      </div>
      <div className="work-route-body">
        <div className="work-task-meta">
          <span>
            <Icon name="activity" /> {session.role}
          </span>
          <span className="branch-inline">
            <b>{session.branch || "—"}</b>
          </span>
          <span>
            <Icon name="clock" /> {formatMinutes(ageMinutes(session.started_at, now))}
            {session.started_at ? ` · ${t("старт")} ${session.started_at.slice(11, 16)}` : ""}
          </span>
        </div>
        <div className="work-flow-scroll">
          <div className="work-flow">
            {steps.map((step, index) => (
              <span key={step.name} style={{ display: "contents" }}>
                <div className={`work-flow-node ${step.state} ${step.state === "current" ? tone : ""}`}>
                  <span className="work-flow-icon">
                    <Icon name={step.name === "PR" ? "github" : "activity"} />
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

/** The timeline rows of the ledger stages, one row per batch, minutes from its first stage. */
export function timelineRows(stages: readonly StageHead[], now: number): { batch: string; ticket: string; total: number; segments: Segment[] }[] {
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
        tone: open ? "cyan" : item.state === "failed" || item.state === "blocked" ? "violet" : "mint",
      };
    });
    return { batch, ticket: items[0]!.ticket, total: Math.max(...segments.map((segment) => segment.to)), segments };
  });
}

export function ActivityTimeline({ ledger, now }: { ledger: Ledger | null; now: number }) {
  const { t } = useI18n();
  const rows = ledger ? timelineRows(ledger.stages, now) : [];
  const max = Math.max(1, ...rows.map((row) => row.total));
  return (
    <section className="panel work-analytics" id="work-timeline">
      <div className="panel-head">
        <h2>{t("Таймлайн")}</h2>
        <span className="small muted">{t("прошлое и текущий шаг · без внутренних рассуждений")}</span>
      </div>
      {rows.length === 0 ? (
        <div className="work-empty">{ledger ? t("Этапов с временем начала нет") : t("нет данных")}</div>
      ) : (
        <div className="work-gantt">
          {rows.map((row) => (
            <div className="work-gantt-row" key={row.batch}>
              <div className="work-gantt-name">
                <b>{row.ticket || row.batch}</b>
                <small>{formatMinutes(row.total)}</small>
              </div>
              <div className="work-gantt-track">
                {row.segments.map((segment, index) => (
                  <div
                    key={index}
                    className={`work-gantt-seg ${segment.tone}`}
                    style={{ left: `${(segment.from / max) * 100}%`, width: `${((segment.to - segment.from) / max) * 100}%` }}
                    title={`${segment.role} · ${segment.from}–${segment.to} min`}
                  >
                    <span>{segment.role}</span>
                  </div>
                ))}
              </div>
              <div className="work-gantt-last" />
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
          <i className="violet" />
          {t("блок")}
        </span>
      </div>
    </section>
  );
}

const record = (figure: unknown): Record<string, number> =>
  figure && typeof figure === "object" && !Array.isArray(figure) ? (figure as Record<string, number>) : {};

function Rows({ values, tone }: { values: Record<string, number>; tone: string }) {
  const { t } = useI18n();
  const entries = Object.entries(values);
  if (!entries.length) return <p className="orch-note">{t("нет данных")}</p>;
  const max = Math.max(...entries.map(([, value]) => value));
  return (
    <>
      {entries.map(([label, value]) => (
        <div className="work-stat-row" key={label}>
          <span>{label}</span>
          <Bar value={value} max={max} tone={tone} />
          <b>{value}</b>
        </div>
      ))}
    </>
  );
}

export function ActivityStats({ analytics }: { analytics: Analytics | null }) {
  const { t } = useI18n();
  const why = t("Журнал событий не агрегируется сервером");
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
        <span className="small muted">{t("аналитика ledger")}</span>
      </div>
      <div className="orch-analytics-grid">
        <article className="orch-chart wide">
          <div className="orch-chart-head">
            <h3>{t("События в минуту")}</h3>
          </div>
          <p className="orch-note">
            <NoData why={why} />
          </p>
        </article>
        <article className="orch-chart">
          <div className="orch-chart-head">
            <h3>{t("Типы событий")}</h3>
          </div>
          <p className="orch-note">
            <NoData why={why} />
          </p>
        </article>
        <article className="orch-chart">
          <div className="orch-chart-head">
            <h3>{t("Загрузка ролей")}</h3>
            <span>{t("активные сессии")}</span>
          </div>
          {analytics ? <Rows values={record(analytics.flow.current_by_role)} tone="cyan" /> : <NoData />}
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
                <span>{role}</span>
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
          {analytics ? <Rows values={record(analytics.quality.rework_by_role)} tone="violet" /> : <NoData />}
          <p className="orch-note">
            {t("Причины повтора")}: <NoData why={why} />
          </p>
        </article>
      </div>
    </section>
  );
}
