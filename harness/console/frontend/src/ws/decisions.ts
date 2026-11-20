/* Pending choices are read models, never authority. The server rechecks every job command. */
export interface DecisionItem {
  kind: string;
  batch_id: string;
  dispatch_id: string | null;
  ticket: string;
  role: string | null;
  reversibility: string;
  command_ids: string[];
  values: Record<string, string>;
  details: Record<string, string>;
}

export interface DecisionsSnapshot {
  version: 1;
  items: DecisionItem[];
  total: number;
  unavailable: boolean;
  error_code?: string;
}

export type DecisionsEvent = { type: "decisions"; snapshot: DecisionsSnapshot }
  | { type: "decisions-error"; code: string };

const object = (v: unknown): v is Record<string, unknown> =>
  v !== null && typeof v === "object" && !Array.isArray(v);
const strings = (v: unknown): v is Record<string, string> =>
  object(v) && Object.values(v).every((value) => typeof value === "string");
const nullable = (v: unknown) => v === null || typeof v === "string";

export function parseDecisions(value: unknown): DecisionsSnapshot | null {
  if (!object(value) || value.version !== 1 || !Number.isSafeInteger(value.total) ||
      Number(value.total) < 0 || typeof value.unavailable !== "boolean" ||
      (value.error_code !== undefined && typeof value.error_code !== "string") ||
      !Array.isArray(value.items) || value.items.length > 32 || Number(value.total) < value.items.length ||
      !value.items.every((item) => object(item) && typeof item.kind === "string" &&
        typeof item.batch_id === "string" && nullable(item.dispatch_id) &&
        typeof item.ticket === "string" && nullable(item.role) && typeof item.reversibility === "string" &&
        Array.isArray(item.command_ids) && item.command_ids.every((id) => typeof id === "string") &&
        strings(item.values) && strings(item.details))) return null;
  return value as unknown as DecisionsSnapshot;
}

/** One read at a time. A disconnect cancels the read, never a choice. */
export function decisionsReader(send: (body: Record<string, unknown>) => string | null,
  settle: (id: string) => void, emit: (event: DecisionsEvent) => void) {
  let held: string | null = null;
  const reset = () => { if (held !== null) settle(held); held = null; };
  return {
    reset,
    request(): boolean {
      if (held !== null) return true;
      held = send({ type: "decisions.snapshot" });
      return held !== null;
    },
    reply(reply: Record<string, unknown>): boolean {
      if (held === null || reply.id !== held) return false;
      reset();
      if (reply.type !== "decisions.snapshot") emit({ type: "decisions-error", code: "invalid" });
      else if (reply.ok !== true) emit({ type: "decisions-error",
        code: object(reply.error) && typeof reply.error.code === "string" ? reply.error.code : "unknown" });
      else {
        const snapshot = parseDecisions(reply.snapshot);
        emit(snapshot ? { type: "decisions", snapshot } : { type: "decisions-error", code: "invalid" });
      }
      return true;
    },
  };
}
