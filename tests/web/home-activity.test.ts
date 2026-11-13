import { describe, expect, test } from "vitest";
import {
  LIVE_AGE_SECONDS,
  eventLine,
  linkState,
} from "../../harness/console/frontend/src/routes/homeActivity";
import { translate } from "../../harness/console/frontend/src/i18n";
import type { HomeActivity } from "../../harness/console/frontend/src/ws/types";

const ru = (text: string, values?: Readonly<Record<string, string | number>>) => translate("ru", text, values);
const en = (text: string, values?: Readonly<Record<string, string | number>>) => translate("en", text, values);

const activity = (links: HomeActivity["links"]): HomeActivity => ({
  window_seconds: 300,
  links,
  last_event_age_seconds: 4,
  events_total_window: 6,
});

describe("the state of a contour link", () => {
  test("no activity at all: static and without numbers", () => {
    expect(linkState(null, "typed", ru)).toEqual({ animated: false, label: "нет данных" });
    expect(linkState(activity([]), "typed", ru)).toEqual({ animated: false, label: "нет данных" });
  });

  test("events flowing: animated, with the counter and the age", () => {
    const flowing = activity([{ link: "typed", events_per_minute: 1.2, last_event_age_seconds: 4.4 }]);
    expect(linkState(flowing, "typed", ru)).toEqual({ animated: true, label: "1.2/мин · 4 с назад" });
    expect(linkState(flowing, "typed", en)).toEqual({ animated: true, label: "1.2/min · 4 s ago" });
  });

  test("the age threshold is one constant: at it the link still moves, one second later it does not", () => {
    const at = activity([{ link: "write", events_per_minute: 0.2, last_event_age_seconds: LIVE_AGE_SECONDS }]);
    const after = activity([{ link: "write", events_per_minute: 0.2, last_event_age_seconds: LIVE_AGE_SECONDS + 1 }]);
    expect(linkState(at, "write", ru).animated).toBe(true);
    expect(linkState(after, "write", ru).animated).toBe(false);
  });

  test("an old last event is shown in minutes and does not animate", () => {
    const old = activity([{ link: "audit", events_per_minute: 0.2, last_event_age_seconds: 150 }]);
    expect(linkState(old, "audit", ru)).toEqual({ animated: false, label: "0.2/мин · 3 мин назад" });
  });

  test("a link without events in the window says so and stays static", () => {
    const idle = activity([{ link: "launch", events_per_minute: 0, last_event_age_seconds: null }]);
    expect(linkState(idle, "launch", ru)).toEqual({ animated: false, label: "нет событий в окне" });
  });

  test("a link counts only its own entry", () => {
    const flowing = activity([
      { link: "typed", events_per_minute: 3, last_event_age_seconds: 1 },
      { link: "launch", events_per_minute: 0, last_event_age_seconds: null },
    ]);
    expect(linkState(flowing, "launch", ru).animated).toBe(false);
    expect(linkState(flowing, "typed", ru).animated).toBe(true);
  });
});

describe("the line of a recent event", () => {
  test("names the batch or ticket and the state change", () => {
    expect(
      eventLine({ seq: 3, observed_at: "t", event: "dispatch.transition", batch_id: "b-1", ticket: null, dispatch_id: "d-9", role: "developer", from: "queued", to: "working", decision: null, outcome: null }, ru),
    ).toEqual({ title: "dispatch.transition", detail: "developer · queued → working" });
    expect(
      eventLine({ seq: 4, observed_at: "t", event: "qa.run", batch_id: "b-1", ticket: null, dispatch_id: "d-9", role: null, from: null, to: null, decision: null, outcome: "passed" }, ru),
    ).toEqual({ title: "qa.run", detail: "passed" });
  });
});
