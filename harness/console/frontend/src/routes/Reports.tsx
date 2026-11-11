/* Reports: the ledger of reports.snapshot laid out as the mockup's #reports. The KPI figures are
   the server's (`reports_kpi`); the page only filters and orders the stages, opens one stage's
   report (reports.report) with its QA log, and a batch's chronology (reports.timeline). The same
   facts as the TUI Reports screen for the same snapshot; report text is untrusted and stays text.
   The mockup's tabs Evidence, Quality and Readiness read the same snapshot and the ledger
   analytics. The batch history and its chronology stay on the Orchestration page: the mockup has
   no batch block on Reports. */
import { useMemo, useState } from "react";
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { NO_FILTERS, reportsById, reportsKpiTiles, selectStages } from "../reports/format";
import type { StageFilters, Tile } from "../reports/format";
import { QaLogs } from "../reports/QaLogs";
import { ReportDetail } from "../reports/ReportDetail";
import { StageFilterBar, StageList } from "../reports/StageList";
import {
  EVIDENCE_COLUMNS,
  EvidenceTab,
  QaLane,
  QualityTab,
  ReadinessTab,
  ReportsSummary,
  reportCounts,
  reportState,
} from "../reports/ReportViews";
import type { ReportState } from "../reports/ReportViews";
import { useScreen } from "../screens/useScreen";
import { snapshotClock } from "../update/format";
import type { ReportHead, ReportsSnapshot, StageHead } from "../ws/ledger";
import { TabList, TabPanels } from "../views/Tabs";
import { parseOrchestration, parseReports } from "../ws/ledger";

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

/** The mockup's second KPI row: evidence completeness, stale evidence cells of the kernel's matrix,
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
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"all" | ReportState>("all");
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
              <span>{t("{count} пройдено", { count: counts.passed })}</span>
              <span>{t("{count} внимание", { count: counts.attention })}</span>
              <span>{t("{count} заблокировано", { count: counts.blocked })}</span>
              <span id="reports-updated" title={`${screen.cached ? t("Кэш") : t("Новый снимок")} · ${screen.ageSeconds ?? 0} s`}>
                {snapshotClock(screen.ageSeconds, language)}
              </span>
            </div>
          )}
        </div>
        <div className="actions">
          <button id="reports-refresh" className="btn" type="button" onClick={() => screen.refresh(true)}>
            <Icon name="refresh" /> {t("Обновить")}
          </button>
          <button
            id="reports-export"
            className="btn"
            type="button"
            disabled={!ledger}
            onClick={() => exportSelection(shown, ledger ? ledger.reports : [])}
          >
            <Icon name="download" /> {t("Экспорт")}
          </button>
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

      {ledger && tiles.length > 0 && <KpiTiles id="reports-kpi" tiles={kpiRow(ledger, tiles, t)} />}

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
      {ledger && tab === "quality" && (
        <>
          <KpiTiles id="reports-quality-kpi" tiles={tiles.slice(4)} />
          <QualityTab ledger={ledger} analytics={orchestration.data?.analytics ?? null} />
        </>
      )}
      {ledger && tab === "readiness" && <ReadinessTab ledger={ledger} />}

      {ledger && tab === "list" && (
        <div className="reports-grid">
          <section className="panel reports-panel">
            <div className="panel-head">
              <h2>{t("Отчёты")}</h2>
              <span className="small muted" id="reports-count">
                {t("{shown} из {total}", { shown: shown.length, total: ledger.stages.length })}
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
          </section>
          {current ? (
            <ReportDetail
              key={current.dispatch_id}
              stage={current}
              report={current.report === null ? undefined : reports.get(current.report)}
            />
          ) : (
            <section className="panel report-detail-panel" id="report-detail">
              <div className="report-empty">{t("Ничего не найдено")}</div>
            </section>
          )}
        </div>
      )}
      {ledger && tab === "list" && current && (
        <QaLane ledger={ledger} ticket={current.ticket}>
          <QaLogs ledger={ledger} dispatchId={current.dispatch_id} />
        </QaLane>
      )}
      </TabPanels>
      )}
    </div>
  );
}
