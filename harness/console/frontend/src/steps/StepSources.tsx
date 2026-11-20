/* "Step sources": Claude Code logs carry structure, Codex logs are a plain tail without it. */
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { STRUCTURE_LABELS } from "../ws/steps";

const SOURCES = [
  {
    name: "Claude Code",
    kind: "structured",
    tone: "mint",
    label: STRUCTURE_LABELS.available,
    detail: "Шаги, роли и инструменты приходят структурированными.",
  },
  {
    name: "Codex",
    kind: "plain",
    tone: "violet",
    label: STRUCTURE_LABELS.unavailable,
    detail: "Только plain-хвост лога. Не выдаём его за шаги и не показываем thinking.",
  },
] as const;

export function StepSources() {
  const { t } = useI18n();
  return (
    <section className="panel work-sources">
      <div className="panel-head">
        <h2>{t("Источники шагов")}</h2>
        <span className="small muted">{t("наблюдаемые данные")}</span>
      </div>
      <div className="work-source-grid">
        {SOURCES.map((source) => (
          <div key={source.kind} className={`work-source ${source.kind}`} data-source={source.kind}>
            <span>
              <Icon name={source.kind === "plain" ? "terminal" : "activity"} />
            </span>
            <div>
              <b>{source.name}</b>
              <small>{t(source.detail)}</small>
            </div>
            <em className={`orch-pill ${source.tone}`}>{t(source.label)}</em>
          </div>
        ))}
      </div>
    </section>
  );
}
