/* Orchestration on the design system v3: the page header, the summary (batches, dispatch, active,
   attention; the pipeline KPI figures as facts) and six pipeline tabs over orchestration.snapshot.
   «Конвейер» holds the stage strip, the dispatch queue (its «Все» scope lists every ticket) and the
   newest batch cards; «Поток» the pipeline map with the flow analytics; «Качество» the quality
   figures and the QA lane; «Runtime» the runtime figures, the ledger lock, the Recovery / Container
   route links and the batch history; «Контейнер» the dispatch containers of the ledger; «Решения»
   the gate figures with the pending human decisions, which keep their old look inside a
   `ds-legacy-island` until their own slice moves them. KPI and analytics figures are the server's;
   the TUI's command menu is not reproduced: decisions cover the human gate. */
import { useState } from "react";
import { DecisionPanel } from "../decisions/DecisionPanel";
import { LedgerAbsent, PageHeader, Panel, PipeTabs, ScreenState, Summary } from "../ds";
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { BatchHistory } from "../orchestration/BatchHistory";
import { FlowTab, GatesTab, PipelineMap, QualityTab, RuntimeTab } from "../orchestration/Charts";
import { ContainerTab } from "../orchestration/ContainerTab";
import { ALL_STATES } from "../orchestration/format";
import { FlowExtras, QualityExtras, RuntimeExtras } from "../orchestration/TabExtras";
import { BatchCards, DispatchQueue, OrchFacts, StageStrip, orchCounts } from "../orchestration/OrchViews";
import { QaLane } from "../reports/ReportViews";
import { useScreen } from "../screens/useScreen";
import { snapshotClock } from "../update/format";
import { TabPanel } from "../views/Tabs";
import { parseOrchestration } from "../ws/ledger";

type Tab = "map" | "flow" | "quality" | "runtime" | "container" | "gates";

export function Orchestration() {
  const { t, section, language } = useI18n();
  const screen = useScreen({ type: "orchestration.snapshot" }, parseOrchestration);
  const [tab, setTab] = useState<Tab>("map");
  const [state, setState] = useState(ALL_STATES);
  const [batch, setBatch] = useState<string | null>(null);
  const data = screen.data;
  const counts = data ? orchCounts(data) : null;
  const pending = data && typeof data.analytics.gates.awaiting === "number" ? data.analytics.gates.awaiting : undefined;
  const tabs: { id: Tab; label: string; count?: number }[] = [
    { id: "map", label: t("Конвейер") },
    { id: "flow", label: t("Поток") },
    { id: "quality", label: t("Качество") },
    { id: "runtime", label: "Runtime" },
    { id: "container", label: t("Контейнер") },
    { id: "gates", label: t("Решения"), count: pending },
  ];

  return (
    <div className="ds-page ds-fit orch-page" data-section="Orchestration">
      <PageHeader
        title={section("Orchestration")}
        subtitle={t("Состояние пайплайна, история batch и решения человека.")}
        actions={
          <>
            <button id="orch-refresh" className="ds-btn ds-btn-icon" type="button" aria-label={t("Обновить")} title={t("Обновить")} onClick={() => screen.refresh(true)}>
              <Icon name="refresh" className="ds-ic-sm" />
            </button>
            <a className="ds-btn" href={href("reports")}>
              <Icon name="reports" className="ds-ic-sm" /> {section("Reports")}
            </a>
          </>
        }
      />

      <ScreenState screen={screen} noun="Снимок оркестрации не получен" />
      <LedgerAbsent reason={data?.ledger.unavailable} />

      <Summary
        id="orch-summary"
        label={t("Сводка оркестрации")}
        stats={[
          { label: t("Батчи"), value: counts?.batches ?? "—", caption: t("в конвейере") },
          { label: "Dispatch", value: counts?.dispatches ?? "—", caption: t("назначено") },
          { label: t("Активные"), value: counts?.active ?? "—", caption: t("работают или ждут") },
          { label: t("Требует внимания"), value: counts?.attention ?? "—", caption: t("dispatch требует решения") },
        ]}
        facts={data ? <OrchFacts data={data} /> : null}
        snapshot={
          data ? (
            <span id="orch-cache" title={`${screen.cached ? t("Кэш") : t("Новый снимок")} · ${screen.ageSeconds ?? 0} s`}>
              <Icon name="clock" className="ds-ic-sm" /> {t("Снимок")} {snapshotClock(screen.ageSeconds, language)}
            </span>
          ) : undefined
        }
      />

      <PipeTabs id="orch" label={section("Orchestration")} tabs={tabs} value={tab} onChange={(id) => setTab(id as Tab)} />

      <TabPanel id="orch" tab="map" value={tab} className="ds-tabpanel">
        {data && (
          <>
            <StageStrip data={data} />
            <div className="ds-split">
              <DispatchQueue data={data} />
              <Panel title="Batch" fill scroll="list" id="orch-batch-panel" meta={t("новые batch: шаги и переходы")}>
                <BatchCards data={data} />
              </Panel>
            </div>
          </>
        )}
      </TabPanel>
      <TabPanel id="orch" tab="flow" value={tab} className="ds-tabpanel">
        {data && (
          <>
            <PipelineMap data={data} />
            <Panel title={t("Поток")} fill scroll="list" id="orch-flow" label={t("Поток")}>
              <FlowTab data={data} />
              <FlowExtras data={data} />
            </Panel>
          </>
        )}
      </TabPanel>
      <TabPanel id="orch" tab="quality" value={tab} className="ds-tabpanel">
        {data && (
          <Panel title={t("Качество")} fill scroll="list" id="orch-quality" label={t("Качество")}>
            <QualityTab data={data} />
            <QualityExtras data={data} />
            <QaLane ledger={data.ledger} ticket={data.ledger.batches[0]?.ticket ?? ""} />
          </Panel>
        )}
      </TabPanel>
      <TabPanel id="orch" tab="runtime" value={tab} className="ds-tabpanel">
        {data && (
          <Panel title="Runtime" fill scroll="list" id="orch-runtime" label="Runtime">
            <RuntimeTab data={data} />
            <RuntimeExtras data={data} batch={batch} />
            <BatchHistory ledger={data.ledger} state={state} onState={setState} selected={batch} onSelect={setBatch} />
          </Panel>
        )}
      </TabPanel>
      <TabPanel id="orch" tab="container" value={tab} className="ds-tabpanel">
        {data && <ContainerTab containers={data.containers} />}
      </TabPanel>
      <TabPanel id="orch" tab="gates" value={tab} className="ds-tabpanel">
        {data && (
          <Panel title={t("Решения")} fill scroll="list" id="orch-gates" label={t("Решения")}>
            <GatesTab data={data} />
            <div className="ds-legacy-island">
              <DecisionPanel />
            </div>
          </Panel>
        )}
      </TabPanel>
    </div>
  );
}
