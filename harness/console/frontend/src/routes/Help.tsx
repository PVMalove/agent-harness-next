/* Help (#/help): the console guide of help.snapshot in the UI language — its introduction and its
   sections as tabs, rendered by the safe Markdown subset of help/Markdown.tsx. The keys, statuses
   and safety rules are the guide's own sections; nothing is added here. The page only reads. */
import { useState } from "react";
import { Markdown } from "../help/Markdown";
import { useI18n } from "../i18n";
import { useScreen } from "../screens/useScreen";
import { parseHelp } from "../ws/projectScreens";

export function Help() {
  const { t, section, language } = useI18n();
  const screen = useScreen({ type: "help.snapshot", params: { language } }, parseHelp);
  const guide = screen.data;
  const [chosen, setChosen] = useState(0);
  const sections = guide?.sections ?? [];
  const index = chosen < sections.length ? chosen : 0;
  const current = sections[index] ?? null;

  return (
    <div className="help-screen work-page" data-section="Help">
      <div className="page-title help-title">
        <div>
          <h1>{section("Help")}</h1>
          <p>{t("Справка по разделам, клавишам и правилам безопасности консоли.")}</p>
          {guide && (
            <div className="home-facts">
              <span id="help-count">{t("Разделов справки: {n}", { n: sections.length })}</span>
            </div>
          )}
        </div>
      </div>

      {screen.error && !guide && (
        <p className="command-refusal err" role="alert" data-code={screen.error.code}>
          {t("Справка недоступна:")} {screen.error.message || screen.error.code}
        </p>
      )}

      {guide && (
        <section className="panel help-hero" id="help-intro">
          <Markdown text={guide.intro} />
        </section>
      )}

      {guide && sections.length > 0 && (
        <>
          <div className="help-tabbar tabs" role="tablist" aria-label={section("Help")}>
            {sections.map((item, at) => (
              <button key={item.title} type="button" role="tab" aria-selected={at === index} className={at === index ? "on" : ""} onClick={() => setChosen(at)}>
                {item.title}
              </button>
            ))}
          </div>
          {current && (
            <section className="panel help-section" id="help-section" role="tabpanel">
              <Markdown text={current.markdown} />
            </section>
          )}
        </>
      )}
    </div>
  );
}
