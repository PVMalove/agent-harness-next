/* The body of a Recovery or Container route view as the TUI's `render_body` draws it: blockers
   first, then the facts by group, the actions that cannot run with their reasons, then the notes.
   Every row, mark and reason is the kernel's own (kernel/screen_views.py); values are never
   shortened, they wrap. Core text is untrusted and stays text. */
import { useI18n } from "../i18n";
import { groupRows } from "../ws/views";
import type { ViewAction, ViewRow } from "../ws/views";

export function RowList({
  rows,
  blockers,
  notes,
  actions,
}: {
  rows: readonly ViewRow[];
  blockers: readonly string[];
  notes: readonly string[];
  actions: readonly ViewAction[];
}) {
  const { t } = useI18n();
  const unavailable = actions.filter((action) => !action.enabled && action.reason);
  return (
    <div className="view-body">
      {blockers.length > 0 && (
        <section className="view-blockers" role="alert">
          <h3>{t("✖ Блокирует маршрут")}</h3>
          {blockers.map((blocker, index) => (
            <p key={index}>{t(blocker)}</p>
          ))}
        </section>
      )}
      {groupRows(rows).map((group, index) => (
        <section key={index} className="view-group">
          {group.group && <h3>{t(group.group)}</h3>}
          <dl>
            {group.rows.map((row, rowIndex) => (
              <div key={rowIndex} className="view-row" data-state={row.state ?? undefined}>
                <dt>
                  {row.mark && <span className={`view-mark ${row.state ?? ""}`}>{t(row.mark)}</span>}
                  <span className="view-label">{t(row.label)}</span>
                </dt>
                <dd>{t(row.value)}</dd>
              </div>
            ))}
          </dl>
        </section>
      ))}
      {unavailable.length > 0 && (
        <ul className="view-unavailable">
          {unavailable.map((action) => (
            <li key={action.key} data-action={action.key}>
              {`${t("✖ недоступно")}: ${t(action.label)} — ${t(action.reason)}`}
            </li>
          ))}
        </ul>
      )}
      {notes.map((note, index) => (
        <p key={index} className="view-note">
          {t(note)}
        </p>
      ))}
    </div>
  );
}

/** One button per action: a disabled action shows its reason beside it and cannot be clicked. */
export function ActionBar({
  actions,
  busy,
  onAction,
}: {
  actions: readonly ViewAction[];
  busy: boolean;
  onAction: (action: ViewAction) => void;
}) {
  const { t } = useI18n();
  return (
    <div className="view-actions" id="view-actions">
      {actions.map((action) => (
        <span key={action.key} className="view-action" data-action={action.key}>
          <button
            type="button"
            className="btn"
            disabled={!action.enabled || busy}
            title={action.enabled ? undefined : t(action.reason)}
            onClick={() => onAction(action)}
          >
            {t(action.label)}
          </button>
          {!action.enabled && action.reason && <small className="view-action-reason">{t(action.reason)}</small>}
        </span>
      ))}
    </div>
  );
}
