/* Publication: the mockup's #publish over the read-only publish view of reports.snapshot
   (kernel/publish_view.py). A batch selector sits above the KPI row and defaults to the latest
   batch with a review report (H1). The live ledger decisions (report-decision and attention, with
   their confirmations) live in the "Решение человека" block of the Overview tab. The console never
   creates a PR: "Подготовить PR" stays disabled, merge is the human's. */
import { useState } from "react";
import { DecisionPanel } from "../decisions/DecisionPanel";
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { VERDICT_TONE } from "../reports/ReportViews";
import { Timeline } from "../reports/Timeline";
import { useScreen } from "../screens/useScreen";
import { NoData } from "../steps/ActivityViews";
import { parseReports } from "../ws/ledger";
import type { PublishEntry } from "../ws/ledger";

type Tab = "overview" | "preflight" | "pr" | "evidence";

const short = (sha: string | null): string => (sha ? sha.slice(0, 12) : "—");

/** The default batch of the selector: the latest one with a review report, else the latest.
    Entries come newest first (kernel/reports.py sorts batches by created_at, descending). */
export function defaultBatch(entries: readonly PublishEntry[]): string | null {
  const reviewed = entries.filter((entry) => entry.review !== null);
  return (reviewed[0] ?? entries[0])?.batch_id ?? null;
}

type Tone = "mint" | "violet" | "blue";

interface Check {
  label: string;
  status: string;
  tone: Tone;
  detail: string;
}

/** The preflight rows of one entry; a fact the view could not read is "unknown", never a pass. */
export function preflightRows(entry: PublishEntry): Check[] {
  const flag = (value: boolean | null): [string, Tone] =>
    value === null ? ["unknown", "blue"] : value ? ["ok", "mint"] : ["blocked", "violet"];
  const report = (ref: PublishEntry["qa"]): [string, Tone] =>
    ref === null ? ["missing", "violet"] : ref.has_blockers || ref.outcome !== "completed" ? ["blocked", "violet"] : ["ok", "mint"];
  const [qa, qaTone] = report(entry.qa);
  const [review, reviewTone] = report(entry.review);
  const [head, headTone] = flag(entry.head_matches);
  const [target, targetTone] = flag(entry.target_in_history);
  return [
    { label: "QA evidence", status: qa, tone: qaTone, detail: entry.qa ? `${entry.qa.dispatch_id} · ${entry.qa.outcome}` : "—" },
    {
      label: "Review",
      status: review,
      tone: reviewTone,
      detail: entry.review ? `${entry.review.dispatch_id} · ${entry.review.outcome}` : "—",
    },
    {
      label: "Release Gate",
      status: entry.verdict,
      tone: VERDICT_TONE[entry.verdict],
      detail: entry.refusals.join(" · ") || "—",
    },
    { label: "Branch head", status: head, tone: headTone, detail: `${short(entry.head)} ↔ ${short(entry.candidate)}` },
    { label: "Target", status: target, tone: targetTone, detail: entry.integration_ref ?? short(entry.target) },
  ];
}

function Preflight({ entry, compact }: { entry: PublishEntry; compact: boolean }) {
  const rows = preflightRows(entry);
  return (
    <div className="publish-preflight">
      {(compact ? rows.slice(0, 3) : rows).map((row) => (
        <div className="publish-check" key={row.label}>
          <span className={`orch-pill ${row.tone}`}>{row.status}</span>
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
  const { t, section, tab: tabLabel } = useI18n();
  const screen = useScreen({ type: "reports.snapshot" }, parseReports);
  const entries = screen.data?.publish ?? [];
  const [chosen, setChosen] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const batch = chosen ?? defaultBatch(entries);
  const entry = entries.find((item) => item.batch_id === batch) ?? null;
  const blocked = entry ? preflightRows(entry).some((row) => row.status !== "ok") : true;
  const tabs: [Tab, string][] = [
    ["overview", tabLabel("Обзор")],
    ["preflight", "Preflight"],
    ["pr", "PR / MR"],
    ["evidence", "Evidence"],
  ];

  return (
    <div className="publish-page work-page" data-section="Публикация">
      <div className="page-title publish-title">
        <div>
          <h1>{section("Публикация")}</h1>
          <p>{t("Candidate → target, PR/MR и evidence. Merge и публикация остаются человеку.")}</p>
          {entry && (
            <div className="home-facts" id="publish-facts">
              <span>{short(entry.candidate)}</span>
              <span>target {short(entry.target)}</span>
              <span>QA {entry.qa ? entry.qa.outcome : "—"}</span>
            </div>
          )}
        </div>
        <div className="actions">
          <button id="publish-refresh" className="btn" type="button" onClick={() => screen.refresh(true)}>
            <Icon name="refresh" /> {t("Проверить")}
          </button>
          <a className="btn" href={href("reports")}>
            <Icon name="reports" /> {section("Reports")}
          </a>
          <a className="btn" href={href("orchestration")}>
            <Icon name="orchestration" /> {section("Orchestration")}
          </a>
        </div>
      </div>

      {screen.error && !screen.data && (
        <p className="command-refusal err" role="alert" data-code={screen.error.code}>
          {t("Отчёт не построен")}: {screen.error.message || screen.error.code}
        </p>
      )}

      <label className="publish-batch" id="publish-batch">
        <span>batch</span>
        <select value={batch ?? ""} onChange={(event) => setChosen(event.target.value || null)} disabled={!entries.length}>
          {entries.length === 0 ? <option value="">{t("Batch для публикации нет")}</option> : null}
          {entries.map((item) => (
            <option key={item.batch_id} value={item.batch_id}>
              {item.ticket || item.batch_id} · {item.state}
            </option>
          ))}
        </select>
      </label>

      <div className="publish-kpis" id="publish-kpis">
        <div>
          <span>Candidate</span>
          <b className="cyan">{entry ? short(entry.candidate) : <NoData />}</b>
          <small>{entry ? `${entry.ticket} · target ${short(entry.target)}` : "—"}</small>
        </div>
        <div>
          <span>Release Gate</span>
          <b className={entry ? VERDICT_TONE[entry.verdict] : undefined} id="publish-verdict">
            {entry ? entry.verdict : <NoData />}
          </b>
          <small>{entry?.refusals[0] ?? "—"}</small>
        </div>
        <div>
          <span>QA source</span>
          <b className="mint">{entry?.qa ? entry.qa.outcome : <NoData />}</b>
          <small>candidate / target pair</small>
        </div>
        <div>
          <span>PR receipt</span>
          <b className="lavender">{entry?.pr_url ? entry.pr_state || "found" : "missing"}</b>
          <small>{entry?.pr_url || t("создание не выполнялось")}</small>
        </div>
      </div>

      <div className="orch-tabbar publish-tabbar" role="tablist">
        {tabs.map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            className={`orch-tab${tab === id ? " on" : ""}`}
            aria-selected={tab === id}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <>
          {entry ? (
            <div className="publish-grid">
              <section className="panel publish-candidate">
                <div className="panel-head">
                  <h2>Release candidate</h2>
                  <span className="small muted">{entry.ticket}</span>
                </div>
                <div className="publish-candidate-body">
                  <code className="publish-sha">{entry.candidate ?? "—"}</code>
                  <h3>
                    {t("название")}: <NoData />
                  </h3>
                  <div className="publish-meta">
                    <span>{entry.branch || "—"}</span>
                    <span>target {short(entry.target)}</span>
                    <span>QA {entry.qa ? entry.qa.outcome : "—"}</span>
                  </div>
                </div>
              </section>
              <section className="panel publish-gate">
                <div className="panel-head">
                  <h2>Release Gate</h2>
                  <span className={`orch-pill ${VERDICT_TONE[entry.verdict]}`}>{entry.verdict}</span>
                </div>
                <div className="publish-gate-body">
                  <div className="publish-gate-facts">
                    <div>
                      <span>tree</span>
                      <b>{entry.head_matches === null ? "unknown" : entry.head_matches ? "match" : "mismatch"}</b>
                    </div>
                    <div>
                      <span>QA</span>
                      <b>{entry.qa ? entry.qa.outcome : "—"}</b>
                    </div>
                    <div>
                      <span>reason</span>
                      <b>{entry.refusals[0] ?? "—"}</b>
                    </div>
                    <div>
                      <span>merge</span>
                      <b>human only</b>
                    </div>
                  </div>
                </div>
              </section>
            </div>
          ) : (
            <section className="panel">
              <div className="report-empty">{t("Batch для публикации нет")}</div>
            </section>
          )}
          {entry && (
            <section className="panel publish-preflight-panel">
              <div className="panel-head">
                <h2>Preflight</h2>
              </div>
              <Preflight entry={entry} compact />
            </section>
          )}
          <section className="panel publish-decision" id="publish-decision">
            <div className="panel-head">
              <h2>{t("Решение человека")}</h2>
              <span className={`orch-pill ${blocked ? "violet" : "mint"}`}>{blocked ? "blocked" : "ready"}</span>
            </div>
            <div className="publish-decision-body">
              <div className="publish-decision-actions">
                <button
                  className="btn primary"
                  type="button"
                  disabled
                  aria-disabled="true"
                  title={t("Консоль не создаёт PR: merge выполняет человек")}
                >
                  {t("Подготовить PR")}
                </button>
                <a className="btn" href={href("reports")}>
                  <Icon name="reports" /> {section("Reports")}
                </a>
              </div>
              <DecisionPanel kinds={["report-decision", "attention"]} />
            </div>
          </section>
        </>
      )}

      {tab === "preflight" && entry && (
        <section className="panel publish-preflight-panel" id="publish-preflight">
          <div className="panel-head">
            <h2>Preflight</h2>
          </div>
          <Preflight entry={entry} compact={false} />
          <div className="publish-preflight-foot">
            {t("Publish evidence должен быть привязан к candidate SHA и target SHA. Merge остаётся человеку.")}
          </div>
        </section>
      )}

      {tab === "pr" && (
        <div className="publish-pr-grid" id="publish-pr">
          <section className="panel publish-pr">
            <div className="panel-head">
              <h2>PR / MR</h2>
            </div>
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
                <button className="btn primary" type="button" disabled>
                  {t("Подготовить PR")}
                </button>
              </div>
            </div>
          </section>
          <aside className="panel publish-pr-side">
            <div className="panel-head">
              <h2>Publication</h2>
            </div>
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
          </aside>
        </div>
      )}

      {tab === "evidence" && entry && (
        <>
          <section className="panel publish-evidence" id="publish-evidence">
            <div className="panel-head">
              <h2>Publish evidence</h2>
            </div>
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
                    <span className={`orch-pill ${row.tone}`}>{row.status}</span>
                    <small>{row.detail}</small>
                  </div>
                ))}
            </div>
          </section>
          <Timeline key={entry.batch_id} batchId={entry.batch_id} />
        </>
      )}
    </div>
  );
}
