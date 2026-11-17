/* The orchestration events of the stream that the Home list shows. */
import type { HomeEvent } from "./types";

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
