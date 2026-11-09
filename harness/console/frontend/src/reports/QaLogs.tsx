/* The QA log of the selected stage: the failed qa-lane attempts and every QA gate run with its
   verdict and log tail, worded as the TUI's `qa_log_text`. Untrusted log lines stay text. */
import { useI18n } from "../i18n";
import type { Ledger } from "../ws/ledger";
import { qaLogText } from "./format";

export function QaLogs({ ledger, dispatchId }: { ledger: Ledger; dispatchId: string }) {
  const { t } = useI18n();
  const log = qaLogText(ledger, dispatchId);
  if (!log) return null;
  return (
    <section className="panel report-qa-log" id="report-qa-log">
      <div className="panel-head">
        <h2>QA log</h2>
      </div>
      <pre className="report-log" aria-label={t("Логи QA")}>
        {log}
      </pre>
    </section>
  );
}
