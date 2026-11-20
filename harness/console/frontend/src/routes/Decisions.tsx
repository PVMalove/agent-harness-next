import { DecisionPanel } from "../decisions/DecisionPanel";
import { useI18n } from "../i18n";

export function Decisions({ section: key }: { section: "Orchestration" | "Публикация" }) {
  const { section } = useI18n();
  return <div className="work-page" data-section={key}>
    <div className="page-title"><h1>{section(key)}</h1></div>
    <DecisionPanel kinds={key === "Публикация" ? ["report-decision", "attention"] : undefined} />
  </div>;
}
