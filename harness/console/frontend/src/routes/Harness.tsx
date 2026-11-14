/* Harness: the mockup's #harness with the facts of harness.overview (state, package version,
   drift, store, runtime status, adapters) and harness.maintenance (cleanup plans, worktrees). Tabs "Обзор" and
   "Команды" are both mounted, the inactive one hidden, so a page button can hand a run to the
   command panel, whose dialog shows the server's confirmation. Runtime and Adapters show the
   store and adapter facts of harness.overview, Containers its container engine inventory; facts
   without a source say so. The overview ends with the mockup's quick command table; the
   maintenance panel (no mockup slot on the overview) sits on the Commands tab under the command
   panel; the pipeline usage block is not in the mockup and is not shown. */
import { useCallback, useState } from "react";
import { CommandPanel } from "../commands/CommandPanel";
import type { RunRequest } from "../commands/CommandPanel";
import { useJobs } from "../commands/useJobs";
import {
  AdaptersPanel,
  AuditPanel,
  ContainersPanel,
  InstallPanel,
  RuntimePanel,
} from "../harness/HarnessOverview";
import { Maintenance } from "../harness/Maintenance";
import { TabList, TabPanel } from "../views/Tabs";
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { useScreen } from "../screens/useScreen";
import { snapshotClock } from "../update/format";
import { parseHarnessOverview, parseMaintenance } from "../ws/screens";

/** The plan each plan-bound cleanup command deletes: the wire contract of `plan_digest`. */
export const PLAN_OF_COMMAND = { "cleanup-apply": "soft", "cleanup-hard-apply": "hard" } as const;

type Tab = "overview" | "runtime" | "adapters" | "containers" | "commands";

/** The mockup's quick access on the overview: the first three commands of the section's catalog
    with their purpose and mode; «Показать» opens the Commands tab, where they run. The console
    keeps no last result per command here, so that column says so. */
function QuickCommands({ onShow }: { onShow: () => void }) {
  const { t } = useI18n();
  const { commands } = useJobs("harness");
  const shown = (commands ?? []).slice(0, 3);
  return (
    <section className="panel harness-commands" id="harness-quick-commands">
      <div className="panel-head">
        <h2>{t("Команды")}</h2>
        <span className="small muted">{t("быстрый доступ")}</span>
      </div>
      {commands === null ? (
        <p className="harness-install-note">{t("Обновление…")}</p>
      ) : (
        <div className="harness-command-table" role="region" tabIndex={0} aria-label={t("Команды")}>
          <div className="harness-command-head">
            <span>{t("команда")}</span>
            <span>{t("назначение")}</span>
            <span>{t("режим")}</span>
            <span>{t("последний результат")}</span>
            <span />
          </div>
          {shown.map((command) => (
            <div className="harness-command-row" key={command.command_id}>
              <code>{command.command_id}</code>
              <span>{command.title}</span>
              <em className={`orch-pill ${command.read_only ? "mint" : command.plan_required ? "blue" : "lavender"}`}>
                {command.read_only ? "read-only" : command.plan_required ? "plan" : command.reversibility_label}
              </em>
              <span className="muted no-data" title={t("результат запуска виден в панели команд")}>
                {t("нет данных")}
              </span>
              <button className="btn" type="button" onClick={onShow}>
                <Icon name="terminal" /> {t("Показать")}
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export function Harness() {
  const { t, section, tab: tabLabel, language } = useI18n();
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

  const tabs: [Tab, string][] = [
    ["overview", tabLabel("Обзор")],
    ["runtime", "Runtime"],
    ["adapters", t("Адаптеры")],
    ["containers", t("Контейнеры")],
    ["commands", tabLabel("Команды")],
  ];
  const store = data?.store ?? null;
  const unavailable = t("Недоступно в текущем снимке");
  return (
    <div className="harness-page" data-section="Harness">
      <div className="page-title harness-title">
        <div>
          <h1>{section("Harness")}</h1>
          <p>{t("Установка, runtime, адаптеры и обслуживание. Команды выполняются как job сервера после подтверждения.")}</p>
          <div className="home-facts">
            <span id="harness-version">
              {state ? (state.installed ? state.installed_version : t("не установлен")) : unavailable}
              {data && data.package_version !== state?.installed_version ? ` → ${data.package_version}` : ""}
            </span>
            {store && <span>{store.authority}</span>}
            {store?.schema != null && <span>schema {store.schema}</span>}
            {state && <span>{t("{count} скилов", { count: state.skills })}</span>}
            {data && (
              <span id="harness-updated" title={`${overview.cached ? t("Кэш") : t("Новый снимок")} · ${overview.ageSeconds ?? 0} s`}>
                {snapshotClock(overview.ageSeconds, language)}
              </span>
            )}
          </div>
        </div>
        <div className="actions">
          <button id="harness-refresh" className="btn" type="button" onClick={refreshAll}>
            <Icon name="refresh" /> {t("Проверить")}
          </button>
          <a className="btn" href={href("diagnostics")}>
            <Icon name="pulse" /> {section("Diagnostics")}
          </a>
          <a className="btn primary" href={href("update-harness")}>
            {t("Обновление")}
          </a>
        </div>
      </div>

      {overview.error && !data && (
        <p className="command-refusal err" role="alert" data-code={overview.error.code}>
          {t("○ Состояние харнесса недоступно: ")}
          {overview.error.message || overview.error.code}
        </p>
      )}

      <div className="harness-kpis" id="harness-kpis">
        <div>
          <span>{t("Установлено")}</span>
          <b className="violet">{state ? (state.installed ? state.installed_version : "—") : "—"}</b>
          <small>{data ? t("доступно {version}", { version: data.package_version }) : unavailable}</small>
        </div>
        <div>
          <span>Runtime store</span>
          <b className="mint">{store?.schema != null ? `schema ${store.schema}` : t("нет данных")}</b>
          <small>
            {store
              ? `generation ${store.generation ?? "—"} · audit ${store.audit_records ?? "—"}`
              : unavailable}
          </small>
        </div>
        <div>
          <span>Audit chain</span>
          <b className="cyan">{store?.audit_records ?? t("нет данных")}</b>
          <small>
            cutover{" "}
            {store?.cutover_at ? (
              store.cutover_at
            ) : store?.authority === "file-ledger" ? (
              t("не выполнен")
            ) : (
              <span className="muted no-data">{t("нет данных")}</span>
            )}
          </small>
        </div>
        <div>
          <span>Skills</span>
          <b className="lavender">{state ? state.skills : "—"}</b>
          <small>
            {state
              ? `drift ${data?.drift_files ?? "—"} · ${t("{count} управляемых файлов", { count: state.managed_files })}`
              : unavailable}
          </small>
        </div>
      </div>

      <TabList id="harness" label={section("Harness")} className="orch-tabbar harness-tabbar" tabs={tabs} value={tab} onChange={(id) => setTab(id as Tab)} />

      <TabPanel id="harness" tab="overview" value={tab} keepMounted>
        <div className="harness-grid">
          <InstallPanel overview={data} />
          <RuntimePanel overview={data} compact />
        </div>
        <AdaptersPanel overview={data} compact />
        <QuickCommands onShow={() => setTab("commands")} />
      </TabPanel>
      <TabPanel id="harness" tab="runtime" value={tab} className="harness-runtime-tab">
          <RuntimePanel overview={data} compact={false} />
          <AuditPanel overview={data} />
      </TabPanel>
      <TabPanel id="harness" tab="adapters" value={tab}>
          <AdaptersPanel overview={data} compact={false} />
      </TabPanel>
      <TabPanel id="harness" tab="containers" value={tab}>
          <ContainersPanel overview={data} maintenance={view} />
      </TabPanel>
      <TabPanel id="harness" tab="commands" value={tab} keepMounted>
        <CommandPanel section="harness" planDigests={digests} request={request} onJobDone={refreshAll} />
        <Maintenance
          facts={maintenance.data}
          error={maintenance.error && !maintenance.data ? maintenance.error.message || maintenance.error.code : null}
          onClean={() => ask("cleanup-apply")}
          onRemove={(path) => ask("worktree-remove", { worktree: path })}
          onRefresh={() => maintenance.refresh(true)}
        />
      </TabPanel>
    </div>
  );
}
