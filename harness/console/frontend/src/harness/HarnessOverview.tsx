/* The panels of the Harness page on the design system v3, filled only with the facts of
   harness.overview: the lock state, the package version and drift, the state store with the runtime
   status probe, the Claude Code, Codex and tracker adapters, the audit count and the container
   engine inventory. A fact without a source says "нет данных". */
import type { ReactNode } from "react";
import { Panel, StatusIcon } from "../ds";
import type { Tone } from "../ds";
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import type { HarnessOverview, MaintenanceView } from "../ws/screens";

/** The explicit no-data value of a fact the console has no source for. */
export function NoData({ why }: { why?: string }) {
  const { t } = useI18n();
  return (
    <span className="ds-muted ds-nodata" title={why ?? t("Недоступно в текущем снимке")}>
      {t("нет данных")}
    </span>
  );
}

type Translate = (text: string, values?: Record<string, string | number>) => string;

/** The six installation rows: name, value, detail, the state word and its tone. The hook policy is
    not part of harness.overview, so its row says no data. */
export function installRows(
  overview: HarnessOverview,
  t: Translate,
  word: (state: string) => string,
): [string, string, string, string, Tone][] {
  const state = overview.state;
  const store = overview.store;
  const current = state.installed_version === overview.package_version;
  return [
    ["Harness package", state.installed_version, t("доступно {version}", { version: overview.package_version }), word(current ? "current" : "outdated"), current ? "ok" : "warn"],
    ["Skills snapshot", String(state.skills), `drift ${overview.drift_files ?? "—"} · ${t("{count} управляемых файлов", { count: state.managed_files })}`, word(overview.drift === "clean" ? "clean" : "drift"), overview.drift === "clean" ? "ok" : "warn"],
    ["Managed files", String(state.managed_files), ".harness/harness.lock", word("ok"), "ok"],
    ["Hook policy", t("нет данных"), t("политику hook снимок harness.overview не читает"), t("нет данных"), "info"],
    ["Runtime store", store?.schema != null ? `schema ${store.schema}` : t("нет данных"), store ? `generation ${store.generation ?? "—"} · audit ${store.audit_records ?? "—"}` : "—", store ? store.authority : t("нет данных"), store ? "ok" : "info"],
    ["harness.lock", state.updated_at || "—", t("Lock обновлён"), word(state.updated_at ? "ok" : "missing"), state.updated_at ? "ok" : "err"],
  ];
}

export function InstallPanel({ overview }: { overview: HarnessOverview | null }) {
  const { t, section, state: word } = useI18n();
  const state = overview?.state;
  const installed = state?.installed ?? false;
  const components = overview && state ? installRows(overview, t, word) : [];
  return (
    <Panel id="harness-install" fill className="ds-install" title={t("Установка")} meta={installed ? t("установлен") : t("не установлен")}
      actions={<>
        <a className="ds-btn ds-btn-primary ds-btn-sm" href={href("update-harness")}>{section("Update Harness")}</a>
        <a className="ds-btn ds-btn-sm" href={href("diagnostics")}><Icon name="pulse" className="ds-ic-sm" /> {section("Diagnostics")}</a>
      </>}>
      {!overview ? <p className="ds-note">{t("Состояние харнесса загружается…")}</p> : <>
        <p className="ds-note">
          {installed ? <>Capability: <code>{state!.capabilities.join(", ") || t("нет")}</code></> : t("Харнесс не установлен: нет читаемого .harness/harness.lock.")}
        </p>
        {installed && <ul className="ds-rows">
          {components.map(([name, value, detail, pill, tone]) => (
            <li className="ds-row" key={name}>
              <StatusIcon tone={tone} label={pill} />
              <span className="ds-row-main"><b className="ds-row-title">{name}</b><small className="ds-row-sub">{detail}</small></span>
              <span className="ds-row-end">{value}</span>
              <em className="ds-tag">{pill}</em>
            </li>
          ))}
        </ul>}
      </>}
    </Panel>
  );
}

/** What needs attention, from the fields of harness.overview only: drift of the package files and
    the adapters that are not current. */
export function AttentionPanel({ overview }: { overview: HarnessOverview | null }) {
  const { t, state: word } = useI18n();
  const items: [string, string, string, Tone, string][] = [];
  if (overview) {
    if (overview.drift !== "clean") items.push(["drift", t("Расхождение навыков · {count}", { count: overview.drift_files ?? "—" }), t("Файлы пакета отличаются от установленных."), "warn", href("update-harness")]);
    if (overview.state.installed_version !== overview.package_version) items.push(["version", `${overview.state.installed_version} → ${overview.package_version}`, t("Доступна другая версия пакета."), "warn", href("update-harness")]);
    for (const item of overview.integrations ?? []) {
      if (item.status !== "current") items.push([item.name, item.name, `${word(item.status)} · ${item.detail || "—"}`, item.status === "missing" ? "err" : "warn", href("diagnostics")]);
    }
  }
  return (
    <Panel id="harness-attention" fill title={t("Требует внимания")} count={overview ? items.length : undefined} meta={t("Файлы Harness")}>
      {!overview ? <p className="ds-note"><NoData why={t("Состояние харнесса загружается…")} /></p>
        : items.length === 0 ? <p className="ds-empty">{t("Всё в порядке")}</p>
        : <ul className="ds-rows">{items.map(([key, title, text, tone, link]) => (
            <li className="ds-row" key={key}>
              <StatusIcon tone={tone} label={tone === "err" ? t("ошибка") : t("Внимание")} />
              <span className="ds-row-main"><b className="ds-row-title">{title}</b><small className="ds-row-sub">{text}</small></span>
              <a className="ds-btn ds-btn-sm ds-btn-icon" href={link} aria-label={title}><Icon name="chevron" className="ds-ic-sm" /></a>
            </li>))}</ul>}
    </Panel>
  );
}

const FLOW: [string, string][] = [
  ["harness", "Python policy"], ["orchestration", "IPC"], ["runtime", "Rust runtime"],
  ["store", "SQLite WAL"], ["orchestration", "Supervisor"], ["reports", "Audit chain"],
];

/** The runtime chain; only the store node and the audit node carry a fact. */
export function LoopPanel({ overview }: { overview: HarnessOverview | null }) {
  const { t } = useI18n();
  const store = overview?.store ?? null;
  const caption = (label: string) =>
    label === "SQLite WAL" && store?.schema != null ? `schema ${store.schema}`
      : label === "Audit chain" && store?.audit_records != null ? t("{count} записей", { count: store.audit_records })
      : "—";
  return (
    <Panel id="harness-loop" title={t("Контур Harness")} meta={t("Состав системы")}>
      <div className="ds-loop" role="region" tabIndex={0} aria-label="Runtime flow">
        {FLOW.map(([icon, label]) => (
          <div className="ds-loop-node" key={label}>
            <Icon name={icon} className="ds-ic-sm" />
            <span><b>{label}</b><small>{caption(label)}</small></span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

export function RuntimePanel({ overview }: { overview: HarnessOverview | null }) {
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
  const online = runtime?.state === "online" || (!runtime && store?.authority === "file-ledger");
  return (
    <Panel id="harness-runtime" fill title="Runtime" actions={<a className="ds-btn ds-btn-sm" href={href("orchestration")}><Icon name="orchestration" className="ds-ic-sm" /> {section("Orchestration")}</a>}
      meta={<span className="ds-status-line"><StatusIcon tone={online ? "ok" : "warn"} label={online ? t("работает") : t("не отвечает")} /><span aria-hidden="true">{runtime ? (runtime.state === "online" ? t("работает") : t("не отвечает")) : (store?.authority ?? t("нет данных"))}</span></span>}>
      <p className="ds-note"><Icon name="harness" className="ds-ic-sm" /> harness-runtime · {store ? store.authority : <NoData />}{runtime?.reason ? ` · ${t(runtime.reason)}` : ""}</p>
      <dl className="ds-kv">
        {facts.map(([label, value]) => (
          <div className="ds-kv-row" key={label}><dt>{label}</dt><dd>{value === null ? <NoData /> : String(value)}</dd></div>
        ))}
      </dl>
    </Panel>
  );
}

const INTEGRATION_ICONS: Record<string, string> = { "Claude Code": "terminal", Codex: "command", GitHub: "github-mark", GitLab: "gitlab-mark", Local: "folder" };
const INTEGRATION_TONES: Record<string, Tone> = { current: "ok", outdated: "warn", missing: "err", unknown: "info" };

/** Claude Code and Codex (adapter files of the installed capabilities, CLI on PATH) and the project
    tracker (its CLI on PATH). Nothing is checked online. */
export function AdaptersPanel({ overview }: { overview: HarnessOverview | null }) {
  const { t, state } = useI18n();
  const integrations = overview?.integrations ?? null;
  return (
    <Panel id="harness-adapters" fill title={t("Адаптеры")} meta={integrations ? integrations.map((item) => item.name).join(" · ") : undefined}>
      {integrations === null ? <p className="ds-note"><NoData why={t("Адаптеры не собраны в этом снимке")} /></p> : (
        <ul className="ds-rows">
          {integrations.map((item) => (
            <li className="ds-row ds-adapter" key={item.name}>
              <StatusIcon tone={INTEGRATION_TONES[item.status] ?? "info"} label={state(item.status)} />
              <Icon name={INTEGRATION_ICONS[item.name] ?? "settings"} className="ds-ic" />
              <span className="ds-row-main">
                <b className="ds-row-title">{item.name}</b>
                <small className="ds-row-sub">
                  {item.kind === "runtime" ? t("runtime-адаптер") : t("адаптер трекера")} · CLI {item.cli === null ? "—" : item.cli ? t("найден в PATH") : t("не найден в PATH")}
                  {" · "}{item.detail || (item.kind === "runtime" ? t("Файлов адаптера нет") : t("локальная работа"))}
                </small>
              </span>
              <span className="ds-row-end">{item.kind === "tracker" ? t("сеть и права не проверялись") : t("файлы адаптера из harness.lock")}</span>
              <em className="ds-tag">{state(item.status)}</em>
              <a className="ds-btn ds-btn-sm" href={href("diagnostics")}><Icon name="pulse" className="ds-ic-sm" /> {t("Проверить")}</a>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

export function AuditPanel({ overview }: { overview: HarnessOverview | null }) {
  const { t } = useI18n();
  const audit = overview?.store?.audit_records ?? null;
  return (
    <Panel id="harness-audit" title="Audit chain" meta={audit === null ? t("нет данных") : t("{count} записей", { count: audit })}>
      <p className="ds-note">{t("Цепочка audit не читается консолью: показано только число записей.")}</p>
    </Panel>
  );
}

const CONTAINER_KINDS = /container|network|volume|image/;
type PlannedItem = MaintenanceView["soft"]["plan"]["remove"][number];

function planRows(planned: PlannedItem[] | null, keep: (kind: string) => boolean, empty: string): ReactNode {
  if (planned === null) return null;
  const rows = planned.filter((item) => keep(item.kind));
  if (rows.length === 0) return <p className="ds-note">{empty}</p>;
  return (
    <ul className="ds-rows">
      {rows.map((item) => (
        <li className="ds-row" key={`${item.kind}-${item.path}`}>
          <span className="ds-row-main"><b className="ds-row-title">{item.path}</b></span>
          <span className="ds-row-end">{item.kind}</span>
          <em className="ds-tag">cleanup</em>
        </li>
      ))}
    </ul>
  );
}

export function ContainersPanel({ overview, maintenance }: { overview: HarnessOverview | null; maintenance: MaintenanceView | null }) {
  const { t } = useI18n();
  const planned = maintenance ? [...maintenance.soft.plan.remove, ...maintenance.hard.plan.remove].filter((item) => CONTAINER_KINDS.test(item.kind)) : null;
  const inventory = overview?.containers ?? null;
  const unprobed = t("Инвентарь движка контейнеров не собран");
  const noSource = t("Источника нет в инвентаре движка");
  // A fact of `info` that is null: the probe's reason, else the engine did not report it.
  const infoWhy = inventory?.info_problem ?? t("Движок не сообщил этот факт");
  const fact = (value: string | null, why: string) => (value === null ? <NoData why={why} /> : value);
  const cgroup = inventory && (inventory.cgroup_version !== null || inventory.cgroup_driver !== null)
    ? [inventory.cgroup_version, inventory.cgroup_driver].filter((part) => part !== null).join(" · ") : null;
  const flag = (value: boolean | null | undefined, on: string, off: string) => (value === null || value === undefined ? null : value ? on : off);
  const engineLine = inventory
    ? [inventory.engine, inventory.version, flag(inventory.rootless, "rootless", "rootful"), cgroup && `cgroup ${cgroup}`].filter(Boolean).join(" · ")
    : unprobed;
  return (
    <Panel id="harness-containers" fill title={t("Контейнеры")} meta={<span id="harness-engine-line">{engineLine}</span>}>
      <div className="ds-container-stats" id="harness-container-summary">
        <div><span>Engine</span>{inventory ? <b>{inventory.engine}</b> : <NoData why={unprobed} />}
          <small>{inventory ? fact(inventory.version, infoWhy) : "—"}{inventory?.rootless != null && ` · ${inventory.rootless ? "rootless" : "rootful"}`}</small></div>
        <div><span>Running</span><NoData why={noSource} /></div>
        <div><span>Images / volumes</span>
          <b data-fact="images-volumes">{inventory?.images ?? <NoData why={inventory?.images_problem ?? unprobed} />} / {inventory?.volumes ?? <NoData why={inventory?.volumes_problem ?? unprobed} />}</b></div>
        <div><span>Disk</span><NoData why={noSource} /></div>
      </div>
      {inventory && (
        <div className="ds-engine" id="harness-engine">
          <span>daemon {inventory.info_problem === null ? t("отвечает") : <NoData why={inventory.info_problem} />}</span>
          <span>{flag(inventory.rootless, "rootless", "rootful") ?? <>rootless <NoData why={infoWhy} /></>}</span>
          <span>cgroup {fact(cgroup, infoWhy)}</span>
          <span>SELinux {fact(flag(inventory.selinux, t("включён"), t("выключен")), infoWhy)}</span>
          <span>{[inventory.images_problem, inventory.volumes_problem].filter(Boolean).join(" · ")}</span>
        </div>
      )}
      <div id="harness-container-plan">
        <h3 className="ds-rel-title ds-pad">{t("объект")} · {t("вид")} · {t("план")}</h3>
        {planned === null ? <p className="ds-note">{t("План обслуживания загружается…")}</p> : planRows(planned, (kind) => kind === "container", t("В плане очистки нет контейнеров"))}
      </div>
      <div className="ds-grid-2 ds-pad" id="harness-container-grid">
        <section aria-label="Images">
          <h3 className="ds-rel-title">Images · {inventory?.images ?? "—"}</h3>
          <p className="ds-note">{inventory?.images_problem ?? t("Инвентарь движка содержит только число образов: список, теги и размер не читаются.")}</p>
          {planRows(planned, (kind) => kind === "image", t("В плане очистки нет образов"))}
        </section>
        <section aria-label="Networks / volumes">
          <h3 className="ds-rel-title">Networks / volumes · — / {inventory?.volumes ?? "—"}</h3>
          <p className="ds-note">{inventory?.volumes_problem ?? t("Сети не входят в инвентарь движка; для томов известно только число.")}</p>
          <p className="ds-note">{t("Очистка")}: {planned === null ? t("План обслуживания загружается…") : t("в плане {count}", { count: planned.filter((item) => /network|volume/.test(item.kind)).length })}</p>
        </section>
      </div>
      <p className="ds-note">{t("Удаление выполняется только командами очистки с подтверждением на вкладке «Команды».")}</p>
    </Panel>
  );
}
