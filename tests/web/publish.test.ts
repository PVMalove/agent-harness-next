import { describe, expect, test } from "vitest";
import { stateLabel } from "../../harness/console/frontend/src/i18n";
import { defaultBatch, preflightRows } from "../../harness/console/frontend/src/routes/Publish";
import type { PublishEntry } from "../../harness/console/frontend/src/ws/ledger";

const entry = (batch_id: string, reviewed: boolean): PublishEntry => ({
  batch_id,
  ticket: "#1",
  state: "open",
  branch: "feature/x",
  candidate: null,
  target: null,
  integration_ref: null,
  head: null,
  head_matches: null,
  target_in_history: null,
  refusals: [],
  review: reviewed ? { dispatch_id: `d-${batch_id}`, outcome: "completed", has_blockers: false } : null,
  qa: null,
  pr_url: "",
  pr_state: "",
  verdict: "unknown",
});

describe("the Publication batch selector", () => {
  test("defaults to the newest reviewed batch; entries come newest first", () => {
    expect(defaultBatch([entry("b-new", true), entry("b-old", true)])).toBe("b-new");
    expect(defaultBatch([entry("b-new", false), entry("b-mid", true), entry("b-old", true)])).toBe("b-mid");
  });

  test("falls back to the newest batch without a review report", () => {
    expect(defaultBatch([entry("b-new", false), entry("b-old", false)])).toBe("b-new");
    expect(defaultBatch([])).toBeNull();
  });
});

describe("the Publication preflight rows", () => {
  test("name the review and QA outcomes in the UI language, never the raw value", () => {
    const reviewed = { ...entry("b-1", true), qa: { dispatch_id: "d-qa", outcome: "failed", has_blockers: true } };
    const details = preflightRows(reviewed, (state) => stateLabel("ru", state)).map((row) => row.detail);
    expect(details).toContain("d-qa · Сбой");
    expect(details).toContain("d-b-1 · Завершено");
    expect(details.join(" ")).not.toMatch(/completed|failed/);
    const english = preflightRows(reviewed, (state) => stateLabel("en", state)).map((row) => row.detail);
    expect(english).toContain("d-b-1 · Completed");
  });
});
