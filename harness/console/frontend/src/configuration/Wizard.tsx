/* The Parameters tab of «Настройки»: the mockup wizard over the kernel parameter catalog
   (kernel/configuration_wizard.py). Each parameter is a real schema path with the schema's type,
   choices and default, and the console recommendation of the shared wizard steps. An answer only
   changes the shared draft (configuration/draft.ts); writing stays on the Changes tab behind the
   confirmed configuration job. */
import { useState } from "react";
import type { ReactNode } from "react";
import { useI18n } from "../i18n";
import type { ConfigurationFacts, JsonObject, WizardParam } from "../ws/projectScreens";
import { valueAt } from "./draft";
import type { ConfigurationDraft } from "./draft";

const GROUPS: readonly (readonly [string, string])[] = [
  ["orchestrator", "Оркестратор"],
  ["project", "Проект"],
  ["qa", "QA"],
  ["dispatch", "Dispatch"],
  ["hooks", "Хуки"],
];

export const keyOf = (param: WizardParam) => `${param.file}:${param.path.join(".")}`;
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
      <select className="ds-input" aria-label={label} value={value === undefined ? "" : String(value)} onChange={(event) => onChange(param.choices.find((item) => String(item) === event.target.value))}>
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
      <label className="ds-wz-toggle">
        <input type="checkbox" aria-label={label} checked={value === true} onChange={(event) => onChange(event.target.checked)} /> <span>{value === true ? t("да") : t("нет")}</span>
      </label>
    );
  }
  const numeric = param.type === "integer" || param.type === "number";
  return (
    <input
      className="ds-input"
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
  draft,
  advisor,
}: {
  facts: ConfigurationFacts;
  draft: ConfigurationDraft;
  /** The AI hints of the selected parameter, beside the console recommendation. */
  advisor?: (param: WizardParam) => ReactNode;
}) {
  const { t } = useI18n();
  const params = facts.wizard ?? null;
  const [index, setIndex] = useState(0);
  if (!params || params.length === 0) {
    return (
      <section className="ds-panel ds-wz-empty" id="configuration-wizard">
        <p className="ds-note">
          <span className="ds-wz-muted">{t("нет данных")}</span> · {t("Каталог параметров не получен: схема конфигурации не установлена или сервер старее консоли.")}
        </p>
      </section>
    );
  }
  const param = params[Math.min(index, params.length - 1)]!;
  const group = GROUPS.findIndex(([id]) => id === param.group);
  const value = (item: WizardParam) => {
    const document = draft.document(item.file);
    return document === null ? currentValue(facts, item) : valueAt(document, item.path);
  };
  const broken = draft.document(param.file) === null;
  const set = (next: unknown) => draft.setValue(param.file, param.path, next);
  const answered = params.filter((item) => value(item) !== undefined).length;
  const recommendation = param.recommendation ?? null;

  return (
    <div className="ds-wz" id="configuration-wizard">
      <aside className="ds-wz-side">
        <div className="ds-wz-side-head">
          <span>{t("Группы")}</span>
          <b>{GROUPS.length}</b>
        </div>
        <div className="ds-wz-groups">
          {GROUPS.map(([id, label], position) => {
            const first = params.findIndex((item) => item.group === id);
            const count = params.filter((item) => item.group === id).length;
            return (
              <button key={id} type="button" className="ds-wz-group" disabled={first < 0} aria-pressed={position === group} onClick={() => setIndex(first)}>
                <b>{t(label)}</b>
                <span>{count}</span>
              </button>
            );
          })}
        </div>
        <div className="ds-wz-progress">
          <span>{t("Прогресс")}</span>
          <div className="ds-wz-bar">
            <i style={{ width: `${Math.round((answered / params.length) * 100)}%` }} />
          </div>
          <small>{t("{done} из {total} параметров заданы", { done: answered, total: params.length })}</small>
        </div>
      </aside>
      <section className="ds-wz-main">
        <div className="ds-wz-step">
          <span>{t("Шаг")}</span>
          <b>{t("Группа {current} / {total}", { current: group + 1, total: GROUPS.length })}</b>
          <b>{t("Параметр {current} / {total}", { current: index + 1, total: params.length })}</b>
          <select className="ds-select" aria-label={t("Выбрать параметр")} value={index} onChange={(event) => setIndex(Number(event.target.value))}>
            {params.map((item, position) => (
              <option key={keyOf(item)} value={position}>
                {`${t(item.label)} → ${item.path.join(".")}`}
              </option>
            ))}
          </select>
        </div>
        <article className="ds-wz-param">
          <div className="ds-wz-head">
            <span>{t(param.label)}</span>
            <code>{nameOf(param)}</code>
          </div>
          {param.description && <p className="ds-wz-desc">{param.description}</p>}
          <div className="ds-wz-line">
            <b>{t("По умолчанию в схеме:")}</b> <code>{param.default === null ? t("не задано") : shown(param.default)}</code>
            {param.choices.length > 0 && (
              <>
                {" · "}
                {t("варианты:")} <code>{param.choices.map(String).join(", ")}</code>
              </>
            )}
          </div>
          <div className="ds-wz-line">
            <b>{t("Сейчас:")}</b> <code>{shown(currentValue(facts, param))}</code>
          </div>
          <ValueField param={param} value={value(param)} onChange={set} />
          {broken && (
            <p className="ds-alert ds-alert-err" role="alert">
              {t("Черновик файла не разобран: исправьте JSON на вкладке JSON.")}
            </p>
          )}
          <div className="ds-wz-line ds-wz-rec" id="configuration-recommendation">
            <b>{t("Рекомендация консоли:")}</b>{" "}
            {recommendation ? (
              <>
                <code>{shown(recommendation.value)}</code> <span className="ds-wz-muted">{recommendation.reason}</span>
              </>
            ) : (
              <span className="ds-wz-muted">{t("нет рекомендации")}</span>
            )}
          </div>
          <div className="ds-wz-actions">
            <button className="ds-btn ds-btn-sm" type="button" disabled={!recommendation || broken} onClick={() => recommendation && set(recommendation.value)}>
              {t("Принять рекомендацию консоли")}
            </button>
            <button className="ds-btn ds-btn-sm" type="button" disabled={param.default === null || broken} onClick={() => set(param.default)}>
              {t("Взять значение по умолчанию")}
            </button>
            <button className="ds-btn ds-btn-sm" type="button" disabled={index + 1 >= params.length} onClick={() => setIndex(index + 1)}>
              {t("Следующий параметр")}
            </button>
          </div>
        </article>
        {advisor?.(param)}
      </section>
    </div>
  );
}
