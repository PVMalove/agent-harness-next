/* The selected stage's completion report, read with reports.report, in the mockup's order: the
   head, the output as the summary, the checks as Evidence rows, then the conclusion (next action
   with the risk and blocker lines) and the actions. The body is untrusted role output: it is only
   ever rendered as React text. */
import { Icon } from "../icons";
import type { IconName } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { useScreen } from "../screens/useScreen";
import { roleIcon } from "../steps/ActivityViews";
import { parseReport } from "../ws/ledger";
import type { ReportHead, StageHead } from "../ws/ledger";
import { kindTone, reportSectionLines, stageStatus, statusWords } from "./format";
import type { StatusKind } from "./format";
import { clockTime } from "./StageList";

const KIND_ICON: Readonly<Record<StatusKind, IconName>> = {
  accepted: "check",
  running: "play",
  paused: "clock",
  not_started: "clock",
  error: "x",
  warning: "warning",
};

export function ReportDetail({ stage, report }: { stage: StageHead; report: ReportHead | undefined }) {
  const { t, language } = useI18n();
  const status = stageStatus(stage, report);
  return (
    <section className="panel report-detail-panel" id="report-detail">
      <div className="panel-head">
        <h2>{t("Детали отчёта")}</h2>
        <span className={`report-status ${kindTone(status.kind)}`}>{statusWords(status, language)}</span>
      </div>
      <div className="report-detail-body">
        <div className="report-detail-top">
          <span className="report-type-label">
            <Icon name={roleIcon(stage.role)} /> {stage.role}
          </span>
          <code>{stage.dispatch_id}</code>
        </div>
        <h3>{t("Отчёт {role} · {ticket}", { role: stage.role, ticket: stage.ticket || "?" })}</h3>
        <div className="report-meta">
          <span>{stage.ticket}</span>
          <span>{stage.role}</span>
          <span>{stage.batch_id || "?"}</span>
          <span>{clockTime(stage.at)}</span>
        </div>
        {report ? <ReportBody dispatchId={report.dispatch_id} /> : <p className="report-empty">{t("нет отчёта")}</p>}
        <div className="report-actions">
          <a className="btn" href={href("orchestration")}>
            {t("Оркестрация")} <Icon name="chevron" />
          </a>
        </div>
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
  const next = typeof body.data.next_coordinator_action === "string" ? body.data.next_coordinator_action : "";
  const outcome = typeof body.data.outcome === "string" ? body.data.outcome : "";
  const tone = outcome === "completed" ? "passed" : outcome === "blocked" || outcome === "failed" ? "blocked" : "attention";
  const sections = new Map(reportSectionLines(body.data));
  const summary = sections.get("Output")?.[0]?.[1] ?? "—";
  const checks = sections.get("Checks") ?? [];
  const review = sections.get("Review");
  const flags: [string, typeof checks][] = [
    ["Risks", sections.get("Risks") ?? []],
    ["Blockers", sections.get("Blockers") ?? []],
  ];
  return (
    <>
      <p className="report-summary">{summary}</p>
      <div className="report-evidence-head">Evidence</div>
      <div className="report-evidences">
        {checks.map(([status, line], index) => {
          const [name, ...rest] = line.split(" — ");
          return (
            <div key={index} className="report-evidence">
              <span className={`report-evidence-icon ${kindTone(status?.kind ?? "not_started")}`}>
                <Icon name={KIND_ICON[status?.kind ?? "not_started"]} />
              </span>
              <span>
                <b>{name}</b>
                {rest.length > 0 && <small>{rest.join(" — ")}</small>}
              </span>
              {status && <span className={`report-evidence-state ${kindTone(status.kind)}`}>{statusWords(status, language)}</span>}
            </div>
          );
        })}
      </div>
      {review && (
        <section className="report-section" data-section="Review">
          <div className="report-evidence-head">Review</div>
          {review.map(([status, line], index) => (
            <p key={index} className="report-line">
              {status && <span className={`report-status ${kindTone(status.kind)}`}>{statusWords(status, language)}</span>}
              {line && <span className="report-line-text">{line}</span>}
            </p>
          ))}
        </section>
      )}
      <div className={`report-conclusion ${tone}`} id="report-conclusion">
        <Icon name={tone === "passed" ? "check" : tone === "blocked" ? "x" : "warning"} />
        <div>
          <p>{next || t("нет данных · следующее действие не записано")}</p>
          {flags.map(([title, lines]) =>
            lines.map(([status, line], index) => (
              <p key={`${title}-${index}`} className="report-line" data-section={title}>
                <span className="report-line-title">{title}</span>
                {status && <span className={`report-status ${kindTone(status.kind)}`}>{statusWords(status, language)}</span>}
                {line && <span className="report-line-text">{line}</span>}
              </p>
            )),
          )}
        </div>
      </div>
    </>
  );
}
