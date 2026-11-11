/* Configuration (#/configuration): the facts of configuration.snapshot — both configuration files
   with their digests and masked documents, the schema and orchestration installation, a pending
   write and the runtime adapter plan. Each file is edited as JSON; its leaf change set and the
   digests of the changed files go to the server, which replays them on the current files. Every
   write (draft version, apply, adapters, current version, recovery) runs only through the
   CommandPanel of the job section `configuration`, and every run opens the confirmation first.
   The Settings tab is the mockup wizard over the kernel parameter catalog; its answers take the
   same confirmed draft path. The version list and restore read local files the snapshot does not
   carry; the page says they are in the TUI. */
import { useState } from "react";
import { CommandPanel } from "../commands/CommandPanel";
import type { RunRequest } from "../commands/CommandPanel";
import { MASK_REFUSAL, draftRequest, holdsMask, leafChanges } from "../configuration/changes";
import type { Change } from "../configuration/changes";
import { ADAPTER_STATUS, adapterName, shortDigest, writeBlock } from "../configuration/format";
import { Wizard, currentValue, shown } from "../configuration/Wizard";
import { useI18n } from "../i18n";
import { TabList, TabPanels } from "../views/Tabs";
import { Icon } from "../icons";
import { useScreen } from "../screens/useScreen";
import { NoData } from "../steps/ActivityViews";
import { snapshotClock } from "../update/format";
import { useConsole } from "../useConsole";
import type { StoreFacts } from "../ws/types";
import { CONFIG_NAMES, parseConfiguration } from "../ws/projectScreens";
import type { ConfigName, ConfigurationFacts, JsonObject } from "../ws/projectScreens";

type Tab = "overview" | "wizard" | ConfigName | "history";
const TABS: readonly (readonly [Tab, string])[] = [
  ["overview", "Обзор"],
  ["wizard", "Настройки"],
  ["project.json", "project.json"],
  ["orchestration.json", "orchestration.json"],
  ["history", "История"],
];

const pretty = (document: JsonObject) => JSON.stringify(document, null, 2);

const SCHEMAS: Readonly<Record<ConfigName, string>> = {
  "project.json": "project.schema.json",
  "orchestration.json": "orchestration.schema.json",
};
const HOOK_POLICY_WHY = "Снимок configuration.snapshot не читает hook policy";
const STORE_WHY = "Снимок Главной ещё не получен";

/** A file's state word and pill tone: valid, missing (the default document is shown) or error. */
function fileState(facts: ConfigurationFacts, name: ConfigName): readonly [string, string] {
  const file = facts.files[name];
  if (file.error) return ["ошибка", "red"];
  return file.exists ? ["valid", "mint"] : ["нет файла", "amber"];
}

/** The edited document of a file: its changes, or why none can be sent. */
function draftOf(facts: ConfigurationFacts, name: ConfigName, text: string): { changes: Change[]; error: string | null } {
  let edited: unknown;
  try {
    edited = JSON.parse(text);
  } catch (error) {
    return { changes: [], error: `JSON: ${(error as Error).message}` };
  }
  if (edited === null || typeof edited !== "object" || Array.isArray(edited)) return { changes: [], error: "Файл должен быть JSON-объектом" };
  const changes = leafChanges(facts.files[name].document, edited as JsonObject, name);
  const masked = changes.some((change) => "value" in change && holdsMask(change.value));
  return { changes, error: masked ? MASK_REFUSAL : null };
}

function FileEditor({
  facts,
  name,
  text,
  onText,
  onRun,
}: {
  facts: ConfigurationFacts;
  name: ConfigName;
  text: string;
  onText: (text: string) => void;
  onRun: (command: string, values: Record<string, string>, reason: string) => void;
}) {
  const { t } = useI18n();
  const [description, setDescription] = useState("");
  const file = facts.files[name];
  const { changes, error } = draftOf(facts, name, text);
  const block = writeBlock(facts) ?? (file.error ? file.error : null);
  const reason = block ?? error ?? (changes.length === 0 ? "Изменений нет" : null);
  const request = () => draftRequest(changes, { [name]: file.digest }, description.trim());
  const summary = changes.map((change) => `${"remove" in change ? "−" : "±"} ${name}: ${change.path.join(".")}`).join("\n");
  return (
    <div className="settings-editor-grid" id={`configuration-editor-${name.split(".")[0]}`}>
      <section className="panel settings-editor">
        <div className="panel-head">
          <h2>{`${t("Редактор")} · ${name}`}</h2>
          <span className={`orch-pill ${fileState(facts, name)[1]}`}>{t(fileState(facts, name)[0])}</span>
        </div>
        <div className="settings-editor-body">
          <div className="settings-file-line">
            <code>{`.harness/${name}`}</code>
            <span>{SCHEMAS[name]}</span>
          </div>
          <label className="field">
            JSON
            <textarea
              className="settings-textarea"
              aria-label={name}
              spellCheck={false}
              value={text}
              disabled={block !== null}
              onChange={(event) => onText(event.target.value)}
            />
          </label>
          {error && (
            <p className="command-refusal err" role="alert">
              {t(error)}
            </p>
          )}
        </div>
      </section>
      <aside className="panel settings-editor-side">
        <div className="panel-head">
          <h2>Schema</h2>
          <span className="small muted">{t("проверка на сервере")}</span>
        </div>
        <div className="settings-side-body">
          <div className="settings-side-row">
            <span>{t("Файл")}</span>
            <b>{name}</b>
          </div>
          <div className="settings-side-row">
            <span>{t("Схема")}</span>
            <b>{facts.schema_installed ? SCHEMAS[name] : t("не установлена")}</b>
          </div>
          <div className="settings-side-row">
            <span>sha256</span>
            <b>{shortDigest(file.digest)}</b>
          </div>
          <div className="settings-side-row">
            <span>{t("Различия")}</span>
            <b>{changes.length}</b>
          </div>
          <ul className="settings-config-list configuration-changes">
            {changes.length === 0 && <li className="muted">{t("Изменений нет")}</li>}
            {changes.map((change) => (
              <li key={change.path.join(".")}>
                <code>{change.path.join(".")}</code> {"remove" in change ? t("удалить") : <code>{JSON.stringify(change.value)}</code>}
              </li>
            ))}
          </ul>
          <label className="field">
            {t("Описание версии")}
            <input className="settings-input" value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <div className="settings-editor-actions">
            <button
              className="btn"
              type="button"
              data-run="configuration-save-draft"
              disabled={reason !== null}
              onClick={() => onRun("configuration-save-draft", { request: request() }, summary)}
            >
              <Icon name="download" /> {t("Сохранить черновик как версию")}
            </button>
            <button
              className="btn primary"
              type="button"
              data-run="configuration-apply"
              disabled={reason !== null}
              onClick={() => onRun("configuration-apply", { request: request() }, summary)}
            >
              <Icon name="check" /> {t("Применить")}
            </button>
          </div>
          {reason && reason !== "Изменений нет" && <p className="orch-note">{t(reason)}</p>}
          <p className="orch-note">{t("Запись идёт через транзакцию: проверка устаревания, резервная копия, подтверждение.")}</p>
        </div>
      </aside>
    </div>
  );
}

function Overview({
  facts,
  store,
  onRun,
}: {
  facts: ConfigurationFacts;
  store: StoreFacts | null;
  onRun: (command: string, values: Record<string, string>, reason: string) => void;
}) {
  const { t } = useI18n();
  const preview = facts.adapters.preview;
  const params = facts.wizard ?? [];
  const resolved = (param: (typeof params)[number]) => {
    const value = currentValue(facts, param);
    const found = value === undefined ? param.default : value;
    return found === null || found === undefined ? t("не задано") : shown(found);
  };
  const numeric = params.filter((param) => param.type === "integer" || param.type === "number");
  const other = params.filter((param) => !numeric.includes(param));
  return (
    <>
      <div className="settings-grid" id="configuration-overview">
        <section className="panel settings-configs" id="configuration-files">
          <div className="panel-head">
            <h2>{t("Конфигурация")}</h2>
            <span className="orch-pill mint">{t("{count} config", { count: CONFIG_NAMES.filter((name) => facts.files[name].exists).length })}</span>
          </div>
          <div className="settings-config-list">
            {CONFIG_NAMES.map((name) => {
              const file = facts.files[name];
              const [word, tone] = fileState(facts, name);
              return (
                <div className="settings-config-row" key={name} data-file={name}>
                  <span><Icon name="settings" /></span>
                  <div>
                    <b>{name}</b>
                    <small>{`.harness/${name} · ${SCHEMAS[name]} · sha256 ${shortDigest(file.digest)}`}</small>
                    {!file.exists && <small>{t("нет — показан документ по умолчанию")}</small>}
                    {file.error && <small className="err">{file.error}</small>}
                  </div>
                  <em className={`orch-pill ${tone}`}>{t(word)}</em>
                </div>
              );
            })}
            <div className="settings-config-row" data-file="hook-policy.json">
              <span><Icon name="settings" /></span>
              <div>
                <b>hook-policy.json</b>
                <small>.harness/hook-policy.json</small>
              </div>
              <em className="orch-pill"><NoData why={t(HOOK_POLICY_WHY)} /></em>
            </div>
            <div className="settings-config-row" data-file="runtime-store">
              <span><Icon name="harness" /></span>
              <div>
                <b>runtime-store</b>
                <small>{store ? [store.authority, store.generation].filter(Boolean).join(" · ") : t("нет данных")}</small>
              </div>
              <em className="orch-pill cyan">{store?.schema != null ? `schema ${store.schema}` : <NoData why={t(store ? store.reason || STORE_WHY : STORE_WHY)} />}</em>
            </div>
          </div>
          <div className="settings-config-foot">
            <span>{facts.transaction_pending ? t("Есть незавершённая запись: сначала восстановите её.") : t("Незавершённой записи нет.")}</span>
            <a className="btn" href="#/harness"><Icon name="harness" /> Harness</a>
          </div>
        </section>
        <section className="panel settings-policy" id="configuration-policy">
          <div className="panel-head">
            <h2>{t("Политики")}</h2>
            <span className="small muted">resolved values</span>
          </div>
          {params.length === 0 ? (
            <p className="orch-note"><NoData why={t("Сервер не прислал каталог параметров")} /></p>
          ) : (
            <>
              <div className="settings-resolved">
                {other.map((param) => (
                  <div key={`${param.file}:${param.path.join(".")}`}>
                    <span>{param.label}</span>
                    <b>{resolved(param)}</b>
                  </div>
                ))}
              </div>
              <div className="settings-policy-chips">
                {numeric.map((param) => (
                  <span className="orch-pill blue" key={`${param.file}:${param.path.join(".")}`}>{`${param.label} ${resolved(param)}`}</span>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
      <section className="panel settings-note">
        <div className="settings-note-body">
          <Icon name="shield" />
          <div>
            <b>{t("Запись только с подтверждением")}</b>
            <p>{t("Изменения уходят на сервер командой configuration: проверка устаревания, резервная копия и подтверждение человека.")}</p>
          </div>
          <a className="btn" href="#/diagnostics"><Icon name="pulse" /> {t("Проверить в Диагностике")}</a>
        </div>
      </section>
      <section className="panel settings-configs" id="configuration-adapters">
        <div className="panel-head">
          <h2>{t("Адаптеры runtime")}</h2>
          {preview && (
            <span className="small muted">
              {`${preview.adapters.filter((item) => item.status === "current").length}/${preview.adapters.length}`}
            </span>
          )}
        </div>
        {preview === null ? (
          <p className="command-refusal err">{t(facts.adapters.error)}</p>
        ) : (
          <>
            <div className="settings-config-list">
              {preview.adapters.map((item) => {
                const [symbol, word] = ADAPTER_STATUS[item.status] ?? ["·", item.status];
                return (
                  <div className="settings-config-row" key={item.path} data-adapter={item.path}>
                    <span><Icon name="harness" /></span>
                    <div>
                      <b>{adapterName(item.path)}</b>
                      <small>{item.path}</small>
                      {item.problem && <small className="warn">{`⚠ ${item.problem}`}</small>}
                    </div>
                    <em className={`orch-pill ${item.status === "current" ? "mint" : item.status === "outdated" ? "amber" : ""}`}>{`${symbol} ${t(word)}`}</em>
                  </div>
                );
              })}
            </div>
            <pre className="command-output-text settings-adapter-plan">{preview.text}</pre>
            <div className="settings-config-foot">
              <span>{preview.blocked ? t(preview.reason) : t("Установка и обновление требуют просмотра и подтверждения. Консоль не включает force и не меняет transport.")}</span>
              <button
                className="btn"
                type="button"
                data-run="configuration-adapters"
                disabled={preview.blocked || facts.transaction_pending}
                onClick={() => onRun("configuration-adapters", { request: JSON.stringify({ fingerprint: preview.fingerprint }) }, preview.text)}
              >
                <Icon name="refresh" /> {t("Обновить адаптеры")}
              </button>
            </div>
          </>
        )}
      </section>
    </>
  );
}

export function Configuration() {
  const { t, section, tab: tabLabel, language } = useI18n();
  const screen = useScreen({ type: "configuration.snapshot" }, parseConfiguration);
  const facts = screen.data;
  const [tab, setTab] = useState<Tab>("overview");
  // The edited text of a file, keyed by the digest it was read at: a new snapshot starts afresh.
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [description, setDescription] = useState("");
  const [request, setRequest] = useState<RunRequest | null>(null);

  const run = (command: string, values: Record<string, string>, reason: string) =>
    setRequest({ command_id: command, values, nonce: Date.now(), reason: reason || undefined });
  const textKey = (name: ConfigName) => `${name}:${facts?.files[name].digest ?? ""}`;
  const onJobDone = () => {
    setTexts({});
    screen.refresh(true);
  };
  const { snapshot } = useConsole();
  const store = snapshot?.store ?? null;
  const exportConfigs = () => {
    if (!facts) return;
    const body = Object.fromEntries(CONFIG_NAMES.map((name) => [name, facts.files[name].document]));
    const url = URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "harness-config.json";
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="settings-page work-page" data-section="Configuration">
      <div className="page-title settings-title">
        <div>
          <h1>{t("Настройки")}</h1>
          <p>{t("Настройка project.json и orchestration.json: черновик, различия и подтверждённая запись с резервной копией.")}</p>
          {facts && (
            <div className="home-facts" title={`${screen.cached ? t("Кэш") : t("Новый снимок")} · ${screen.ageSeconds ?? 0} s`}>
              {snapshot?.project && <span>{snapshot.project.name}</span>}
              {snapshot?.project?.branch && <span>{snapshot.project.branch}</span>}
              <span>{t("{count} config", { count: CONFIG_NAMES.filter((name) => facts.files[name].exists).length })}</span>
              {store?.schema != null && <span>schema {store.schema}</span>}
              <span id="configuration-cache">{snapshotClock(screen.ageSeconds, language)}</span>
            </div>
          )}
        </div>
        <div className="actions">
          <button id="configuration-refresh" className="btn" type="button" onClick={() => screen.refresh(true)}>
            <Icon name="refresh" /> {t("Проверить")}
          </button>
          <button className="btn" type="button" disabled={!facts} onClick={exportConfigs}>
            <Icon name="download" /> {t("Экспорт")}
          </button>
          <a className="btn" href="#/diagnostics">
            <Icon name="pulse" /> {t("Диагностика")}
          </a>
        </div>
      </div>

      {screen.error && !facts && (
        <p className="command-refusal err" role="alert" data-code={screen.error.code}>
          {t("Данные не получены")}: {screen.error.message || screen.error.code}
        </p>
      )}

      {facts && (
        <div className="settings-kpis" id="configuration-kpi">
          {CONFIG_NAMES.map((name) => {
            const [word, tone] = fileState(facts, name);
            return (
              <div key={name} data-tone={tone === "mint" ? undefined : "warning"}>
                <span>{name}</span>
                <b className={tone}>{t(word)}</b>
                <small>{facts.schema_installed ? SCHEMAS[name] : t("схема не установлена")}</small>
              </div>
            );
          })}
          <div>
            <span>Hook policy</span>
            <b><NoData why={t(HOOK_POLICY_WHY)} /></b>
            <small>hook-policy.json</small>
          </div>
          <div>
            <span>Runtime store</span>
            <b className="cyan">{store?.schema != null ? `schema ${store.schema}` : <NoData why={t(store ? store.reason || STORE_WHY : STORE_WHY)} />}</b>
            <small>{store?.authority ?? "—"}</small>
          </div>
        </div>
      )}

      {facts?.transaction_pending && (
        <div className="panel update-banner" role="alert" id="configuration-pending">
          <span>{t("Незавершённая запись конфигурации: сначала восстановите её")}</span>
          <button className="btn" type="button" data-run="configuration-recover" onClick={() => run("configuration-recover", {}, "")}>
            {t("Восстановить незавершённую запись")}
          </button>
        </div>
      )}

      {facts && !facts.schema_installed && <p className="command-refusal err">{t("Сначала установите engineering-suite или backend-orchestration через меню подключения проекта")}</p>}

      {facts && (
        <>
          <TabList
            id="settings"
            label={section("Configuration")}
            className="orch-tabbar settings-tabbar"
            tabs={TABS.map(([key, label]) => [key, key === "overview" || key === "history" ? tabLabel(label) : key === "wizard" ? t(label) : label] as const)}
            value={tab}
            onChange={(key) => setTab(key as Tab)}
          />
          <TabPanels id="settings" tabs={TABS} value={tab}>
          {tab === "overview" && <Overview facts={facts} store={store} onRun={run} />}
          {tab === "wizard" && <Wizard facts={facts} onRun={run} />}
          {(tab === "project.json" || tab === "orchestration.json") && (
            <FileEditor
              key={textKey(tab)}
              facts={facts}
              name={tab}
              text={texts[textKey(tab)] ?? pretty(facts.files[tab].document)}
              onText={(text) => setTexts({ ...texts, [textKey(tab)]: text })}
              onRun={run}
            />
          )}
          {tab === "history" && (
            <section className="panel settings-history" id="configuration-history">
              <div className="panel-head">
                <h2>{t("История")}</h2>
                <span className="small muted">{t("Хранилище версий")}</span>
              </div>
              <code>{facts.store_root}</code>
              <label className="field">
                {t("Описание версии")}
                <input className="settings-input" value={description} onChange={(event) => setDescription(event.target.value)} />
              </label>
              <div className="settings-history-foot">
                <button
                  className="btn"
                  type="button"
                  data-run="configuration-save-current"
                  disabled={facts.transaction_pending}
                  onClick={() => run("configuration-save-current", { request: JSON.stringify({ description: description.trim() }) }, "")}
                >
                  {t("Сохранить текущую конфигурацию как версию")}
                </button>
              </div>
              <p className="settings-note muted">{t("Список версий и восстановление доступны в TUI.")}</p>
            </section>
          )}
          </TabPanels>
        </>
      )}

      <CommandPanel section="configuration" confirmAll listed={false} request={request} onJobDone={onJobDone} />
    </div>
  );
}
