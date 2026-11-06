/* Harness: the "Commands" tab of the mockup runs the section's catalog commands as server jobs.
   The other tabs of the mockup are not shown yet. */
import { useI18n } from "../i18n";
import { CommandPanel } from "../commands/CommandPanel";

export function Harness() {
  const { t, section } = useI18n();
  return (
    <div className="harness-page" data-section="Harness">
      <div className="page-title harness-title">
        <div>
          <h1>{section("Harness")}</h1>
        </div>
      </div>
      <div className="orch-tabbar harness-tabbar" role="tablist">
        <button type="button" className="orch-tab on" role="tab" aria-selected="true">
          {t("Команды")}
        </button>
      </div>
      <CommandPanel section="harness" />
    </div>
  );
}
