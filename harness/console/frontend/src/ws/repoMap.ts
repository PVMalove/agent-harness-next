/* Read models of repo_map.snapshot. Keep the wire fields, including provenance, for export. */
import type { RepoMapSnapshotRequest, SnapshotPageRequest } from "./protocol.gen";
export interface MapFile { path: string; signatures?: string[]; parser_status?: string }
export interface MapEdge { source: string; target: string; kind: string; confidence: string }
export interface RepoMap {
  schema_version: 1; commit: string; tier: "minimal" | "full"; parser: string;
  degradation_reason: string; estimated_tokens: number; token_estimator_version: string;
  parser_provenance: Record<string, unknown>;
  files: MapFile[]; edges: MapEdge[]; diagnostics: { code: string; path: string }[];
}
export interface RepoMapFacts {
  head: string | null; map: RepoMap | null;
  tier: { tier: string; editable: boolean; reason: string };
  memory: { enabled: boolean; active: boolean; source_types: string[]; indexed: number | null;
    problem: string; inactive: string; top_k: number | null; max_tokens: number | null };
  parsers: { registry: string; pair: string | null; source: string | null;
    grammars: string[]; problem: string | null } | null;
  language_files: Record<string, number>;
}

const object = (v: unknown): v is Record<string, unknown> =>
  v !== null && typeof v === "object" && !Array.isArray(v);
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every((x) => typeof x === "string");
const integer = (v: unknown): v is number => Number.isSafeInteger(v) && Number(v) >= 0;
const optionalString = (v: unknown) => v === null || typeof v === "string";
const optionalInt = (v: unknown) => v === null || integer(v);

/** Reject malformed displayed fields; the server validates the full Repo Map v1 schema. */
export function parseRepoMap(v: unknown): RepoMap | null {
  if (!object(v) || v.schema_version !== 1 || typeof v.commit !== "string" || v.commit.length < 40 ||
      !["full", "minimal"].includes(String(v.tier)) || !["bundle", "path-only"].includes(String(v.parser)) ||
      typeof v.degradation_reason !== "string" || typeof v.token_estimator_version !== "string" ||
      !integer(v.estimated_tokens) || !object(v.parser_provenance) ||
      !Array.isArray(v.files) || !v.files.every((f) => object(f) && typeof f.path === "string" &&
        (f.signatures === undefined || strings(f.signatures)) && (f.parser_status === undefined ||
          ["ok", "syntax_error", "invalid_encoding", "too_large"].includes(String(f.parser_status)))) ||
      !Array.isArray(v.edges) || !v.edges.every((e) => object(e) && typeof e.source === "string" &&
        typeof e.target === "string" && ["import", "unique-name-ref", "ambiguous-name-ref"].includes(String(e.kind)) &&
        ["high", "medium", "low"].includes(String(e.confidence))) ||
      !Array.isArray(v.diagnostics) || !v.diagnostics.every((d) => object(d) &&
        typeof d.code === "string" && typeof d.path === "string")) return null;
  return v as unknown as RepoMap;
}

export function parseRepoMapFacts(v: unknown): RepoMapFacts | null {
  if (!object(v) || !optionalString(v.head) || (v.map !== null && !parseRepoMap(v.map)) ||
      !object(v.tier) || typeof v.tier.tier !== "string" || typeof v.tier.editable !== "boolean" ||
      typeof v.tier.reason !== "string" || !object(v.memory)) return null;
  const m = v.memory;
  if (typeof m.enabled !== "boolean" || typeof m.active !== "boolean" || !strings(m.source_types) ||
      !optionalInt(m.indexed) || typeof m.problem !== "string" || typeof m.inactive !== "string" ||
      !optionalInt(m.top_k) || !optionalInt(m.max_tokens) || !object(v.language_files) ||
      !Object.values(v.language_files).every(integer)) return null;
  const p = v.parsers;
  if (p !== null && (!object(p) || typeof p.registry !== "string" || !optionalString(p.pair) ||
      !optionalString(p.source) || !optionalString(p.problem) || !strings(p.grammars))) return null;
  const facts = v as unknown as RepoMapFacts;
  if (facts.map !== null && facts.map.commit !== facts.head) return null;
  return facts;
}

export type RepoMapEvent = { type: "facts"; facts: RepoMapFacts; cached: boolean; ageSeconds: number }
  | { type: "repo-map-error"; code: string };

/** One paged read at a time. Superseded replies are ignored; reconnect starts a fresh read. */
export function repoMapReader(send: (body: Record<string, unknown>) => string | null,
  settle: (id: string) => void, emit: (event: RepoMapEvent) => void) {
  let held: { id: string; type: string; snapshotId: number; text: string; offset: number;
    cached: boolean; age: number } | null = null;
  const reset = () => { if (held) settle(held.id); held = null; };
  const fail = (code: string) => { reset(); emit({ type: "repo-map-error", code }); };
  return {
    reset,
    request(force = false): boolean {
      reset();
      const request: RepoMapSnapshotRequest = { type: "repo_map.snapshot", force };
      const id = send({ ...request });
      if (id === null) return false;
      held = { id, type: "repo_map.snapshot", snapshotId: 0, text: "", offset: 0, cached: false, age: 0 };
      return true;
    },
    reply(reply: Record<string, unknown>): boolean {
      if (!held || reply.id !== held.id) return false;
      settle(held.id);
      if (reply.type !== held.type) { fail("invalid"); return true; }
      if (reply.ok !== true) {
        fail(object(reply.error) && typeof reply.error.code === "string" ? reply.error.code : "unknown");
        return true;
      }
      if (held.type === "repo_map.snapshot") {
        if (!integer(reply.snapshot_id) || typeof reply.cached !== "boolean" ||
            typeof reply.age_seconds !== "number" || !Number.isFinite(reply.age_seconds) || reply.age_seconds < 0) {
          fail("invalid"); return true;
        }
        held.snapshotId = reply.snapshot_id; held.cached = reply.cached; held.age = reply.age_seconds;
      }
      if (typeof reply.text !== "string" || !integer(reply.next) || typeof reply.done !== "boolean" ||
          (!reply.done && reply.next <= held.offset) || held.text.length + reply.text.length > 32 * 1024 * 1024) {
        fail("invalid"); return true;
      }
      held.text += reply.text; held.offset = reply.next;
      if (reply.done) {
        let facts: RepoMapFacts | null = null;
        try { facts = parseRepoMapFacts(JSON.parse(held.text)); } catch { /* Invalid JSON is a typed error. */ }
        if (facts) {
          const event = { type: "facts", facts, cached: held.cached, ageSeconds: held.age } as const;
          reset(); emit(event);
        } else fail("invalid");
      } else {
        const request: SnapshotPageRequest = { type: "snapshot.page", snapshot_id: held.snapshotId, offset: held.offset };
        const id = send({ ...request });
        if (id === null) reset();
        else { held.id = id; held.type = "snapshot.page"; }
      }
      return true;
    },
  };
}
