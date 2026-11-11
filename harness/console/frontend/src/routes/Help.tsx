/* Help (#/help): the mockup's tabs Start, Screens, Commands, Hotkeys and Boundaries over the
   console guide of help.snapshot in the UI language (rendered by the safe Markdown subset of
   help/Markdown.tsx) and the console's own catalogs: the menu sections, the job sections that
   run commands and the web shortcuts. Every guide section is shown in one tab; nothing is
   invented here. The page only reads. The page wrapper is `.help-page`: the mockup's
   `.help-screen` is the 22px-icon card of the Screens grid, and wrapping the whole page in it
   squeezed the guide into a one-character column. */
import { useState } from "react";
import { Markdown } from "../help/Markdown";
import { useI18n } from "../i18n";
import { Icon } from "../icons";
import { NAV_ITEMS, SHORTCUTS, href, navItemOf } from "../navigation";
import { TabList, TabPanels } from "../views/Tabs";
import { useScreen } from "../screens/useScreen";
import { NoData } from "../steps/ActivityViews";
import { useConsole } from "../useConsole";
import { preRelease } from "../AppShell";
import { parseHelp } from "../ws/projectScreens";

type Tab = "start" | "screens" | "commands" | "keys" | "limits";
/** The tabs with their Russian and English names: «Начало» alone is a time word elsewhere in the
    catalog, so the tab names are kept here. */
const TABS: readonly (readonly [Tab, string, string])[] = [
  ["start", "Начало", "Start"],
  ["screens", "Экраны", "Screens"],
  ["commands", "Команды", "Commands"],
  ["keys", "Горячие клавиши", "Hotkeys"],
  ["limits", "Границы", "Boundaries"],
];
/** The guide sections of each tab, by their place in kernel/help_text.py (the same in ru and en):
    console window and documentation, sections, keys, statuses and safety. */
const SECTIONS: Readonly<Record<Tab, readonly number[]>> = { start: [0, 5], screens: [1], commands: [], keys: [2], limits: [3, 4] };
/** The FAQ section (the guide's last one): `### question` blocks, each followed by its answer. */
const FAQ_SECTION = 6;
const DOCS_SECTION = 5;

function faqItems(markdown: string): [string, string][] {
  return markdown
    .split("\n### ")
    .slice(1)
    .map((block) => {
      const [question = "", ...answer] = block.split("\n");
      return [question.trim(), answer.join("\n").trim()];
    });
}
const PILLARS: readonly (readonly [string, string])[] = [
  ["01 · Наблюдай", "Сессии, dispatch, heartbeat и события."],
  ["02 · Проверяй", "Health, QA evidence, Release Gate."],
  ["03 · Решай", "Подтверждения, повторы, передача человеку."],
];
/** The mockup quick links: route, icon and title. */
const QUICK: readonly (readonly [string, string, string])[] = [
  ["diagnostics", "pulse", "Проверить здоровье"],
  ["update-harness", "refresh", "Открыть обновление"],
  ["repo-map", "map", "Изучить Repo Map"],
  ["configuration", "settings", "Настроить Harness"],
];
/** The job sections that run commands, the page that offers them and what they do. */
const COMMANDS: readonly (readonly [string, string, string])[] = [
  ["setup", "open-project", "Установка Harness в проект"],
  ["update", "update-harness", "Обновление управляемых файлов"],
  ["harness", "harness", "Очистка и обслуживание .harness"],
  ["configuration", "configuration", "Черновик и запись конфигурации"],
  ["repo-map", "repo-map", "Построение Repo Map для HEAD"],
];
/** What each web shortcut opens. */
const KEY_ROUTES = Object.entries(SHORTCUTS);

export function Help() {
  const { t, section, language } = useI18n();
  const { snapshot } = useConsole();
  const tabs = TABS.map(([key, ru, en]) => [key, language === "en" ? en : ru] as const);
  const screen = useScreen({ type: "help.snapshot", params: { language } }, parseHelp);
  const guide = screen.data;
  const [tab, setTab] = useState<Tab>("start");
  const sections = guide?.sections ?? [];
  const title = (route: string) => {
    const item = navItemOf(route);
    return item.label ? t(item.label) : section(item.section);
  };
  const guideSections = (which: Tab) =>
    SECTIONS[which]
      .map((at) => [at, sections[at]] as const)
      .filter((pair) => pair[1] !== undefined)
      .map(([at, item]) => (
        <section className="panel help-section" key={item!.title} id={`help-section-${at}`}>
          <Markdown text={item!.markdown} />
        </section>
      ));
  const version = snapshot?.harness_version ?? null;
  const health = snapshot ? snapshot.health.ok + snapshot.health.warn + snapshot.health.fail + snapshot.health.skipped : null;
  const quickCaption = (route: string) => {
    const none = <NoData why={t("Снимок Главной ещё не получен")} />;
    if (route === "diagnostics") return health === null ? none : t("{count} проверок", { count: health });
    if (route === "update-harness")
      return snapshot?.drift_counts ? t("{count} изменений пакета", { count: snapshot.drift_counts.total }) : none;
    if (route === "repo-map") {
      const map = snapshot?.repo_map.head_map ?? null;
      return map ? t("{count} файлов", { count: map.files }) : snapshot ? t("карты для HEAD нет") : none;
    }
    return "project.json";
  };
  const faq = sections[FAQ_SECTION];
  const openReadme = () => {
    setTab("start");
    window.setTimeout(() => document.getElementById(`help-section-${DOCS_SECTION}`)?.scrollIntoView({ block: "start" }), 0);
  };

  return (
    <div className="help-page work-page" data-section="Help">
      <div className="page-title help-title">
        <div>
          <h1>{section("Help")}</h1>
          <p>{t("Экраны, команды, горячие клавиши и границы наблюдения.")}</p>
          <div className="home-facts">
            {version && <span>Harness {version}</span>}
            {version && preRelease(version) && <span>pre-release</span>}
            <span>{t("{count} экранов", { count: NAV_ITEMS.length })}</span>
          </div>
        </div>
        <div className="actions">
          <button className="btn" type="button" title={t("Документация консоли")} onClick={openReadme}>
            <Icon name="reports" /> README
          </button>
          <a className="btn" href={href("diagnostics")}>
            <Icon name="pulse" /> {section("Diagnostics")}
          </a>
        </div>
      </div>

      {screen.error && !guide && (
        <p className="command-refusal err" role="alert" data-code={screen.error.code}>
          {t("Справка недоступна:")} {screen.error.message || screen.error.code}
        </p>
      )}

      <div className="help-kpis">
        <div>
          <span>{t("Экранов")}</span>
          <b>{NAV_ITEMS.length}</b>
          <small>{t("в меню консоли")}</small>
        </div>
        <div>
          <span>{t("Команд")}</span>
          <b>{COMMANDS.length}</b>
          <small>{t("после подтверждения")}</small>
        </div>
        <div>
          <span>{t("Горячих клавиш")}</span>
          <b>{KEY_ROUTES.length}</b>
          <small>{t("вне полей ввода")}</small>
        </div>
        <div>
          <span>{t("Разделов справки")}</span>
          <b>{guide ? sections.length : "—"}</b>
          <small>{t("в справке консоли")}</small>
        </div>
      </div>

      <TabList
        id="help"
        label={section("Help")}
        className="orch-tabbar help-tabbar"
        tabs={tabs}
        value={tab}
        onChange={(key) => setTab(key as Tab)}
      />
      <TabPanels id="help" tabs={tabs} value={tab}>
        {tab === "start" && (
          <>
            <section className="panel help-hero" id="help-intro">
              <div className="help-hero-head">
                <span>{`${t("СПРАВКА")}${version ? ` · ${version}` : ""}`}</span>
                {guide && <Markdown text={guide.intro} />}
              </div>
              <div className="help-pillars">
                {PILLARS.map(([head, text]) => (
                  <div key={head}>
                    <b>{t(head)}</b>
                    <span>{t(text)}</span>
                  </div>
                ))}
              </div>
            </section>
            <div className="help-quick">
              {QUICK.map(([route, icon, label]) => (
                <a key={route} className="help-quick-card" href={href(route)}>
                  <span>
                    <Icon name={icon} />
                  </span>
                  <b>{t(label)}</b>
                  <small>{quickCaption(route)}</small>
                </a>
              ))}
            </div>
            {faq && (
              <section className="panel help-faq" id="help-faq">
                <div className="panel-head">
                  <h2>{faq.title}</h2>
                  <span className="small muted">{t("коротко о главном")}</span>
                </div>
                <div className="help-faq-list">
                  {faqItems(faq.markdown).map(([question, answer]) => (
                    <details key={question}>
                      <summary>{question}</summary>
                      <p>{answer}</p>
                    </details>
                  ))}
                </div>
              </section>
            )}
            {guideSections("start")}
          </>
        )}
        {tab === "screens" && (
          <>
            <section className="panel help-screens">
              <div className="panel-head">
                <h2>{t("Экраны")}</h2>
                <span className="small muted">{t("{count} разделов", { count: NAV_ITEMS.length })}</span>
              </div>
              <div className="help-screen-grid">
                {NAV_ITEMS.map((item) => (
                  <a key={item.route} className="help-screen" href={href(item.route)}>
                    <span>
                      <Icon name={item.icon} />
                    </span>
                    <div>
                      <b>{title(item.route)}</b>
                      <small>#/{item.route}</small>
                    </div>
                  </a>
                ))}
              </div>
            </section>
            {guideSections("screens")}
          </>
        )}
        {tab === "commands" && (
          <section className="panel help-commands">
            <div className="panel-head">
              <h2>{t("Команды")}</h2>
              <span className="small muted">{t("запуск только после подтверждения")}</span>
            </div>
            <div className="help-command-table">
              <div className="help-command-head">
                <span>{t("раздел заданий")}</span>
                <span>{t("назначение")}</span>
                <span>{t("страница")}</span>
              </div>
              {COMMANDS.map(([job, route, purpose]) => (
                <div className="help-command-row" key={job}>
                  <code>{job}</code>
                  <span>{t(purpose)}</span>
                  <a className="btn" href={href(route)}>
                    {title(route)}
                  </a>
                </div>
              ))}
            </div>
            <p className="harness-note">{t("Команды выполняются как job сервера; каждая открывает подтверждение, отмена ничего не запускает.")}</p>
          </section>
        )}
        {tab === "keys" && (
          <>
            <section className="panel help-keys">
              <div className="panel-head">
                <h2>{t("Горячие клавиши")}</h2>
                <span className="small muted">{t("работают вне полей ввода")}</span>
              </div>
              <div className="help-key-grid">
                {KEY_ROUTES.map(([key, route]) => (
                  <div key={key}>
                    <kbd>{key}</kbd>
                    <span>{title(route)}</span>
                  </div>
                ))}
              </div>
            </section>
            {guideSections("keys")}
          </>
        )}
        {tab === "limits" && guideSections("limits")}
      </TabPanels>
    </div>
  );
}
