/* The "Установка" and "Использование пайплайна" panels of the Harness overview, filled only with
   the facts of harness.overview: the lock state, the package version, the drift state and the
   pipeline usage counted on the server. */
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import type { HarnessOverview } from "../ws/screens";
import { driftLabel } from "./format";

export function InstallPanel({ overview }: { overview: HarnessOverview | null }) {
  const { t, section } = useI18n();
  const state = overview?.state;
  const installed = state?.installed ?? false;
  // name, value, detail, and the state pill with its tone when the fact has a state.
  const components: [string, string, string, string, string][] = state
    ? [
        [t("Скилов"), String(state.skills), ".harness/skills", "", ""],
        [t("Управляемых файлов"), String(state.managed_files), ".harness/harness.lock", "", ""],
        ["Lock", state.updated_at || "—", t("Lock обновлён"), "", ""],
        [
          t("Оркестрация"),
          state.orchestration ? "✔" : "○",
          ".harness/orchestration",
          state.orchestration ? t("✔ подключена") : t("○ не подключена"),
          state.orchestration ? "mint" : "violet",
        ],
        [
          t("Дрейф"),
          overview.drift,
          "harness diff",
          t(driftLabel(overview.drift)),
          overview.drift === "clean" ? "mint" : "lavender",
        ],
      ]
    : [];
  return (
    <section className="panel harness-install" id="harness-install">
      <div className="panel-head">
        <h2>{t("Установка")}</h2>
        <span className={`orch-pill ${installed ? "mint" : "violet"}`}>
          {installed ? t("установлен") : t("не установлен")}
        </span>
      </div>
      <div className="harness-install-body">
        {!overview ? (
          <p className="harness-install-note">{t("Состояние харнесса загружается…")}</p>
        ) : (
          <>
            <div className="harness-version-pair">
              <div>
                <span>{t("Установлено")}</span>
                <b>{installed ? state!.installed_version : "—"}</b>
              </div>
              <span>→</span>
              <div>
                <span>{t("Пакет")}</span>
                <b>{overview.package_version}</b>
              </div>
            </div>
            <p className="harness-install-note">
              {installed ? (
                <>
                  Capability: <code>{state!.capabilities.join(", ") || t("нет")}</code>
                </>
              ) : (
                t("Харнесс не установлен: нет читаемого .harness/harness.lock.")
              )}
            </p>
            {installed && (
              <div className="harness-components">
                {components.map(([name, value, detail, pill, tone]) => (
                  <div className="harness-component" key={name}>
                    <span>{name}</span>
                    <b>{value}</b>
                    <small>{detail}</small>
                    {pill ? <em className={`orch-pill ${tone}`}>{pill}</em> : <em />}
                  </div>
                ))}
              </div>
            )}
          </>
        )}
        <div className="harness-install-actions">
          <a className="btn primary" href={href("update-harness")}>
            {section("Update Harness")}
          </a>
          <a className="btn" href={href("diagnostics")}>
            <Icon name="pulse" /> {section("Diagnostics")}
          </a>
        </div>
      </div>
    </section>
  );
}

export function UsagePanel({ overview }: { overview: HarnessOverview | null }) {
  const { t, section } = useI18n();
  const usage = overview?.usage;
  const facts: [string, number][] = usage
    ? [
        [t("Запусков (batch)"), usage.batches],
        [t("Тикетов"), usage.tickets],
        [t("Диспатчей"), usage.dispatches],
        [t("Отчётов"), usage.reports],
      ]
    : [];
  return (
    <section className="panel harness-runtime" id="harness-usage">
      <div className="panel-head">
        <h2>{t("Использование пайплайна")}</h2>
        {usage && (
          <span className={`orch-pill ${usage.unavailable === null ? "mint" : "violet"}`}>
            {usage.unavailable === null ? "ledger" : t("недоступно")}
          </span>
        )}
      </div>
      <div className="harness-runtime-body">
        {!usage ? (
          <p className="harness-install-note">{t("Состояние харнесса загружается…")}</p>
        ) : usage.unavailable !== null ? (
          <p className="harness-install-note">
            {t("Использование пайплайна")}: {usage.unavailable}
          </p>
        ) : (
          <div className="harness-store-facts">
            {facts.map(([label, value]) => (
              <div key={label}>
                <span>{label}</span>
                <b>{value}</b>
              </div>
            ))}
          </div>
        )}
        <div className="harness-runtime-actions">
          <a className="btn" href={href("orchestration")}>
            <Icon name="orchestration" /> {section("Orchestration")}
          </a>
          <a className="btn" href={href("reports")}>
            <Icon name="reports" /> {section("Reports")}
          </a>
        </div>
      </div>
    </section>
  );
}
