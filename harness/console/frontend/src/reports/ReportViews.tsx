/* The mockup's Reports blocks over reports.snapshot and the ledger analytics: the summary, the QA
   lane, and the Evidence, Quality and Readiness tabs. The evidence matrix is the kernel's
   (`evidence` of the snapshot, pipeline_kpi.py `evidence_matrix`); a column without a source shows
   no data. */
import type { ReactNode } from "react";
import { useI18n } from "../i18n";
import { Bar, NoData } from "../steps/ActivityViews";
import type {
  Analytics,
  EvidenceCell,
  EvidenceRow,
  Ledger,
  PublishEntry,
  ReportHead,
  ReportsSnapshot,
} from "../ws/ledger";

export type ReportState = "passed" | "attention" | "blocked";

/** The mockup's status of a report head: a blocker blocks, a risk asks for attention. */
export const reportState = (report: ReportHead): ReportState =>
  report.has_blockers || report.outcome === "blocked" || report.outcome === "failed"
    ? "blocked"
    : report.has_risks
      ? "attention"
      : "passed";

export function reportCounts(reports: readonly ReportHead[]): Record<"all" | ReportState, number> {
  const counts = { all: reports.length, passed: 0, attention: 0, blocked: 0 };
  for (const report of reports) counts[reportState(report)] += 1;
  return counts;
}

export function ReportsSummary({ reports }: { reports: readonly ReportHead[] }) {
  const { t } = useI18n();
  const counts = reportCounts(reports);
  return (
    <div className="reports-summary" id="reports-summary">
      <div>
        <span>{t("Отчётов")}</span>
        <b>{counts.all}</b>
        <small>{t("в выборке")}</small>
      </div>
      <div>
        <span>{t("Пройдено")}</span>
        <b className="ok">{counts.passed}</b>
        <small>{t("без рисков и блокеров")}</small>
      </div>
      <div>
        <span>{t("Внимание")}</span>
        <b className="warn">{counts.attention}</b>
        <small>{t("нужен просмотр")}</small>
      </div>
      <div>
        <span>{t("Заблокировано")}</span>
        <b className="err">{counts.blocked}</b>
        <small>{t("решение человека")}</small>
      </div>
    </div>
  );
}

/** The QA lane of the selected ticket, full width under the report grid: its failed attempts,
    then its QA runs, in time order; `children` (the folded QA log) close the panel. */
export function QaLane({ ledger, ticket, children }: { ledger: Ledger; ticket: string; children?: ReactNode }) {
  const { t, state } = useI18n();
  const ticketDispatches = new Set(ledger.stages.filter((stage) => stage.ticket === ticket).map((stage) => stage.dispatch_id));
  const attempts = ledger.qa_attempts
    .filter((attempt) => ticketDispatches.has(attempt.dispatch_id))
    .map((attempt) => ({ at: attempt.failed_at, title: attempt.stage, detail: attempt.message, state: "fail" }));
  const runs = ledger.qa_runs
    .filter((run) => run.ticket === ticket)
    .map((run) => ({
      at: run.logged_at,
      title: "QA gate",
      detail: run.commands.map(([command, code]) => `${command} → ${code}`).join(" · "),
      state: run.outcome === "pass" || run.outcome === "passed" ? "pass" : "fail",
    }));
  const lane = [...attempts, ...runs].sort((a, b) => (a.at < b.at ? -1 : 1));
  return (
    <section className="panel qa-lane-panel" id="qa-lane">
      <div className="panel-head">
        <h2>QA lane · {ticket || "—"}</h2>
        <span className="small muted">{t("{count} попыток", { count: lane.length })}</span>
      </div>
      {lane.length === 0 ? (
        <div className="report-empty">{t("QA-попыток нет")}</div>
      ) : (
        <div className="qa-lane">
          {lane.map((item, index) => (
            <span key={index} style={{ display: "contents" }}>
              <div className={`qa-attempt ${item.state}`}>
                <span className="qa-attempt-num">{String(index + 1).padStart(2, "0")}</span>
                <b>{item.title}</b>
                <small>{item.detail}</small>
                <span className="qa-attempt-state">{state(item.state)}</span>
              </div>
              {index < lane.length - 1 ? <span className="qa-arrow">→</span> : null}
            </span>
          ))}
        </div>
      )}
      {children}
    </section>
  );
}

/** The matrix columns: the wire field of `EvidenceRow` and its header. */
export const EVIDENCE_COLUMNS: readonly [Exclude<keyof EvidenceRow, "batch_id" | "ticket">, string][] = [
  ["developer", "developer"],
  ["review", "review"],
  ["qa", "qa"],
  ["qa_run", "QA run"],
  ["receipt", "receipt"],
  ["publish", "publish"],
];

const MARK: Record<EvidenceCell, string> = { present: "✓", stale: "!", missing: "—", none: "·" };

export function EvidenceTab({ rows }: { rows: readonly EvidenceRow[] }) {
  const { t } = useI18n();
  const known = 4;
  const cells = (row: EvidenceRow) => EVIDENCE_COLUMNS.map(([field]) => row[field]);
  return (
    <section className="panel report-analytics" id="reports-evidence">
      <div className="orch-analytics-head">
        <h2>Evidence</h2>
        <span>present / stale / missing</span>
      </div>
      <div className="orch-analytics-grid">
        <article className="orch-chart wide">
          <div className="orch-chart-head">
            <h3>{t("Coverage по batch")}</h3>
            <span>{t("обязательные артефакты")}</span>
          </div>
          {rows.length === 0 ? (
            <p className="orch-note">{t("Batch в ledger нет")}</p>
          ) : (
            <div className="report-evidence-matrix">
              <div className="report-evidence-head">
                <span>batch</span>
                {EVIDENCE_COLUMNS.map(([field, column]) => (
                  <span key={field}>{column}</span>
                ))}
              </div>
              {rows.map((row) => (
                <div className="report-evidence-row" key={row.batch_id} data-batch={row.batch_id}>
                  <b>{row.ticket || row.batch_id}</b>
                  {cells(row).map((cell, index) => (
                    <span
                      key={index}
                      className={`report-evidence-cell ${cell === "none" ? "missing" : cell}`}
                      title={cell === "none" ? t("Источника нет") : `${EVIDENCE_COLUMNS[index]![1]}: ${cell}`}
                    >
                      {MARK[cell]}
                    </span>
                  ))}
                </div>
              ))}
            </div>
          )}
          <div className="orch-legend">
            <span>
              <i className="mint" />
              present
            </span>
            <span>
              <i className="lavender" />
              stale
            </span>
            <span>
              <i className="muted" />
              missing
            </span>
          </div>
        </article>
        <article className="orch-chart wide">
          <div className="orch-chart-head">
            <h3>Completeness</h3>
            <span>present / {known}</span>
          </div>
          {rows.map((row) => {
            const present = cells(row).filter((cell) => cell === "present").length;
            return (
              <div className="report-complete-row" key={row.batch_id}>
                <span>{row.ticket || row.batch_id}</span>
                <Bar value={present} max={known} tone={present === known ? "mint" : "lavender"} />
                <b>
                  {present} / {known}
                </b>
              </div>
            );
          })}
          <p className="orch-note">{t("Stale evidence остаётся видимым, но не считается актуальным доказательством.")}</p>
        </article>
      </div>
    </section>
  );
}

const record = (figure: unknown): Record<string, number> =>
  figure && typeof figure === "object" && !Array.isArray(figure) ? (figure as Record<string, number>) : {};

export function QualityTab({ ledger, analytics }: { ledger: ReportsSnapshot; analytics: Analytics | null }) {
  const { t } = useI18n();
  const findings = record(analytics?.quality.findings_by_severity);
  const maxFindings = Math.max(1, ...Object.values(findings));
  const p50 = record(analytics?.flow.stage_p50_by_role);
  const p95 = record(analytics?.flow.stage_p95_by_role);
  const maxLatency = Math.max(1, ...Object.values(p95));
  const passed = ledger.reports_kpi.qa_first_pass;
  const total = ledger.reports_kpi.qa_tickets;
  const attempts = new Map<string, number>();
  for (const attempt of ledger.qa_attempts) attempts.set(attempt.dispatch_id, (attempts.get(attempt.dispatch_id) ?? 0) + 1);
  const minutes = (seconds: number) => Math.round(seconds / 60);
  return (
    <section className="panel report-analytics" id="reports-quality">
      <div className="orch-analytics-head">
        <h2>{t("Качество")}</h2>
        <span>findings · {t("попытки")} · latency</span>
      </div>
      <div className="orch-analytics-grid">
        <article className="orch-chart">
          <div className="orch-chart-head">
            <h3>{t("Findings по severity")}</h3>
            <span>{Object.values(findings).reduce((sum, value) => sum + value, 0)} findings</span>
          </div>
          {analytics === null ? (
            <NoData />
          ) : Object.keys(findings).length === 0 ? (
            <p className="orch-note">{t("Findings нет")}</p>
          ) : (
            Object.entries(findings).map(([label, value]) => (
              <div className="work-stat-row" key={label}>
                <span>{label}</span>
                <Bar value={value} max={maxFindings} tone="violet" />
                <b>{value}</b>
              </div>
            ))
          )}
        </article>
        <article className="orch-chart">
          <div className="orch-chart-head">
            <h3>{t("Приёмка с первого раза")}</h3>
            <span>QA</span>
          </div>
          {passed === null || total === null ? (
            <NoData />
          ) : (
            <div className="report-firstpass">
              <b>
                {passed} / {total}
              </b>
              <Bar value={passed} max={total} tone="mint" />
              <small>{t("приняты без повторного прогона")}</small>
            </div>
          )}
        </article>
        <article className="orch-chart wide">
          <div className="orch-chart-head">
            <h3>{t("Попытки QA")}</h3>
            <span>{t("по dispatch")}</span>
          </div>
          {attempts.size === 0 ? (
            <p className="orch-note">{t("QA-попыток нет")}</p>
          ) : (
            [...attempts.entries()].map(([dispatch, count]) => (
              <div className="report-version-row" key={dispatch}>
                <b>{dispatch}</b>
                <div className="report-version-steps">
                  <span className="report-version-step fail">
                    <i />
                    {t("{count} попыток", { count: count })}
                  </span>
                </div>
              </div>
            ))
          )}
        </article>
        <article className="orch-chart wide">
          <div className="orch-chart-head">
            <h3>{t("Длительность этапа p50 / p95")}</h3>
            <span>{t("минуты")}</span>
          </div>
          {Object.keys(p50).length === 0 ? (
            <p className="orch-note">{t("нет данных")}</p>
          ) : (
            Object.keys(p50).map((role) => (
              <div className="report-latency-row" key={role}>
                <span>{role}</span>
                <div className="work-age-bars">
                  <div>
                    <Bar value={minutes(p50[role]!)} max={minutes(maxLatency)} tone="cyan" />
                    <small>{minutes(p50[role]!)}</small>
                  </div>
                  <div>
                    <Bar value={minutes(p95[role] ?? 0)} max={minutes(maxLatency)} tone="violet" />
                    <small>{p95[role] === undefined ? "—" : minutes(p95[role]!)}</small>
                  </div>
                </div>
              </div>
            ))
          )}
          <div className="orch-legend">
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
      </div>
    </section>
  );
}

/** The Release Gate tree check in words: the branch head equals the candidate, or not, or unknown. */
export const tree = (matches: boolean | null): [string, string] =>
  matches === null ? ["Неизвестно", "blue"] : matches ? ["совпадает", "mint"] : ["расходится", "violet"];

/** The tone of a Release Gate verdict (kernel/publish_view.py `verdict`). */
export const VERDICT_TONE: Record<PublishEntry["verdict"], "mint" | "violet" | "blue"> = {
  ready: "mint",
  blocked: "violet",
  unknown: "blue",
};

export function ReadinessTab({ ledger }: { ledger: ReportsSnapshot }) {
  const { t, state } = useI18n();
  const blocked = ledger.publish.filter((entry) => entry.refusals.length > 0);
  return (
    <section className="panel report-analytics" id="reports-readiness">
      <div className="orch-analytics-head">
        <h2>{t("Готовность")}</h2>
        <span>Release Gate · publish blockers</span>
      </div>
      <div className="orch-analytics-grid">
        <article className="orch-chart wide">
          <div className="orch-chart-head">
            <h3>Release Gate</h3>
            <span>candidate / target / tree</span>
          </div>
          {ledger.publish.length === 0 ? (
            <p className="orch-note">{t("Batch для публикации нет")}</p>
          ) : (
            <div className="report-ready-table">
              <div className="report-ready-head">
                <span>candidate</span>
                <span>target</span>
                <span>tree</span>
                <span>QA</span>
                <span>verdict</span>
                <span>blocker</span>
              </div>
              {ledger.publish.map((entry) => {
                const [label, tone] = tree(entry.head_matches);
                return (
                  <div className="report-ready-row" key={entry.batch_id}>
                    <b>{entry.candidate ? entry.candidate.slice(0, 12) : "—"}</b>
                    <span>{entry.target ? entry.target.slice(0, 12) : "—"}</span>
                    <span className={`orch-pill ${tone}`}>{t(label)}</span>
                    <span>{entry.qa ? state(entry.qa.outcome) : "—"}</span>
                    <span className={`orch-pill ${VERDICT_TONE[entry.verdict]}`} data-verdict={entry.verdict}>
                      {state(entry.verdict)}
                    </span>
                    <small>{entry.refusals.join(" · ") || "—"}</small>
                  </div>
                );
              })}
            </div>
          )}
        </article>
        <article className="orch-chart wide">
          <div className="orch-chart-head">
            <h3>Publish blockers</h3>
            <span>{t("{count} в очереди", { count: blocked.length })}</span>
          </div>
          <div className="report-blockers">
            {blocked.length === 0 ? (
              <p className="orch-note">{t("Блокеров публикации нет")}</p>
            ) : (
              blocked.map((entry) => (
                <div key={entry.batch_id}>
                  <span>{entry.ticket || entry.batch_id}</span>
                  <b className="orch-pill lavender">{entry.refusals[0]}</b>
                </div>
              ))
            )}
          </div>
        </article>
      </div>
    </section>
  );
}
