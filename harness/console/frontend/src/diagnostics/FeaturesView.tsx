/* The Features tab of Diagnostics (features.snapshot): the feature list grouped by category with
   filters by state and category and a search, the selected feature with the tabs Готовность /
   Конфигурация / Связи, and the switch plan aside with the state counts before and after.
   A switch is enabled only for a feature with a boolean configuration key and while no
   configuration write is pending; the page decides what a switch does. */
import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Panel, PipeTabs, StatusIcon, Switch } from "../ds";
import type { Tone } from "../ds";
import { useI18n } from "../i18n";
import { TabPanel } from "../views/Tabs";
import { FEATURE_CATEGORIES, FEATURE_STATES, countsAfterToggle, stateCounts } from "../ws/features";
import type { Feature, FeatureCategory, FeatureState, FeaturesSnapshot } from "../ws/features";
import { STATE_WORD } from "./togglePlan";

export const STATE_TONE: Readonly<Record<FeatureState, Tone>> = {
  working: "ok",
  partial: "warn",
  not_working: "err",
  disabled: "off",
};
const STATE_LABEL = STATE_WORD;
const FILTER_LABEL: Readonly<Record<FeatureState, string>> = {
  working: "Работают",
  partial: "Частично",
  not_working: "Не работают",
  disabled: "Выключены",
};
export const CATEGORY_LABEL: Readonly<Record<FeatureCategory, string>> = {
  execution: "Исполнение",
  roles: "Роли",
  hooks: "Хуки",
  context: "Контекст",
  process: "Процесс",
  publication: "Публикация",
  capabilities: "Capabilities",
  platform: "Платформа",
};
const SOURCE_KIND: Readonly<Record<string, string>> = {
  capabilities: "каталог capabilities",
  hook: "хук",
  agent: "агент",
  "project.json": "project.json",
  "orchestration.json": "orchestration.json",
  "harness.lock": "harness.lock",
  runtime: "runtime",
};
export const NO_KEY_REASON = "Нет булевого ключа конфигурации для переключения";
export const PENDING_REASON = "Есть незавершённая запись конфигурации";

type DetailTab = "ready" | "config" | "links";

/** Why the switch of `feature` is disabled, or null when it can be used. */
export function switchBlocked(snapshot: FeaturesSnapshot, feature: Feature): string | null {
  if (feature.toggle === null) return NO_KEY_REASON;
  if (snapshot.transaction_pending) return PENDING_REASON;
  return null;
}

function Counts({ counts, id }: { counts: Record<FeatureState, number>; id?: string }) {
  const { t } = useI18n();
  return (
    <span className="ds-feature-counts" id={id}>
      {FEATURE_STATES.map((state) => (
        <span key={state} data-state={state} title={t(FILTER_LABEL[state])}>
          <StatusIcon tone={STATE_TONE[state]} label={t(FILTER_LABEL[state])} />
          <b>{counts[state]}</b>
        </span>
      ))}
    </span>
  );
}

export function FeaturesView({
  snapshot,
  onToggle,
  alert,
}: {
  snapshot: FeaturesSnapshot;
  /** Switching a feature to `enabled`; absent, the switch shows the plan only. */
  onToggle?: (feature: Feature, enabled: boolean) => void;
  /** A message for the selected feature's switch (a refused or stale write). */
  alert?: ReactNode;
}) {
  const { t } = useI18n();
  const [filter, setFilter] = useState<FeatureState | "all">("all");
  const [category, setCategory] = useState<FeatureCategory | "all">("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState<DetailTab>("ready");
  const { features } = snapshot;
  const counts = stateCounts(features);
  const byId = useMemo(() => new Map(features.map((item) => [item.id, item])), [features]);

  const needle = query.trim().toLowerCase();
  const visible = features.filter(
    (item) =>
      (filter === "all" || item.state === filter) &&
      (category === "all" || item.category === category) &&
      (!needle || `${item.name} ${t(item.name)} ${t(item.description)} ${item.id}`.toLowerCase().includes(needle)),
  );
  const current = visible.find((item) => item.id === selected) ?? visible[0] ?? null;
  const groups = FEATURE_CATEGORIES.map((key) => [key, visible.filter((item) => item.category === key)] as const).filter(
    ([, items]) => items.length > 0,
  );

  const link = (id: string) => {
    const item = byId.get(id);
    if (!item) return <span className="ds-tag" key={id}>{id}</span>;
    return (
      <button
        key={id}
        type="button"
        className="ds-btn ds-btn-sm"
        onClick={() => {
          setFilter("all");
          setCategory("all");
          setQuery("");
          setSelected(id);
        }}
      >
        <StatusIcon tone={STATE_TONE[item.state]} label={t(STATE_LABEL[item.state])} /> {t(item.name)}
      </button>
    );
  };

  const blocked = current ? switchBlocked(snapshot, current) : null;
  const on = current ? current.state !== "disabled" : false;
  return (
    <>
      <div className="ds-toolbar ds-feature-filters" id="features-filters">
        <div className="ds-filter" role="group" aria-label={t("Фильтр по состоянию")}>
          <button type="button" aria-pressed={filter === "all"} data-feature-filter="all" onClick={() => setFilter("all")}>
            {t("Все")} <b>{features.length}</b>
          </button>
          {FEATURE_STATES.map((state) => (
            <button key={state} type="button" aria-pressed={filter === state} data-feature-filter={state} onClick={() => setFilter(state)}>
              <StatusIcon tone={STATE_TONE[state]} label={t(FILTER_LABEL[state])} /> {t(FILTER_LABEL[state])} <b>{counts[state]}</b>
            </button>
          ))}
        </div>
        <label className="ds-feature-category">
          <span className="ds-sr">{t("Категория")}</span>
          <select
            className="ds-select"
            aria-label={t("Категория")}
            value={category}
            onChange={(event) => setCategory(event.target.value as FeatureCategory | "all")}
          >
            <option value="all">{t("Все категории")}</option>
            {FEATURE_CATEGORIES.map((key) => (
              <option key={key} value={key}>
                {t(CATEGORY_LABEL[key])}
              </option>
            ))}
          </select>
        </label>
        <span className="ds-feature-note">{t("Выключенная функция не считается ошибкой")}</span>
      </div>

      <div className="ds-features">
        <Panel title={t("Функции")} count={`${visible.length}/${features.length}`} fill scroll="list" id="features-list" label={t("Список функций")}>
          <div className="ds-toolbar ds-toolbar-flat">
            <label className="ds-search">
              <span className="ds-sr">{t("Найти функцию")}</span>
              <input
                className="ds-input"
                type="search"
                value={query}
                placeholder={t("Найти функцию")}
                aria-label={t("Найти функцию")}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
          </div>
          {groups.length === 0 ? (
            <p className="ds-empty">{t("Нет функций для этого фильтра")}</p>
          ) : (
            groups.map(([key, items]) => (
              <div key={key} className="ds-feature-group" data-category={key}>
                <h3 className="ds-group-title">
                  {t(CATEGORY_LABEL[key])} · {items.length}
                </h3>
                {items.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="ds-row ds-row-button"
                    data-feature={item.id}
                    data-state={item.state}
                    aria-pressed={current?.id === item.id}
                    onClick={() => setSelected(item.id)}
                  >
                    <StatusIcon tone={STATE_TONE[item.state]} label={t(STATE_LABEL[item.state])} />
                    <span className="ds-row-main">
                      <span className="ds-row-title">{t(item.name)}</span>
                      <span className="ds-row-sub">{t(item.description)}</span>
                    </span>
                    <span className="ds-row-end">{t(STATE_LABEL[item.state])}</span>
                  </button>
                ))}
              </div>
            ))
          )}
        </Panel>

        <Panel
          title={current ? t(current.name) : t("Функция")}
          id="feature-detail"
          fill
          scroll="text"
          label={t("Функция")}
          meta={current ? `${t(CATEGORY_LABEL[current.category])} · ${t(STATE_LABEL[current.state])}` : undefined}
          actions={
            current ? (
              <span className="ds-feature-switch">
                <Switch
                  id="feature-switch"
                  checked={on}
                  disabled={blocked !== null || onToggle === undefined}
                  label={t("Функция «{name}»", { name: t(current.name) })}
                  onChange={(next) => onToggle?.(current, next)}
                />
                <span>{on ? t("вкл") : t("выкл")}</span>
              </span>
            ) : undefined
          }
        >
          {current === null ? (
            <p className="ds-empty">{t("Выберите функцию")}</p>
          ) : (
            <div className="ds-feature-detail" data-feature={current.id}>
              <div className="ds-feature-head">
                <StatusIcon tone={STATE_TONE[current.state]} label={t(STATE_LABEL[current.state])} />
                <p className="ds-sub">{t(current.description)}</p>
              </div>
              {blocked !== null && (
                <p className="ds-note" id="feature-switch-reason">
                  {t(blocked)}
                </p>
              )}
              {alert}
              <PipeTabs
                id="feature-detail"
                label={t("Функция")}
                value={tab}
                onChange={(id) => setTab(id as DetailTab)}
                tabs={[
                  { id: "ready", label: t("Готовность"), count: current.requirements.length },
                  { id: "config", label: t("Конфигурация"), count: current.settings.length },
                  { id: "links", label: t("Связи"), count: current.depends_on.length + current.required_by.length },
                ]}
              />
              <TabPanel id="feature-detail" tab="ready" value={tab}>
                <div id="feature-detail-ready">
                  {current.state === "disabled" && (
                    <p className="ds-alert">
                      <b>{t("Функция выключена.")}</b> {t(current.off_effect)} {t("Требования показаны для справки.")}
                    </p>
                  )}
                  {current.requirements.length === 0 ? (
                    <p className="ds-empty">{t("Требований нет")}</p>
                  ) : (
                    <ul className="ds-rows">
                      {current.requirements.map((item, index) => (
                        <li className="ds-row" key={index} data-level={item.state}>
                          <StatusIcon tone={item.state} label={t(item.state === "ok" ? "Выполнено" : item.state === "warn" ? "Внимание" : "Ошибка")} />
                          <span className="ds-row-main">
                            <span className="ds-row-title">{t(item.title)}</span>
                            {item.detail && <code className="ds-row-sub">{item.detail}</code>}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </TabPanel>
              <TabPanel id="feature-detail" tab="config" value={tab}>
                <div id="feature-detail-config">
                  {current.settings.length === 0 ? (
                    <p className="ds-empty">{t("Функция не читает ключей конфигурации")}</p>
                  ) : (
                    <dl className="ds-kv">
                      {current.settings.map((item) => (
                        <div className="ds-kv-row" key={`${item.file}:${item.path.join(".")}`}>
                          <dt>
                            <code>{item.path.join(".")}</code> <small>{item.file}</small>
                          </dt>
                          <dd>{item.value === null ? <span className="ds-faint">{t("не задано")}</span> : item.present ? item.value : t(item.value)}</dd>
                        </div>
                      ))}
                    </dl>
                  )}
                  <h3 className="ds-group-title">{t("Источники")}</h3>
                  <ul className="ds-rows">
                    {current.sources.map((item) => (
                      <li className="ds-row" key={`${item.kind}:${item.path}`}>
                        <span className="ds-tag">{t(SOURCE_KIND[item.kind] ?? item.kind)}</span>
                        <code className="ds-row-main">{item.path}</code>
                      </li>
                    ))}
                  </ul>
                </div>
              </TabPanel>
              <TabPanel id="feature-detail" tab="links" value={tab}>
                <div id="feature-detail-links" className="ds-grid-2">
                  <div>
                    <h3 className="ds-group-title">{t("Зависит от")}</h3>
                    <div className="ds-feature-links">{current.depends_on.length ? current.depends_on.map(link) : <span className="ds-faint">{t("ничего")}</span>}</div>
                  </div>
                  <div>
                    <h3 className="ds-group-title">{t("Нужна для")}</h3>
                    <div className="ds-feature-links">{current.required_by.length ? current.required_by.map(link) : <span className="ds-faint">{t("ничего")}</span>}</div>
                  </div>
                </div>
              </TabPanel>
            </div>
          )}
        </Panel>

        <Panel title={t("План переключения")} id="feature-plan" fill scroll="text" label={t("План переключения")}>
          {current === null ? (
            <p className="ds-empty">{t("Выберите функцию")}</p>
          ) : current.toggle === null ? (
            <p className="ds-note">{t(NO_KEY_REASON)}</p>
          ) : (
            <div className="ds-feature-plan">
              <dl className="ds-kv">
                <div className="ds-kv-row">
                  <dt>{t("Ключ")}</dt>
                  <dd>
                    {current.toggle.file} › {current.toggle.path.join(".")}
                  </dd>
                </div>
                <div className="ds-kv-row">
                  <dt>{t("Действие")}</dt>
                  <dd>{on ? t("Выключить") : t("Включить")}</dd>
                </div>
                <div className="ds-kv-row">
                  <dt>{t("Состояние")}</dt>
                  <dd>
                    {t(STATE_LABEL[current.state])} → {t(STATE_LABEL[current.toggle.state_after])}
                  </dd>
                </div>
              </dl>
              <div className="ds-feature-ba">
                <span>{t("Сейчас")}</span>
                <Counts counts={counts} id="feature-plan-before" />
                <span>{t("После")}</span>
                <Counts counts={countsAfterToggle(features, current)} id="feature-plan-after" />
              </div>
              <p className="ds-note">{t("Запись идёт через подтверждённое применение конфигурации; отмена ничего не меняет.")}</p>
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
