/* The sessions panel: every dispatch of the roster is a dispatch filter, the select a role
   filter. Only observed facts: a quiet dispatch is not reported as stopped. */
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { rosterRoles } from "../ws/steps";
import type { HeldStep, RosterDispatch, StepFilter } from "../ws/steps";

const tone = (state: string): string =>
  state === "dispatched" || state === "working" ? "ok" : state === "failed" || state === "blocked" ? "err" : "";

export function StepFilters({
  dispatches,
  steps,
  filter,
  onChange,
}: {
  dispatches: readonly RosterDispatch[];
  steps: readonly HeldStep[];
  filter: StepFilter;
  onChange: (filter: StepFilter) => void;
}) {
  const { t } = useI18n();
  const shown = dispatches.filter((entry) => filter.role === null || entry.role === filter.role);
  const counts = new Map<string, number>();
  for (const { step } of steps) {
    if (step.dispatch_id) counts.set(step.dispatch_id, (counts.get(step.dispatch_id) ?? 0) + 1);
  }
  return (
    <section className="panel work-sessions">
      <div className="panel-head">
        <h2>{t("Сессии")}</h2>
        <span className="small muted">{t("{shown} из {total}", { shown: shown.length, total: dispatches.length })}</span>
      </div>
      <div className="work-filters">
        <div className="chips">
          <button
            className={`chip ${filter.dispatch === null ? "on" : ""}`}
            type="button"
            aria-pressed={filter.dispatch === null}
            onClick={() => onChange({ ...filter, dispatch: null })}
          >
            {t("Все сессии")}
          </button>
        </div>
        <select
          aria-label={t("Фильтр по роли")}
          value={filter.role ?? ""}
          onChange={(event) => onChange({ ...filter, role: event.target.value || null })}
        >
          <option value="">{t("Все роли")}</option>
          {rosterRoles(dispatches).map((role) => (
            <option key={role} value={role}>
              {role}
            </option>
          ))}
        </select>
      </div>
      <div className="work-list">
        {shown.length === 0 ? <div className="work-empty">{t("Сессий пока нет")}</div> : null}
        {shown.map((entry) => {
          const on = filter.dispatch === entry.dispatch_id;
          return (
            <button
              key={entry.dispatch_id}
              type="button"
              className={`work-row ${on ? "on" : ""}`}
              aria-pressed={on}
              data-dispatch={entry.dispatch_id}
              onClick={() => onChange({ ...filter, dispatch: on ? null : entry.dispatch_id })}
            >
              <span className="work-role">
                <Icon name="activity" />
              </span>
              <span className="work-row-main">
                <b>
                  {entry.ticket ? `${entry.ticket} · ` : ""}
                  {entry.dispatch_id}
                </b>
                <small>
                  {entry.role} · {entry.batch_id}
                </small>
              </span>
              <span className={`work-status ${tone(entry.state)}`}>{entry.state}</span>
              <span className="work-time">{counts.get(entry.dispatch_id) ?? 0}</span>
            </button>
          );
        })}
      </div>
      <div className="work-note">{t("Только наблюдаемые события; отсутствие события не доказывает остановку.")}</div>
    </section>
  );
}
