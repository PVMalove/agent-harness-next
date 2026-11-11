/* The mockup's Orchestration blocks over orchestration.snapshot: the summary, the KPI row, the
   Scheme/Flow/Quality/Runtime/Gates tabs, the batch cards, the dispatch table with its filters
   and the ticket list. Figures are the server's; a mockup figure without a source says so. */
import { TabList, TabPanels } from "../views/Tabs";
import { useState } from "react";
import type { ReactNode } from "react";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { Icon } from "../icons";
import { NoData, roleIcon, roleName } from "../steps/ActivityViews";
import type { AnalyticsSection, Figure, OrchestrationSnapshot, StageHead } from "../ws/ledger";
import { FlowTab, GatesTab, PipelineMap, QualityTab, RuntimeTab } from "./Charts";
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

export function OrchSummary({ data }: { data: OrchestrationSnapshot }) {
  const { t } = useI18n();
  const counts = orchCounts(data);
  return (
    <div className="orch-summary" id="orch-summary">
      <div>
        <span>{t("Батчи")}</span>
        <b>{counts.batches}</b>
        <small>{t("в конвейере")}</small>
      </div>
      <div>
        <span>Dispatch</span>
        <b>{counts.dispatches}</b>
        <small>{t("назначено")}</small>
      </div>
      <div>
        <span>{t("Активные")}</span>
        <b className="ok">{counts.active}</b>
        <small>{t("работают или ждут")}</small>
      </div>
      <div>
        <span>{t("Требует внимания")}</span>
        <b className="warn">{counts.attention}</b>
        <small>{t("dispatch требует решения")}</small>
      </div>
    </div>
  );
}

export function OrchKpis({ data }: { data: OrchestrationSnapshot }) {
  const { t, duration } = useI18n();
  const k = data.kpi;
  const value = (key: string) => k[key] ?? null;
  return (
    <div className="orch-kpis" id="orch-mockup-kpis">
      <div>
        <span>{t("В работе / старейший")}</span>
        <b>
          {value("wip") ?? "—"} / {duration(value("oldest_wip_seconds"))}
        </b>
        <small>{t("{count} заблокировано", { count: value("blocked") ?? 0 })}</small>
      </div>
      <div>
        <span>{t("Переработки")}</span>
        <b className="violet">
          {value("rework_batches") === null || value("batches") === null
            ? t("нет данных")
            : t("{count} из {total}", { count: value("rework_batches")!, total: value("batches")! })}
        </b>
        <small>{t("хотя бы один retry")}</small>
      </div>
      <div>
        <span>{t("QA с первого раза")}</span>
        <b className="lavender">
          {value("qa_first_pass") === null || value("qa_tickets") === null
            ? t("нет данных")
            : `${value("qa_first_pass")} / ${value("qa_tickets")}`}
        </b>
        <small>{t("первый прогон QA")}</small>
      </div>
      <div>
        <span>{t("Устарело + неизвестно")}</span>
        <b className="blue">
          {value("stale") ?? "—"} + {value("unknown") ?? "—"}
        </b>
        <small>dispatch / execution</small>
      </div>
      <div>
        <span>{t("Эффективность потока")}</span>
        <b className="mint">{value("flow_efficiency_pct") === null ? <NoData /> : `${value("flow_efficiency_pct")}%`}</b>
        <small>active / lead time</small>
      </div>
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
            <text x={L - 8} y={T + 4} textAnchor="end" className="orch-line-axis">
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

export type OrchTab = "map" | AnalyticsSection;

export function OrchTabs({ data, extras = {} }: { data: OrchestrationSnapshot; extras?: Partial<Record<OrchTab, ReactNode>> }) {
  const { t } = useI18n();
  const [tab, setTab] = useState<OrchTab>("map");
  const tabs: [OrchTab, string][] = [
    ["map", t("Схема")],
    ["flow", t("Поток")],
    ["quality", t("Качество")],
    ["runtime", "Runtime"],
    ["gates", t("Гейты")],
  ];
  return (
    <>
      <TabList id="orch" label={t("Оркестрация")} tabs={tabs} value={tab} onChange={(id) => setTab(id as OrchTab)} />
      <TabPanels id="orch" tabs={tabs} value={tab}>
      {tab === "map" ? (
        <PipelineMap data={data} />
      ) : tab === "flow" ? (
        <FlowTab data={data} />
      ) : tab === "quality" ? (
        <QualityTab data={data} />
      ) : tab === "runtime" ? (
        <RuntimeTab data={data} />
      ) : (
        <GatesTab data={data} />
      )}
      {extras[tab]}
      </TabPanels>
    </>
  );
}

/** The mockup shows three batch cards; older batches are rows of «Все тикеты». */
export const BATCH_CARD_LIMIT = 3;
/** Dispatch rows before the list scrolls inside its panel. */
export const DISPATCH_ROWS = 8;

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
        const tone = status === "attention" ? "err" : status === "awaiting" ? "warn" : "ok";
        const beat = last ? last.heartbeat_at || last.at : "";
        return (
          <article className={`panel orch-batch ${status}`} key={batch.batch_id} data-batch={batch.batch_id}>
            <div className="orch-batch-head">
              <span className="orch-batch-id">{batch.batch_id}</span>
              <span className={`orch-status ${tone}`} data-state={batch.state}>
                {step?.kind === "gate" ? t("ждёт гейта") : stateText(batch.state)}
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
              <a href={href("agent-activity")}>
                {t("Ход работы")} <Icon name="chevron" />
              </a>
            </div>
          </article>
        );
      })}
    </div>
  );
}

const statusOf = (stage: StageHead): string =>
  ACTIVE.has(stage.state) ? "working" : ATTENTION.has(stage.state) ? "attention" : stage.report ? "reported" : "awaiting";
const STATUS_TONE: Readonly<Record<string, string>> = { working: "ok", attention: "err", awaiting: "warn", reported: "" };

export function DispatchTable({ data, now = Date.now() }: { data: OrchestrationSnapshot; now?: number }) {
  const { t, language, duration, state: stateText } = useI18n();
  const [role, setRole] = useState("all");
  const [status, setStatus] = useState("all");
  const roles = [...new Set(data.ledger.stages.map((stage) => stage.role))].sort();
  const shown = data.ledger.stages.filter(
    (stage) => (role === "all" || stage.role === role) && (status === "all" || statusOf(stage) === status),
  );
  return (
    <section className="panel orch-dispatch-panel" id="orch-dispatch">
      <div className="panel-head">
        <h2>Dispatch</h2>
        <span className="small muted" id="orch-dispatch-count">
          {t("{count} из {total}", { count: shown.length, total: data.ledger.stages.length })}
        </span>
      </div>
      <div className="orch-dispatch-filters">
        <select aria-label={t("Роль dispatch")} value={role} onChange={(event) => setRole(event.target.value)}>
          <option value="all">{t("Все роли")}</option>
          {roles.map((name) => (
            <option key={name} value={name}>
              {roleName(name)}
            </option>
          ))}
        </select>
        <select aria-label={t("Статус dispatch")} value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="all">{t("Все статусы")}</option>
          <option value="working">{t("Выполняется")}</option>
          <option value="awaiting">{t("Ждёт решения")}</option>
          <option value="attention">{t("Требует внимания")}</option>
          <option value="reported">{t("Отчёт получен")}</option>
        </select>
      </div>
      <div id="orch-dispatch-list" className={shown.length > DISPATCH_ROWS ? "orch-dispatch-scroll" : undefined} tabIndex={0} role="region" aria-label="Dispatch">
        {shown.length === 0 ? (
          <div className="report-empty">{t("Dispatch с такими фильтрами нет")}</div>
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
              <span className={`orch-status ${STATUS_TONE[statusOf(stage)] ?? ""}`}>{stateText(stage.state)}</span>
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
    </section>
  );
}

export function TicketList({ data, now = Date.now() }: { data: OrchestrationSnapshot; now?: number }) {
  const { t, language, duration, state: stateText } = useI18n();
  const batches = [...data.ledger.batches].sort((a, b) => newestFirst(a.created_at, b.created_at));
  // One row per ticket, its newest batch: `batches` is newest first, so the first one of a ticket wins.
  const rows = batches.filter((batch, index) => batches.findIndex((other) => (other.ticket || other.batch_id) === (batch.ticket || batch.batch_id)) === index);
  return (
    <section className="panel orch-tickets" id="orch-tickets">
      <div className="panel-head">
        <h2>{t("Все тикеты")}</h2>
        <span className="small muted">{t("{count} в выборке", { count: rows.length })}</span>
      </div>
      {rows.length === 0 ? (
        <div className="report-empty">{t("Batch в ledger нет")}</div>
      ) : (
        <div className="orch-ticket-table" tabIndex={0} role="region" aria-label={t("Все тикеты")}>
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
            const tone = ATTENTION.has(batch.state) ? "err" : batch.state === "active" ? "ok" : "muted";
            return (
              <div className="orch-ticket-row" key={batch.batch_id} data-batch={batch.batch_id}>
                <b>{batch.ticket || batch.batch_id}</b>
                <div className="orch-ticket-title" title={t("Названия тикета в ledger нет: показан номер и ветка")}>
                  <span>{batch.branch || batch.batch_id}</span>
                  <small>{batch.batch_id}</small>
                </div>
                <span>{last ? `${roleName(last.role)} · ${stateText(last.state)}` : "—"}</span>
                <a className={`orch-pill ${tone}`} href={`${href("recovery")}?batch=${encodeURIComponent(batch.batch_id)}`}>
                  {stateText(batch.state)}
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
