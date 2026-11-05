/* Generated from harness/console/backend/api/ws-schema.json by scripts/gen-protocol.mjs.
   Do not edit: run `npm run gen:protocol` in harness/console/frontend. */

/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ConsoleReply".
 */
export type ConsoleReply =
  | ErrorReply
  | HomeSnapshotReply
  | HomeProblemsReply
  | JobListReply
  | JobReply
  | DecisionsSnapshotReply
  | OrchestrationSourceReply
  | OrchestrationEventsReply;
export type Code = string;
export type JobId = string | null;
export type Message = string;
export type Id = string | number | null;
export type Ok = false;
export type Type = string | null;
export type V = 1;
export type AgeSeconds = number;
export type Cached = boolean;
export type Id1 = string | number | null;
export type Ok1 = true;
export type ProblemsSnapshotId = number | null;
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JsonValue".
 */
export type JsonValue = unknown | undefined;
export type Type1 = "home.snapshot";
export type V1 = 1;
export type Done = boolean;
export type Id2 = string | number | null;
export type Next = number;
export type Ok2 = true;
export type Text = string;
export type Type2 = "home.problems";
export type V2 = 1;
export type Id3 = string | number | null;
export type CommandId = string;
export type Cursor = number;
export type Done1 = boolean;
export type Error = string | null;
export type Id4 = string;
export type Phase = "running" | "completed" | "failed" | "cancelled";
export type Returncode = number | null;
export type Truncated = boolean;
export type Jobs = JobSummary[];
export type Ok3 = true;
export type Type3 = "job.list";
export type V3 = 1;
export type Id5 = string | number | null;
export type Ok4 = true;
export type Type4 = "job.start" | "job.get" | "job.subscribe" | "job.cancel";
export type V4 = 1;
export type Id6 = string | number | null;
export type Ok5 = true;
export type Type5 = "decisions.snapshot";
export type V5 = 1;
export type Cursor1 = string | null;
export type Id7 = string | number | null;
export type Kind = "source";
export type Ok6 = true;
export type Source = {
  [k: string]: JsonValue | undefined;
} | null;
export type Type6 = "orchestration.subscribe";
export type V6 = 1;
export type Cursor2 = string;
export type Events = JsonValue | undefined[];
export type Id8 = string | number | null;
export type Kind1 = "events";
export type Ok7 = true;
export type Type7 = "orchestration.subscribe";
export type V7 = 1;
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ConsoleRequest".
 */
export type ConsoleRequest =
  | HomeSnapshotRequest
  | HomeProblemsRequest
  | JobStartRequest
  | JobGetRequest
  | JobSubscribeRequest
  | JobCancelRequest
  | JobListRequest
  | DecisionsSnapshotRequest
  | OrchestrationSubscribeRequest;
export type Force = boolean;
export type Id9 = string | number | null;
export type Online = boolean;
export type Type8 = "home.snapshot";
export type Id10 = string | number | null;
export type Offset = number;
export type SnapshotId = number;
export type Type9 = "home.problems";
export type Client = string;
export type CommandId1 = string;
export type Confirmation = string | null;
export type Confirmed = boolean;
export type Id11 = string | number | null;
export type PlanDigest = string | null;
export type Type10 = "job.start";
export type Cursor3 = number;
export type Id12 = string | number | null;
export type JobId1 = string;
export type Type11 = "job.get";
export type Cursor4 = number;
export type Id13 = string | number | null;
export type JobId2 = string;
export type Type12 = "job.subscribe";
export type Confirmed1 = boolean;
export type Id14 = string | number | null;
export type JobId3 = string;
export type Type13 = "job.cancel";
export type Id15 = string | number | null;
export type Type14 = "job.list";
export type Id16 = string | number | null;
export type Type15 = "decisions.snapshot";
export type Cursor5 = string | null;
export type Id17 = string | number | null;
export type Type16 = "orchestration.subscribe";

/**
 * Text frames on /ws: one request object per frame, replies by id.
 */
export interface ConsoleWebSocketProtocol {
  [k: string]: unknown | undefined;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ErrorReply".
 */
export interface ErrorReply {
  error: ErrorBody;
  id: Id;
  ok: Ok;
  type: Type;
  v: V;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ErrorBody".
 */
export interface ErrorBody {
  code: Code;
  job_id?: JobId;
  message: Message;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HomeSnapshotReply".
 */
export interface HomeSnapshotReply {
  age_seconds: AgeSeconds;
  cached: Cached;
  id: Id1;
  ok: Ok1;
  problems_snapshot_id?: ProblemsSnapshotId;
  snapshot: Snapshot;
  type: Type1;
  v: V1;
}
export interface Snapshot {
  [k: string]: JsonValue | undefined;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HomeProblemsReply".
 */
export interface HomeProblemsReply {
  done: Done;
  id: Id2;
  next: Next;
  ok: Ok2;
  text: Text;
  type: Type2;
  v: V2;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobListReply".
 */
export interface JobListReply {
  id: Id3;
  jobs: Jobs;
  ok: Ok3;
  type: Type3;
  v: V3;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobSummary".
 */
export interface JobSummary {
  command_id: CommandId;
  cursor: Cursor;
  done: Done1;
  error: Error;
  id: Id4;
  phase: Phase;
  returncode: Returncode;
  truncated: Truncated;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobReply".
 */
export interface JobReply {
  id: Id5;
  job: Job;
  ok: Ok4;
  type: Type4;
  v: V4;
}
export interface Job {
  [k: string]: JsonValue | undefined;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "DecisionsSnapshotReply".
 */
export interface DecisionsSnapshotReply {
  id: Id6;
  ok: Ok5;
  snapshot: Snapshot1;
  type: Type5;
  v: V5;
}
export interface Snapshot1 {
  [k: string]: JsonValue | undefined;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationSourceReply".
 */
export interface OrchestrationSourceReply {
  cursor: Cursor1;
  id: Id7;
  kind: Kind;
  ok: Ok6;
  source: Source;
  type: Type6;
  v: V6;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationEventsReply".
 */
export interface OrchestrationEventsReply {
  cursor: Cursor2;
  events: Events;
  id: Id8;
  kind: Kind1;
  ok: Ok7;
  type: Type7;
  v: V7;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HomeSnapshotRequest".
 */
export interface HomeSnapshotRequest {
  force?: Force;
  id?: Id9;
  online?: Online;
  type: Type8;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HomeProblemsRequest".
 */
export interface HomeProblemsRequest {
  id?: Id10;
  offset: Offset;
  snapshot_id: SnapshotId;
  type: Type9;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobStartRequest".
 */
export interface JobStartRequest {
  client?: Client;
  command_id: CommandId1;
  confirmation?: Confirmation;
  confirmed?: Confirmed;
  id?: Id11;
  plan_digest?: PlanDigest;
  type: Type10;
  values?: Values;
}
export interface Values {
  [k: string]: JsonValue | undefined;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobGetRequest".
 */
export interface JobGetRequest {
  cursor?: Cursor3;
  id?: Id12;
  job_id: JobId1;
  type: Type11;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobSubscribeRequest".
 */
export interface JobSubscribeRequest {
  cursor?: Cursor4;
  id?: Id13;
  job_id: JobId2;
  type: Type12;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobCancelRequest".
 */
export interface JobCancelRequest {
  confirmed?: Confirmed1;
  id?: Id14;
  job_id: JobId3;
  type: Type13;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobListRequest".
 */
export interface JobListRequest {
  id?: Id15;
  type: Type14;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "DecisionsSnapshotRequest".
 */
export interface DecisionsSnapshotRequest {
  id?: Id16;
  type: Type15;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationSubscribeRequest".
 */
export interface OrchestrationSubscribeRequest {
  cursor?: Cursor5;
  id?: Id17;
  type: Type16;
}
