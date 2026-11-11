/* Configuration (#/configuration): the facts of configuration.snapshot — both configuration files
   with their digests and masked documents, the schema and orchestration installation, a pending
   write and the runtime adapter plan. Each file is edited as JSON; its leaf change set and the
   digests of the changed files go to the server, which replays them on the current files. Every
   write (draft version, apply, adapters, current version, recovery) runs only through the
   CommandPanel of the job section `configuration`, and every run opens the confirmation first.
   The TUI's guided wizard, version list and restore read local files the snapshot does not
   carry; the page says they are in the TUI. */
import { useState } from "react";
import { CommandPanel } from "../commands/CommandPanel";
import type { RunRequest } from "../commands/CommandPanel";
import { MASK_REFUSAL, draftRequest, holdsMask, leafChanges } from "../configuration/changes";
import type { Change } from "../configuration/changes";
import { ADAPTER_STATUS, adapterName, shortDigest, writeBlock } from "../configuration/format";
import { useI18n } from "../i18n";
import { Icon } from "../icons";
import { useScreen } from "../screens/useScreen";
import { CONFIG_NAMES, parseConfiguration } from "../ws/projectScreens";
import type { ConfigName, ConfigurationFacts, JsonObject } from "../ws/projectScreens";

type Tab = "overview" | ConfigName | "history";
const TABS: readonly (readonly [Tab, string])[] = [
  ["overview", "Обзор"],
  ["project.json", "project.json"],
  ["orchestration.json", "orchestration.json"],
  ["history", "История"],
];

const pretty = (document: JsonObject) => JSON.stringify(document, null, 2);

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
    <div className="settings-editor" id={`configuration-editor-${name.split(".")[0]}`}>
      <div className="settings-editor-grid">
        <div className="settings-editor-body">
          <textarea
            className="settings-textarea"
            aria-label={name}
            spellCheck={false}
            value={text}
            disabled={block !== null}
            onChange={(event) => onText(event.target.value)}
          />
          {error && (
            <p className="command-refusal err" role="alert">
              {t(error)}
            </p>
          )}
        </div>
        <div className="settings-editor-side">
          <div className="panel-head">
            <h3>{t("Различия")}</h3>
            <span className="small muted">{changes.length}</span>
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
              {t("Сохранить черновик как версию")}
            </button>
            <button
              className="btn primary"
              type="button"
              data-run="configuration-apply"
              disabled={reason !== null}
              onClick={() => onRun("configuration-apply", { request: request() }, summary)}
            >
              {t("Применить")}
            </button>
          </div>
          {reason && <p className="settings-note muted">{t(reason)}</p>}
          <p className="settings-note muted">{t("Запись идёт через транзакцию: проверка устаревания, резервная копия, подтверждение.")}</p>
        </div>
      </div>
    </div>
  );
}

function Overview({ facts, onRun }: { facts: ConfigurationFacts; onRun: (command: string, values: Record<string, string>, reason: string) => void }) {
  const { t } = useI18n();
  const preview = facts.adapters.preview;
  return (
    <div className="settings-grid" id="configuration-overview">
      <section className="panel settings-configs">
        <div className="panel-head">
          <h2>{t("Файлы конфигурации")}</h2>
        </div>
        <div className="settings-config-list">
          {CONFIG_NAMES.map((name) => {
            const file = facts.files[name];
            return (
              <div className="settings-config-row" key={name} data-file={name}>
                <code>{name}</code>
                <span>{file.exists ? t("есть") : t("нет — показан документ по умолчанию")}</span>
                <span className="muted">sha256 {shortDigest(file.digest)}</span>
                {file.error && <span className="err">✖ {file.error}</span>}
              </div>
            );
          })}
        </div>
      </section>
      <section className="panel settings-configs" id="configuration-adapters">
        <div className="panel-head">
          <h2>{t("Адаптеры runtime")}</h2>
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
                    <b>{adapterName(item.path)}</b>
                    <span>{`${symbol} ${t(word)}`}</span>
                    <code>{item.path}</code>
                    {item.problem && <span className="warn">{`⚠ ${item.problem}`}</span>}
                  </div>
                );
              })}
            </div>
            <pre className="settings-resolved">{preview.text}</pre>
            <p className="settings-note muted">{t("Установка и обновление требуют просмотра и подтверждения. Консоль не включает force и не меняет transport.")}</p>
            <div className="settings-config-foot">
              <button
                className="btn"
                type="button"
                data-run="configuration-adapters"
                disabled={preview.blocked || facts.transaction_pending}
                onClick={() => onRun("configuration-adapters", { request: JSON.stringify({ fingerprint: preview.fingerprint }) }, preview.text)}
              >
                {t("Обновить адаптеры")}
              </button>
              {preview.blocked && <span className="warn">{t(preview.reason)}</span>}
            </div>
          </>
        )}
      </section>
    </div>
  );
}

export function Configuration() {
  const { t, section, tab: tabLabel } = useI18n();
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
  const valid = (name: ConfigName) => (facts ? facts.files[name].error === "" : false);
  const adapters = facts?.adapters.preview?.adapters ?? [];
  const outdated = adapters.filter((item) => item.status !== "current").length;

  return (
    <div className="settings-page work-page" data-section="Configuration">
      <div className="page-title settings-title">
        <div>
          <h1>{section("Configuration")}</h1>
          <p>{t("Настройка project.json и orchestration.json: черновик, различия и подтверждённая запись с резервной копией.")}</p>
          {facts && (
            <div className="home-facts">
              <span id="configuration-cache">
                {screen.cached ? t("Кэш") : t("Новый снимок")} · {screen.ageSeconds ?? 0} s
              </span>
            </div>
          )}
        </div>
        <div className="actions">
          <button id="configuration-refresh" className="btn" type="button" onClick={() => screen.refresh(true)}>
            <Icon name="refresh" /> {t("Обновить")}
          </button>
        </div>
      </div>

      {screen.error && !facts && (
        <p className="command-refusal err" role="alert" data-code={screen.error.code}>
          {t("Данные не получены")}: {screen.error.message || screen.error.code}
        </p>
      )}

      {facts && (
        <div className="report-kpis settings-kpis" id="configuration-kpi">
          {CONFIG_NAMES.map((name) => (
            <div key={name} data-tone={valid(name) ? undefined : "warning"}>
              <span>{name}</span>
              <b>{valid(name) ? (facts.files[name].exists ? t("✔ валиден") : t("○ нет файла")) : t("✖ ошибка")}</b>
            </div>
          ))}
          <div data-tone={facts.schema_installed ? undefined : "warning"}>
            <span>{t("Схема")}</span>
            <b>{facts.schema_installed ? t("✔ установлена") : t("○ не установлена")}</b>
          </div>
          <div>
            <span>{t("Оркестрация")}</span>
            <b>{facts.orchestration_installed ? t("✔ установлена") : t("○ не установлена")}</b>
          </div>
          <div data-tone={facts.transaction_pending ? "warning" : undefined}>
            <span>{t("Незавершённая запись")}</span>
            <b>{facts.transaction_pending ? t("⚠ есть") : t("✔ нет")}</b>
          </div>
          <div data-tone={outdated ? "warning" : undefined}>
            <span>{t("Адаптеры runtime")}</span>
            <b>{facts.adapters.preview ? `${adapters.length - outdated}/${adapters.length}` : "—"}</b>
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
          <div className="settings-tabbar tabs" role="tablist">
            {TABS.map(([key, label]) => (
              <button key={key} type="button" role="tab" aria-selected={tab === key} className={tab === key ? "on" : ""} onClick={() => setTab(key)}>
                {key === "overview" || key === "history" ? tabLabel(label) : label}
              </button>
            ))}
          </div>
          {tab === "overview" && <Overview facts={facts} onRun={run} />}
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
              <div className="panel-head settings-history-head">
                <h2>{t("Хранилище версий")}</h2>
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
        </>
      )}

      <CommandPanel section="configuration" confirmAll listed={false} request={request} onJobDone={onJobDone} />
    </div>
  );
}
