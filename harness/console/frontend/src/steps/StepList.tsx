/* The step list: time, role and text of each observed step. An agent step shows only its kind
   and text; a Codex step says its structure is unavailable; an orchestration step is a template
   filled with allowlisted fields. Every value renders as text, never as markup. */
import { useState } from "react";
import { useI18n } from "../i18n";
import { STRUCTURE_LABELS, eventText } from "../ws/steps";
import type { HeldStep, Step } from "../ws/steps";
import { STEP_LIMIT } from "./ActivityViews";
import { clusterSteps, durationText } from "./clusters";
import type { StepCluster } from "./clusters";

/** hh:mm:ss of an ISO 8601 time, as the server observed it. */
const clock = (observedAt: string): string => observedAt.slice(11, 19);

/** The cluster badge and its members: a run of close steps of one source reads as one row. */
function ClusterMark({
  cluster,
  open,
  onToggle,
}: {
  cluster: StepCluster;
  open: boolean;
  onToggle: () => void;
}) {
  const { t } = useI18n();
  if (cluster.members.length < 2) return null;
  return (
    <button
      type="button"
      className="work-cluster-toggle"
      aria-expanded={open}
      title={t("Соседние события одного источника")}
      onClick={onToggle}
    >
      ×{cluster.members.length}
    </button>
  );
}

function StepRow({ step, cluster, open, onToggle }: { step: Step; cluster: StepCluster; open: boolean; onToggle: () => void }) {
  const { t, section, language } = useI18n();
  const duration = (
    <span className="work-event-duration" title={t("Длительность")}>
      {durationText(cluster.durationSeconds, language)}
    </span>
  );
  const members = open ? (
    <ul className="work-cluster-members">
      {cluster.members.map((member) => (
        <li key={member.key}>
          <span>{clock(member.step.observed_at)}</span>
          {member.step.origin === "agent" ? member.step.text : eventText(member.step, t)}
        </li>
      ))}
    </ul>
  ) : null;
  if (step.origin === "agent") {
    return (
      <div className="work-event" data-origin="agent" data-source={step.source}>
        <span className="work-event-time">{clock(step.observed_at)}</span>
        <span className="work-event-role">{step.role}</span>
        <span className="work-event-main">
          <b>{step.text}</b>
          <small>
            {step.kind} · {step.dispatch_id}
          </small>
          {step.structure === "unavailable" ? (
            <em className="orch-pill violet">{t(STRUCTURE_LABELS.unavailable)}</em>
          ) : null}
          <ClusterMark cluster={cluster} open={open} onToggle={onToggle} />
        </span>
        {duration}
        {members}
      </div>
    );
  }
  const details = [step.ticket, step.batch_id].filter((part): part is string => Boolean(part));
  if (step.next_role) details.push(t("дальше: {role}", { role: step.next_role }));
  if (step.message) details.push(step.message);
  return (
    <div className="work-event" data-origin="orchestration">
      <span className="work-event-time">{clock(step.observed_at)}</span>
      <span className="work-event-role">{step.role ?? section("Orchestration")}</span>
      <span className="work-event-main">
        <b>{eventText(step, t)}</b>
        <small>{details.join(" · ")}</small>
        <ClusterMark cluster={cluster} open={open} onToggle={onToggle} />
      </span>
      {duration}
      {members}
    </div>
  );
}

export function StepList({ steps, unavailable }: { steps: readonly HeldStep[]; unavailable: boolean }) {
  const { t } = useI18n();
  const [opened, setOpened] = useState<ReadonlySet<number>>(new Set());
  const clusters = clusterSteps(steps).slice(-STEP_LIMIT);
  const shown = clusters.reduce((total, cluster) => total + cluster.members.length, 0);
  const toggle = (key: number) =>
    setOpened((kept) => {
      const next = new Set(kept);
      if (!next.delete(key)) next.add(key);
      return next;
    });
  return (
    <section className="panel work-events-panel">
      <div className="panel-head">
        <h2>{t("Шаги и события")}</h2>
        <span className="small muted">
          {shown < steps.length ? `${t("{shown} из {total}", { shown, total: steps.length })} · ` : ""}
          {t("наблюдаемые факты")}
        </span>
      </div>
      {unavailable ? <div className="work-empty">{t("Источник оркестрации недоступен")}</div> : null}
      <div className="work-events" id="work-steps" aria-live="polite" tabIndex={0} role="region" aria-label={t("Шаги и события")}>
        {steps.length === 0 ? <div className="work-empty">{t("Шагов пока нет")}</div> : null}
        {clusters.map((cluster) => (
          <StepRow
            key={cluster.key}
            step={cluster.last.step}
            cluster={cluster}
            open={opened.has(cluster.key)}
            onToggle={() => toggle(cluster.key)}
          />
        ))}
      </div>
    </section>
  );
}
