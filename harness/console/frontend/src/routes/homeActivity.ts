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

/** The movement and the caption of one link. No activity (the console could not count it)
    is "нет данных", never zero; an idle link is "нет событий в окне". */
export function linkState(activity: HomeActivity | null, link: string, t: Translate): LinkState {
  const found = activity?.links.find((item) => item.link === link);
  if (!found) return { animated: false, label: t("нет данных") };
  const age = found.last_event_age_seconds;
  if (found.events_per_minute <= 0 || age === null) {
    return { animated: false, label: t("нет событий в окне") };
  }
  const rate = String(found.events_per_minute);
  const label =
    age < 120
      ? t("{rate}/мин · {age} с назад", { rate, age: Math.round(age) })
      : t("{rate}/мин · {age} мин назад", { rate, age: Math.round(age / 60) });
  return { animated: found.events_per_minute > 0 && age <= LIVE_AGE_SECONDS, label };
}

/** The part of the console's orchestration events the Home list shows. */
const KEPT = ["seq", "observed_at", "event"] as const;

/** The events of one batch of the stream that have the fields the list needs. */
export function parseHomeEvents(values: readonly unknown[]): HomeEvent[] {
  const events: HomeEvent[] = [];
  for (const value of values) {
    if (value === null || typeof value !== "object") continue;
    const item = value as Record<string, unknown>;
    if (!KEPT.every((key) => key in item)) continue;
    if (typeof item.seq !== "number" || typeof item.observed_at !== "string" || typeof item.event !== "string") continue;
    const text = (key: string): string | null => (typeof item[key] === "string" ? (item[key] as string) : null);
    events.push({
      seq: item.seq,
      observed_at: item.observed_at,
      event: item.event,
      batch_id: text("batch_id"),
      ticket: text("ticket"),
      dispatch_id: text("dispatch_id"),
      role: text("role"),
      from: text("from"),
      to: text("to"),
      decision: text("decision"),
      outcome: text("outcome"),
    });
  }
  return events;
}

/** The two lines of an event: its kind and what it says. */
export function eventLine(event: HomeEvent, t: Translate): { title: string; detail: string } {
  const change = event.to ? `${event.from ?? "—"} → ${event.to}` : "";
  const parts = [event.role, change, event.decision, event.outcome].filter((part): part is string => !!part);
  const detail = parts.length ? parts.join(" · ") : (event.ticket ?? event.batch_id ?? t("нет данных"));
  return { title: event.event, detail };
}
