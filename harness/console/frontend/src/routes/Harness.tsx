/* Harness: the mockup's #harness with the facts of harness.overview (state, package version,
   drift, pipeline usage) and harness.maintenance (cleanup plans, worktrees). Tabs "Обзор" and
   "Команды" are both mounted, the inactive one hidden, so a page button can hand a run to the
   command panel, whose dialog shows the server's confirmation. The other tabs of the mockup
   (Runtime, Adapters, Containers) have no TUI facts yet and are not shown. */
import { useCallback, useState } from "react";
import { CommandPanel } from "../commands/CommandPanel";
import type { RunRequest } from "../commands/CommandPanel";
import { InstallPanel, UsagePanel } from "../harness/HarnessOverview";
import { Maintenance } from "../harness/Maintenance";
import { driftLabel, formatSize } from "../harness/format";
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { useScreen } from "../screens/useScreen";
import { parseHarnessOverview, parseMaintenance } from "../ws/screens";

/** The plan each plan-bound cleanup command deletes: the wire contract of `plan_digest`. */
export const PLAN_OF_COMMAND = { "cleanup-apply": "soft", "cleanup-hard-apply": "hard" } as const;

type Tab = "overview" | "commands";

export function Harness() {
  const { t, section, tab: tabLabel } = useI18n();
  const [tab, setTab] = useState<Tab>("overview");
  const [request, setRequest] = useState<RunRequest | null>(null);
  const overview = useScreen({ type: "harness.overview" }, parseHarnessOverview);
  const maintenance = useScreen({ type: "harness.maintenance" }, parseMaintenance);
  const data = overview.data;
  const state = data?.state;
  const usage = data?.usage;
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
    ["commands", tabLabel("Команды")],
  ];
  const unavailable = t("Недоступно в текущем снимке");
  return (
    <div className="harness-page" data-section="Harness">
      <div className="page-title harness-title">
        <div>
          <h1>{section("Harness")}</h1>
          <p>{t("Установка, использование пайплайна и обслуживание. Команды выполняются как job сервера после подтверждения.")}</p>
          <div className="home-facts">
            <span id="harness-version">
              {state ? (state.installed ? state.installed_version : t("не установлен")) : unavailable}
            </span>
            {state && <span>{t("{count} скилов", { count: state.skills })}</span>}
            {data && <span id="harness-drift">{t(driftLabel(data.drift))}</span>}
            {state?.updated_at && <span>Lock {state.updated_at}</span>}
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
            {section("Update Harness")}
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
          <small>{data ? `${t("Пакет")} ${data.package_version}` : unavailable}</small>
        </div>
        <div>
          <span>Skills</span>
          <b className="lavender">{state ? state.skills : "—"}</b>
          <small>{state ? t("{count} управляемых файлов", { count: state.managed_files }) : unavailable}</small>
        </div>
        <div>
          <span>{t("Пайплайн")}</span>
          <b className="mint">{usage ? (usage.unavailable === null ? usage.batches : "—") : "—"}</b>
          <small>
            {usage
              ? usage.unavailable === null
                ? t("тикетов {tickets} · диспатчей {dispatches} · отчётов {reports}", {
                    tickets: usage.tickets,
                    dispatches: usage.dispatches,
                    reports: usage.reports,
                  })
                : t(usage.unavailable)
              : unavailable}
          </small>
        </div>
        <div>
          <span>{t("Временные файлы")}</span>
          <b className="cyan">{view ? formatSize(view.soft.total.bytes) : "—"}</b>
          <small>{view ? t("{count} объектов", { count: view.soft.items }) : t("Статистика считается…")}</small>
        </div>
      </div>

      <div className="orch-tabbar harness-tabbar" role="tablist">
        {tabs.map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`orch-tab${tab === id ? " on" : ""}`}
            role="tab"
            aria-selected={tab === id}
            aria-controls={`harness-tab-${id}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div id="harness-tab-overview" role="tabpanel" hidden={tab !== "overview"}>
        <div className="harness-grid">
          <InstallPanel overview={data} />
          <UsagePanel overview={data} />
        </div>
        <Maintenance
          facts={maintenance.data}
          error={maintenance.error && !maintenance.data ? maintenance.error.message || maintenance.error.code : null}
          onClean={() => ask("cleanup-apply")}
          onRemove={(path) => ask("worktree-remove", { worktree: path })}
          onRefresh={() => maintenance.refresh(true)}
        />
      </div>
      <div id="harness-tab-commands" role="tabpanel" hidden={tab !== "commands"}>
        <CommandPanel section="harness" planDigests={digests} request={request} onJobDone={refreshAll} />
      </div>
    </div>
  );
}
