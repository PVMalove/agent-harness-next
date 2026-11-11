/* The Settings tab of «Настройки»: the mockup wizard over the kernel parameter catalog
   (kernel/configuration_wizard.py). Each parameter is a real schema path with the schema's type,
   choices and default; the answers become one configuration draft that goes through the confirmed
   write path (configuration-save-draft / configuration-apply). The mockup's AI hints are not built:
   they would need a model call the console does not make. */
import { useState } from "react";
import { useI18n } from "../i18n";
import type { ConfigurationFacts, JsonObject, WizardParam } from "../ws/projectScreens";
import { draftRequest } from "./changes";
import type { Change } from "./changes";
import { writeBlock } from "./format";

const GROUPS: readonly (readonly [string, string])[] = [
  ["orchestrator", "Оркестратор"],
  ["project", "Проект"],
  ["qa", "QA"],
  ["dispatch", "Dispatch"],
  ["hooks", "Хуки"],
];

const keyOf = (param: WizardParam) => `${param.file}:${param.path.join(".")}`;
const nameOf = (param: WizardParam) => `${param.file} → ${param.path.join(".")}`;

/** The current value of a parameter in its served document, or undefined when absent. */
export function currentValue(facts: ConfigurationFacts, param: WizardParam): unknown {
  let value: unknown = facts.files[param.file].document;
  for (const key of param.path) {
    if (value === null || typeof value !== "object" || Array.isArray(value) || !Object.hasOwn(value, key)) return undefined;
    value = (value as JsonObject)[key];
  }
  return value;
}

export const shown = (value: unknown) => (value === undefined ? "—" : typeof value === "string" ? value : JSON.stringify(value));

function ValueField({ param, value, onChange }: { param: WizardParam; value: unknown; onChange: (value: unknown) => void }) {
  const { t } = useI18n();
  const label = t(param.label);
  if (param.type === "enum") {
    return (
      <select className="settings-input" aria-label={label} value={value === undefined ? "" : String(value)} onChange={(event) => onChange(param.choices.find((item) => String(item) === event.target.value))}>
        {value === undefined && <option value="">{t("не задано")}</option>}
        {param.choices.map((choice) => (
          <option key={String(choice)} value={String(choice)}>
            {String(choice)}
          </option>
        ))}
      </select>
    );
  }
  if (param.type === "boolean") {
    return (
      <label className="settings-toggle">
        <input type="checkbox" aria-label={label} checked={value === true} onChange={(event) => onChange(event.target.checked)} /> <span>{value === true ? t("да") : t("нет")}</span>
      </label>
    );
  }
  const numeric = param.type === "integer" || param.type === "number";
  return (
    <input
      className="settings-input"
      aria-label={label}
      type={numeric ? "number" : "text"}
      min={param.minimum ?? undefined}
      value={value === undefined ? "" : String(value)}
      onChange={(event) => {
        const text = event.target.value;
        if (!numeric) onChange(text);
        else if (text.trim() !== "" && Number.isFinite(Number(text))) onChange(param.type === "integer" ? Math.trunc(Number(text)) : Number(text));
      }}
    />
  );
}

export function Wizard({
  facts,
  onRun,
}: {
  facts: ConfigurationFacts;
  onRun: (command: string, values: Record<string, string>, reason: string) => void;
}) {
  const { t } = useI18n();
  const params = facts.wizard ?? null;
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [description, setDescription] = useState("");
  if (!params || params.length === 0) {
    return (
      <section className="panel settings-wizard-empty" id="configuration-wizard">
        <p className="harness-note">
          <span className="muted no-data">{t("нет данных")}</span> · {t("Каталог параметров не получен: схема конфигурации не установлена или сервер старее консоли.")}
        </p>
      </section>
    );
  }
  const param = params[Math.min(index, params.length - 1)]!;
  const group = GROUPS.findIndex(([id]) => id === param.group);
  const value = (item: WizardParam) => (keyOf(item) in answers ? answers[keyOf(item)] : currentValue(facts, item));
  const changes: Change[] = params
    .filter((item) => keyOf(item) in answers && JSON.stringify(answers[keyOf(item)]) !== JSON.stringify(currentValue(facts, item)))
    .map((item) => ({ file: item.file, path: item.path, value: answers[keyOf(item)] }));
  const digests = Object.fromEntries(Object.entries(facts.files).map(([name, file]) => [name, file.digest]));
  const block = writeBlock(facts);
  const reason = block ?? (changes.length === 0 ? "Изменений нет" : null);
  const summary = changes.map((change) => `± ${change.file}: ${change.path.join(".")}`).join("\n");
  const request = () => draftRequest(changes, digests, description.trim());
  const answered = params.filter((item) => value(item) !== undefined).length;
  const set = (next: unknown) => setAnswers({ ...answers, [keyOf(param)]: next });

  return (
    <div className="settings-wizard" id="configuration-wizard">
      <aside className="wizard-side">
        <div className="wizard-side-head">
          <span>{t("Группы")}</span>
          <b>{GROUPS.length}</b>
        </div>
        <div className="wizard-groups">
          {GROUPS.map(([id, label], position) => {
            const first = params.findIndex((item) => item.group === id);
            const count = params.filter((item) => item.group === id).length;
            return (
              <button key={id} type="button" className={`wizard-group${position === group ? " on" : ""}`} disabled={first < 0} aria-pressed={position === group} onClick={() => setIndex(first)}>
                <b>{t(label)}</b>
                <span>{count}</span>
              </button>
            );
          })}
        </div>
        <div className="wizard-progress">
          <span>{t("Прогресс")}</span>
          <div className="orch-bar">
            <i className="cyan" style={{ width: `${Math.round((answered / params.length) * 100)}%` }} />
          </div>
          <small>{t("{done} из {total} параметров заданы", { done: answered, total: params.length })}</small>
        </div>
      </aside>
      <section className="wizard-main">
        <div className="wizard-step">
          <span>{t("Шаг")}</span>
          <b>{t("Группа {current} / {total}", { current: group + 1, total: GROUPS.length })}</b>
          <b>{t("Параметр {current} / {total}", { current: index + 1, total: params.length })}</b>
          <select className="wizard-param-select" aria-label={t("Выбрать параметр")} value={index} onChange={(event) => setIndex(Number(event.target.value))}>
            {params.map((item, position) => (
              <option key={keyOf(item)} value={position}>
                {`${t(item.label)} → ${item.path.join(".")}`}
              </option>
            ))}
          </select>
        </div>
        <article className="wizard-param">
          <div className="wizard-param-head">
            <span>{t(param.label)}</span>
            <code>{nameOf(param)}</code>
          </div>
          {param.description && <p className="wizard-desc">{param.description}</p>}
          <div className="wizard-rec">
            <b>{t("По умолчанию в схеме:")}</b> <code>{param.default === null ? t("не задано") : shown(param.default)}</code>
            {param.choices.length > 0 && (
              <>
                {" · "}
                {t("варианты:")} <code>{param.choices.map(String).join(", ")}</code>
              </>
            )}
          </div>
          <div className="wizard-why">
            <b>{t("Сейчас:")}</b> <code>{shown(currentValue(facts, param))}</code>
          </div>
          <ValueField param={param} value={value(param)} onChange={set} />
          <div className="wizard-accept-row">
            <button className="btn" type="button" disabled={param.default === null} onClick={() => set(param.default)}>
              {t("Взять значение по умолчанию")}
            </button>
            <button className="btn" type="button" disabled={index + 1 >= params.length} onClick={() => setIndex(index + 1)}>
              {t("Следующий параметр")}
            </button>
          </div>
        </article>
        <article className="wizard-param">
          <div className="wizard-param-head">
            <span>{t("Различия")}</span>
            <span>{changes.length}</span>
          </div>
          <ul className="settings-config-list configuration-changes">
            {changes.length === 0 && <li className="muted">{t("Изменений нет")}</li>}
            {changes.map((change) => (
              <li key={`${change.file}:${change.path.join(".")}`}>
                <code>{`${change.file} → ${change.path.join(".")}`}</code> <code>{JSON.stringify((change as { value: unknown }).value)}</code>
              </li>
            ))}
          </ul>
          <label className="field">
            {t("Описание версии")}
            <input className="settings-input" value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <div className="settings-editor-actions">
            <button className="btn" type="button" disabled={reason !== null} onClick={() => onRun("configuration-save-draft", { request: request() }, summary)}>
              {t("Сохранить черновик как версию")}
            </button>
            <button className="btn primary" type="button" disabled={reason !== null} onClick={() => onRun("configuration-apply", { request: request() }, summary)}>
              {t("Применить")}
            </button>
          </div>
          {reason && <p className="settings-note muted">{t(reason)}</p>}
        </article>
      </section>
    </div>
  );
}
