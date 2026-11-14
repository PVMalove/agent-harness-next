/* The blocks the mockup keeps inside the Orchestration tabs that the kernel analytics cards do not
   draw: the Flow mini-flow and the TUI statistics, the Quality evidence by stage and local QA
   attempts, the Runtime recovery checks (no source: an honest no-data), the ledger lock and the
   Recovery / Container route links. Every figure is the snapshot's. */
import type { ReactNode } from "react";
import { useI18n } from "../i18n";
import { Icon } from "../icons";
import { href } from "../navigation";
import { Bar, NoData } from "../steps/ActivityViews";
import type { EvidenceRow, OrchestrationSnapshot } from "../ws/ledger";
import { pipelineStats, pipelineStatsFields } from "./format";
import { LedgerLock } from "./LedgerLock";

const withBatch = (route: string, batch: string | null) =>
  batch ? `${href(route)}?batch=${encodeURIComponent(batch)}` : href(route);

function Chart({ title, note, id, wide, children }: { title: string; note?: string; id?: string; wide?: boolean; children: ReactNode }) {
  return (
    <article className={wide ? "orch-chart wide" : "orch-chart"} id={id}>
      <div className="orch-chart-head">
        <h3>{title}</h3>
        {note ? <span>{note}</span> : null}
      </div>
      {children}
    </article>
  );
}

export function FlowExtras({ data }: { data: OrchestrationSnapshot }) {
  const { t, duration } = useI18n();
  const kpi = data.kpi;
  const efficiency = kpi.flow_efficiency_pct ?? null;
  const fields = pipelineStatsFields(pipelineStats(data.ledger));
  return (
    <>
      <article className="orch-chart wide orch-mini-flow" id="orch-mini-flow">
        <div>
          <span>{t("Завершено")}</span>
          <b>{kpi.throughput_7d ?? "—"}</b>
          <small>{t("PR за 7 дней")}</small>
        </div>
        <div>
          <span>{t("Эффективность потока")}</span>
          <b>{efficiency === null ? "—" : `${efficiency}%`}</b>
          {efficiency !== null && <Bar value={efficiency} max={100} tone="mint" />}
          <small>active / lead time</small>
        </div>
        <div>
          <span>{t("Самый старый")}</span>
          <b>{duration(kpi.oldest_wip_seconds ?? null)}</b>
          <small>{t("в работе")}</small>
        </div>
        <div>
          <span>{t("Цикл до PR")}</span>
          <b>{`${duration(kpi.cycle_p50_seconds ?? null)} / ${duration(kpi.cycle_p95_seconds ?? null)}`}</b>
          <small>p50 / p95</small>
        </div>
      </article>
      <section className="panel orch-stats" id="pipeline-stats">
        <div className="panel-head">
          <h2>{t("Состояние и статистика")}</h2>
        </div>
        {fields.length ? (
          <dl className="orch-analytics-rows">
            {fields.map(([label, value]) => (
              <div key={label}>
                <dt>{t(label)}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="report-empty">{t("Пайплайн ещё не запускался: batch в леджере нет.")}</p>
        )}
      </section>
    </>
  );
}

const STAGES: readonly [keyof EvidenceRow, string][] = [
  ["developer", "Developer"],
  ["review", "Review"],
  ["qa", "QA"],
  ["qa_run", "QA run"],
  ["receipt", "Receipt"],
  ["publish", "Publish"],
];

export function QualityExtras({ data }: { data: OrchestrationSnapshot }) {
  const { t } = useI18n();
  const rows = data.ledger.evidence;
  const attempts = data.ledger.qa_attempts;
  return (
    <div className="orch-chart-grid orch-extras">
      <Chart title={t("Evidence по стадиям")} note={t("{count} batch", { count: rows.length })} id="orch-evidence-stages">
        {rows.length === 0 ? (
          <NoData why={t("в ledger нет batch")} />
        ) : (
          STAGES.map(([key, label]) => {
            const present = rows.filter((row) => row[key] === "present").length;
            return (
              <div className="work-stat-row orch-row" key={key}>
                <span>{label}</span>
                <Bar value={present} max={rows.length} tone="cyan" />
                <b>{`${present}/${rows.length}`}</b>
              </div>
            );
          })
        )}
      </Chart>
      <Chart title="Local QA attempts" note={t("{count} попыток", { count: attempts.length })} id="orch-qa-attempts">
        {attempts.length === 0 ? (
          <p className="orch-note">{t("Неудачных попыток QA нет")}</p>
        ) : (
          attempts.map((attempt) => (
            <div className="orch-attempt-row" key={`${attempt.dispatch_id}-${attempt.failed_at}`}>
              <b>{attempt.dispatch_id}</b>
              <span>{attempt.stage}</span>
              <small>{attempt.message}</small>
            </div>
          ))
        )}
      </Chart>
    </div>
  );
}

export function RuntimeExtras({ data, batch }: { data: OrchestrationSnapshot; batch: string | null }) {
  const { t } = useI18n();
  return (
    <div className="orch-runtime-extras">
      <Chart title="Recovery checks" id="orch-recovery-checks" wide>
        <p className="orch-note">{`${t("нет данных")} · ${t("проверки восстановления в снимке не собираются")}`}</p>
        <div className="orch-runtime-actions">
          <a id="open-recovery" className="btn" href={withBatch("recovery", batch)}>
            <Icon name="lock" /> {t("Восстановление")}
          </a>
          <a id="open-container-route" className="btn" href={withBatch("container-route", batch)}>
            <Icon name="container" /> {t("Контейнерный маршрут")}
          </a>
          <span className="small muted">{batch ? t("batch {batch} выбран в истории", { batch }) : t("выберите batch в истории ниже")}</span>
        </div>
      </Chart>
      <LedgerLock lock={data.lock} />
    </div>
  );
}
