/* The mockup's Orchestration blocks over orchestration.snapshot: the summary, the KPI row, the
   Scheme/Flow/Quality/Runtime/Gates tabs, the batch cards, the dispatch table with its filters
   and the ticket list. Figures are the server's; a mockup figure without a source says so. */
import { TabList, TabPanels } from "../views/Tabs";
import { useState } from "react";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { NoData, roleName } from "../steps/ActivityViews";
import type { AnalyticsSection, Figure, OrchestrationSnapshot, StageHead } from "../ws/ledger";
import { FlowTab, GatesTab, PipelineMap, QualityTab, RuntimeTab } from "./Charts";

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

const hours = (seconds: number | null): string =>
  seconds === null ? "—" : seconds >= 3600 ? `${Math.round(seconds / 3600)}h` : `${Math.round(seconds / 60)}m`;

export function OrchKpis({ data }: { data: OrchestrationSnapshot }) {
  const { t } = useI18n();
  const k = data.kpi;
  const value = (key: string) => k[key] ?? null;
  return (
    <div className="orch-kpis" id="orch-mockup-kpis">
      <div>
        <span>{t("В работе / старейший")}</span>
        <b>
          {value("wip") ?? "—"} / {hours(value("oldest_wip_seconds"))}
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
        <div className="orch-line-chart">
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

export function OrchTabs({ data }: { data: OrchestrationSnapshot }) {
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
      </TabPanels>
    </>
  );
}

export function BatchCards({ data }: { data: OrchestrationSnapshot }) {
  const { t, state: stateText } = useI18n();
  const batches = data.ledger.batches.slice(-6).reverse();
  if (batches.length === 0) return <div className="report-empty">{t("Batch в ledger нет")}</div>;
  const tone = (state: string) => (ATTENTION.has(state) ? "err" : state === "active" ? "ok" : "warn");
  return (
    <div className="orch-batches" id="orch-batch-cards">
      {batches.map((batch) => (
        <article className="panel orch-batch" key={batch.batch_id}>
          <div className="orch-batch-head">
            <span className="orch-batch-id">{batch.batch_id}</span>
            <span className={`orch-status ${tone(batch.state)}`} data-state={batch.state}>
              {stateText(batch.state)}
            </span>
          </div>
          <h3 title={t("Названия тикета в ledger нет: показан номер и ветка")}>{batch.ticket || batch.batch_id}</h3>
          <div className="orch-batch-meta">
            {batch.branch || "—"}
            {batch.pr_url ? ` · PR ${stateText(batch.pr_state)}` : ""}
          </div>
        </article>
      ))}
    </div>
  );
}

const statusOf = (stage: StageHead): string =>
  ACTIVE.has(stage.state) ? "working" : ATTENTION.has(stage.state) ? "attention" : stage.report ? "reported" : "awaiting";

export function DispatchTable({ data }: { data: OrchestrationSnapshot }) {
  const { t, state: stateText } = useI18n();
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
      <div id="orch-dispatch-list" tabIndex={0} role="region" aria-label="Dispatch">
        {shown.length === 0 ? (
          <div className="report-empty">{t("Dispatch с такими фильтрами нет")}</div>
        ) : (
          shown.map((stage) => (
            <div className="orch-dispatch-row row" key={stage.dispatch_id}>
              <div>
                <b>
                  {stage.ticket} · {roleName(stage.role)}
                </b>
                <small>
                  {stage.dispatch_id} · {stage.at || "—"}
                </small>
              </div>
              <span className={`status ${statusOf(stage) === "attention" ? "err" : statusOf(stage) === "working" ? "active" : ""}`}>
                {stateText(stage.state)}
              </span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

export function TicketList({ data }: { data: OrchestrationSnapshot }) {
  const { t, state: stateText } = useI18n();
  const tickets = [...new Map(data.ledger.batches.map((batch) => [batch.ticket || batch.batch_id, batch])).values()];
  return (
    <section className="panel orch-tickets" id="orch-tickets">
      <div className="panel-head">
        <h2>{t("Все тикеты")}</h2>
        <span className="small muted">{tickets.length}</span>
      </div>
      {tickets.length === 0 ? (
        <div className="report-empty">{t("Batch в ledger нет")}</div>
      ) : (
        tickets.map((batch) => (
          <div className="row" key={batch.batch_id}>
            <div>
              <b>{batch.ticket || batch.batch_id}</b>
              <small title={t("Названия тикета в ledger нет: показан номер и ветка")}>{batch.branch || batch.batch_id}</small>
            </div>
            <a className="status" href={`${href("recovery")}?batch=${encodeURIComponent(batch.batch_id)}`}>
              {stateText(batch.state)}
            </a>
          </div>
        ))
      )}
    </section>
  );
}
