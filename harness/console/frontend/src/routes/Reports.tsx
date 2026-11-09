/* Reports: the ledger of reports.snapshot laid out as the mockup's #reports. The KPI figures are
   the server's (`reports_kpi`); the page only filters and orders the stages, opens one stage's
   report (reports.report) with its QA log, and a batch's chronology (reports.timeline). The same
   facts as the TUI Reports screen for the same snapshot; report text is untrusted and stays text. */
import { useMemo, useState } from "react";
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { NO_FILTERS, reportsById, reportsKpiTiles, selectStages } from "../reports/format";
import type { StageFilters } from "../reports/format";
import { QaLogs } from "../reports/QaLogs";
import { ReportDetail } from "../reports/ReportDetail";
import { StageFilterBar, StageList } from "../reports/StageList";
import { BatchList, Timeline } from "../reports/Timeline";
import { useScreen } from "../screens/useScreen";
import { parseReports } from "../ws/ledger";

export function Reports() {
  const { t, section, language } = useI18n();
  const screen = useScreen({ type: "reports.snapshot" }, parseReports);
  const [filters, setFilters] = useState<StageFilters>(NO_FILTERS);
  const [selected, setSelected] = useState<string | null>(null);
  const [batch, setBatch] = useState<string | null>(null);
  const ledger = screen.data;

  const reports = useMemo(() => (ledger ? reportsById(ledger) : new Map()), [ledger]);
  const shown = useMemo(
    () => (ledger ? selectStages(ledger.stages, reports, filters) : []),
    [ledger, reports, filters],
  );
  const current = shown.find((stage) => stage.dispatch_id === selected) ?? shown[0] ?? null;
  const tiles = ledger ? reportsKpiTiles(ledger.reports_kpi, t, language) : [];

  return (
    <div className="reports-page" data-section="Reports">
      <div className="page-title reports-title">
        <div>
          <h1>{section("Reports")}</h1>
          <p>{t("Отчёты не заменяют решение; evidence доступен в деталях.")}</p>
          {ledger && (
            <div className="home-facts">
              <span id="reports-cache">
                {screen.cached ? t("Кэш") : t("Новый снимок")} · {screen.ageSeconds ?? 0} s
              </span>
            </div>
          )}
        </div>
        <div className="actions">
          <button id="reports-refresh" className="btn" type="button" onClick={() => screen.refresh(true)}>
            <Icon name="refresh" /> {t("Обновить отчёты")}
          </button>
          <a className="btn" href={href("orchestration")}>
            {section("Orchestration")}
          </a>
        </div>
      </div>

      {screen.error && !ledger && (
        <p className="command-refusal err" role="alert" data-code={screen.error.code}>
          {t("Отчёт не построен")}: {screen.error.message || screen.error.code}
        </p>
      )}
      {ledger?.unavailable && (
        <p className="command-refusal err" role="alert">
          {ledger.unavailable}
        </p>
      )}

      {tiles.length > 0 && (
        <div className="report-kpis" id="reports-kpi">
          {tiles.map((tile) => (
            <div key={tile.label} data-tone={tile.tone || undefined}>
              <span>{tile.label}</span>
              <b className={tile.tone === "warning" ? "warn" : undefined}>{tile.figure}</b>
              {tile.hint && <small>{tile.hint}</small>}
            </div>
          ))}
        </div>
      )}

      {ledger && (
        <div className="reports-grid">
          <section className="panel reports-panel">
            <div className="panel-head">
              <h2>{t("Стадии и отчёты")}</h2>
              <span className="small muted" id="reports-count">
                {shown.length} / {ledger.stages.length}
              </span>
            </div>
            <StageFilterBar filters={filters} onChange={setFilters} />
            <StageList stages={shown} reports={reports} selected={current?.dispatch_id ?? null} onSelect={setSelected} />
          </section>
          <div className="reports-detail-column">
            {current ? (
              <>
                <ReportDetail
                  key={current.dispatch_id}
                  stage={current}
                  report={current.report === null ? undefined : reports.get(current.report)}
                />
                <QaLogs ledger={ledger} dispatchId={current.dispatch_id} />
              </>
            ) : (
              <section className="panel report-detail-panel">
                <div className="report-empty">{t("Ничего не найдено")}</div>
              </section>
            )}
          </div>
        </div>
      )}

      {ledger && (
        <div className="reports-grid reports-batches">
          <section className="panel reports-panel">
            <div className="panel-head">
              <h2>{t("История batch")}</h2>
              <span className="small muted">{ledger.batches.length}</span>
            </div>
            <BatchList batches={ledger.batches} selected={batch} onSelect={setBatch} />
          </section>
          {batch ? (
            <Timeline key={batch} batchId={batch} />
          ) : (
            <section className="panel report-timeline">
              <div className="report-empty">{t("Выберите batch, чтобы открыть его хронологию")}</div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
