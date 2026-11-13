/* Harness on the design system v3: the summary (installed version, runtime store, audit chain,
   skills), five pipeline tabs and the tiles of the related screens. The facts are those of
   harness.overview (state, package version, drift, store, runtime probe, adapters, containers) and
   harness.maintenance (cleanup plans, worktrees). Tabs "Обзор" and "Команды" stay mounted, the
   inactive one hidden, so a page button can hand a run to the command panel, whose dialog shows the
   server's confirmation. The command panel and the maintenance panel are shared with other screens
   and keep their old look inside a `ds-legacy-island` until their own slice moves them. */
import { useCallback, useState } from "react";
import { CommandPanel } from "../commands/CommandPanel";
import type { RunRequest } from "../commands/CommandPanel";
import { PageHeader, Panel, PipeTabs, RelatedTiles, Summary } from "../ds";
import type { Tile } from "../ds";
import {
  AdaptersPanel,
  AttentionPanel,
  AuditPanel,
  ContainersPanel,
  InstallPanel,
  LoopPanel,
  NoData,
  RuntimePanel,
} from "../harness/HarnessOverview";
import { Maintenance } from "../harness/Maintenance";
import { TabPanel } from "../views/Tabs";
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { NAV_ITEMS, href } from "../navigation";
import { useScreen } from "../screens/useScreen";
import { snapshotClock } from "../update/format";
import { useConsole } from "../useConsole";
import { parseHarnessOverview, parseMaintenance } from "../ws/screens";

/** The plan each plan-bound cleanup command deletes: the wire contract of `plan_digest`. */
export const PLAN_OF_COMMAND = { "cleanup-apply": "soft", "cleanup-hard-apply": "hard" } as const;

type Tab = "overview" | "runtime" | "adapters" | "containers" | "commands";

/** The screens a Harness user goes to next, each with what it is for. */
const RELATED: readonly (readonly [route: string, text: string])[] = [
  ["diagnostics", "Отчёт harness health, онлайн-проверки, исправление --fix и экспорт в Markdown."],
  ["update-harness", "Установленная и доступная версии, дрейф, diff, режим обновления и подтверждённый запуск."],
  ["open-project", "Путь, проверка Git-проекта и план init/adopt/update перед подтверждением."],
  ["orchestration", "Статистика пайплайна, история batch по состояниям и команды coordinator."],
  ["repo-map", "Карта для HEAD: сводка, файлы со статусом парсера, символы, связи и хабы."],
  ["configuration", "Шаги project.json и orchestration.json, черновик, проверка и diff, версии и откат."],
];

export function Harness() {
  const { t, section, tab: tabLabel, language } = useI18n();
  const { snapshot } = useConsole();
  const [tab, setTab] = useState<Tab>("overview");
  const [request, setRequest] = useState<RunRequest | null>(null);
  const overview = useScreen({ type: "harness.overview" }, parseHarnessOverview);
  const maintenance = useScreen({ type: "harness.maintenance" }, parseMaintenance);
  const data = overview.data;
  const state = data?.state;
  const view = maintenance.data?.maintenance ?? null;

  const digests: Record<string, string> = {};
  if (view) {
    for (const [command, plan] of Object.entries(PLAN_OF_COMMAND)) digests[command] = view[plan].digest;
  }

  const refreshAll = useCallback(() => {
    overview.refresh(true);
    maintenance.refresh(true);
  }, [overview, maintenance]);
  const ask = (command_id: string, values: Record<string, string> = {}) => {
    setTab("commands");
    setRequest({ command_id, values, nonce: Date.now() });
  };

  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: tabLabel("Обзор") },
    { id: "runtime", label: "Runtime" },
    { id: "adapters", label: t("Адаптеры") },
    { id: "containers", label: t("Контейнеры") },
    { id: "commands", label: tabLabel("Команды") },
  ];
  const store = data?.store ?? null;
  const unavailable = t("Недоступно в текущем снимке");
  const title = (route: string) => {
    const item = NAV_ITEMS.find((candidate) => candidate.route === route)!;
    return item.label ? t(item.label) : section(item.section);
  };
  const problems = snapshot ? snapshot.health.fail + snapshot.health.warn : null;
  const tiles: Tile[] = RELATED.map(([route, text]) => ({
    key: route,
    icon: NAV_ITEMS.find((item) => item.route === route)!.icon,
    title: title(route),
    count: route === "diagnostics" && problems ? problems : undefined,
    text: t(text),
    href: href(route),
  }));
  return (
    <div className="ds-page ds-fit" data-section="Harness">
      <PageHeader
        title={section("Harness")}
        subtitle={t("Установка, runtime, адаптеры и обслуживание. Команды выполняются как job сервера после подтверждения.")}
        actions={
          <>
            <button id="harness-refresh" className="ds-btn" type="button" onClick={refreshAll}>
              <Icon name="refresh" className="ds-ic-sm" /> {t("Проверить")}
            </button>
            <a className="ds-btn" href={href("diagnostics")}>
              <Icon name="pulse" className="ds-ic-sm" /> {section("Diagnostics")}
            </a>
            <a className="ds-btn ds-btn-primary" href={href("update-harness")}>
              {t("Обновление")}
            </a>
          </>
        }
      />

      {overview.error && !data && (
        <p className="ds-alert ds-alert-err" role="alert" data-code={overview.error.code}>
          {t("○ Состояние харнесса недоступно: ")}
          {overview.error.message || overview.error.code}
        </p>
      )}

      <Summary
        id="harness-kpis"
        label={t("Сводка Harness")}
        stats={[
          { label: t("Установлено"), value: state ? (state.installed ? state.installed_version : "—") : "—", caption: data ? t("доступно {version}", { version: data.package_version }) : unavailable },
          { label: "Runtime store", value: store?.schema != null ? `schema ${store.schema}` : t("нет данных"),
            caption: store ? `generation ${store.generation ?? "—"} · audit ${store.audit_records ?? "—"}` : unavailable },
          { label: "Audit chain", value: store?.audit_records ?? t("нет данных"),
            caption: <>cutover {store?.cutover_at ? store.cutover_at : store?.authority === "file-ledger" ? t("не выполнен") : <NoData />}</> },
          { label: "Skills", value: state ? state.skills : "—",
            caption: state ? `drift ${data?.drift_files ?? "—"} · ${t("{count} управляемых файлов", { count: state.managed_files })}` : unavailable },
        ]}
        facts={
          <>
            <span id="harness-version">
              {state ? (state.installed ? state.installed_version : t("не установлен")) : unavailable}
              {data && data.package_version !== state?.installed_version ? ` → ${data.package_version}` : ""}
            </span>
            {store && <span>{store.authority}</span>}
            {store?.schema != null && <span>schema {store.schema}</span>}
            {state && <span>{t("{count} скилов", { count: state.skills })}</span>}
          </>
        }
        snapshot={data ? (
          <span id="harness-updated" title={`${overview.cached ? t("Кэш") : t("Новый снимок")} · ${overview.ageSeconds ?? 0} s`}>
            <Icon name="clock" className="ds-ic-sm" /> {t("Снимок")} {snapshotClock(overview.ageSeconds, language)}
          </span>
        ) : undefined}
      />

      <PipeTabs id="harness" label={section("Harness")} tabs={tabs} value={tab} onChange={(id) => setTab(id as Tab)} />

      <TabPanel id="harness" tab="overview" value={tab} keepMounted className="ds-tabpanel ds-overview">
        <div className="ds-overview-top">
          <InstallPanel overview={data} />
          <AttentionPanel overview={data} />
        </div>
        <LoopPanel overview={data} />
        <RelatedTiles id="harness-related" title={t("Связанные разделы")} tiles={tiles} />
      </TabPanel>
      <TabPanel id="harness" tab="runtime" value={tab} className="ds-tabpanel">
        <RuntimePanel overview={data} />
        <AuditPanel overview={data} />
      </TabPanel>
      <TabPanel id="harness" tab="adapters" value={tab} className="ds-tabpanel">
        <AdaptersPanel overview={data} />
      </TabPanel>
      <TabPanel id="harness" tab="containers" value={tab} className="ds-tabpanel">
        <ContainersPanel overview={data} maintenance={view} />
      </TabPanel>
      <TabPanel id="harness" tab="commands" value={tab} keepMounted className="ds-tabpanel">
        <Panel title={t("Команды")} fill scroll="text" id="harness-commands">
          <div className="ds-legacy-island">
            <CommandPanel section="harness" planDigests={digests} request={request} onJobDone={refreshAll} />
            <Maintenance
              facts={maintenance.data}
              error={maintenance.error && !maintenance.data ? maintenance.error.message || maintenance.error.code : null}
              onClean={() => ask("cleanup-apply")}
              onRemove={(path) => ask("worktree-remove", { worktree: path })}
              onRefresh={() => maintenance.refresh(true)}
            />
          </div>
        </Panel>
      </TabPanel>
    </div>
  );
}
