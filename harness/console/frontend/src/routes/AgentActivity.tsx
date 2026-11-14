/* Agent activity: the mockup's #agent-activity. The summary, the KPI row and the Overview tab
   (step sources, sessions with ticket, status and role filters, the session route) come from the
   live step feed; the session events from the batch's audit chronology; Timeline and Statistics
   from the ledger snapshot and the live feed. Native-permission decisions have no mockup slot and
   follow the mockup blocks (H4). */
import { useState } from "react";
import { DecisionPanel } from "../decisions/DecisionPanel";
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { useScreen } from "../screens/useScreen";
import {
  ActivityStats,
  ActivityTimeline,
  SessionRoute,
  WorkKpis,
  WorkSummary,
  statusCounts,
} from "../steps/ActivityViews";
import type { SessionStatus } from "../steps/ActivityViews";
import { InProcessPanel } from "../steps/InProcessPanel";
import { SessionEvents } from "../steps/SessionEvents";
import { StepFilters } from "../steps/StepFilters";
import { StepList } from "../steps/StepList";
import { StepSources } from "../steps/StepSources";
import { useLiveSteps } from "../steps/useLiveSteps";
import { TabList, TabPanels } from "../views/Tabs";
import { parseOrchestration } from "../ws/ledger";
import { filterSteps } from "../ws/steps";
import type { StepFilter } from "../ws/steps";

type Tab = "overview" | "timeline" | "stats";

export function AgentActivity() {
  const { t, section, tab: tabLabel } = useI18n();
  const live = useLiveSteps();
  const ledger = useScreen({ type: "orchestration.snapshot" }, parseOrchestration);
  const [filter, setFilter] = useState<StepFilter>({ dispatch: null, role: null });
  const [status, setStatus] = useState<"all" | SessionStatus>("all");
  const [tab, setTab] = useState<Tab>("overview");
  const [ticket, setTicket] = useState<string | null>(null);
  const now = Date.now();
  const counts = statusCounts(live.dispatches);
  const tickets = [...new Set(live.dispatches.map((entry) => entry.ticket).filter(Boolean))].sort((a, b) =>
    b.localeCompare(a, undefined, { numeric: true }),
  );
  const scoped = ticket ? live.dispatches.filter((entry) => entry.ticket === ticket) : live.dispatches;
  const ids = new Set(scoped.map((entry) => entry.dispatch_id));
  const steps = ticket ? live.steps.filter(({ step }) => ids.has(step.dispatch_id ?? "")) : live.steps;
  const session = scoped.find((entry) => entry.dispatch_id === filter.dispatch) ?? scoped[0] ?? null;
  const chooseTicket = (next: string | null) => {
    setTicket(next);
    setFilter({ ...filter, dispatch: null });
  };
  const prState = session ? (ledger.data?.ledger.batches.find((batch) => batch.batch_id === session.batch_id)?.pr_state ?? null) : null;
  const tabs: [Tab, string][] = [
    ["overview", tabLabel("Обзор")],
    ["timeline", t("Таймлайн")],
    ["stats", t("Статистика")],
  ];
  return (
    <div className="work-page" data-section="Ход работы">
      <div className="page-title work-title">
        <div>
          <h1>{section("Ход работы")}</h1>
          <p>{t("Наблюдаемые шаги, роли и события. Внутренние рассуждения не отображаются.")}</p>
          <div className="home-facts" id="work-facts">
            <span>{t("{count} сессий", { count: counts.all })}</span>
            <span>{t("{count} выполняется", { count: counts.running })}</span>
            <span>{t("{count} заблокировано", { count: counts.blocked })}</span>
            <span>{t("{count} ждёт решения", { count: counts.awaiting })}</span>
          </div>
        </div>
        <div className="actions">
          <button className="btn" type="button" onClick={() => ledger.refresh(true)}>
            <Icon name="refresh" /> {t("Обновить")}
          </button>
          <a className="btn" href={href("orchestration")}>
            <Icon name="orchestration" /> {section("Orchestration")}
          </a>
        </div>
      </div>
      <WorkSummary dispatches={live.dispatches} />
      <WorkKpis dispatches={live.dispatches} analytics={ledger.data?.analytics ?? null} now={now} />
      <TabList id="work" label={section("Ход работы")} className="orch-tabbar work-tabbar" tabs={tabs} value={tab} onChange={(id) => setTab(id as Tab)} />
      <TabPanels id="work" tabs={tabs} value={tab}>
      {tab === "overview" ? (
        <>
          <StepSources />
          <div className="work-grid">
            <StepFilters
              dispatches={scoped}
              steps={steps}
              filter={filter}
              onChange={setFilter}
              status={status}
              onStatus={setStatus}
              now={now}
              tickets={tickets}
              ticket={ticket}
              onTicket={chooseTicket}
            />
            <SessionRoute session={session} dispatches={live.dispatches} prState={prState} now={now} />
          </div>
          <InProcessPanel session={session} />
          <SessionEvents session={session} />
          <StepList steps={filterSteps(steps, filter)} unavailable={live.orchestration === "unavailable"} />
          <DecisionPanel kinds={["native-permission"]} hideWhenEmpty />
        </>
      ) : tab === "timeline" ? (
        <ActivityTimeline ledger={ledger.data?.ledger ?? null} now={now} />
      ) : (
        <ActivityStats analytics={ledger.data?.analytics ?? null} steps={live.steps} now={now} />
      )}
      </TabPanels>
    </div>
  );
}
