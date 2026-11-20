/* The candidate drawer shared by Reports and Publish: one publish entry of reports.snapshot in the
   v3 Drawer with three tabs. Evidence: the batch's row of the evidence matrix, its review and QA
   report refs and the batch chronology (reports.timeline). Качество: the report heads of the batch
   with their state and the QA attempts of its dispatches. Готовность: the preflight rows, the
   verdict, the refusals, candidate → target and the PR receipt. Every value comes from reports.*;
   an unknown one stays «нет данных». */
import { useState } from "react";
import { Drawer } from "../ds";
import { useI18n } from "../i18n";
import { TabList, TabPanel } from "../views/Tabs";
import type { PublishEntry, ReportsSnapshot } from "../ws/ledger";
import { preflightRows } from "./preflight";
import { EVIDENCE_COLUMNS, StatusWord, VERDICT_TONE, reportState } from "./ReportViews";
import { Timeline } from "./Timeline";

type Tab = "evidence" | "quality" | "readiness";
const STATE_TONE = { passed: "mint", attention: "lavender", blocked: "violet" } as const;
const CELL_TONE = { present: "mint", stale: "lavender", missing: "violet", none: "blue" } as const;
const CELL_WORD = { present: "есть", stale: "устарело", missing: "нет", none: "впереди" } as const;

const short = (sha: string | null) => (sha ? sha.slice(0, 12) : null);

export function CandidateDrawer({ entry, ledger, onClose }: { entry: PublishEntry; ledger: ReportsSnapshot; onClose: () => void }) {
  const { t, state } = useI18n();
  const [tab, setTab] = useState<Tab>("evidence");
  const noData = t("нет данных");
  const evidence = ledger.evidence.find((row) => row.batch_id === entry.batch_id) ?? null;
  const heads = ledger.reports.filter((report) => report.batch_id === entry.batch_id);
  const dispatches = new Set(ledger.stages.filter((stage) => stage.batch_id === entry.batch_id).map((stage) => stage.dispatch_id));
  const attempts = ledger.qa_attempts.filter((attempt) => dispatches.has(attempt.dispatch_id));
  const tabs: [Tab, string][] = [
    ["evidence", "Evidence"],
    ["quality", t("Качество")],
    ["readiness", t("Готовность")],
  ];
  return (
    <Drawer
      id="candidate-drawer"
      title={`${t("Кандидат")} · ${entry.ticket || entry.batch_id}`}
      closeLabel={t("Закрыть")}
      onClose={onClose}
    >
      <TabList id="candidate" label={t("Кандидат")} className="ds-pipe" tabClass={(on) => (on ? "ds-pipe-tab ds-on" : "ds-pipe-tab")} tabs={tabs} value={tab} onChange={(id) => setTab(id as Tab)} />
      <TabPanel id="candidate" tab="evidence" value={tab} className="ds-drawer-tab">
        <dl className="ds-kv" id="candidate-evidence">
          {EVIDENCE_COLUMNS.map(([column, label]) => (
            <div className="ds-kv-row" key={column}>
              <dt>{label}</dt>
              <dd>{evidence ? <StatusWord tone={CELL_TONE[evidence[column]]} word={t(CELL_WORD[evidence[column]])} /> : noData}</dd>
            </div>
          ))}
          <div className="ds-kv-row">
            <dt>Review</dt>
            <dd>{entry.review ? `${entry.review.dispatch_id} · ${state(entry.review.outcome)}` : noData}</dd>
          </div>
          <div className="ds-kv-row">
            <dt>QA</dt>
            <dd>{entry.qa ? `${entry.qa.dispatch_id} · ${state(entry.qa.outcome)}` : noData}</dd>
          </div>
        </dl>
        <Timeline batchId={entry.batch_id} />
      </TabPanel>
      <TabPanel id="candidate" tab="quality" value={tab} className="ds-drawer-tab">
        <h3 className="ds-group-title">{t("Отчёты batch")}</h3>
        {heads.length === 0 ? (
          <p className="ds-empty">{noData}</p>
        ) : (
          <ul className="ds-rows" id="candidate-reports">
            {heads.map((report) => {
              const status = reportState(report);
              return (
                <li className="ds-row" key={report.dispatch_id} data-dispatch={report.dispatch_id}>
                  <StatusWord tone={STATE_TONE[status]} word={t(status === "passed" ? "Пройдено" : status === "attention" ? "Внимание" : "Заблокировано")} />
                  <span className="ds-row-main">
                    <span className="ds-row-title">{`${report.role} · ${report.dispatch_id}`}</span>
                    <span className="ds-row-sub">{`${state(report.outcome)} · ${report.reported_at || noData}`}</span>
                  </span>
                </li>
              );
            })}
          </ul>
        )}
        <h3 className="ds-group-title">{t("Попытки QA")}</h3>
        {attempts.length === 0 ? (
          <p className="ds-empty">{t("QA-попыток нет")}</p>
        ) : (
          <ul className="ds-rows" id="candidate-qa-attempts">
            {attempts.map((attempt) => (
              <li className="ds-row" key={`${attempt.dispatch_id}-${attempt.failed_at}`}>
                <StatusWord tone="violet" word={attempt.stage} />
                <span className="ds-row-main">
                  <span className="ds-row-title">{attempt.dispatch_id}</span>
                  <span className="ds-row-sub">{attempt.message || noData}</span>
                </span>
                <span className="ds-row-end">{attempt.failed_at || noData}</span>
              </li>
            ))}
          </ul>
        )}
      </TabPanel>
      <TabPanel id="candidate" tab="readiness" value={tab} className="ds-drawer-tab">
        <dl className="ds-kv" id="candidate-readiness">
          <div className="ds-kv-row">
            <dt>{t("Вердикт")}</dt>
            <dd>
              <StatusWord tone={VERDICT_TONE[entry.verdict]} word={state(entry.verdict)} verdict={entry.verdict} />
            </dd>
          </div>
          {preflightRows(entry, state).map((row) => (
            <div className="ds-kv-row" key={row.label} data-check={row.label}>
              <dt>{row.label}</dt>
              <dd>
                <StatusWord tone={row.tone} word={state(row.status)} /> {row.detail}
              </dd>
            </div>
          ))}
          <div className="ds-kv-row">
            <dt>{t("Кандидат → цель")}</dt>
            <dd>{`${short(entry.candidate) ?? noData} → ${entry.integration_ref ?? short(entry.target) ?? noData}`}</dd>
          </div>
          <div className="ds-kv-row">
            <dt>{t("Отказы")}</dt>
            <dd>{entry.refusals.length ? entry.refusals.join(" · ") : t("нет")}</dd>
          </div>
          <div className="ds-kv-row">
            <dt>PR</dt>
            <dd>{entry.pr_url ? `${state(entry.pr_state)} · ${entry.pr_url}` : `${state(entry.pr_state) || noData}`}</dd>
          </div>
        </dl>
      </TabPanel>
    </Drawer>
  );
}
