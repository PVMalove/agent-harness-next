/* The "Установка" and "Использование пайплайна" panels of the Harness overview, filled only with
   the facts of harness.overview: the lock state, the package version, the drift state and the
   pipeline usage counted on the server. */
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import type { HarnessOverview, MaintenanceView } from "../ws/screens";
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
            {t("Использование пайплайна")}: {t(usage.unavailable)}
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

/** The explicit no-data value of a fact the console has no source for. */
function NoData({ why }: { why?: string }) {
  const { t } = useI18n();
  return (
    <b className="muted no-data" title={why ?? t("Недоступно в текущем снимке")}>
      {t("нет данных")}
    </b>
  );
}

const FLOW: [string, string, string][] = [
  ["harness", "Python policy", "violet"],
  ["orchestration", "IPC", "cyan"],
  ["harness", "Rust runtime", "mint"],
  ["settings", "SQLite WAL", "blue"],
  ["orchestration", "Supervisor", "lavender"],
  ["reports", "Audit chain", "cyan"],
];

/** The mockup's runtime chain; only the store node carries a fact (its schema). */
function Flow({ overview, compact }: { overview: HarnessOverview | null; compact: boolean }) {
  const store = overview?.store ?? null;
  return (
    <div className={`harness-flow${compact ? " compact" : ""}`}>
      {FLOW.map(([icon, label, tone], index) => (
        <span key={label} style={{ display: "contents" }}>
          <div className={`harness-flow-node ${tone}`}>
            <span>
              <Icon name={icon} />
            </span>
            <b>{label}</b>
            <small>
              {label === "SQLite WAL" && store?.schema != null
                ? `schema ${store.schema}`
                : label === "Audit chain" && store?.audit_records != null
                  ? String(store.audit_records)
                  : "—"}
            </small>
          </div>
          {index < FLOW.length - 1 ? <i className="harness-flow-arrow">→</i> : null}
        </span>
      ))}
    </div>
  );
}

export function RuntimePanel({ overview, compact }: { overview: HarnessOverview | null; compact: boolean }) {
  const { t, section } = useI18n();
  const store = overview?.store ?? null;
  const facts: [string, string | number | null][] = [
    ["authority", store?.authority ?? null],
    ["schema", store?.schema ?? null],
    ["generation", store?.generation ?? null],
    ["audit", store?.audit_records ?? null],
    ["cutover", null],
    ["protocol", null],
  ];
  return (
    <section className="panel harness-runtime" id="harness-runtime">
      <div className="panel-head">
        <h2>Runtime</h2>
        <span className={`orch-pill ${store ? "mint" : "violet"}`}>{store ? store.authority : t("нет данных")}</span>
      </div>
      <div className="harness-runtime-body">
        <div className="harness-runtime-line">
          <span>
            <Icon name="harness" /> binary <NoData />
          </span>
          <span>
            uptime <NoData />
          </span>
        </div>
        <div className="harness-store-facts">
          {facts.map(([label, value]) => (
            <div key={label}>
              <span>{label}</span>
              {value === null ? <NoData /> : <b>{String(value)}</b>}
            </div>
          ))}
        </div>
        <Flow overview={overview} compact={compact} />
        <div className="harness-runtime-actions">
          <a className="btn" href={href("orchestration")}>
            <Icon name="orchestration" /> {section("Orchestration")}
          </a>
        </div>
      </div>
    </section>
  );
}

export function AdaptersPanel({ overview, compact }: { overview: HarnessOverview | null; compact: boolean }) {
  const { t } = useI18n();
  const adapters = overview?.adapters ?? null;
  return (
    <section className="panel harness-adapters" id="harness-adapters">
      <div className="panel-head">
        <h2>{t("Адаптеры")}</h2>
        <span className="small muted">{adapters ? t("{count} файлов адаптеров", { count: adapters.length }) : ""}</span>
      </div>
      {adapters === null ? (
        <p className="harness-note">{t("нет данных")}</p>
      ) : adapters.length === 0 ? (
        <p className="harness-note">{t("Файлов адаптеров нет")}</p>
      ) : (
        <div className="harness-adapter-grid">
          {adapters.map((adapter) => (
            <article className="harness-adapter" key={adapter.path}>
              <div className="harness-adapter-head">
                <span>
                  <Icon name="settings" />
                </span>
                <em className={`orch-pill ${adapter.status === "current" ? "mint" : "lavender"}`}>{adapter.status}</em>
              </div>
              <h3>{adapter.path.split("/").slice(-2).join("/")}</h3>
              <div className="harness-adapter-meta">
                <span>
                  CLI <NoData />
                </span>
              </div>
              <p>{adapter.problem ?? adapter.path}</p>
              {compact ? null : (
                <div className="harness-adapter-foot">
                  <span>{adapter.path}</span>
                  <a className="btn" href={href("diagnostics")}>
                    <Icon name="pulse" /> {t("Проверить")}
                  </a>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export function AuditPanel({ overview }: { overview: HarnessOverview | null }) {
  const { t } = useI18n();
  const audit = overview?.store?.audit_records ?? null;
  return (
    <section className="panel harness-audit" id="harness-audit">
      <div className="panel-head">
        <h2>Audit chain</h2>
        <span className="small muted">{audit === null ? t("нет данных") : t("{count} записей", { count: audit })}</span>
      </div>
      <p className="harness-note">{t("Цепочка audit не читается консолью: показано только число записей.")}</p>
    </section>
  );
}

const CONTAINER_KINDS = /container|network|volume|image/;

export function ContainersPanel({ maintenance }: { maintenance: MaintenanceView | null }) {
  const { t } = useI18n();
  const planned = maintenance
    ? [...maintenance.soft.plan.remove, ...maintenance.hard.plan.remove].filter((item) => CONTAINER_KINDS.test(item.kind))
    : null;
  const why = t("Инвентаря Docker/Podman в консоли нет");
  const tiles = ["Engine", "Running", "Images / volumes", "Disk"];
  return (
    <section className="panel harness-containers" id="harness-containers">
      <div className="panel-head">
        <h2>{t("Контейнеры")}</h2>
        <span className="small muted">{why}</span>
      </div>
      <div className="harness-container-summary">
        {tiles.map((tile) => (
          <div key={tile}>
            <span>{tile}</span>
            <NoData why={why} />
          </div>
        ))}
      </div>
      <div className="harness-container-table" id="harness-container-plan">
        <div className="harness-container-head">
          <span>{t("объект")}</span>
          <span>{t("вид")}</span>
          <span>{t("план")}</span>
        </div>
        {planned === null ? (
          <p className="harness-note">{t("План обслуживания загружается…")}</p>
        ) : planned.length === 0 ? (
          <p className="harness-note">{t("В плане очистки нет контейнеров и сетей")}</p>
        ) : (
          planned.map((item) => (
            <div className="harness-container-row" key={`${item.kind}-${item.path}`}>
              <b>{item.path}</b>
              <span>{item.kind}</span>
              <em className="orch-pill lavender">cleanup</em>
            </div>
          ))
        )}
      </div>
      <p className="harness-note">
        {t("Удаление выполняется только командами очистки с подтверждением на вкладке «Команды».")}
      </p>
    </section>
  );
}
