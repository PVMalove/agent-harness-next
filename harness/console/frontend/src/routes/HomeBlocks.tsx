/* The blocks of Home that are lists of numbers and events: the KPI strip and the last events. */
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import type { HomeActivity, HomeEvent, HomeSnapshot } from "../ws/types";
import { healthTotal } from "../ws/types";
import { ageText, eventLine } from "./homeActivity";

/** The strip of the main numbers over the blocks: every value is a fact of the snapshot or of
    the counted activity; one without a source reads "нет данных". */
export function KpiStrip({ snapshot, activity }: { snapshot: HomeSnapshot | null; activity: HomeActivity | null }) {
  const { t } = useI18n();
  const health = snapshot?.health ?? null;
  const install = snapshot?.harness ?? null;
  const store = snapshot?.store ?? null;
  const batches = snapshot?.active_batches ?? null;
  const tiles: { label: string; icon: string; value: string | null; note: string | null; tone?: string }[] = [
    {
      label: t("Проверки пройдено"),
      icon: "check",
      value: health ? `${health.ok} / ${healthTotal(health)}` : null,
      note: health ? `${t("пропущено")}: ${health.skipped}` : null,
      tone: health && health.fail === 0 ? "ok" : "",
    },
    {
      label: t("Ошибки и предупреждения"),
      icon: "warning",
      value: health ? `${health.fail} · ${health.warn}` : null,
      note: health ? `${t("ошибки")} · ${t("внимание")}` : null,
      tone: health && health.fail > 0 ? "err" : "",
    },
    { label: t("Активные batch"), icon: "orchestration", value: batches === null ? null : String(batches), note: null },
    {
      label: t("Событий в минуту"),
      icon: "activity",
      value: activity ? String(activity.events_per_minute) : null,
      note: activity
        ? activity.last_event_age_seconds === null
          ? t("нет событий в окне")
          : ageText(activity.last_event_age_seconds, t)
        : null,
    },
    { label: "Runtime store", icon: "store", value: store?.authority ?? null, note: store?.schema != null ? `schema ${store.schema}` : null },
    {
      label: t("Скиллы"),
      icon: "skills",
      value: install ? String(install.skills) : null,
      note: install ? `${install.installed ? install.installed_version : t("не установлен")}` : null,
    },
  ];
  return (
    <div className="tiles home-kpis" role="group" aria-label={t("Показатели Главной")}>
      {tiles.map((tile) => (
        <div className="tile" key={tile.label}>
          <div className="label">
            <Icon name={tile.icon} /> {tile.label}
          </div>
          {tile.value === null ? <b className="muted no-data">{t("нет данных")}</b> : <b className={tile.tone ?? ""}>{tile.value}</b>}
          <span>{tile.note ?? "\u00a0"}</span>
        </div>
      ))}
    </div>
  );
}

/** The last orchestration events the console saw since it opened, newest first. */
export function RecentEvents({ events }: { events: HomeEvent[] }) {
  const { t, language } = useI18n();
  const clock = new Intl.DateTimeFormat(language, { timeStyle: "medium", timeZone: "UTC" });
  return (
    <section id="home-events" className="panel events-panel">
      <div className="panel-head">
        <h2>
          {t("Последние события")} <span className="small muted">{events.length}</span>
        </h2>
        <a className="small" href={href("agent-activity")}>
          {t("Ход работы")} →
        </a>
      </div>
      {events.length ? (
        <ul className="home-event-list" tabIndex={0} aria-label={t("Последние события")}>
          {events.map((event) => {
            const line = eventLine(event, t);
            const moment = Date.parse(event.observed_at);
            return (
              <li key={event.seq}>
                <time dateTime={event.observed_at}>{Number.isNaN(moment) ? "—" : clock.format(moment)}</time>
                <b>{line.title}</b>
                <small>{line.detail}</small>
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="body">
          <p className="empty">{t("Событий с момента открытия консоли не было")}</p>
        </div>
      )}
    </section>
  );
}
