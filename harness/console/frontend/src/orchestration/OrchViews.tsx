/* The mockup's Orchestration blocks over orchestration.snapshot on the v3 shell: the KPI facts of
   the summary, the stage strip, the dispatch queue with its filters and scope (the ticket list is
   its «Все» view), the batch cards and the gate latency trend. Figures are the server's; a
   mockup figure without a source says so. Statuses are StatusIcon shapes, not pills. */
import { useState } from "react";
import { Panel, StatusIcon } from "../ds";
import type { Tone } from "../ds";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { Icon } from "../icons";
import { NoData, roleIcon, roleName } from "../steps/ActivityViews";
import type { Figure, OrchestrationSnapshot, StageHead } from "../ws/ledger";
import { liveSteps, miniSteps } from "./format";

const ACTIVE = new Set(["working", "dispatched", "approved"]);
const ATTENTION = new Set(["failed", "blocked", "auto_stop"]);

export function orchCounts(data: OrchestrationSnapshot) {
  const stages = data.ledger.stages;
  return {
    batches: data.ledger.batches.length,
    dispatches: stages.length,
    active: stages.filter((stage) => ACTIVE.has(stage.state)).length,
    attention: stages.filter((stage) => ATTENTION.has(stage.state)).length,
  };
}

/** The pipeline KPI figures of the summary facts row: WIP and its oldest item, rework, QA first
    pass, stale and unknown, flow efficiency. */
export function OrchFacts({ data }: { data: OrchestrationSnapshot }) {
  const { t, duration } = useI18n();
  const k = data.kpi;
  const value = (key: string) => k[key] ?? null;
  return (
    <span className="orch-facts" id="orch-mockup-kpis">
      <span title={t("{count} заблокировано", { count: value("blocked") ?? 0 })}>
        {t("В работе / старейший")} <b>{value("wip") ?? "—"} / {duration(value("oldest_wip_seconds"))}</b>
      </span>
      <span title={t("хотя бы один retry")}>
        {t("Переработки")}{" "}
        <b>
          {value("rework_batches") === null || value("batches") === null
            ? t("нет данных")
            : t("{count} из {total}", { count: value("rework_batches")!, total: value("batches")! })}
        </b>
      </span>
      <span title={t("первый прогон QA")}>
        {t("QA с первого раза")}{" "}
        <b>{value("qa_first_pass") === null || value("qa_tickets") === null ? t("нет данных") : `${value("qa_first_pass")} / ${value("qa_tickets")}`}</b>
      </span>
      <span title="dispatch / execution">
        {t("Устарело + неизвестно")}{" "}
        <b>
          {value("stale") ?? "—"} + {value("unknown") ?? "—"}
        </b>
      </span>
      <span title="active / lead time">
        {t("Эффективность потока")} <b>{value("flow_efficiency_pct") === null ? <NoData /> : `${value("flow_efficiency_pct")}%`}</b>
      </span>
    </span>
  );
}

/** The open stages of each role as a strip over the map tab. */
const STRIP_ROLES: readonly (readonly [role: string, roles: readonly string[]])[] = [
  ["architect", ["architect"]],
  ["developer", ["developer"]],
  ["review", ["review", "code-review"]],
  ["qa", ["qa"]],
];

export function StageStrip({ data }: { data: OrchestrationSnapshot }) {
  const { t } = useI18n();
  return (
    <div className="orch-stage-strip" id="orch-stage-strip" aria-label={t("Этапы")}>
      {STRIP_ROLES.map(([role, roles]) => {
        const stages = data.ledger.stages.filter((stage) => roles.includes(stage.role));
        const attention = stages.filter((stage) => ATTENTION.has(stage.state)).length;
        const active = stages.filter((stage) => ACTIVE.has(stage.state)).length;
        const tone: Tone = attention ? "err" : active ? "ok" : "off";
        const label = attention ? t("Требует внимания") : active ? t("Выполняется") : t("нет открытых");
        return (
          <span className="orch-stage" key={role} data-role={role}>
            <StatusIcon tone={tone} label={label} />
            <b>{roleName(role)}</b>
            <small>{t("{count} активны", { count: active })}</small>
          </span>
        );
      })}
    </div>
  );
}

/** Mockup figures each analytics tab has no source for. */
const TREND = { width: 1000, height: 250, left: 54, right: 18, top: 16, bottom: 34 };

/** The hourly gate latency of the last day (`latency_p50_by_hour`, `latency_p95_by_hour`), in
    minutes, as the mockup's line chart; an hour without a decision has no point. */
export function GateTrend({ gates }: { gates: Record<string, Figure> }) {
  const { t } = useI18n();
  const series = (key: string): (number | null)[] | null => {
    const figure = gates[key];
    return Array.isArray(figure) ? figure.map((value) => (value === null ? null : value / 60)) : null;
  };
  const p50 = series("latency_p50_by_hour");
  const p95 = series("latency_p95_by_hour");
  const known = [...(p50 ?? []), ...(p95 ?? [])].filter((value): value is number => value !== null);
  const { width: W, height: H, left: L, right: R, top: T, bottom: B } = TREND;
  const hours = Math.max(p50?.length ?? 0, 2);
  const max = Math.max(10, Math.ceil(Math.max(0, ...known) / 10) * 10);
  const x = (index: number) => L + (index * (W - L - R)) / (hours - 1);
  const y = (value: number) => T + ((max - value) / max) * (H - T - B);
  // Each run of hours with a value is one polyline; a lone hour is a dot.
  const lines = (values: (number | null)[], className: string) => {
    const runs: [number, number][][] = [];
    values.forEach((value, index) => {
      if (value === null) return;
      const point: [number, number] = [x(index), y(value)];
      if (index > 0 && values[index - 1] !== null) runs.at(-1)!.push(point);
      else runs.push([point]);
    });
    return runs.map((run, index) =>
      run.length === 1 ? (
        <circle key={index} cx={run[0]![0]} cy={run[0]![1]} r="3" className={`${className}-dot`} />
      ) : (
        <polyline key={index} className={className} points={run.map(([px, py]) => `${px.toFixed(1)},${py.toFixed(1)}`).join(" ")} />
      ),
    );
  };
  const ticks = [0, max / 4, max / 2, (3 * max) / 4, max];
  const labels = [0, 6, 12, 18, hours - 1].filter((index) => index < hours);
  return (
    <article className="orch-chart wide gate-trend" id="orch-gate-trend">
      <div className="orch-chart-head">
        <h3>{t("Тренд latency за сутки")}</h3>
        <span>{t("p50 / p95 по часам, минуты")}</span>
      </div>
      {p50 === null || p95 === null ? (
        <NoData />
      ) : known.length === 0 ? (
        <p className="orch-note">{t("За сутки решений координатора не было")}</p>
      ) : (
        <div className="orch-line-chart" role="region" tabIndex={0} aria-label={t("Тренд latency за сутки")}>
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={t("Тренд latency за сутки")}>
            {ticks.map((value) => (
              <g key={value}>
                <line x1={L} y1={y(value)} x2={W - R} y2={y(value)} className="orch-line-grid" />
                <text x={L - 8} y={y(value) + 3} textAnchor="end" className="orch-line-axis">
                  {Math.round(value)}
                </text>
              </g>
            ))}
            {labels.map((index) => (
              <text key={index} x={x(index)} y={H - 12} textAnchor="middle" className="orch-line-axis">
                {t("−{hours} ч", { hours: hours - index })}
              </text>
            ))}
            {lines(p95, "orch-line-p95")}
            {lines(p50, "orch-line-avg")}
            <text x={0} y={T + 3} className="orch-line-axis">
              {t("мин")}
            </text>
          </svg>
        </div>
      )}
      <div className="orch-legend">
        <span>
          <i className="cyan" />
          p50
        </span>
        <span>
          <i className="lavender" />
          p95
        </span>
      </div>
    </article>
  );
}

/** The mockup shows three batch cards; older batches are rows of «Все тикеты». */
export const BATCH_CARD_LIMIT = 3;

const clock = (iso: string, language: string): string => {
  const at = Date.parse(iso);
  return Number.isNaN(at) ? "—" : new Intl.DateTimeFormat(language, { hour: "2-digit", minute: "2-digit", hour12: false }).format(at);
};
const ageSeconds = (iso: string, now: number): number | null => {
  const at = Date.parse(iso);
  return Number.isNaN(at) ? null : Math.max(0, (now - at) / 1000);
};
const newestFirst = (a: string, b: string) => (a < b ? 1 : a > b ? -1 : 0);

export function BatchCards({ data, now = Date.now() }: { data: OrchestrationSnapshot; now?: number }) {
  const { t, duration, state: stateText } = useI18n();
  const batches = [...data.ledger.batches].sort((a, b) => newestFirst(a.created_at, b.created_at)).slice(0, BATCH_CARD_LIMIT);
  if (batches.length === 0) return <div className="report-empty">{t("Batch в ledger нет")}</div>;
  const live = liveSteps(data.ledger);
  return (
    <div className="orch-batches" id="orch-batch-cards">
      {batches.map((batch) => {
        const step = live.find((item) => item.batch === batch.batch_id);
        const stages = data.ledger.stages.filter((stage) => stage.batch_id === batch.batch_id).sort((a, b) => newestFirst(a.at || a.started_at, b.at || b.started_at));
        const last = stages[0];
        const status = ATTENTION.has(batch.state) ? "attention" : batch.state !== "active" ? "done" : step?.kind === "role" ? "working" : "awaiting";
        const tone: Tone = status === "attention" ? "err" : status === "awaiting" ? "wait" : "ok";
        const beat = last ? last.heartbeat_at || last.at : "";
        const label = step?.kind === "gate" ? t("ждёт гейта") : stateText(batch.state);
        const batchParam = `?batch=${encodeURIComponent(batch.batch_id)}`;
        return (
          <article className={`panel orch-batch ${status}`} key={batch.batch_id} data-batch={batch.batch_id}>
            <div className="orch-batch-head">
              <span className="orch-batch-id">{batch.batch_id}</span>
              <span className="orch-state" data-state={batch.state}>
                <StatusIcon tone={tone} /> {label}
              </span>
            </div>
            <h3 title={t("Названия тикета в ledger нет: показан номер и ветка")}>{`${batch.ticket || batch.batch_id} · ${batch.branch || "—"}`}</h3>
            <div className="orch-batch-meta">
              {last ? (
                <>
                  <Icon name={roleIcon(last.role)} /> {roleName(last.role)} · heartbeat {beat ? duration(ageSeconds(beat, now)) : t("нет данных")}
                </>
              ) : (
                t("dispatch ещё не было")
              )}
            </div>
            <div className="orch-mini">
              {miniSteps(data.ledger, batch, step).map((state, index) => (
                <span key={index} className={`orch-mini-step ${state}`.trim()} title={["Architect", "Developer", "Review", "QA", "PR"][index]} />
              ))}
            </div>
            <div className="orch-batch-foot">
              <span>{last ? `${last.dispatch_id} · ${duration(ageSeconds(last.started_at || last.at, now))}` : "—"}</span>
              <span className="orch-batch-links">
                <a href={href("agent-activity")}>
                  {t("Ход работы")} <Icon name="chevron" />
                </a>
                <a href={`${href("recovery")}${batchParam}`}>{t("Восстановление")}</a>
                <a href={`${href("container-route")}${batchParam}`}>{t("Контейнерный маршрут")}</a>
              </span>
            </div>
          </article>
        );
      })}
    </div>
  );
}

const statusOf = (stage: StageHead): string =>
  ACTIVE.has(stage.state) ? "working" : ATTENTION.has(stage.state) ? "attention" : stage.report ? "reported" : "awaiting";
const STATUS_TONE: Readonly<Record<string, Tone>> = { working: "ok", attention: "err", awaiting: "wait", reported: "info" };

/** The dispatch queue of the map tab: role and status filters and the «Активные» / «Все» scope;
    «Все» also lists every ticket with its newest batch. */
export function DispatchQueue({ data, now = Date.now() }: { data: OrchestrationSnapshot; now?: number }) {
  const { t, language, duration, state: stateText } = useI18n();
  const [role, setRole] = useState("all");
  const [status, setStatus] = useState("all");
  const [scope, setScope] = useState<"active" | "all">("all");
  const roles = [...new Set(data.ledger.stages.map((stage) => stage.role))].sort();
  const shown = data.ledger.stages.filter(
    (stage) =>
      (scope === "all" || ACTIVE.has(stage.state) || ATTENTION.has(stage.state)) &&
      (role === "all" || stage.role === role) &&
      (status === "all" || statusOf(stage) === status),
  );
  const filters = (
    <span className="orch-dispatch-filters">
      <span className="ds-filter" role="group" aria-label={t("Охват")}>
        <button type="button" aria-pressed={scope === "active"} onClick={() => setScope("active")}>
          {t("Активные")}
        </button>
        <button type="button" aria-pressed={scope === "all"} onClick={() => setScope("all")}>
          {t("Все")}
        </button>
      </span>
      <select className="ds-select" aria-label={t("Роль dispatch")} value={role} onChange={(event) => setRole(event.target.value)}>
        <option value="all">{t("Все роли")}</option>
        {roles.map((name) => (
          <option key={name} value={name}>
            {roleName(name)}
          </option>
        ))}
      </select>
      <select className="ds-select" aria-label={t("Статус dispatch")} value={status} onChange={(event) => setStatus(event.target.value)}>
        <option value="all">{t("Все статусы")}</option>
        <option value="working">{t("Выполняется")}</option>
        <option value="awaiting">{t("Ждёт решения")}</option>
        <option value="attention">{t("Требует внимания")}</option>
        <option value="reported">{t("Отчёт получен")}</option>
      </select>
    </span>
  );
  return (
    <Panel
      title="Dispatch"
      count={<span id="orch-dispatch-count">{t("{count} из {total}", { count: shown.length, total: data.ledger.stages.length })}</span>}
      actions={filters}
      fill
      scroll="list"
      id="orch-dispatch"
      label="Dispatch"
    >
      <div id="orch-dispatch-list">
        {shown.length === 0 ? (
          <div className="report-empty">
            {data.ledger.stages.length ? t("Dispatch с такими фильтрами нет") : t("Dispatch ещё не создавались")}
          </div>
        ) : (
          shown.map((stage) => (
            <div className="orch-dispatch-row" key={stage.dispatch_id} data-dispatch={stage.dispatch_id}>
              <span className="orch-role" title={roleName(stage.role)}>
                <Icon name={roleIcon(stage.role)} />
              </span>
              <span className="orch-dispatch-main">
                <b>{`${stage.dispatch_id} · ${stage.ticket || stage.batch_id}`}</b>
                <small>{`${stage.batch_id} · ${roleName(stage.role)} · ${t("старт")} ${clock(stage.started_at || stage.at, language)}`}</small>
              </span>
              <span className="orch-state">
                <StatusIcon tone={STATUS_TONE[statusOf(stage)] ?? "off"} /> {stateText(stage.state)}
              </span>
              <span className="orch-heartbeat" title={t("с последнего heartbeat или события")}>
                {/* The 44px column of the mockup holds the largest unit only («3 дн», «12 мин»). */}
                {duration(ageSeconds(stage.heartbeat_at || stage.at, now)).split(" ").slice(0, 2).join(" ")}
              </span>
              <a className="orch-link" href={href("agent-activity")}>
                {t("Ход")} <Icon name="chevron" />
              </a>
            </div>
          ))
        )}
      </div>
      {scope === "all" && <TicketList data={data} now={now} />}
    </Panel>
  );
}

export function TicketList({ data, now = Date.now() }: { data: OrchestrationSnapshot; now?: number }) {
  const { t, language, duration, state: stateText } = useI18n();
  const batches = [...data.ledger.batches].sort((a, b) => newestFirst(a.created_at, b.created_at));
  // One row per ticket, its newest batch: `batches` is newest first, so the first one of a ticket wins.
  const rows = batches.filter((batch, index) => batches.findIndex((other) => (other.ticket || other.batch_id) === (batch.ticket || batch.batch_id)) === index);
  return (
    <section className="orch-tickets" id="orch-tickets" aria-label={t("Все тикеты")}>
      <h3 className="ds-group-title">
        {t("Все тикеты")} · <span className="orch-tickets-count">{t("{count} в выборке", { count: rows.length })}</span>
      </h3>
      {rows.length === 0 ? (
        <div className="report-empty">{t("Batch в ledger нет")}</div>
      ) : (
        <div className="orch-ticket-table">
          <div className="orch-ticket-head">
            <span>{t("тикет")}</span>
            <span>{t("название")}</span>
            <span>{t("стадия / роль")}</span>
            <span>{t("статус")}</span>
            <span>{t("возраст")}</span>
            <span>{t("обновлён")}</span>
          </div>
          {rows.map((batch) => {
            const last = data.ledger.stages
              .filter((stage) => stage.batch_id === batch.batch_id)
              .sort((a, b) => newestFirst(a.at || a.started_at, b.at || b.started_at))[0];
            const tone: Tone = ATTENTION.has(batch.state) ? "err" : batch.state === "active" ? "ok" : "info";
            return (
              <div className="orch-ticket-row" key={batch.batch_id} data-batch={batch.batch_id}>
                <b>{batch.ticket || batch.batch_id}</b>
                <div className="orch-ticket-title" title={t("Названия тикета в ledger нет: показан номер и ветка")}>
                  <span>{batch.branch || batch.batch_id}</span>
                  <small>{batch.batch_id}</small>
                </div>
                <span>{last ? `${roleName(last.role)} · ${stateText(last.state)}` : "—"}</span>
                <a className="orch-state" href={`${href("recovery")}?batch=${encodeURIComponent(batch.batch_id)}`}>
                  <StatusIcon tone={tone} /> {stateText(batch.state)}
                </a>
                <span>{duration(ageSeconds(batch.created_at, now))}</span>
                <span>{last ? clock(last.at || last.started_at, language) : "—"}</span>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
