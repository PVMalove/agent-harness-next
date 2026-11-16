/* The AI advice of «Настройки» (backend/api/protocol/advisor.py): advisor.check reports the CLI
   presence, version and login without a model call; advisor.ask names one parameter (file and path
   only, never a value) and gets the advice or a fallback; advisor.cancel stops an ask of this
   connection. The server bounds an ask by 90 s, so its request waits 100 s here instead of the
   ordinary 30 s. Advice is a hint: the page puts an accepted value into the draft only. */

export type AdvisorProvider = "codex" | "claude";
export const ADVISOR_PROVIDERS: readonly AdvisorProvider[] = ["codex", "claude"];
/** The client wait of an advisor.ask: the server's 90 s bound plus a margin. */
export const ADVICE_TIMEOUT_MS = 100_000;

export interface CliStatus {
  provider: string;
  found: boolean;
  /** Null for a stage the check did not reach. */
  version_supported: boolean | null;
  authorized: boolean | null;
  ready: boolean;
  message: string;
}

export interface Advice {
  value: unknown;
  why: string;
  impact: string;
  comparison: { option: string; tradeoff: string }[];
}

export type FallbackCause = "refused" | "invalid" | "timeout" | "cancelled" | "closed";

export type AdvisorEvent =
  | { type: "advisor-status"; requestId: string; status: CliStatus }
  | { type: "advisor-advice"; requestId: string; advice: Advice }
  | { type: "advisor-fallback"; requestId: string; cause: FallbackCause; reason: string }
  | { type: "advisor-error"; request: "check" | "ask" | "cancel"; requestId: string | null; code: string; message: string };

const object = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const optionalFlag = (value: unknown) => value === null || typeof value === "boolean";

export function parseCliStatus(value: unknown): CliStatus | null {
  if (!object(value)) return null;
  const { provider, found, version_supported, authorized, ready, message } = value;
  if (typeof provider !== "string" || typeof found !== "boolean" || typeof ready !== "boolean" || typeof message !== "string") return null;
  if (!optionalFlag(version_supported) || !optionalFlag(authorized)) return null;
  return value as unknown as CliStatus;
}

export function parseAdvice(value: unknown): Advice | null {
  if (!object(value) || !("value" in value) || typeof value.why !== "string" || typeof value.impact !== "string") return null;
  const rows = value.comparison;
  if (!Array.isArray(rows) || rows.length > 4) return null;
  if (!rows.every((row) => object(row) && typeof row.option === "string" && typeof row.tradeoff === "string")) return null;
  return value as unknown as Advice;
}

type Kind = "check" | "ask" | "cancel";
const TYPES: Readonly<Record<Kind, string>> = { check: "advisor.check", ask: "advisor.ask", cancel: "advisor.cancel" };
const FALLBACK_CAUSES = new Set(["refused", "invalid", "timeout", "cancelled"]);

/** The open advisor requests of one socket. A closed socket ends a pending ask as a fallback. */
export function advisorReader(
  send: (body: Record<string, unknown>, timeoutMs?: number) => string | null,
  settle: (id: string) => void,
  emit: (event: AdvisorEvent) => void,
) {
  const open = new Map<string, Kind>();
  const error = (request: Kind, requestId: string | null, reply: Record<string, unknown>) => {
    const body = object(reply.error) ? reply.error : {};
    emit({
      type: "advisor-error",
      request,
      requestId,
      code: typeof body.code === "string" ? body.code : "unknown",
      message: typeof body.message === "string" ? body.message : "",
    });
  };
  return {
    reset() {
      for (const [id, kind] of open) {
        settle(id);
        if (kind === "ask") emit({ type: "advisor-fallback", requestId: id, cause: "closed", reason: "" });
        else if (kind === "check") emit({ type: "advisor-error", request: "check", requestId: id, code: "closed", message: "" });
      }
      open.clear();
    },
    /** The request id of the check, or null when no socket is open. */
    check(provider: AdvisorProvider): string | null {
      const id = send({ type: TYPES.check, provider });
      if (id !== null) open.set(id, "check");
      return id;
    },
    /** The request id of the ask, or null when no socket is open. */
    ask(provider: AdvisorProvider, file: string, path: readonly string[]): string | null {
      const id = send({ type: TYPES.ask, provider, file, path: [...path] }, ADVICE_TIMEOUT_MS);
      if (id !== null) open.set(id, "ask");
      return id;
    },
    cancel(requestId: string): boolean {
      const id = send({ type: TYPES.cancel, request_id: requestId });
      if (id !== null) open.set(id, "cancel");
      return id !== null;
    },
    reply(reply: Record<string, unknown>): boolean {
      const id = reply.id;
      if (typeof id !== "string" || !open.has(id)) return false;
      const kind = open.get(id)!;
      open.delete(id);
      settle(id);
      if (reply.type !== TYPES[kind] || reply.ok !== true) {
        error(kind, kind === "cancel" ? null : id, reply);
        return true;
      }
      if (kind === "check") {
        const status = parseCliStatus(reply.status);
        if (status) emit({ type: "advisor-status", requestId: id, status });
        else emit({ type: "advisor-error", request: kind, requestId: id, code: "invalid", message: "" });
      } else if (kind === "ask") {
        const advice = reply.outcome === "advice" ? parseAdvice(reply.advice) : null;
        if (advice) emit({ type: "advisor-advice", requestId: id, advice });
        else if (reply.outcome === "fallback" && typeof reply.cause === "string" && FALLBACK_CAUSES.has(reply.cause) && typeof reply.reason === "string")
          emit({ type: "advisor-fallback", requestId: id, cause: reply.cause as FallbackCause, reason: reply.reason });
        else emit({ type: "advisor-fallback", requestId: id, cause: "invalid", reason: "" });
      }
      return true;
    },
  };
}
