import { describe, expect, test } from "vitest";
import { defaultBatch } from "../../harness/console/frontend/src/routes/Publish";
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
