/* Configuration (#/configuration): the facts of configuration.snapshot in five tabs on the design
   system v3 — Overview (files, policies, runtime adapters), Parameters (the wizard with the console
   recommendation), JSON (both files as text), Changes (the change set of the one shared draft and
   its confirmed write) and History (the saved versions and the JSON of the selected one). The
   Parameters and JSON tabs only edit the draft; every write (draft version, apply, adapters,
   current version, recovery) runs only through the CommandPanel of the job section
   `configuration`, and every run opens the confirmation first. Restore stays in the TUI. */
import { downloadJson } from "../diagnostics/exportReport";
import { useState } from "react";
import { CommandPanel } from "../commands/CommandPanel";
import type { RunRequest } from "../commands/CommandPanel";
import { draftRequest } from "../configuration/changes";
import { pretty, useConfigurationDraft } from "../configuration/draft";
import type { ConfigurationDraft } from "../configuration/draft";
import { ADAPTER_STATUS, NO_SCHEMA, PENDING, adapterName, shortDigest, writeBlock } from "../configuration/format";
import { Wizard, currentValue, shown } from "../configuration/Wizard";
import { PageHeader, Panel, PipeTabs, ScreenState, Summary } from "../ds";
import { useI18n } from "../i18n";
import { Icon } from "../icons";
import { useScreen } from "../screens/useScreen";
import { NoData } from "../steps/ActivityViews";
import { snapshotClock } from "../update/format";
import { useConsole } from "../useConsole";
import { TabList, TabPanels } from "../views/Tabs";
import type { StoreFacts } from "../ws/types";
import { CONFIG_NAMES, parseConfiguration } from "../ws/projectScreens";
import type { ConfigName, ConfigurationFacts } from "../ws/projectScreens";

type Tab = "overview" | "parameters" | "json" | "changes" | "history";
const TABS: readonly (readonly [Tab, string])[] = [
  ["overview", "Обзор"],
  ["parameters", "Параметры"],
  ["json", "JSON"],
  ["changes", "Изменения"],
  ["history", "История"],
];

const SCHEMAS: Readonly<Record<ConfigName, string>> = {
  "project.json": "project.schema.json",
  "orchestration.json": "orchestration.schema.json",
};
const HOOK_POLICY_WHY = "Снимок configuration.snapshot не читает hook policy";
const STORE_WHY = "Снимок Главной ещё не получен";

type Run = (command: string, values: Record<string, string>, reason: string) => void;

/** A file's state word and tone: valid, missing (the default document is shown) or error. */
function fileState(facts: ConfigurationFacts, name: ConfigName): readonly [string, string] {
  const file = facts.files[name];
  if (file.error) return ["ошибка", "err"];
  return file.exists ? ["valid", "ok"] : ["нет файла", "warn"];
}

function Overview({ facts, store, onRun }: { facts: ConfigurationFacts; store: StoreFacts | null; onRun: Run }) {
  const { t } = useI18n();
  const preview = facts.adapters.preview;
  const params = facts.wizard ?? [];
  const resolved = (param: (typeof params)[number]) => {
    const value = currentValue(facts, param);
    const found = value === undefined ? param.default : value;
    return found === null || found === undefined ? t("не задано") : shown(found);
  };
  return (
    <div className="ds-settings-cols" id="configuration-overview">
      <div className="ds-settings-col">
        <Panel title={t("Конфигурация")} id="configuration-files" count={CONFIG_NAMES.filter((name) => facts.files[name].exists).length}>
          <div className="ds-rows">
            {CONFIG_NAMES.map((name) => {
              const file = facts.files[name];
              const [word, tone] = fileState(facts, name);
              return (
                <div className="ds-row" key={name} data-file={name}>
                  <Icon name="settings" className="ds-ic-sm" />
                  <span className="ds-row-main">
                    <b className="ds-row-title">{name}</b>
                    <small className="ds-row-sub">{`.harness/${name} · ${SCHEMAS[name]} · sha256 ${shortDigest(file.digest)}`}</small>
                    {!file.exists && <small className="ds-row-sub">{t("нет — показан документ по умолчанию")}</small>}
                    {file.error && <small className="ds-row-sub" data-tone="err">{file.error}</small>}
                  </span>
                  <span className="ds-tag" data-tone={tone}>{t(word)}</span>
                </div>
              );
            })}
            <div className="ds-row" data-file="hook-policy.json">
              <Icon name="settings" className="ds-ic-sm" />
              <span className="ds-row-main">
                <b className="ds-row-title">hook-policy.json</b>
                <small className="ds-row-sub">.harness/hook-policy.json</small>
              </span>
              <span className="ds-tag"><NoData why={t(HOOK_POLICY_WHY)} /></span>
            </div>
            <div className="ds-row" data-file="runtime-store">
              <Icon name="harness" className="ds-ic-sm" />
              <span className="ds-row-main">
                <b className="ds-row-title">runtime-store</b>
                <small className="ds-row-sub">{store ? [store.authority, store.generation].filter(Boolean).join(" · ") : t("нет данных")}</small>
              </span>
              <span className="ds-tag">{store?.schema != null ? `schema ${store.schema}` : <NoData why={t(store ? store.reason || STORE_WHY : STORE_WHY)} />}</span>
            </div>
          </div>
          <p className="ds-note">{facts.transaction_pending ? t("Есть незавершённая запись: сначала восстановите её.") : t("Незавершённой записи нет.")}</p>
        </Panel>
        <Panel title={t("Политики")} id="configuration-policy" meta={t("итоговые значения")} fill scroll="list">
          {params.length === 0 ? (
            <p className="ds-note"><NoData why={t("Сервер не прислал каталог параметров")} /></p>
          ) : (
            <dl className="ds-kv">
              {params.map((param) => (
                <div className="ds-kv-row" key={`${param.file}:${param.path.join(".")}`}>
                  <dt>{t(param.label)}</dt>
                  <dd>{resolved(param)}</dd>
                </div>
              ))}
            </dl>
          )}
        </Panel>
      </div>
      <div className="ds-settings-col">
        <Panel
          title={t("Адаптеры runtime")}
          id="configuration-adapters"
          fill
          scroll="text"
          meta={preview ? `${preview.adapters.filter((item) => item.status === "current").length}/${preview.adapters.length}` : undefined}
          actions={
            preview && (
              <button
                className="ds-btn ds-btn-sm"
                type="button"
                data-run="configuration-adapters"
                disabled={preview.blocked || facts.transaction_pending}
                onClick={() => onRun("configuration-adapters", { request: JSON.stringify({ fingerprint: preview.fingerprint }) }, preview.text)}
              >
                <Icon name="refresh" className="ds-ic-sm" /> {t("Обновить адаптеры")}
              </button>
            )
          }
        >
          {preview === null ? (
            <p className="ds-alert ds-alert-err">{t(facts.adapters.error)}</p>
          ) : (
            <>
              <div className="ds-rows">
                {preview.adapters.map((item) => {
                  const [symbol, word] = ADAPTER_STATUS[item.status] ?? ["·", item.status];
                  return (
                    <div className="ds-row" key={item.path} data-adapter={item.path}>
                      <Icon name="harness" className="ds-ic-sm" />
                      <span className="ds-row-main">
                        <b className="ds-row-title">{adapterName(item.path)}</b>
                        <small className="ds-row-sub">{item.path}</small>
                        {item.problem && <small className="ds-row-sub" data-tone="warn">{`⚠ ${item.problem}`}</small>}
                      </span>
                      <span className="ds-tag" data-tone={item.status === "current" ? "ok" : item.status === "outdated" ? "warn" : undefined}>{`${symbol} ${t(word)}`}</span>
                    </div>
                  );
                })}
              </div>
              <pre className="ds-code" tabIndex={0} role="region" aria-label={t("Команда")}>{preview.text}</pre>
              <p className="ds-note">{preview.blocked ? t(preview.reason) : t("Установка и обновление требуют просмотра и подтверждения. Консоль не включает force и не меняет transport.")}</p>
            </>
          )}
        </Panel>
      </div>
    </div>
  );
}

function JsonTab({ facts, draft }: { facts: ConfigurationFacts; draft: ConfigurationDraft }) {
  const { t } = useI18n();
  const [file, setFile] = useState<ConfigName>("project.json");
  const block = writeBlock(facts) ?? (facts.files[file].error || null);
  const error = draft.error(file);
  return (
    <div className="ds-settings-json">
      <TabList id="settings-file" label={t("Файл")} className="ds-toolbar ds-settings-files" tabs={CONFIG_NAMES.map((name) => [name, name] as const)} value={file} onChange={(name) => setFile(name as ConfigName)} />
      <TabPanels id="settings-file" tabs={CONFIG_NAMES.map((name) => [name, name] as const)} value={file} className="ds-tabpanel">
        <Panel
          title={`${t("Редактор")} · ${file}`}
          id={`configuration-editor-${file.split(".")[0]}`}
          className="ds-settings-editor"
          meta={`${SCHEMAS[file]} · sha256 ${shortDigest(facts.files[file].digest)}`}
          fill
          scroll="text"
        >
          <textarea
            className="ds-input ds-settings-text"
            aria-label={file}
            spellCheck={false}
            value={draft.text(file)}
            disabled={block !== null}
            onChange={(event) => draft.setText(file, event.target.value)}
          />
          {error && (
            <p className="ds-alert ds-alert-err" role="alert">
              {t(error)}
            </p>
          )}
        </Panel>
      </TabPanels>
    </div>
  );
}

function ChangesTab({ facts, draft, onRun }: { facts: ConfigurationFacts; draft: ConfigurationDraft; onRun: Run }) {
  const { t } = useI18n();
  const [description, setDescription] = useState("");
  const changes = draft.changes;
  const reason = writeBlock(facts) ?? draft.problem ?? (changes.length === 0 ? "Изменений нет" : null);
  const digests = Object.fromEntries(CONFIG_NAMES.map((name) => [name, facts.files[name].digest]));
  const request = () => draftRequest(changes, digests, description.trim());
  const summary = changes.map((change) => `${"remove" in change ? "−" : "±"} ${change.file}: ${change.path.join(".")}`).join("\n");
  return (
    <Panel
      title={t("Изменения черновика")}
      id="configuration-changes"
      count={changes.length}
      fill
      scroll="list"
      actions={
        <>
          <button className="ds-btn ds-btn-sm" type="button" data-run="configuration-save-draft" disabled={reason !== null} onClick={() => onRun("configuration-save-draft", { request: request() }, summary)}>
            <Icon name="download" className="ds-ic-sm" /> {t("Сохранить черновик как версию")}
          </button>
          <button className="ds-btn ds-btn-sm ds-btn-primary" type="button" data-run="configuration-apply" disabled={reason !== null} onClick={() => onRun("configuration-apply", { request: request() }, summary)}>
            <Icon name="check" className="ds-ic-sm" /> {t("Применить")}
          </button>
        </>
      }
    >
      <ul className="ds-rows ds-settings-changes">
        {changes.length === 0 && <li className="ds-row ds-wz-muted">{t("Изменений нет")}</li>}
        {changes.map((change) => (
          <li className="ds-row" key={`${change.file}:${change.path.join(".")}`}>
            <code>{`${change.file} → ${change.path.join(".")}`}</code> {"remove" in change ? t("удалить") : <code>{JSON.stringify(change.value)}</code>}
          </li>
        ))}
      </ul>
      <label className="ds-settings-desc">
        {t("Описание версии")}
        <input className="ds-input" value={description} onChange={(event) => setDescription(event.target.value)} />
      </label>
      {reason && reason !== "Изменений нет" && <p className="ds-alert ds-alert-err" role="alert">{t(reason)}</p>}
      <p className="ds-note">{t("Запись идёт через транзакцию: проверка устаревания, резервная копия, подтверждение.")}</p>
    </Panel>
  );
}

/** The JSON of one saved version, read with its own configuration.snapshot request. */
function VersionView({ id }: { id: string }) {
  const { t } = useI18n();
  const screen = useScreen({ type: "configuration.snapshot", params: { version: id } }, parseConfiguration);
  const version = screen.data?.version;
  if (screen.error) {
    return (
      <p className="ds-alert ds-alert-err" role="alert" data-code={screen.error.code}>
        {t("Данные не получены")}: {screen.error.message || screen.error.code}
      </p>
    );
  }
  if (!version) return <p className="ds-empty">{t("Читаю версию…")}</p>;
  if (version.error) {
    return (
      <p className="ds-alert ds-alert-err" role="alert" id="configuration-version-error">
        {version.error}
      </p>
    );
  }
  return (
    <div id="configuration-version-json">
      {CONFIG_NAMES.map((name) => {
        const file = version.files[name];
        return (
          <section key={name} data-file={name}>
            <h3 className="ds-settings-vfile">{`${name} · sha256 ${shortDigest(file?.digest ?? "")}`}</h3>
            {file?.exists ? <pre className="ds-code" tabIndex={0} role="region" aria-label={name}>{pretty(file.document)}</pre> : <p className="ds-note">{t("Файла нет в этой версии")}</p>}
          </section>
        );
      })}
    </div>
  );
}

function History({ facts, onRun }: { facts: ConfigurationFacts; onRun: Run }) {
  const { t } = useI18n();
  const versions = facts.versions ?? [];
  const [selected, setSelected] = useState<string | null>(null);
  const [description, setDescription] = useState("");
  const chosen = selected ?? versions[0]?.id ?? null;
  return (
    <div className="ds-settings-cols" id="configuration-history">
      <div className="ds-settings-col">
        <Panel title={t("Версии")} id="configuration-versions" count={versions.length} meta={facts.store_root} fill scroll="list">
          {versions.length === 0 ? (
            <p className="ds-note">{t("Сохранённых версий нет.")}</p>
          ) : (
            <div className="ds-rows">
              {versions.map((version) => (
                <button
                  type="button"
                  className="ds-row ds-row-button"
                  key={version.id}
                  data-version={version.id}
                  aria-pressed={version.id === chosen}
                  onClick={() => setSelected(version.id)}
                >
                  <span className="ds-row-main">
                    <b className="ds-row-title">{version.created_at}</b>
                    <small className="ds-row-sub">{[version.description, version.files.join(", "), version.package_version].filter(Boolean).join(" · ")}</small>
                    {version.problem && <small className="ds-row-sub" data-tone="err">{version.problem}</small>}
                  </span>
                  <code className="ds-row-end">{version.id}</code>
                </button>
              ))}
            </div>
          )}
          <label className="ds-settings-desc">
            {t("Описание версии")}
            <input className="ds-input" value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <button
            className="ds-btn ds-btn-sm"
            type="button"
            data-run="configuration-save-current"
            disabled={facts.transaction_pending}
            onClick={() => onRun("configuration-save-current", { request: JSON.stringify({ description: description.trim() }) }, "")}
          >
            {t("Сохранить текущую конфигурацию как версию")}
          </button>
          <p className="ds-note">{t("Восстановление версии доступно в TUI.")}</p>
        </Panel>
      </div>
      <div className="ds-settings-col">
        <Panel title={chosen ? `${t("Содержимое версии")} · ${chosen}` : t("Содержимое версии")} id="configuration-version" fill scroll="text">
          {chosen ? <VersionView key={chosen} id={chosen} /> : <p className="ds-note">{t("Выберите версию в списке.")}</p>}
        </Panel>
      </div>
    </div>
  );
}

function Settings({ facts, store, run }: { facts: ConfigurationFacts; store: StoreFacts | null; run: Run }) {
  const { t, section } = useI18n();
  const [tab, setTab] = useState<Tab>("overview");
  const draft = useConfigurationDraft(facts);
  return (
    <>
      <PipeTabs
        id="settings"
        label={section("Configuration")}
        tabs={TABS.map(([key, label]) => ({ id: key, label: t(label), badge: key === "changes" && draft.changes.length > 0 ? draft.changes.length : undefined }))}
        value={tab}
        onChange={(key) => setTab(key as Tab)}
      />
      <TabPanels id="settings" tabs={TABS} value={tab} className="ds-tabpanel">
        {tab === "overview" && <Overview facts={facts} store={store} onRun={run} />}
        {tab === "parameters" && (
          <Panel title={t("Параметры")} id="configuration-parameters" fill scroll="text">
            <Wizard facts={facts} draft={draft} />
          </Panel>
        )}
        {tab === "json" && <JsonTab facts={facts} draft={draft} />}
        {tab === "changes" && <ChangesTab facts={facts} draft={draft} onRun={run} />}
        {tab === "history" && <History facts={facts} onRun={run} />}
      </TabPanels>
    </>
  );
}

export function Configuration() {
  const { t, language } = useI18n();
  const screen = useScreen({ type: "configuration.snapshot" }, parseConfiguration);
  const facts = screen.data;
  const [request, setRequest] = useState<RunRequest | null>(null);

  const run: Run = (command, values, reason) => setRequest({ command_id: command, values, nonce: Date.now(), reason: reason || undefined });
  // The draft is keyed by the digests it was read at: a written file starts afresh.
  const onJobDone = () => screen.refresh(true);
  const { snapshot } = useConsole();
  const store = snapshot?.store ?? null;
  const exportConfigs = () => {
    if (!facts) return;
    const body = Object.fromEntries(CONFIG_NAMES.map((name) => [name, facts.files[name].document]));
    downloadJson("harness-config.json", body);
  };
  const configs = facts ? CONFIG_NAMES.filter((name) => facts.files[name].exists).length : 0;

  return (
    <div className="ds-page ds-fit ds-settings" data-section="Configuration">
      <PageHeader
        title={t("Настройки")}
        subtitle={t("Настройка project.json и orchestration.json: черновик, различия и подтверждённая запись с резервной копией.")}
        actions={
          <>
            <button id="configuration-refresh" className="ds-btn" type="button" onClick={() => screen.refresh(true)}>
              <Icon name="refresh" className="ds-ic-sm" /> {t("Проверить")}
            </button>
            <button className="ds-btn" type="button" disabled={!facts} onClick={exportConfigs}>
              <Icon name="download" className="ds-ic-sm" /> {t("Экспорт")}
            </button>
            <a className="ds-btn" href="#/diagnostics">
              <Icon name="pulse" className="ds-ic-sm" /> {t("Диагностика")}
            </a>
          </>
        }
      />

      <ScreenState screen={screen} noun="Настройки не получены" />

      {facts && (
        <>
          <Summary
            id="configuration-kpi"
            label={t("Сводка настроек")}
            stats={[
              ...CONFIG_NAMES.map((name) => {
                const [word, tone] = fileState(facts, name);
                return { label: name, value: <span data-tone={tone}>{t(word)}</span>, caption: facts.schema_installed ? SCHEMAS[name] : t("схема не установлена") };
              }),
              { label: t("Версии"), value: facts.versions?.length ?? <NoData why={t("Сервер не прислал список версий")} />, caption: ".harness/config_versions" },
              { label: "Runtime store", value: store?.schema != null ? `schema ${store.schema}` : <NoData why={t(store ? store.reason || STORE_WHY : STORE_WHY)} />, caption: store?.authority ?? "—" },
            ]}
            facts={
              <>
                {snapshot?.project && <span>{snapshot.project.name}</span>}
                {snapshot?.project?.branch && <span>{snapshot.project.branch}</span>}
                <span>{t("{count} config", { count: configs })}</span>
                <span>Hook policy <NoData why={t(HOOK_POLICY_WHY)} /></span>
              </>
            }
            snapshot={
              <span id="configuration-cache" title={`${screen.cached ? t("Кэш") : t("Новый снимок")} · ${screen.ageSeconds ?? 0} s`}>
                <Icon name="clock" className="ds-ic-sm" /> {snapshotClock(screen.ageSeconds, language)}
              </span>
            }
          />
          {facts.transaction_pending && (
            <div className="ds-alert ds-alert-warn" role="alert" id="configuration-pending">
              <span>{t(PENDING)}</span>
              <button className="ds-btn ds-btn-sm" type="button" data-run="configuration-recover" onClick={() => run("configuration-recover", {}, "")}>
                {t("Восстановить незавершённую запись")}
              </button>
            </div>
          )}
          {!facts.schema_installed && <p className="ds-alert ds-alert-err">{t(NO_SCHEMA)}</p>}
          <Settings facts={facts} store={store} run={run} />
        </>
      )}

      <CommandPanel section="configuration" confirmAll listed={false} request={request} onJobDone={onJobDone} />
    </div>
  );
}
