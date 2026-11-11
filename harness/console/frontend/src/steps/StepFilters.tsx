/* The sessions panel: every dispatch of the roster is a dispatch filter, the selects a ticket and
   a role filter. Only observed facts: a quiet dispatch is not reported as stopped. */
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { rosterRoles } from "../ws/steps";
import type { HeldStep, RosterDispatch, StepFilter } from "../ws/steps";
import {
  STATUS_ICON,
  STATUS_LABEL,
  STATUS_TONE,
  ageMinutes,
  formatMinutes,
  roleIcon,
  roleName,
  sessionStatus,
  statusCounts,
} from "./ActivityViews";
import type { SessionStatus } from "./ActivityViews";

const tone = (state: string): string =>
  state === "dispatched" || state === "working" ? "ok" : state === "failed" || state === "blocked" ? "err" : "";

export function StepFilters({
  dispatches,
  steps,
  filter,
  onChange,
  status = "all",
  onStatus,
  now = Date.now(),
  tickets = [],
  ticket = null,
  onTicket,
}: {
  dispatches: readonly RosterDispatch[];
  steps: readonly HeldStep[];
  filter: StepFilter;
  onChange: (filter: StepFilter) => void;
  status?: "all" | SessionStatus;
  onStatus?: (status: "all" | SessionStatus) => void;
  now?: number;
  /** The tickets of the roster for the ticket picker; the dispatches are already narrowed to `ticket`. */
  tickets?: readonly string[];
  ticket?: string | null;
  onTicket?: (ticket: string | null) => void;
}) {
  const { t, state: stateText } = useI18n();
  const counts = statusCounts(dispatches);
  const shown = dispatches.filter(
    (entry) =>
      (filter.role === null || entry.role === filter.role) && (status === "all" || sessionStatus(entry) === status),
  );
  const chips: ["all" | SessionStatus, string][] = [
    ["all", t("Все")],
    ["running", t("Выполняется")],
    ["blocked", t("Заблокировано")],
    ["awaiting", t("Ждёт")],
  ];
  const stepCounts = new Map<string, number>();
  for (const { step } of steps) {
    if (step.dispatch_id) stepCounts.set(step.dispatch_id, (stepCounts.get(step.dispatch_id) ?? 0) + 1);
  }
  return (
    <section className="panel work-sessions">
      <div className="panel-head">
        <h2>{t("Сессии")}</h2>
        <span className="small muted">{t("{shown} из {total}", { shown: shown.length, total: dispatches.length })}</span>
      </div>
      <div className="work-filters">
        <div className="chips" id="work-status-chips">
          {onStatus
            ? chips.map(([key, label]) => (
                <button
                  key={key}
                  className={`chip ${status === key ? "on" : ""}`}
                  type="button"
                  aria-pressed={status === key}
                  data-status={key}
                  onClick={() => onStatus(key)}
                >
                  {label} {counts[key]}
                </button>
              ))
            : null}
          <button
            className={`chip ${filter.dispatch === null ? "on" : ""}`}
            type="button"
            aria-pressed={filter.dispatch === null}
            onClick={() => onChange({ ...filter, dispatch: null })}
          >
            {t("Все сессии")}
          </button>
        </div>
        {onTicket ? (
          <select
            id="work-ticket"
            aria-label={t("Выбрать задачу")}
            value={ticket ?? ""}
            onChange={(event) => onTicket(event.target.value || null)}
          >
            <option value="">{t("Все задачи")}</option>
            {tickets.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        ) : null}
        <select
          aria-label={t("Фильтр по роли")}
          value={filter.role ?? ""}
          onChange={(event) => onChange({ ...filter, role: event.target.value || null })}
        >
          <option value="">{t("Все роли")}</option>
          {rosterRoles(dispatches).map((role) => (
            <option key={role} value={role}>
              {roleName(role)}
            </option>
          ))}
        </select>
      </div>
      <div className="work-list">
        {shown.length === 0 ? <div className="work-empty">{t("Сессий пока нет")}</div> : null}
        {shown.map((entry) => {
          const on = filter.dispatch === entry.dispatch_id;
          const status = sessionStatus(entry);
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
                <Icon name={roleIcon(entry.role)} />
              </span>
              <span className="work-row-main">
                <b>
                  {entry.ticket ? `${entry.ticket} · ` : ""}
                  {entry.dispatch_id}
                </b>
                <small>
                  {roleName(entry.role)} · {entry.branch || entry.batch_id}
                </small>
              </span>
              <span className={`work-status ${STATUS_TONE[status] || tone(entry.state)}`} data-state={entry.state}>
                <Icon name={STATUS_ICON[status]} />{" "}
                {status === "other" ? stateText(entry.state) : t(STATUS_LABEL[status])}
                {entry.silent ? ` · ${t("тишина")}` : ""}
              </span>
              <span className="work-time" title={t("{count} шагов", { count: stepCounts.get(entry.dispatch_id) ?? 0 })}>
                {formatMinutes(ageMinutes(entry.started_at, now))}
              </span>
            </button>
          );
        })}
      </div>
      <div className="work-note">{t("Только наблюдаемые события; отсутствие события не доказывает остановку.")}</div>
    </section>
  );
}
