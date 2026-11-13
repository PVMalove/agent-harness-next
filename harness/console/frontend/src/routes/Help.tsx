/* Help (#/help) on the design system v3: seven tabs (Start, Sections, Keys, Statuses, Safety, FAQ,
   Documentation) built on the client from the seven Markdown sections of help.snapshot, one search
   over every block of every tab, and the "read next" tiles. The counters of the summary and the
   tabs are counted from the data (menu sections, SHORTCUTS, list items of the guide); nothing is
   invented. The page only reads. */
import { useState } from "react";
import { blockText, blocks, countItems, Markdown } from "../help/Markdown";
import { PageHeader, Panel, PipeTabs, RelatedTiles, Summary } from "../ds";
import type { Tile } from "../ds";
import { useI18n } from "../i18n";
import { Icon } from "../icons";
import { NAV_GROUPS, NAV_ITEMS, SHORTCUTS, href } from "../navigation";
import { useScreen } from "../screens/useScreen";
import { NoData } from "../steps/ActivityViews";
import { useConsole } from "../useConsole";
import { preRelease } from "../AppShell";
import { parseHelp } from "../ws/projectScreens";

type Tab = "start" | "sections" | "keys" | "statuses" | "safety" | "faq" | "docs";
/** The tabs with their Russian and English names (a tab name alone is not a catalog string) and the
    guide section each one shows, by its place in kernel/help_text.py (the same in ru and en):
    window, sections, keys, statuses, safety, documentation, FAQ. «Начало» also shows the intro. */
const TABS: readonly (readonly [Tab, string, string, number, string])[] = [
  ["start", "Начало", "Start", 0, "help"],
  ["sections", "Разделы", "Sections", 1, "grid"],
  ["keys", "Клавиши", "Keys", 2, "terminal"],
  ["statuses", "Статусы", "Statuses", 3, "check"],
  ["safety", "Безопасность", "Safety", 4, "shield"],
  ["faq", "Вопросы", "Questions", 6, "info"],
  ["docs", "Документация", "Documentation", 5, "reports"],
];
const TILE_TEXT: Readonly<Record<Tab, string>> = {
  start: "Схема окна и порядок чтения",
  sections: "Все разделы консоли по группам",
  keys: "Переходы между разделами и общие сочетания",
  statuses: "Значки сессий и проверок",
  safety: "Что консоль не делает без подтверждения",
  faq: "Почему «пропущено» не успех и что такое stale",
  docs: "Команды CLI и файлы с подробностями",
};
/** The mockup quick links: route, icon and title. */
const QUICK: readonly (readonly [string, string, string])[] = [
  ["diagnostics", "pulse", "Проверить здоровье"],
  ["update-harness", "refresh", "Открыть обновление"],
  ["repo-map", "map", "Изучить Repo Map"],
  ["configuration", "settings", "Настроить Harness"],
];
const PILLARS: readonly (readonly [string, string])[] = [
  ["01 · Наблюдай", "Сессии, dispatch, heartbeat и события."],
  ["02 · Проверяй", "Health, QA evidence, Release Gate."],
  ["03 · Решай", "Подтверждения, повторы, передача человеку."],
];
const KEY_ROUTES = Object.entries(SHORTCUTS);
const SHORTCUT_OF = new Map(KEY_ROUTES.map(([key, route]) => [route, key]));

/** The `### question` blocks of the FAQ section, each followed by its answer. */
function faqItems(markdown: string): [string, string][] {
  return markdown.split("\n### ").slice(1).map((block) => {
    const [question = "", ...answer] = block.split("\n");
    return [question.trim(), answer.join("\n").trim()];
  });
}

export function Help() {
  const { t, section, language } = useI18n();
  const { snapshot } = useConsole();
  const screen = useScreen({ type: "help.snapshot", params: { language } }, parseHelp);
  const guide = screen.data;
  const sections = guide?.sections ?? [];
  const [tab, setTab] = useState<Tab>("start");
  const [query, setQuery] = useState("");
  const needle = query.trim().toLowerCase();
  const name = (entry: (typeof TABS)[number]) => (language === "en" ? entry[2] : entry[1]);
  const title = (route: string) => {
    const item = NAV_ITEMS.find((candidate) => candidate.route === route)!;
    return item.label ? t(item.label) : section(item.section);
  };
  const markdown = (at: number) => sections[at]?.markdown ?? "";
  const faq = faqItems(markdown(6));
  const counts: Partial<Record<Tab, number>> = {
    sections: NAV_ITEMS.length,
    keys: KEY_ROUTES.length,
    statuses: countItems(markdown(3)),
    safety: countItems(markdown(4)),
    faq: faq.length,
    docs: countItems(markdown(5)),
  };
  const version = snapshot?.harness_version ?? null;
  const health = snapshot ? snapshot.health.ok + snapshot.health.warn + snapshot.health.fail + snapshot.health.skipped : null;
  const quickCaption = (route: string) => {
    const none = <NoData why={t("Снимок Главной ещё не получен")} />;
    if (route === "diagnostics") return health === null ? none : t("{count} проверок", { count: health });
    if (route === "update-harness") return snapshot?.drift_counts ? t("{count} изменений пакета", { count: snapshot.drift_counts.total }) : none;
    if (route === "repo-map") {
      const map = snapshot?.repo_map.head_map ?? null;
      return map ? t("{count} файлов", { count: map.files }) : snapshot ? t("карты для HEAD нет") : none;
    }
    return "project.json";
  };
  const tabEntry = TABS.find((entry) => entry[0] === tab)!;
  const tiles: Tile[] = TABS.filter((entry) => entry[0] !== tab).map((entry) => ({
    key: entry[0], icon: entry[4], title: name(entry), count: counts[entry[0]], text: t(TILE_TEXT[entry[0]]),
  }));
  const guideBody = (at: number, label: string, extra?: React.ReactNode) => (
    <Panel id={`help-section-${at}`} fill title={sections[at]?.title ?? label} label={sections[at]?.title ?? label}>
      {extra}
      {sections[at] ? <Markdown text={sections[at]!.markdown} /> : <p className="ds-empty">{screen.error ? "" : t("Справка загружается…")}</p>}
    </Panel>
  );
  const hits = needle
    ? sections.map((item, at) => ({ item, at, found: blocks(item.markdown).filter((block) => blockText(block).includes(needle)).length })).filter((hit) => hit.found > 0)
    : [];
  const body = (() => {
    if (needle) {
      return (
        <Panel id="help-search-results" fill title={t("Найдено в справке")} count={hits.length} label={t("Найдено в справке")}>
          {hits.length === 0 ? <p className="ds-empty">{t("Ничего не найдено")}</p> : hits.map(({ item, at }) => (
            <div key={at}><h3 className="ds-rel-title ds-pad">{item.title}</h3><Markdown text={item.markdown} match={needle} /></div>
          ))}
        </Panel>
      );
    }
    switch (tab) {
      case "start":
        return (
          <>
            <div className="ds-split">
              <Panel id="help-intro" fill title={`${t("СПРАВКА")}${version ? ` · ${version}` : ""}`} label={t("СПРАВКА")}>
                {guide && <Markdown text={guide.intro} />}
                <div className="ds-pillars">{PILLARS.map(([head, text]) => (<div key={head}><b>{t(head)}</b><span>{t(text)}</span></div>))}</div>
                {sections[0] && <Markdown text={sections[0].markdown} />}
              </Panel>
              <Panel fill title={t("Быстрые ссылки")} label={t("Быстрые ссылки")}>
                <ul className="ds-rows">{QUICK.map(([route, icon, label]) => (
                  <li key={route}><a className="ds-row ds-quick" href={href(route)}>
                    <Icon name={icon} className="ds-ic" />
                    <span className="ds-row-main"><b className="ds-row-title">{t(label)}</b><small className="ds-row-sub">{quickCaption(route)}</small></span>
                    <Icon name="chevron" className="ds-ic-sm" />
                  </a></li>))}</ul>
              </Panel>
            </div>
            <RelatedTiles id="help-next" title={t("Читать дальше")} tiles={tiles} onSelect={(key) => setTab(key as Tab)} />
          </>
        );
      case "sections":
        return (
          <>
            <div className="ds-grid-3">{NAV_GROUPS.map((group) => (
              <Panel key={group.label} title={t(group.label)} count={group.items.length}>
                <ul className="ds-rows">{group.items.map((item) => (
                  <li key={item.route}><a className="ds-row ds-quick" href={href(item.route)}>
                    <Icon name={item.icon} className="ds-ic" />
                    <span className="ds-row-main"><b className="ds-row-title">{title(item.route)}</b><small className="ds-row-sub">#/{item.route}</small></span>
                    {SHORTCUT_OF.has(item.route) ? <kbd className="ds-kbd">{SHORTCUT_OF.get(item.route)}</kbd> : null}
                  </a></li>))}</ul>
              </Panel>))}</div>
            {guideBody(1, name(tabEntry))}
          </>
        );
      case "keys":
        return (
          <>
            <Panel title={t("Горячие клавиши")} meta={t("работают вне полей ввода")}>
              <div className="ds-key-grid">{KEY_ROUTES.map(([key, route]) => (<div key={key}><kbd className="ds-kbd">{key}</kbd><span>{title(route)}</span></div>))}</div>
            </Panel>
            {guideBody(2, name(tabEntry))}
          </>
        );
      case "faq":
        return (
          <Panel id="help-faq" fill title={sections[6]?.title ?? name(tabEntry)} count={faq.length} label={name(tabEntry)}>
            <div className="ds-faq">{faq.map(([question, answer]) => (<details key={question}><summary>{question}</summary><p>{answer}</p></details>))}</div>
          </Panel>
        );
      default:
        return guideBody(tabEntry[3], name(tabEntry));
    }
  })();
  return (
    <div className="ds-page ds-fit" data-section="Help">
      <PageHeader
        title={section("Help")}
        subtitle={t("Как устроена консоль: разделы, клавиши, статусы и правила безопасности")}
        actions={<>
          <button className="ds-btn" type="button" title={t("Документация консоли")} onClick={() => { setQuery(""); setTab("docs"); }}>
            <Icon name="reports" className="ds-ic-sm" /> README
          </button>
          <a className="ds-btn" href={href("diagnostics")}><Icon name="pulse" className="ds-ic-sm" /> {section("Diagnostics")}</a>
        </>}
      />
      {screen.error && !guide && (
        <p className="ds-alert ds-alert-err" role="alert" data-code={screen.error.code}>{t("Справка недоступна:")} {screen.error.message || screen.error.code}</p>
      )}
      <Summary
        id="help-kpis"
        label={t("Сводка справки")}
        stats={[
          { label: t("Разделов"), value: NAV_ITEMS.length },
          { label: t("Сочетаний клавиш"), value: KEY_ROUTES.length },
          { label: t("Правил безопасности"), value: guide ? counts.safety ?? 0 : "—" },
          { label: t("Вопросов"), value: guide ? faq.length : "—" },
        ]}
        facts={<>
          {version && <span>Harness {version}</span>}
          {version && preRelease(version) && <span>pre-release</span>}
          <span>{t("Текст передаёт сервер консоли")}</span>
        </>}
        snapshot={<span>{t("Справка ничего не запускает")}</span>}
      />
      <div className="ds-toolbar">
        <label className="ds-search">
          <Icon name="search" className="ds-ic-sm" />
          <input className="ds-input" type="search" aria-label={t("Поиск по справке")} placeholder={t("Поиск по справке: раздел, клавиша, статус, команда")}
            value={query} onChange={(event) => setQuery(event.target.value)} />
        </label>
        <button className="ds-btn ds-btn-sm" type="button" disabled={!query} onClick={() => setQuery("")}>{t("Сбросить")}</button>
      </div>
      <PipeTabs id="help" label={section("Help")} value={tab} onChange={(id) => { setTab(id as Tab); }}
        tabs={TABS.map((entry) => ({ id: entry[0], label: name(entry), count: counts[entry[0]] }))} />
      <div id={`help-tab-${tab}`} className="ds-tabpanel" role="tabpanel" aria-labelledby={`help-tab-${tab}-button`} tabIndex={0}>{body}</div>
    </div>
  );
}
