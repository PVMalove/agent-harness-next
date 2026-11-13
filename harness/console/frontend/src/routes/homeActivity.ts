/* The contour of Home from the activity the console counted: pure helpers with no state. */
import type { HomeActivity, HomeEvent } from "../ws/types";

/** A link moves only while its last event is at most this old (and it saw events in the window). */
export const LIVE_AGE_SECONDS = 60;
/** The links of the contour, in the order the console counts them (kernel/home_activity.py). */
export const LINKS = ["decision", "typed", "write", "launch", "audit", "receipts"] as const;
export type Link = (typeof LINKS)[number];

type Translate = (text: string, values?: Readonly<Record<string, string | number>>) => string;

export interface LinkState {
  animated: boolean;
  label: string;
}

/** How long ago something happened: seconds under two minutes, minutes after. */
export function ageText(seconds: number, t: Translate): string {
  return seconds < 120
    ? t("{count} с назад", { count: Math.round(seconds) })
    : t("{count} мин назад", { count: Math.round(seconds / 60) });
}

/** The movement and the caption of one link. No activity (the console could not count it)
    is "нет данных", never zero; an idle link is "нет событий в окне". */
export function linkState(activity: HomeActivity | null, link: string, t: Translate): LinkState {
  const found = activity?.links.find((item) => item.link === link);
  if (!found) return { animated: false, label: t("нет данных") };
  const age = found.last_event_age_seconds;
  if (found.events_per_minute <= 0 || age === null) {
    return { animated: false, label: t("нет событий в окне") };
  }
  return {
    animated: age <= LIVE_AGE_SECONDS,
    label: t("{rate}/мин · {age}", { rate: String(found.events_per_minute), age: ageText(age, t) }),
  };
}

/** The activity as it is `elapsedSeconds` after it was counted: the ages grow, so a link whose
    events stopped goes still without a new reply. The rates describe the window of the reply. */
export function ageActivity(activity: HomeActivity, elapsedSeconds: number): HomeActivity {
  if (elapsedSeconds <= 0) return activity;
  const later = (age: number | null) => (age === null ? null : age + elapsedSeconds);
  return {
    ...activity,
    last_event_age_seconds: later(activity.last_event_age_seconds),
    links: activity.links.map((item) => ({ ...item, last_event_age_seconds: later(item.last_event_age_seconds) })),
  };
}

/** The two lines of an event: its kind and what it says. */
export function eventLine(event: HomeEvent, t: Translate): { title: string; detail: string } {
  const change = event.to ? `${event.from ?? "—"} → ${event.to}` : "";
  const parts = [event.role, change, event.decision, event.outcome].filter((part): part is string => !!part);
  const detail = parts.length ? parts.join(" · ") : (event.ticket ?? event.batch_id ?? t("нет данных"));
  return { title: event.event, detail };
}
