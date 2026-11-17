/* Reports on the design system v3: the page header (refresh and the JSON export on the right), the
   summary (reports by state; the Reports KPIs as facts) and four pipeline tabs over
   reports.snapshot only. «Отчёты» filters and orders the stages and opens one stage's report
   (reports.report) with the QA lane and its log; Evidence is the kernel's evidence matrix;
   «Качество» the results by role, first-pass QA and the QA attempts; «Готовность» the Release Gate
   rows, each opening the shared candidate drawer. The same facts as the TUI Reports screen for the
   same snapshot; report text is untrusted and stays text. The batch history and its chronology
   stay on Orchestration. */
import { downloadJson } from "../diagnostics/exportReport";
import { useMemo, useState } from "react";
import { PageHeader, Panel, PipeTabs, Summary } from "../ds";
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { CandidateDrawer } from "../reports/CandidateDrawer";
import { NO_FILTERS, reportsById, reportsKpiTiles, selectStages } from "../reports/format";
import type { StageFilters, Tile } from "../reports/format";
import { QaLogs } from "../reports/QaLogs";
import { ReportDetail } from "../reports/ReportDetail";
import { StageFilterBar, StageList } from "../reports/StageList";
import { EVIDENCE_COLUMNS, EvidenceTab, QaLane, QualityTab, ReadinessTab, reportCounts, reportState } from "../reports/ReportViews";
import type { ReportState } from "../reports/ReportViews";
import { useScreen } from "../screens/useScreen";
import { snapshotClock } from "../update/format";
import { TabPanel } from "../views/Tabs";
import type { ReportHead, ReportsSnapshot, StageHead } from "../ws/ledger";
import { parseReports } from "../ws/ledger";

type Tab = "list" | "evidence" | "quality" | "readiness";
const TYPE_CHIPS: [string, string][] = [
  ["", "Все"],
  ["qa", "QA"],
  ["review", "Review"],
  ["developer", "Developer"],
];

/** The mockup's free search: a stage matches when its ticket, role, report outcome or dispatch
    id holds the text. */
function matchesQuery(stage: StageHead, report: ReportHead | undefined, query: string): boolean {
  const text = query.trim().toLowerCase();
  if (!text) return true;
  return [stage.ticket, stage.role, report?.outcome ?? "", stage.dispatch_id].some((field) => field.toLowerCase().includes(text));
}

/** The mockup's KPI facts: evidence completeness, stale evidence cells of the kernel's matrix,
    report latency and first-pass QA; the risk and blocker tiles go to the Quality tab. */
function kpiRow(ledger: ReportsSnapshot, tiles: readonly Tile[], t: (text: string) => string): Tile[] {
  const stale = ledger.evidence.reduce(
    (sum, row) => sum + EVIDENCE_COLUMNS.filter(([column]) => row[column] === "stale").length,
    0,
  );
  const staleTile: Tile = {
    label: "Stale evidence",
    figure: String(stale),
    hint: t("нельзя считать актуальным"),
    tone: stale ? "warning" : "",
  };
  return [tiles[1]!, staleTile, tiles[2]!, tiles[3]!];
}

function KpiTiles({ id, tiles }: { id: string; tiles: readonly Tile[] }) {
  return (
    <div className="report-kpis" id={id}>
      {tiles.map((tile) => (
        <div key={tile.label} data-tone={tile.tone || undefined}>
          <span>{tile.label}</span>
          <b className={tile.tone === "warning" ? "warn" : undefined}>{tile.figure}</b>
          {tile.hint && <small>{tile.hint}</small>}
        </div>
      ))}
    </div>
  );
}

/** The JSON of the shown stages and their report heads: the export of the current selection. */
function exportSelection(stages: readonly unknown[], reports: readonly unknown[]) {
  // The shared helper revokes the URL after the download started, never in the same tick.
  downloadJson("reports.json", { stages, reports });
}

export function Reports() {
  const { t, section, language, tab: tabLabel } = useI18n();
  const screen = useScreen({ type: "reports.snapshot" }, parseReports);
  const [tab, setTab] = useState<Tab>("list");
  const [filters, setFilters] = useState<StageFilters>(NO_FILTERS);
  const [selected, setSelected] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"all" | ReportState>("all");
  const [candidate, setCandidate] = useState<string | null>(null);
  const ledger = screen.data;

  const reports = useMemo(() => (ledger ? reportsById(ledger) : new Map<string, ReportHead>()), [ledger]);
  const shown = useMemo(
    () =>
      ledger
        ? selectStages(ledger.stages, reports, filters).filter((stage) => {
            const report = stage.report === null ? undefined : reports.get(stage.report);
            return matchesQuery(stage, report, query) && (status === "all" || (report !== undefined && reportState(report) === status));
          })
        : [],
    [ledger, reports, filters, query, status],
  );
  const current = shown.find((stage) => stage.dispatch_id === selected) ?? shown[0] ?? null;
  const tiles = ledger ? reportsKpiTiles(ledger.reports_kpi, t, language) : [];
  const counts = ledger ? reportCounts(ledger.reports) : null;
  const opened = ledger && candidate ? (ledger.publish.find((entry) => entry.batch_id === candidate) ?? null) : null;
  const tabs: { id: Tab; label: string }[] = [
    { id: "list", label: tabLabel(t("Отчёты")) },
    { id: "evidence", label: "Evidence" },
    { id: "quality", label: t("Качество") },
    { id: "readiness", label: t("Готовность") },
  ];

  return (
    <div className="ds-page ds-fit reports-page" data-section="Reports">
      <PageHeader
        title={section("Reports")}
        subtitle={t("Результаты ролей, QA evidence и события. Отчёты хранятся отдельно от решений человека.")}
        actions={
          <>
            <button id="reports-refresh" className="ds-btn ds-btn-icon" type="button" aria-label={t("Обновить")} title={t("Обновить")} onClick={() => screen.refresh(true)}>
              <Icon name="refresh" className="ds-ic-sm" />
            </button>
            <button id="reports-export" className="ds-btn" type="button" disabled={!ledger} onClick={() => exportSelection(shown, ledger ? ledger.reports : [])}>
              <Icon name="download" className="ds-ic-sm" /> {t("Экспорт JSON")}
            </button>
          </>
        }
      />

      {screen.error && !ledger && (
        <p className="ds-alert ds-alert-err" role="alert" data-code={screen.error.code}>
          {t("Отчёт не построен")}: {screen.error.message || screen.error.code}
        </p>
      )}
      {ledger?.unavailable && (
        <p className="ds-alert ds-alert-err" role="alert">
          {ledger.unavailable}
        </p>
      )}

      <Summary
        id="reports-summary"
        label={t("Сводка отчётов")}
        stats={[
          { label: t("Отчётов"), value: counts?.all ?? "—", caption: t("в выборке") },
          { label: t("Пройдено"), value: counts?.passed ?? "—", caption: t("без рисков и блокеров") },
          { label: t("Внимание"), value: counts?.attention ?? "—", caption: t("нужен просмотр") },
          { label: t("Заблокировано"), value: counts?.blocked ?? "—", caption: t("решение человека") },
        ]}
        facts={ledger && tiles.length > 0 ? <KpiTiles id="reports-kpi" tiles={kpiRow(ledger, tiles, t)} /> : null}
        snapshot={
          ledger ? (
            <span title={`${screen.cached ? t("Кэш") : t("Новый снимок")} · ${screen.ageSeconds ?? 0} s`}>
              <Icon name="clock" className="ds-ic-sm" /> {t("Снимок")} <span id="reports-updated">{snapshotClock(screen.ageSeconds, language)}</span>
            </span>
          ) : undefined
        }
      />

      <PipeTabs id="reports" label={t("Отчёты")} tabs={tabs} value={tab} onChange={(id) => setTab(id as Tab)} />

      <TabPanel id="reports" tab="list" value={tab} className="ds-tabpanel">
        {ledger && (
          <div className="ds-split reports-grid">
            <Panel
              title={t("Список отчётов")}
              count={<span id="reports-count">{t("{shown} из {total}", { shown: shown.length, total: ledger.stages.length })}</span>}
              fill
              scroll="list"
              id="reports-list"
              label={t("Список отчётов")}
            >
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
                <div className="report-filter-row" id="report-filter-row">
                  <select
                    id="report-status"
                    aria-label={t("Статус отчёта")}
                    value={status}
                    onChange={(event) => setStatus(event.target.value as "all" | ReportState)}
                  >
                    <option value="all">{t("Все статусы")}</option>
                    <option value="passed">{t("Пройдено")}</option>
                    <option value="attention">{t("Внимание")}</option>
                    <option value="blocked">{t("Заблокировано")}</option>
                  </select>
                  <label className="report-search">
                    <Icon name="search" />
                    <input
                      id="reports-search"
                      type="search"
                      placeholder={t("Найти отчёт")}
                      aria-label={t("Поиск отчёта")}
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                    />
                  </label>
                </div>
                <details className="report-more-filters" id="report-more-filters">
                  <summary>{t("Ещё фильтры")}</summary>
                  <StageFilterBar filters={filters} onChange={setFilters} />
                </details>
              </div>
              <StageList stages={shown} reports={reports} selected={current?.dispatch_id ?? null} onSelect={setSelected} />
              <div className="report-list-foot">{t("Отчёты не заменяют решение; evidence доступен в деталях.")}</div>
            </Panel>
            <Panel title={t("Детали отчёта")} fill scroll="text" id="reports-detail" label={t("Детали отчёта")}>
              {current ? (
                <>
                  <ReportDetail key={current.dispatch_id} stage={current} report={current.report === null ? undefined : reports.get(current.report)} />
                  <QaLane ledger={ledger} ticket={current.ticket}>
                    <QaLogs ledger={ledger} dispatchId={current.dispatch_id} />
                  </QaLane>
                </>
              ) : (
                <p className="ds-empty" id="report-detail">
                  {t("Ничего не найдено")}
                </p>
              )}
            </Panel>
          </div>
        )}
      </TabPanel>
      <TabPanel id="reports" tab="evidence" value={tab} className="ds-tabpanel">
        {ledger && (
          <Panel title="Evidence" fill scroll="list" id="reports-evidence-panel" label="Evidence">
            <EvidenceTab rows={ledger.evidence} />
          </Panel>
        )}
      </TabPanel>
      <TabPanel id="reports" tab="quality" value={tab} className="ds-tabpanel">
        {ledger && (
          <Panel title={t("Качество")} fill scroll="list" id="reports-quality-panel" label={t("Качество")}>
            <KpiTiles id="reports-quality-kpi" tiles={tiles.slice(4)} />
            <QualityTab ledger={ledger} />
          </Panel>
        )}
      </TabPanel>
      <TabPanel id="reports" tab="readiness" value={tab} className="ds-tabpanel">
        {ledger && (
          <Panel title={t("Готовность")} fill scroll="list" id="reports-readiness-panel" label={t("Готовность")}>
            <ReadinessTab ledger={ledger} onOpen={setCandidate} />
          </Panel>
        )}
      </TabPanel>
      {ledger && opened && <CandidateDrawer entry={opened} ledger={ledger} onClose={() => setCandidate(null)} />}
    </div>
  );
}
