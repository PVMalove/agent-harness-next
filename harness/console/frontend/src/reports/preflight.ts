/* The preflight rows of one publish entry, shared by Publish and the candidate drawer. */
import type { PublishEntry } from "../ws/ledger";
import { VERDICT_TONE } from "./ReportViews";

type Tone = "mint" | "violet" | "blue";

export interface Check {
  label: string;
  status: string;
  tone: Tone;
  detail: string;
}

export const short = (sha: string | null): string => (sha ? sha.slice(0, 12) : "—");

/** The preflight rows of one entry; a fact the view could not read is "unknown", never a pass.
    `word` renders a report outcome in the UI language (the raw value without it). */
export function preflightRows(entry: PublishEntry, word: (state: string) => string = (state) => state): Check[] {
  const flag = (value: boolean | null): [string, Tone] =>
    value === null ? ["unknown", "blue"] : value ? ["ok", "mint"] : ["blocked", "violet"];
  const report = (ref: PublishEntry["qa"]): [string, Tone] =>
    ref === null ? ["missing", "violet"] : ref.has_blockers || ref.outcome !== "completed" ? ["blocked", "violet"] : ["ok", "mint"];
  const [qa, qaTone] = report(entry.qa);
  const [review, reviewTone] = report(entry.review);
  const [head, headTone] = flag(entry.head_matches);
  const [target, targetTone] = flag(entry.target_in_history);
  return [
    { label: "QA evidence", status: qa, tone: qaTone, detail: entry.qa ? `${entry.qa.dispatch_id} · ${word(entry.qa.outcome)}` : "—" },
    {
      label: "Review",
      status: review,
      tone: reviewTone,
      detail: entry.review ? `${entry.review.dispatch_id} · ${word(entry.review.outcome)}` : "—",
    },
    {
      label: "Release Gate",
      status: entry.verdict,
      tone: VERDICT_TONE[entry.verdict],
      detail: entry.refusals.join(" · ") || "—",
    },
    { label: "Branch head", status: head, tone: headTone, detail: `${short(entry.head)} ↔ ${short(entry.candidate)}` },
    { label: "Target", status: target, tone: targetTone, detail: entry.integration_ref ?? short(entry.target) },
  ];
}

export const passes = (row: Check) => row.status === "ok" || row.status === "ready";

/** The reasons a PR is not ready: the gate refusals, then every preflight row that is not ok. */
export const blockingReasons = (entry: PublishEntry): string[] => [
  ...entry.refusals,
  ...preflightRows(entry)
    .filter((row) => !passes(row))
    .map((row) => row.label),
];
