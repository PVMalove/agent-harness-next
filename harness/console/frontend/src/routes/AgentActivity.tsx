/* Agent activity: the "Overview" tab of the mockup as one live list of Claude and Codex agent
   steps and orchestration events, filtered by dispatch and role. The other tabs of the mockup
   (timeline, statistics) and the session route diagram are not shown yet. */
import { useState } from "react";
import { DecisionPanel } from "../decisions/DecisionPanel";
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { StepFilters } from "../steps/StepFilters";
import { StepList } from "../steps/StepList";
import { StepSources } from "../steps/StepSources";
import { useLiveSteps } from "../steps/useLiveSteps";
import { filterSteps } from "../ws/steps";
import type { StepFilter } from "../ws/steps";

export function AgentActivity() {
  const { t, section } = useI18n();
  const live = useLiveSteps();
  const [filter, setFilter] = useState<StepFilter>({ dispatch: null, role: null });
  return (
    <div className="work-page" data-section="Ход работы">
      <div className="page-title work-title">
        <div>
          <h1>{section("Ход работы")}</h1>
          <p>{t("Наблюдаемые шаги, роли и события. Внутренние рассуждения не отображаются.")}</p>
        </div>
        <div className="actions">
          <a className="btn" href={href("orchestration")}>
            <Icon name="orchestration" /> {section("Orchestration")}
          </a>
        </div>
      </div>
      <div className="orch-tabbar" role="tablist">
        <button type="button" className="orch-tab on" role="tab" aria-selected="true">
          {t("Обзор")}
        </button>
      </div>
      <StepSources />
      <DecisionPanel kinds={["native-permission"]} hideWhenEmpty />
      <div className="work-grid">
        <StepFilters dispatches={live.dispatches} steps={live.steps} filter={filter} onChange={setFilter} />
        <StepList steps={filterSteps(live.steps, filter)} unavailable={live.orchestration === "unavailable"} />
      </div>
    </div>
  );
}
