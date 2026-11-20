/* "Session events" of the mockup: the audit chronology of the selected session's batch
   (reports.timeline), newest first. Only recorded facts; the agents' reasoning is never shown. */
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { useScreen } from "../screens/useScreen";
import { parseTimeline } from "../ws/ledger";
import type { RosterDispatch } from "../ws/steps";
import { EVENT_LIMIT, roleIcon, roleName } from "./ActivityViews";

const KINDS: Record<string, string> = {
  state: "состояние",
  dispatch: "запуск роли",
  report: "отчёт",
  decision: "решение",
  risk: "риск",
};

function BatchEvents({ batchId }: { batchId: string }) {
  const { t } = useI18n();
  const screen = useScreen({ type: "reports.timeline", params: { batch_id: batchId } }, parseTimeline);
  if (screen.error && !screen.data) {
    return (
      <p className="command-refusal err" role="alert" data-code={screen.error.code}>
        {screen.error.message || screen.error.code}
      </p>
    );
  }
  if (!screen.data) return <div className="work-empty">{screen.loading ? t("Загрузка…") : t("нет данных")}</div>;
  const events = [...screen.data.events].reverse().slice(0, EVENT_LIMIT);
  if (!events.length) return <div className="work-empty">{t("Событий нет.")}</div>;
  return (
    <>
      {events.map((event, index) => (
        <div className="work-event" key={index} data-kind={event.kind}>
          <span className="work-event-time" title={event.at}>
            {event.at ? event.at.slice(11, 16) : "—"}
          </span>
          <span className="work-event-role">
            {event.role ? (
              <>
                <Icon name={roleIcon(event.role)} /> {roleName(event.role)}
              </>
            ) : (
              "—"
            )}
          </span>
          <span className="work-event-main">
            <b>{event.text}</b>
            <small>{t(KINDS[event.kind] ?? event.kind)}</small>
          </span>
        </div>
      ))}
    </>
  );
}

export function SessionEvents({ session }: { session: RosterDispatch | null }) {
  const { t } = useI18n();
  return (
    <section className="panel work-events-panel" id="work-events-panel">
      <div className="panel-head">
        <h2>
          {t("События сессии")} <span id="work-events-id">{session ? session.ticket || session.batch_id : "—"}</span>
        </h2>
        <span className="small muted">{t("наблюдаемые факты")}</span>
      </div>
      <div className="work-events" id="work-events" tabIndex={0} role="region" aria-label={t("События сессии")}>
        {session ? <BatchEvents key={session.batch_id} batchId={session.batch_id} /> : <div className="work-empty">{t("Событий нет.")}</div>}
      </div>
    </section>
  );
}
