/* The panels of the Harness page, filled only with the facts of harness.overview: the lock
   state, the package version and drift, the state store with the runtime status probe, the
   Claude Code, Codex and tracker adapters, the audit count and the container engine inventory. */
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import type { HarnessOverview, MaintenanceView } from "../ws/screens";

/** The six installation rows of the mockup: name, value, detail, and the state pill with its
    tone. The hook policy is not part of harness.overview, so its row says no data. */
export function installRows(
  overview: HarnessOverview,
  t: (text: string, values?: Record<string, string | number>) => string,
  word: (state: string) => string,
): [string, string, string, string, string][] {
  const state = overview.state;
  const store = overview.store;
  const current = state.installed_version === overview.package_version;
  return [
    [
      "Harness package",
      state.installed_version,
      t("доступно {version}", { version: overview.package_version }),
      word(current ? "current" : "outdated"),
      current ? "mint" : "lavender",
    ],
    [
      "Skills snapshot",
      String(state.skills),
      `drift ${overview.drift_files ?? "—"} · ${t("{count} управляемых файлов", { count: state.managed_files })}`,
      word(overview.drift === "clean" ? "clean" : "drift"),
      overview.drift === "clean" ? "mint" : "lavender",
    ],
    ["Managed files", String(state.managed_files), ".harness/harness.lock", word("ok"), "mint"],
    ["Hook policy", t("нет данных"), t("политику hook снимок harness.overview не читает"), t("нет данных"), "blue"],
    [
      "Runtime store",
      store?.schema != null ? `schema ${store.schema}` : t("нет данных"),
      store ? `generation ${store.generation ?? "—"} · audit ${store.audit_records ?? "—"}` : "—",
      store ? store.authority : t("нет данных"),
      store ? "mint" : "blue",
    ],
    ["harness.lock", state.updated_at || "—", t("Lock обновлён"), word(state.updated_at ? "ok" : "missing"), state.updated_at ? "mint" : "violet"],
  ];
}

export function InstallPanel({ overview }: { overview: HarnessOverview | null }) {
  const { t, section, state: word } = useI18n();
  const state = overview?.state;
  const installed = state?.installed ?? false;
  const components = overview && state ? installRows(overview, t, word) : [];
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
  const runtime = overview?.runtime ?? null;
  const facts: [string, string | number | null][] = [
    ["authority", store?.authority ?? null],
    ["schema", store?.schema ?? null],
    ["generation", store?.generation ?? null],
    ["audit", store?.audit_records ?? null],
    ["cutover", store?.cutover_at ?? (store?.authority === "file-ledger" ? t("не выполнен") : null)],
    ["revision", runtime?.revision ?? null],
  ];
  return (
    <section className="panel harness-runtime" id="harness-runtime">
      <div className="panel-head">
        <h2>Runtime</h2>
        <span className={`orch-pill ${runtime?.state === "online" || (!runtime && store?.authority === "file-ledger") ? "mint" : "violet"}`}>
          {runtime ? (runtime.state === "online" ? t("работает") : t("не отвечает")) : (store?.authority ?? t("нет данных"))}
        </span>
      </div>
      <div className="harness-runtime-body">
        <div className="harness-runtime-line">
          <span>
            <Icon name="harness" /> harness-runtime
          </span>
          <span>{store ? store.authority : <NoData />}</span>
          {runtime?.reason ? <span className="muted">{t(runtime.reason)}</span> : null}
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

const INTEGRATION_ICONS: Record<string, string> = { "Claude Code": "terminal", Codex: "command", GitHub: "github-mark", GitLab: "gitlab-mark", Local: "folder" };
const INTEGRATION_TONES: Record<string, string> = { current: "mint", outdated: "lavender", missing: "violet", unknown: "blue" };

/** The mockup adapters: Claude Code and Codex (adapter files of the installed capabilities, CLI on
    PATH) and the project tracker (its CLI on PATH). Nothing is checked online. */
export function AdaptersPanel({ overview, compact }: { overview: HarnessOverview | null; compact: boolean }) {
  const { t, state } = useI18n();
  const integrations = overview?.integrations ?? null;
  return (
    <section className="panel harness-adapters" id="harness-adapters">
      <div className="panel-head">
        <h2>{t("Адаптеры")}</h2>
        <span className="small muted">{integrations ? integrations.map((item) => item.name).join(" · ") : ""}</span>
      </div>
      {integrations === null ? (
        <p className="harness-note">
          <NoData why={t("Адаптеры не собраны в этом снимке")} />
        </p>
      ) : (
        <div className="harness-adapter-grid">
          {integrations.map((item) => (
            <article className="harness-adapter" key={item.name}>
              <div className="harness-adapter-head">
                <span>
                  <Icon name={INTEGRATION_ICONS[item.name] ?? "settings"} />
                </span>
                <em className={`orch-pill ${INTEGRATION_TONES[item.status]}`}>{state(item.status)}</em>
              </div>
              <h3>{item.name}</h3>
              <div className="harness-adapter-meta">
                <span>{item.kind === "runtime" ? t("runtime-адаптер") : t("адаптер трекера")}</span>
                <span>CLI {item.cli === null ? "—" : item.cli ? t("найден в PATH") : t("не найден в PATH")}</span>
              </div>
              <p>{item.detail || (item.kind === "runtime" ? t("Файлов адаптера нет") : t("локальная работа"))}</p>
              {compact ? null : (
                <div className="harness-adapter-foot">
                  <span>{item.kind === "tracker" ? t("сеть и права не проверялись") : t("файлы адаптера из harness.lock")}</span>
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

export function ContainersPanel({
  overview,
  maintenance,
}: {
  overview: HarnessOverview | null;
  maintenance: MaintenanceView | null;
}) {
  const { t } = useI18n();
  const planned = maintenance
    ? [...maintenance.soft.plan.remove, ...maintenance.hard.plan.remove].filter((item) => CONTAINER_KINDS.test(item.kind))
    : null;
  const inventory = overview?.containers ?? null;
  const unprobed = t("Инвентарь движка контейнеров не собран");
  const noSource = t("Источника нет в инвентаре движка");
  // A fact of `info` that is null: the probe's reason, else the engine did not report it.
  const infoWhy = inventory?.info_problem ?? t("Движок не сообщил этот факт");
  const fact = (value: string | null, why: string) => (value === null ? <NoData why={why} /> : value);
  const cgroup =
    inventory && (inventory.cgroup_version !== null || inventory.cgroup_driver !== null)
      ? [inventory.cgroup_version, inventory.cgroup_driver].filter((part) => part !== null).join(" · ")
      : null;
  const flag = (value: boolean | null | undefined, on: string, off: string) =>
    value === null || value === undefined ? null : value ? on : off;
  return (
    <section className="panel harness-containers" id="harness-containers">
      <div className="panel-head">
        <h2>{t("Контейнеры")}</h2>
        <span className="small muted" id="harness-engine-line">
          {inventory
            ? [inventory.engine, inventory.version, flag(inventory.rootless, "rootless", "rootful"), cgroup && `cgroup ${cgroup}`]
                .filter(Boolean)
                .join(" · ")
            : unprobed}
        </span>
      </div>
      <div className="harness-container-summary" id="harness-container-summary">
        <div>
          <span>Engine</span>
          {inventory ? <b className="mint">{inventory.engine}</b> : <NoData why={unprobed} />}
          <small>
            {inventory ? fact(inventory.version, infoWhy) : "—"}
            {inventory?.rootless != null && ` · ${inventory.rootless ? "rootless" : "rootful"}`}
          </small>
        </div>
        <div>
          <span>Running</span>
          <NoData why={noSource} />
        </div>
        <div>
          <span>Images / volumes</span>
          <b className="cyan" data-fact="images-volumes">
            {inventory?.images ?? <NoData why={inventory?.images_problem ?? unprobed} />} /{" "}
            {inventory?.volumes ?? <NoData why={inventory?.volumes_problem ?? unprobed} />}
          </b>
        </div>
        <div>
          <span>Disk</span>
          <NoData why={noSource} />
        </div>
      </div>
      {inventory && (
        <div className="harness-engine" id="harness-engine">
          <span className={inventory.info_problem === null ? "ok" : undefined}>
            daemon {inventory.info_problem === null ? t("отвечает") : <NoData why={inventory.info_problem} />}
          </span>
          <span className={inventory.rootless ? "ok" : undefined}>
            {flag(inventory.rootless, "rootless", "rootful") ?? <>rootless <NoData why={infoWhy} /></>}
          </span>
          <span className={cgroup ? "ok" : undefined}>cgroup {fact(cgroup, infoWhy)}</span>
          <span className={inventory.selinux ? "ok" : undefined}>
            SELinux {fact(flag(inventory.selinux, t("включён"), t("выключен")), infoWhy)}
          </span>
          <span>{[inventory.images_problem, inventory.volumes_problem].filter(Boolean).join(" · ")}</span>
        </div>
      )}
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
