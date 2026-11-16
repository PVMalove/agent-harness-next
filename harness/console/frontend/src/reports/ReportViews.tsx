/* The mockup's Reports blocks over reports.snapshot and the ledger analytics: the summary, the QA
   lane, and the Evidence, Quality and Readiness tabs. The evidence matrix is the kernel's
   (`evidence` of the snapshot, pipeline_kpi.py `evidence_matrix`); a column without a source shows
   no data. */
import type { ReactNode } from "react";
import { StatusIcon } from "../ds";
import type { Tone } from "../ds";
import { useI18n } from "../i18n";
import { Bar, NoData } from "../steps/ActivityViews";
import type {
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

/** An evidence cell as a status shape and a word, never a glyph whose meaning lives in a title. */
const CELL_TONE: Record<EvidenceCell, Tone> = { present: "ok", stale: "warn", missing: "err", none: "off" };
const CELL_WORD: Record<EvidenceCell, string> = { present: "есть", stale: "устарело", missing: "нет", none: "впереди" };

/** The Evidence tab inside its panel: the matrix as a table with row and column headers, then the
    completeness of every batch. */
export function EvidenceTab({ rows }: { rows: readonly EvidenceRow[] }) {
  const { t } = useI18n();
  const known = 4;
  const cells = (row: EvidenceRow) => EVIDENCE_COLUMNS.map(([field]) => row[field]);
  return (
    <div className="ds-report-tab" id="reports-evidence">
      {rows.length === 0 ? (
        <p className="ds-empty">{t("Batch в ledger нет")}</p>
      ) : (
        <div className="ds-table-wrap" role="region" tabIndex={0} aria-labelledby="reports-evidence-caption">
          <table className="ds-table">
            <caption id="reports-evidence-caption">
              {t("Coverage по batch")} · {t("обязательные артефакты")}
            </caption>
            <thead>
              <tr>
                <th scope="col">batch</th>
                {EVIDENCE_COLUMNS.map(([field, column]) => (
                  <th scope="col" key={field}>
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr className="ds-evidence-row" key={row.batch_id} data-batch={row.batch_id}>
                  <th scope="row">{row.ticket || row.batch_id}</th>
                  {cells(row).map((cell, index) => (
                    <td key={EVIDENCE_COLUMNS[index]![0]} className="ds-evidence-cell" data-cell={cell}>
                      <span className="ds-status-line">
                        <StatusIcon tone={CELL_TONE[cell]} />
                        {t(CELL_WORD[cell])}
                      </span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <section className="ds-report-block" aria-labelledby="reports-complete-title">
        <h3 className="ds-report-sub" id="reports-complete-title">
          {t("Полнота")} <span className="ds-muted">{`${t("есть")} / ${known}`}</span>
        </h3>
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
        <p className="ds-note">{t("Stale evidence остаётся видимым, но не считается актуальным доказательством.")}</p>
      </section>
    </div>
  );
}

/** The Quality tab reads reports.snapshot only: results by role from the report heads, first-pass
    QA and the QA attempts. Findings by severity and stage latency are not in reports.* and stay on
    Orchestration; their cards say so instead of borrowing another snapshot. */
export function QualityTab({ ledger }: { ledger: ReportsSnapshot }) {
  const { t } = useI18n();
  const passed = ledger.reports_kpi.qa_first_pass;
  const total = ledger.reports_kpi.qa_tickets;
  const attempts = new Map<string, number>();
  for (const attempt of ledger.qa_attempts) attempts.set(attempt.dispatch_id, (attempts.get(attempt.dispatch_id) ?? 0) + 1);
  const roles = [...new Set(ledger.reports.map((report) => report.role))].sort();
  const notInSnapshot = <p className="orch-note">{t("нет данных в снимке отчётов")}</p>;
  return (
    <section className="panel report-analytics" id="reports-quality">
      <div className="orch-analytics-head">
        <h2>{t("Качество")}</h2>
        <span>{t("результаты по ролям")} · {t("попытки")}</span>
      </div>
      <div className="orch-analytics-grid">
        <article className="orch-chart" id="reports-results-by-role">
          <div className="orch-chart-head">
            <h3>{t("Результаты по ролям")}</h3>
            <span>{t("{count} отчётов", { count: ledger.reports.length })}</span>
          </div>
          {roles.length === 0 ? (
            <p className="orch-note">{t("Отчётов нет")}</p>
          ) : (
            roles.map((role) => {
              const counts = reportCounts(ledger.reports.filter((report) => report.role === role));
              return (
                <div className="work-stat-row" key={role} data-role={role}>
                  <span>{role}</span>
                  <span className="report-role-stack">
                    <span className="ds-status-line">
                      <StatusIcon tone="ok" label={t("Пройдено")} /> {counts.passed}
                    </span>
                    <span className="ds-status-line">
                      <StatusIcon tone="warn" label={t("Внимание")} /> {counts.attention}
                    </span>
                    <span className="ds-status-line">
                      <StatusIcon tone="err" label={t("Заблокировано")} /> {counts.blocked}
                    </span>
                  </span>
                  <b>{counts.all}</b>
                </div>
              );
            })
          )}
        </article>
        <article className="orch-chart">
          <div className="orch-chart-head">
            <h3>{t("Findings по severity")}</h3>
            <span>{t("на экране «Оркестрация»")}</span>
          </div>
          {notInSnapshot}
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
            <span>{t("на экране «Оркестрация»")}</span>
          </div>
          {notInSnapshot}
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

/** The StatusIcon tone of a mockup tone word. */
export const ICON_TONE: Readonly<Record<string, Tone>> = { mint: "ok", violet: "err", blue: "off", lavender: "warn" };

/** A status as a StatusIcon with its word beside it; the word is hidden from assistive technology
    because the icon already carries it. */
export function StatusWord({ tone, word, verdict }: { tone: string; word: string; verdict?: string }) {
  return (
    <span className="ds-status-line">
      <StatusIcon tone={ICON_TONE[tone] ?? "off"} label={word} />
      <span aria-hidden="true" data-verdict={verdict}>
        {word}
      </span>
    </span>
  );
}

export function ReadinessTab({ ledger, onOpen }: { ledger: ReportsSnapshot; onOpen?: (batchId: string) => void }) {
  const { t, state } = useI18n();
  const blocked = ledger.publish.filter((entry) => entry.refusals.length > 0);
  return (
    <div className="ds-report-tab" id="reports-readiness">
      {ledger.publish.length === 0 ? (
        <p className="ds-empty">{t("Batch для публикации нет")}</p>
      ) : (
        <div className="ds-table-wrap" role="region" tabIndex={0} aria-labelledby="reports-ready-caption">
          <table className="ds-table">
            <caption id="reports-ready-caption">Release Gate</caption>
            <thead>
              <tr>
                <th scope="col">{t("Кандидат")}</th>
                <th scope="col">{t("Цель")}</th>
                <th scope="col">{t("Дерево")}</th>
                <th scope="col">QA</th>
                <th scope="col">{t("Вердикт")}</th>
                <th scope="col">{t("Блокер")}</th>
              </tr>
            </thead>
            <tbody>
              {ledger.publish.map((entry) => {
                const [label, tone] = tree(entry.head_matches);
                return (
                  <tr className="ds-ready-row" key={entry.batch_id} data-batch={entry.batch_id}>
                    <th scope="row">
                      {onOpen ? (
                        <button type="button" className="ds-btn ds-btn-sm report-ready-open" title={t("Открыть кандидата")} onClick={() => onOpen(entry.batch_id)}>
                          {entry.candidate ? entry.candidate.slice(0, 12) : entry.ticket || entry.batch_id}
                        </button>
                      ) : entry.candidate ? (
                        entry.candidate.slice(0, 12)
                      ) : (
                        "—"
                      )}
                    </th>
                    <td className="ds-mono">{entry.target ? entry.target.slice(0, 12) : "—"}</td>
                    <td>
                      <StatusWord tone={tone} word={t(label)} />
                    </td>
                    <td>{entry.qa ? state(entry.qa.outcome) : "—"}</td>
                    <td>
                      <StatusWord tone={VERDICT_TONE[entry.verdict]} word={state(entry.verdict)} verdict={entry.verdict} />
                    </td>
                    <td className="ds-table-wrapcell">{entry.refusals.join(" · ") || "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <section className="ds-report-block" aria-labelledby="reports-blockers-title">
        <h3 className="ds-report-sub" id="reports-blockers-title">
          Publish blockers <span className="ds-muted">{t("{count} в очереди", { count: blocked.length })}</span>
        </h3>
        <div className="report-blockers">
          {blocked.length === 0 ? (
            <p className="ds-note">{t("Блокеров публикации нет")}</p>
          ) : (
            blocked.map((entry) => (
              <div key={entry.batch_id}>
                <span>{entry.ticket || entry.batch_id}</span>
                <StatusWord tone="lavender" word={entry.refusals[0]!} />
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
