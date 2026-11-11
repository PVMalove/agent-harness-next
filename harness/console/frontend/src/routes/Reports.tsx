/* Reports: the ledger of reports.snapshot laid out as the mockup's #reports. The KPI figures are
   the server's (`reports_kpi`); the page only filters and orders the stages, opens one stage's
   report (reports.report) with its QA log, and a batch's chronology (reports.timeline). The same
   facts as the TUI Reports screen for the same snapshot; report text is untrusted and stays text.
   The mockup's tabs Evidence, Quality and Readiness read the same snapshot and the ledger
   analytics; the batch history has no mockup slot and follows the mockup blocks (H4). */
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
import { EvidenceTab, QaLane, QualityTab, ReadinessTab, ReportsSummary, reportCounts } from "../reports/ReportViews";
import { useScreen } from "../screens/useScreen";
import { TabList, TabPanels } from "../views/Tabs";
import { parseOrchestration, parseReports } from "../ws/ledger";

type Tab = "list" | "evidence" | "quality" | "readiness";
const TYPE_CHIPS: [string, string][] = [
  ["", "Все"],
  ["qa", "QA"],
  ["review", "Review"],
  ["developer", "Developer"],
];

/** The JSON of the shown stages and their report heads: the export of the current selection. */
function exportSelection(stages: readonly unknown[], reports: readonly unknown[]) {
  const blob = new Blob([JSON.stringify({ stages, reports }, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "reports.json";
  link.click();
  URL.revokeObjectURL(url);
}

export function Reports() {
  const { t, section, language, tab: tabLabel } = useI18n();
  const screen = useScreen({ type: "reports.snapshot" }, parseReports);
  const orchestration = useScreen({ type: "orchestration.snapshot" }, parseOrchestration);
  const [tab, setTab] = useState<Tab>("list");
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
  const counts = ledger ? reportCounts(ledger.reports) : null;
  const tabs: [Tab, string][] = [
    ["list", t("Отчёты")],
    ["evidence", "Evidence"],
    ["quality", t("Качество")],
    ["readiness", t("Готовность")],
  ];

  return (
    <div className="reports-page" data-section="Reports">
      <div className="page-title reports-title">
        <div>
          <h1>{section("Reports")}</h1>
          <p>{t("Результаты ролей, QA evidence и события. Отчёты хранятся отдельно от решений человека.")}</p>
          {ledger && counts && (
            <div className="home-facts">
              <span>{t("{count} отчётов", { count: counts.all })}</span>
              <span>{counts.passed} passed</span>
              <span>{counts.attention} attention</span>
              <span>{counts.blocked} blocked</span>
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
          <button
            id="reports-export"
            className="btn"
            type="button"
            disabled={!ledger}
            onClick={() => exportSelection(shown, ledger ? ledger.reports : [])}
          >
            <Icon name="reports" /> {t("Экспорт")}
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

      {ledger && <ReportsSummary reports={ledger.reports} />}

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
        <TabList
          id="reports"
          label={t("Отчёты")}
          className="orch-tabbar report-tabbar"
          tabs={tabs.map(([id, label]) => [id, id === "list" ? tabLabel(label) : label] as const)}
          value={tab}
          onChange={(id) => setTab(id as Tab)}
        />
      )}

      {ledger && (
      <TabPanels id="reports" tabs={tabs} value={tab}>
      {ledger && tab === "evidence" && <EvidenceTab rows={ledger.evidence} />}
      {ledger && tab === "quality" && <QualityTab ledger={ledger} analytics={orchestration.data?.analytics ?? null} />}
      {ledger && tab === "readiness" && <ReadinessTab ledger={ledger} />}

      {ledger && tab === "list" && (
        <div className="reports-grid">
          <section className="panel reports-panel">
            <div className="panel-head">
              <h2>{t("Отчёты")}</h2>
              <span className="small muted" id="reports-count">
                {shown.length} / {ledger.stages.length}
              </span>
            </div>
            <div className="report-filters">
              <div className="chips" id="report-types">
                {TYPE_CHIPS.map(([role, label]) => (
                  <button
                    key={label}
                    type="button"
                    className={`chip ${filters.role === role ? "on" : ""}`}
                    aria-pressed={filters.role === role}
                    onClick={() => setFilters({ ...filters, role })}
                  >
                    {role ? label : t(label)}
                  </button>
                ))}
                <a className="chip" href={href("diagnostics")}>
                  Health
                </a>
                <a className="chip" href={href("publish")}>
                  Publish
                </a>
              </div>
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
                <QaLane ledger={ledger} ticket={current.ticket} />
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

      {ledger && tab === "list" && (
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
      </TabPanels>
      )}
    </div>
  );
}
