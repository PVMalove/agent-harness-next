/* Publication on the design system v3 over the read-only publish view of reports.snapshot
   (kernel/publish_view.py): the page header (refresh and links on the right), the summary (publish
   entries by verdict; the selected candidate, its target and PR receipt as facts), the pipeline
   tabs Обзор / Preflight / PR / MR / Evidence, the candidate list and the selected candidate's
   detail. The list defaults to the latest batch with a review report (H1); «Открыть кандидата»
   opens the candidate drawer shared with Reports. "Решение человека" words the verdict and its
   reasons (gate refusals and every preflight row that is not ok); the live ledger decisions keep
   their old look inside a `ds-legacy-island`. The console never creates a PR: "Подготовить PR"
   stays disabled, merge is the human's. */
import { useState } from "react";
import { DecisionPanel } from "../decisions/DecisionPanel";
import { PageHeader, Panel, PipeTabs, Summary } from "../ds";
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { CandidateDrawer } from "../reports/CandidateDrawer";
import { blockingReasons, passes, preflightRows, short } from "../reports/preflight";
import { StatusWord, VERDICT_TONE, tree } from "../reports/ReportViews";
import { Timeline } from "../reports/Timeline";
import { useScreen } from "../screens/useScreen";
import { NoData } from "../steps/ActivityViews";
import { snapshotClock } from "../update/format";
import { TabPanel } from "../views/Tabs";
import { parseReports } from "../ws/ledger";
import type { PublishEntry } from "../ws/ledger";

type Tab = "overview" | "preflight" | "pr" | "evidence";

/** The default batch of the selector: the latest one with a review report, else the latest.
    Entries come newest first (kernel/reports.py sorts batches by created_at, descending). */
export function defaultBatch(entries: readonly PublishEntry[]): string | null {
  const reviewed = entries.filter((entry) => entry.review !== null);
  return (reviewed[0] ?? entries[0])?.batch_id ?? null;
}

function Preflight({ entry }: { entry: PublishEntry }) {
  const { state } = useI18n();
  const rows = preflightRows(entry, state);
  return (
    <div className="publish-preflight">
      {rows.map((row) => (
        <div className="publish-check" key={row.label}>
          <StatusWord tone={row.tone} word={state(row.status)} />
          <div>
            <b>{row.label}</b>
            <small>{row.detail}</small>
          </div>
        </div>
      ))}
    </div>
  );
}

export function Publish() {
  const { t, section, tab: tabLabel, state: stateText, language } = useI18n();
  const screen = useScreen({ type: "reports.snapshot" }, parseReports);
  const ledger = screen.data;
  const entries = ledger?.publish ?? [];
  const [chosen, setChosen] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [why, setWhy] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const batch = chosen ?? defaultBatch(entries);
  const entry = entries.find((item) => item.batch_id === batch) ?? null;
  const blocked = entry ? preflightRows(entry).some((row) => !passes(row)) : true;
  const targetRef = entry ? (entry.integration_ref ?? (entry.target ? short(entry.target) : t("нет данных"))) : "";
  // Before the first snapshot nothing is known: no "no batch" and no "blocked" verdict yet.
  const empty = ledger ? t("Batch для публикации нет") : screen.error ? t("Нет данных") : t("Загрузка…");
  const reasons = entry ? blockingReasons(entry) : [empty];
  const verdicts = (verdict: PublishEntry["verdict"]) => (ledger ? entries.filter((item) => item.verdict === verdict).length : "—");
  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: tabLabel("Обзор") },
    { id: "preflight", label: "Preflight" },
    { id: "pr", label: "PR / MR" },
    { id: "evidence", label: "Evidence" },
  ];

  return (
    <div className="ds-page ds-fit publish-page" data-section="Публикация">
      <PageHeader
        title={section("Публикация")}
        subtitle={t("Candidate → target, PR/MR и evidence. Merge и публикация остаются человеку.")}
        actions={
          <>
            <button id="publish-refresh" className="ds-btn ds-btn-icon" type="button" aria-label={t("Проверить")} title={t("Проверить")} onClick={() => screen.refresh(true)}>
              <Icon name="refresh" className="ds-ic-sm" />
            </button>
            <a className="ds-btn" href={href("reports")}>
              <Icon name="reports" className="ds-ic-sm" /> {section("Reports")}
            </a>
            <a className="ds-btn" href={href("orchestration")}>
              <Icon name="orchestration" className="ds-ic-sm" /> {section("Orchestration")}
            </a>
          </>
        }
      />

      {screen.error && !ledger && (
        <p className="ds-alert ds-alert-err" role="alert" data-code={screen.error.code}>
          {t("Отчёт не построен")}: {screen.error.message || screen.error.code}
        </p>
      )}

      <Summary
        id="publish-kpis"
        label={t("Сводка публикации")}
        stats={[
          { label: t("Готово"), value: verdicts("ready"), caption: "Release Gate" },
          { label: t("Заблокировано"), value: verdicts("blocked"), caption: "Release Gate" },
          { label: t("Неизвестно"), value: verdicts("unknown"), caption: "Release Gate" },
        ]}
        facts={
          entry ? (
            <span className="publish-facts" id="publish-facts">
              <span>
                Candidate <b>{short(entry.candidate)}</b>
              </span>
              <span>target {targetRef}</span>
              <span>
                Release Gate · <b id="publish-verdict">{stateText(entry.verdict)}</b>
              </span>
              <span>PR receipt · {stateText(entry.pr_url ? entry.pr_state || "found" : "missing")}</span>
            </span>
          ) : null
        }
        snapshot={
          ledger ? (
            <span title={`${screen.cached ? t("Кэш") : t("Новый снимок")} · ${screen.ageSeconds ?? 0} s`}>
              <Icon name="clock" className="ds-ic-sm" /> {t("Снимок")} <span id="publish-updated">{snapshotClock(screen.ageSeconds, language)}</span>
            </span>
          ) : undefined
        }
      />

      <PipeTabs id="publish" label={section("Публикация")} tabs={tabs} value={tab} onChange={(id) => setTab(id as Tab)} />

      <div className="ds-split publish-workspace">
        <Panel title={t("Кандидаты")} count={ledger ? entries.length : "—"} fill scroll="list" id="publish-candidates" label={t("Кандидаты")}>
          {entries.length === 0 ? (
            <p className="ds-empty">{empty}</p>
          ) : (
            entries.map((item) => {
              const rows = preflightRows(item);
              return (
                <button
                  key={item.batch_id}
                  type="button"
                  className="ds-row ds-row-button"
                  data-batch={item.batch_id}
                  aria-pressed={item.batch_id === batch}
                  onClick={() => setChosen(item.batch_id)}
                >
                  <StatusWord tone={VERDICT_TONE[item.verdict]} word={stateText(item.verdict)} />
                  <span className="ds-row-main">
                    <span className="ds-row-title">{`${item.ticket || item.batch_id} · ${short(item.candidate)}`}</span>
                    <span className="ds-row-sub">{item.branch || "—"}</span>
                  </span>
                  <span className="ds-row-end">{t("{passed} / {total} пройдено", { passed: rows.filter(passes).length, total: rows.length })}</span>
                </button>
              );
            })
          )}
        </Panel>

        <Panel
          title="Release candidate"
          fill
          scroll="text"
          id="publish-candidate"
          className="publish-candidate"
          label="Release candidate"
          actions={
            entry ? (
              <button id="publish-open-candidate" className="ds-btn ds-btn-sm" type="button" onClick={() => setDrawer(true)}>
                {t("Открыть кандидата")}
              </button>
            ) : null
          }
        >
          <TabPanel id="publish" tab="overview" value={tab} className="publish-tab">
            {entry ? (
              <>
                <div className="publish-candidate-body">
                  <code className="publish-sha">{entry.candidate ?? "—"}</code>
                  <h3>{[entry.ticket || entry.batch_id, entry.branch].filter(Boolean).join(" · ")}</h3>
                  <div className="publish-meta">
                    <span>
                      <Icon name="branch" />
                      {entry.branch || "—"}
                    </span>
                    <span>target {targetRef}</span>
                    <span>QA {entry.qa ? stateText(entry.qa.outcome) : "—"}</span>
                  </div>
                </div>
                <section className="publish-gate" id="publish-gate" aria-label="Release Gate">
                  <h3 className="ds-group-title">
                    Release Gate · <StatusWord tone={VERDICT_TONE[entry.verdict]} word={stateText(entry.verdict)} />
                  </h3>
                  <div className="publish-gate-facts">
                    <div>
                      <span>tree</span>
                      <b>{t(tree(entry.head_matches)[0])}</b>
                    </div>
                    <div>
                      <span>QA</span>
                      <b>{entry.qa ? stateText(entry.qa.outcome) : "—"}</b>
                    </div>
                    <div>
                      <span>reason</span>
                      <b>{entry.refusals[0] ?? t("нет отказов")}</b>
                    </div>
                    <div>
                      <span>merge</span>
                      <b>{t("только человек")}</b>
                    </div>
                  </div>
                </section>
                <section className="publish-preflight-panel" id="publish-preflight-overview" aria-label="Preflight">
                  <h3 className="ds-group-title">
                    Preflight · {t("{passed} / {total} пройдено", { passed: preflightRows(entry).filter(passes).length, total: preflightRows(entry).length })}
                  </h3>
                  <Preflight entry={entry} />
                </section>
              </>
            ) : (
              <p className="ds-empty">{empty}</p>
            )}
            {ledger && (
            <section className="publish-decision" id="publish-decision" aria-label={t("Решение человека")}>
              <h3 className="ds-group-title">
                {t("Решение человека")} · <StatusWord tone={blocked ? "violet" : "mint"} word={stateText(blocked ? "blocked" : "ready")} />
              </h3>
              <div className="publish-decision-body">
                <div className={`publish-decision-text ${blocked ? "blocked" : "ready"}`}>
                  <b>{blocked ? t("PR не готов к созданию") : t("PR готов к созданию")}</b>
                  <p>{reasons.length ? reasons.join(" · ") : t("Отказов гейта нет")}</p>
                  {why && reasons.length > 0 && (
                    <ul className="publish-why" id="publish-why">
                      {reasons.map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="publish-decision-actions">
                  <button className="ds-btn ds-btn-primary" type="button" disabled aria-disabled="true" title={t("Консоль не создаёт PR: merge выполняет человек")}>
                    {t("Подготовить PR")}
                  </button>
                  <button className="ds-btn" type="button" aria-expanded={why} onClick={() => setWhy(!why)}>
                    {t("Почему")}
                  </button>
                  <a className="ds-btn" href={href("reports")}>
                    <Icon name="reports" className="ds-ic-sm" /> {section("Reports")}
                  </a>
                </div>
              </div>
            </section>
            )}
            <div className="publish-decisions ds-legacy-island" id="publish-decisions">
              <DecisionPanel kinds={["report-decision", "attention"]} hideWhenEmpty />
            </div>
          </TabPanel>

          <TabPanel id="publish" tab="preflight" value={tab} className="publish-tab">
            {entry ? (
              <section className="publish-preflight-panel" id="publish-preflight" aria-label="Preflight">
                <h3 className="ds-group-title">
                  Preflight · <StatusWord tone={VERDICT_TONE[entry.verdict]} word={stateText(entry.verdict)} />
                </h3>
                <Preflight entry={entry} />
                <p className="ds-note">{t("Publish evidence должен быть привязан к candidate SHA и target SHA. Merge остаётся человеку.")}</p>
              </section>
            ) : (
              <p className="ds-empty">{empty}</p>
            )}
          </TabPanel>

          <TabPanel id="publish" tab="pr" value={tab} className="publish-tab">
            <div className="publish-pr-grid" id="publish-pr">
              <section className="publish-pr" aria-label="PR / MR">
                <h3 className="ds-group-title">PR / MR</h3>
                <div className="publish-pr-body">
                  <div className="publish-pr-field">
                    <span>base</span>
                    <b>{entry?.integration_ref ?? "—"}</b>
                  </div>
                  {["title", "labels", "body"].map((field) => (
                    <div className="publish-pr-field" key={field}>
                      <span>{field}</span>
                      <NoData why={t("Черновик PR консоль не формирует")} />
                    </div>
                  ))}
                  <div className="publish-pr-actions">
                    <button className="ds-btn ds-btn-primary" type="button" disabled>
                      {t("Подготовить PR")}
                    </button>
                  </div>
                </div>
              </section>
              <section className="publish-pr-side" aria-label="Publication">
                <h3 className="ds-group-title">Publication</h3>
                <div className="publish-side-body">
                  <div>
                    <span>Provider</span>
                    <NoData />
                  </div>
                  <div>
                    <span>Repo</span>
                    <NoData />
                  </div>
                  <div>
                    <span>PR</span>
                    <b>{entry?.pr_url || "—"}</b>
                  </div>
                  <p className="orch-note">{t("Консоль не создаёт PR: merge выполняет человек")}</p>
                </div>
              </section>
            </div>
          </TabPanel>

          <TabPanel id="publish" tab="evidence" value={tab} className="publish-tab">
            {entry ? (
              <>
                <section className="publish-evidence" id="publish-evidence" aria-label="Publish evidence">
                  <h3 className="ds-group-title">Publish evidence</h3>
                  <div className="publish-evidence-table">
                    <div className="publish-evidence-head">
                      <span>{t("артефакт")}</span>
                      <span>{t("статус")}</span>
                      <span>{t("детали")}</span>
                    </div>
                    {preflightRows(entry)
                      .filter((row) => ["QA evidence", "Review", "Release Gate"].includes(row.label))
                      .map((row) => (
                        <div className="publish-evidence-row" key={row.label}>
                          <b>{row.label}</b>
                          <StatusWord tone={row.tone} word={stateText(row.status)} />
                          <small>{row.detail}</small>
                        </div>
                      ))}
                  </div>
                </section>
                <Timeline key={entry.batch_id} batchId={entry.batch_id} id="publish-timeline" />
              </>
            ) : (
              <p className="ds-empty">{empty}</p>
            )}
          </TabPanel>
        </Panel>
      </div>
      {ledger && entry && drawer && <CandidateDrawer entry={entry} ledger={ledger} onClose={() => setDrawer(false)} />}
    </div>
  );
}
