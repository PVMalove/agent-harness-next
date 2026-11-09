/* The selected stage's completion report, read with reports.report: its sections as the TUI draws
   them (a check, a review axis, a risk and a blocker carry a status). The body is untrusted
   role output: it is only ever rendered as React text. */
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { useScreen } from "../screens/useScreen";
import { parseReport } from "../ws/ledger";
import type { ReportHead, StageHead } from "../ws/ledger";
import { renderStatus, reportSectionLines, stageStatus } from "./format";

export function ReportDetail({ stage, report }: { stage: StageHead; report: ReportHead | undefined }) {
  const { t, language } = useI18n();
  const status = stageStatus(stage, report);
  return (
    <section className="panel report-detail-panel" id="report-detail">
      <div className="panel-head">
        <h2>{t("Детали отчёта")}</h2>
        <span className={`report-status ${status.kind}`}>{renderStatus(status, language)}</span>
      </div>
      <div className="report-detail-body">
        <div className="report-detail-top">
          <span className="report-type-label">
            <Icon name="reports" /> {stage.role}
          </span>
          <code>{stage.dispatch_id}</code>
        </div>
        <h3>{t("Отчёт {role} · {ticket}", { role: stage.role, ticket: stage.ticket || "?" })}</h3>
        <div className="report-meta">
          <span>{stage.ticket}</span>
          <span>{stage.role}</span>
          <span>{stage.batch_id || "?"}</span>
          <span>{stage.at || "?"}</span>
        </div>
        {report ? <ReportBody dispatchId={report.dispatch_id} /> : <p className="report-empty">{t("нет отчёта")}</p>}
      </div>
    </section>
  );
}

function ReportBody({ dispatchId }: { dispatchId: string }) {
  const { t, language } = useI18n();
  const body = useScreen({ type: "reports.report", params: { dispatch_id: dispatchId } }, parseReport);
  if (body.error) {
    return (
      <p className="command-refusal err" role="alert" data-code={body.error.code}>
        {t("Отчёт не построен")}: {body.error.message || body.error.code}
      </p>
    );
  }
  if (!body.data) return <p className="report-empty">{t("Обновление…")}</p>;
  const next = body.data.next_coordinator_action;
  const outcome = typeof body.data.outcome === "string" ? body.data.outcome : "";
  const tone = outcome === "completed" ? "passed" : outcome === "blocked" || outcome === "failed" ? "blocked" : "attention";
  return (
    <div className="report-sections">
      {typeof next === "string" && next ? (
        <div className={`report-conclusion ${tone}`} id="report-conclusion">
          <Icon name={tone === "passed" ? "check" : tone === "blocked" ? "x" : "warning"} />
          <p>{next}</p>
        </div>
      ) : null}
      {reportSectionLines(body.data).map(([title, lines]) => (
        <section key={title} className="report-section" data-section={title}>
          <div className="report-evidence-head">{title}</div>
          {lines.map(([status, line], index) => (
            <p key={index} className="report-line">
              {status && <span className={`report-status ${status.kind}`}>{renderStatus(status, language)}</span>}
              {line && <span className="report-line-text">{line}</span>}
            </p>
          ))}
        </section>
      ))}
    </div>
  );
}
