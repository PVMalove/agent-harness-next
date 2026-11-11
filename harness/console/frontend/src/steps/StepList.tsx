/* The step list: time, role and text of each observed step. An agent step shows only its kind
   and text; a Codex step says its structure is unavailable; an orchestration step is a template
   filled with allowlisted fields. Every value renders as text, never as markup. */
import { useI18n } from "../i18n";
import { STRUCTURE_LABELS, eventText } from "../ws/steps";
import type { HeldStep, Step } from "../ws/steps";
import { STEP_LIMIT } from "./ActivityViews";

/** hh:mm:ss of an ISO 8601 time, as the server observed it. */
const clock = (observedAt: string): string => observedAt.slice(11, 19);

function StepRow({ step }: { step: Step }) {
  const { t, section } = useI18n();
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
        </span>
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
      </span>
    </div>
  );
}

export function StepList({ steps, unavailable }: { steps: readonly HeldStep[]; unavailable: boolean }) {
  const { t } = useI18n();
  return (
    <section className="panel work-events-panel">
      <div className="panel-head">
        <h2>{t("Шаги и события")}</h2>
        <span className="small muted">
          {steps.length > STEP_LIMIT ? `${t("{shown} из {total}", { shown: STEP_LIMIT, total: steps.length })} · ` : ""}
          {t("наблюдаемые факты")}
        </span>
      </div>
      {unavailable ? <div className="work-empty">{t("Источник оркестрации недоступен")}</div> : null}
      <div className="work-events" id="work-steps" aria-live="polite" tabIndex={0} role="region" aria-label={t("Шаги и события")}>
        {steps.length === 0 ? <div className="work-empty">{t("Шагов пока нет")}</div> : null}
        {steps.slice(-STEP_LIMIT).map((held) => (
          <StepRow key={held.key} step={held.step} />
        ))}
      </div>
    </section>
  );
}
