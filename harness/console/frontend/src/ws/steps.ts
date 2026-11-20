/* The live step list of the steps.subscribe protocol: the roster of followed dispatches and the
   agent and orchestration steps of one feed. The server allowlists every field; the client only
   checks the shapes, holds the newest steps and filters them by dispatch and role. */
import type { AgentStep, OrchestrationStep, RosterDispatch } from "./protocol.gen";

export type { AgentStep, OrchestrationStep, RosterDispatch };
export type Step = AgentStep | OrchestrationStep;

/** The newest steps the list holds; older ones drop off. */
export const MAX_STEPS = 500;

/** What the list shows for a step's structure (catalog.json translates it). */
export const STRUCTURE_LABELS: Readonly<Record<AgentStep["structure"], string>> = {
  available: "структура доступна",
  unavailable: "структура недоступна",
};

/** The Russian text of each orchestration event; the placeholders come from the step. */
export const EVENT_LABELS: Readonly<Record<OrchestrationStep["event"], string>> = {
  "batch.transition": "Пакет {batch}: {from} → {to}",
  "dispatch.transition": "Dispatch {dispatch}: {from} → {to}",
  "gate.decision": "Гейт {dispatch}: {decision}",
  "qa.run": "Прогон QA {dispatch}: {outcome}",
  "qa.attempt": "Попытка QA {dispatch} не прошла этап {stage}",
};

export type StepsEvent =
  | {
      type: "roster";
      reset: boolean;
      orchestration: "available" | "unavailable";
      dispatches: RosterDispatch[];
    }
  | { type: "steps"; steps: Step[] }
  | { type: "steps-error"; code: string; message: string };

export interface HeldStep {
  /** A client-side key, unique within the list. */
  key: number;
  step: Step;
}

export interface StepsState {
  dispatches: RosterDispatch[];
  /** null until the first roster arrives. */
  orchestration: "available" | "unavailable" | null;
  steps: HeldStep[];
  next: number;
}

export const EMPTY_STEPS: StepsState = { dispatches: [], orchestration: null, steps: [], next: 0 };

export interface StepFilter {
  dispatch: string | null;
  role: string | null;
}

const isObject = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const isText = (value: unknown): value is string => typeof value === "string";
const isOptionalText = (value: unknown): value is string | null => value === null || isText(value);

const AGENT_FIELDS = [
  "origin",
  "dispatch_id",
  "batch_id",
  "role",
  "source",
  "structure",
  "kind",
  "text",
  "observed_at",
];
const ORCHESTRATION_TEXT = [
  "batch_id",
  "dispatch_id",
  "ticket",
  "role",
  "from_state",
  "to_state",
  "decision",
  "next_role",
  "outcome",
  "stage",
];

/** Exactly the allowlisted fields: a step with any other field is refused. */
function parseStep(value: unknown): Step | null {
  if (!isObject(value)) return null;
  if (value.origin === "agent") {
    const keys = Object.keys(value);
    if (keys.length !== AGENT_FIELDS.length || !AGENT_FIELDS.every((key) => key in value)) return null;
    if (!AGENT_FIELDS.every((key) => isText(value[key]))) return null;
    if (value.source !== "structured" && value.source !== "plain") return null;
    if (value.structure !== "available" && value.structure !== "unavailable") return null;
    return value as unknown as AgentStep;
  }
  if (value.origin === "orchestration") {
    const fields = ["origin", "seq", "observed_at", "event", "message", ...ORCHESTRATION_TEXT];
    if (Object.keys(value).length !== fields.length || !fields.every((key) => key in value)) return null;
    if (typeof value.seq !== "number" || !isText(value.observed_at) || !isText(value.message)) return null;
    if (!(typeof value.event === "string" && value.event in EVENT_LABELS)) return null;
    if (!ORCHESTRATION_TEXT.every((key) => isOptionalText(value[key]))) return null;
    return value as unknown as OrchestrationStep;
  }
  return null;
}

function parseDispatch(value: unknown): RosterDispatch | null {
  if (!isObject(value)) return null;
  const fields = [
    "dispatch_id",
    "batch_id",
    "ticket",
    "role",
    "state",
    "batch_state",
    "branch",
    "started_at",
    "last_event_at",
  ];
  if (Object.keys(value).length !== fields.length + 2 || typeof value.silent !== "boolean") return null;
  if (!(value.observation === null || isObservation(value.observation))) return null;
  return fields.every((key) => isText(value[key])) ? (value as unknown as RosterDispatch) : null;
}

/** The ledger facts of an in-process dispatch: its stream reason, heartbeat, self-report and
    newest checkpoints of the count it recorded, each with exactly the allowlisted fields. */
function isObservation(value: unknown): boolean {
  if (!isObject(value) || Object.keys(value).length !== 5) return false;
  const { stream_reason, heartbeat_at, self_report, checkpoints, checkpoint_count } = value;
  if (!isText(stream_reason) || !isText(heartbeat_at) || !Array.isArray(checkpoints)) return false;
  if (typeof checkpoint_count !== "number" || checkpoint_count < checkpoints.length) return false;
  const report =
    self_report === null ||
    (isObject(self_report) &&
      Object.keys(self_report).length === 3 &&
      isText(self_report.reported_model) &&
      typeof self_report.match === "boolean" &&
      isText(self_report.reported_at));
  return (
    report &&
    checkpoints.every(
      (item) =>
        isObject(item) &&
        Object.keys(item).length === 3 &&
        isText(item.checkpoint_id) &&
        isText(item.commit_sha) &&
        isText(item.created_at),
    )
  );
}

/** The event of one ok steps.subscribe reply; null for a reply of another shape. */
export function parseStepsReply(reply: Record<string, unknown>): StepsEvent | null {
  if (reply.kind === "roster") {
    const { reset, orchestration, dispatches } = reply;
    if (typeof reset !== "boolean" || !Array.isArray(dispatches)) return null;
    if (orchestration !== "available" && orchestration !== "unavailable") return null;
    const parsed = dispatches.map(parseDispatch);
    if (!parsed.every((entry) => entry !== null)) return null;
    return { type: "roster", reset, orchestration, dispatches: parsed as RosterDispatch[] };
  }
  if (reply.kind === "steps" && Array.isArray(reply.steps)) {
    const parsed = reply.steps.map(parseStep);
    return parsed.every((step) => step !== null) ? { type: "steps", steps: parsed as Step[] } : null;
  }
  return null;
}

/** A roster with `reset` drops the held steps: the server sends the backlog again. */
export function reduceSteps(state: StepsState, event: StepsEvent): StepsState {
  if (event.type === "roster") {
    return {
      ...state,
      dispatches: event.dispatches,
      orchestration: event.orchestration,
      steps: event.reset ? [] : state.steps,
    };
  }
  if (event.type === "steps") {
    const added = event.steps.map((step, index) => ({ key: state.next + index, step }));
    return {
      ...state,
      steps: [...state.steps, ...added].slice(-MAX_STEPS),
      next: state.next + added.length,
    };
  }
  return state;
}

export function filterSteps(steps: readonly HeldStep[], filter: StepFilter): HeldStep[] {
  return steps.filter(
    ({ step }) =>
      (filter.dispatch === null || step.dispatch_id === filter.dispatch) &&
      (filter.role === null || step.role === filter.role),
  );
}

/** The roles of the roster, each once, in roster order. */
export function rosterRoles(dispatches: readonly RosterDispatch[]): string[] {
  return [...new Set(dispatches.map((entry) => entry.role).filter((role) => role !== ""))];
}

type Translate = (text: string, values?: Readonly<Record<string, string | number>>) => string;

/** The translated text of an orchestration step. */
export function eventText(step: OrchestrationStep, t: Translate): string {
  const dash = "—";
  return t(EVENT_LABELS[step.event], {
    batch: step.batch_id ?? dash,
    dispatch: step.dispatch_id ?? dash,
    from: step.from_state ?? dash,
    to: step.to_state ?? dash,
    decision: step.decision ?? dash,
    outcome: step.outcome ?? dash,
    stage: step.stage ?? dash,
  });
}
