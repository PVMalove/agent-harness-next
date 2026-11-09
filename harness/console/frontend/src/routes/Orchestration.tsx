/* Orchestration: the orchestration.snapshot of the server laid out as the mockup's #orchestration.
   KPI and analytics figures are the server's; the page words them as the TUI Orchestration screen
   does, shows the ledger lock, the batch history with its chronology and the pending human
   decisions. Recovery and Container route open as hidden routes carrying the selected batch. The
   TUI's command menu is not reproduced: decisions cover the human gate. The mockup blocks
   (summary, KPI row, Scheme/Flow/Quality/Runtime/Gates tabs, batch cards, dispatch table, QA lane,
   all tickets) come first; the TUI-worded KPI row, analytics, statistics, lock, batch history and
   decisions have no mockup slot and follow them (H4). */
import { useState } from "react";
import { DecisionPanel } from "../decisions/DecisionPanel";
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { Analytics, KpiRow } from "../orchestration/Analytics";
import { BatchHistory } from "../orchestration/BatchHistory";
import { ALL_STATES, kpiTiles, pipelineStats, pipelineStatsFields } from "../orchestration/format";
import { LedgerLock } from "../orchestration/LedgerLock";
import { BatchCards, DispatchTable, OrchKpis, OrchSummary, OrchTabs, TicketList, orchCounts } from "../orchestration/OrchViews";
import { QaLane } from "../reports/ReportViews";
import { useScreen } from "../screens/useScreen";
import { parseOrchestration } from "../ws/ledger";

const withBatch = (route: string, batch: string | null) =>
  batch ? `${href(route)}?batch=${encodeURIComponent(batch)}` : href(route);

export function Orchestration() {
  const { t, section, language } = useI18n();
  const screen = useScreen({ type: "orchestration.snapshot" }, parseOrchestration);
  const [state, setState] = useState(ALL_STATES);
  const [batch, setBatch] = useState<string | null>(null);
  const data = screen.data;
  const fields = data ? pipelineStatsFields(pipelineStats(data.ledger)) : [];

  return (
    <div className="orch-page work-page" data-section="Orchestration">
      <div className="page-title orch-title">
        <div>
          <h1>{section("Orchestration")}</h1>
          <p>{t("Состояние пайплайна, история batch и решения человека.")}</p>
          {data && (
            <div className="home-facts">
              <span>{t("{count} батчей", { count: orchCounts(data).batches })}</span>
              <span>{orchCounts(data).dispatches} dispatch</span>
              <span>{t("{count} активны", { count: orchCounts(data).active })}</span>
              <span id="orch-cache">
                {screen.cached ? t("Кэш") : t("Новый снимок")} · {screen.ageSeconds ?? 0} s
              </span>
            </div>
          )}
        </div>
        <div className="actions">
          <button id="orch-refresh" className="btn" type="button" onClick={() => screen.refresh(true)}>
            <Icon name="refresh" /> {t("Обновить снимок")}
          </button>
          <a id="open-recovery" className="btn" href={withBatch("recovery", batch)}>
            {t("Восстановление")}
          </a>
          <a id="open-container-route" className="btn" href={withBatch("container-route", batch)}>
            {t("Контейнерный маршрут")}
          </a>
          <a className="btn" href={href("agent-activity")}>
            {section("Ход работы")}
          </a>
          <a className="btn" href={href("reports")}>
            {section("Reports")}
          </a>
        </div>
      </div>

      {screen.error && !data && (
        <p className="command-refusal err" role="alert" data-code={screen.error.code}>
          {t("Отчёт не построен")}: {screen.error.message || screen.error.code}
        </p>
      )}
      {data?.ledger.unavailable && (
        <p className="command-refusal err" role="alert">
          {data.ledger.unavailable}
        </p>
      )}

      {data && (
        <>
          <OrchSummary data={data} />
          <OrchKpis data={data} />
          <OrchTabs data={data} />
          <BatchCards data={data} />
          <DispatchTable data={data} />
          <QaLane ledger={data.ledger} ticket={data.ledger.batches.at(-1)?.ticket ?? ""} />
          <TicketList data={data} />
          <KpiRow tiles={kpiTiles(data.kpi, t, language)} id="orch-kpi" className="orch-kpis" />
          <div className="orch-overview-grid">
            <Analytics analytics={data.analytics} />
            <section className="panel orch-stats" id="pipeline-stats">
              <div className="panel-head">
                <h2>{t("Состояние и статистика")}</h2>
              </div>
              {fields.length ? (
                <dl className="orch-analytics-rows">
                  {fields.map(([label, value]) => (
                    <div key={label}>
                      <dt>{t(label)}</dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="report-empty">{t("Пайплайн ещё не запускался: batch в леджере нет.")}</p>
              )}
            </section>
            <LedgerLock lock={data.lock} />
          </div>
          <BatchHistory ledger={data.ledger} state={state} onState={setState} selected={batch} onSelect={setBatch} />
        </>
      )}

      <section className="orch-decisions" aria-label={t("Решения")}>
        <h2 className="orch-section-title">{t("Решения")}</h2>
        <DecisionPanel />
      </section>
    </div>
  );
}
