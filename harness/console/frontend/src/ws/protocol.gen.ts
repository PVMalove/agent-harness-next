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
  | OrchestrationEventsReply
  | ScreenSnapshotReply
  | PagedReply
  | SnapshotPageReply
  | OrchestrationLockReply;
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
export type AgeSeconds1 = number;
export type Cached1 = boolean;
export type Done2 = boolean;
export type Id9 = string | number | null;
export type Next1 = number;
export type Ok8 = true;
export type SnapshotId = number;
export type Text1 = string;
export type Type8 =
  | "reports.snapshot"
  | "orchestration.snapshot"
  | "recovery.snapshot"
  | "container_route.snapshot"
  | "task_board.specs"
  | "task_board.snapshot";
export type V8 = 1;
export type Done3 = boolean;
export type Id10 = string | number | null;
export type Next2 = number;
export type Ok9 = true;
export type SnapshotId1 = number;
export type Text2 = string;
export type Type9 = "reports.report" | "reports.timeline";
export type V9 = 1;
export type Done4 = boolean;
export type Id11 = string | number | null;
export type Next3 = number;
export type Ok10 = true;
export type Text3 = string;
export type Type10 = "snapshot.page";
export type V10 = 1;
export type Error1 = string | null;
export type Id12 = string | number | null;
export type Lock = {
  [k: string]: JsonValue | undefined;
} | null;
export type Ok11 = true;
export type Type11 = "orchestration.lock";
export type V11 = 1;
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
  | OrchestrationSubscribeRequest
  | ReportsSnapshotRequest
  | ReportRequest
  | TimelineRequest
  | OrchestrationSnapshotRequest
  | OrchestrationLockRequest
  | RecoverySnapshotRequest
  | ContainerRouteSnapshotRequest
  | TaskBoardSpecsRequest
  | TaskBoardSnapshotRequest
  | SnapshotPageRequest;
export type Force = boolean;
export type Id13 = string | number | null;
export type Online = boolean;
export type Type12 = "home.snapshot";
export type Id14 = string | number | null;
export type Offset = number;
export type SnapshotId2 = number;
export type Type13 = "home.problems";
export type Client = string;
export type CommandId1 = string;
export type Confirmation = string | null;
export type Confirmed = boolean;
export type Id15 = string | number | null;
export type PlanDigest = string | null;
export type Type14 = "job.start";
export type Cursor3 = number;
export type Id16 = string | number | null;
export type JobId1 = string;
export type Type15 = "job.get";
export type Cursor4 = number;
export type Id17 = string | number | null;
export type JobId2 = string;
export type Type16 = "job.subscribe";
export type Confirmed1 = boolean;
export type Id18 = string | number | null;
export type JobId3 = string;
export type Type17 = "job.cancel";
export type Id19 = string | number | null;
export type Type18 = "job.list";
export type Id20 = string | number | null;
export type Type19 = "decisions.snapshot";
export type Cursor5 = string | null;
export type Id21 = string | number | null;
export type Type20 = "orchestration.subscribe";
export type Force1 = boolean;
export type Id22 = string | number | null;
export type Online1 = boolean;
export type Type21 = "reports.snapshot";
export type DispatchId = string;
export type Id23 = string | number | null;
export type Type22 = "reports.report";
export type BatchId = string;
export type Id24 = string | number | null;
export type Type23 = "reports.timeline";
export type Force2 = boolean;
export type Id25 = string | number | null;
export type Type24 = "orchestration.snapshot";
export type Id26 = string | number | null;
export type Type25 = "orchestration.lock";
export type Batch = string;
export type Force3 = boolean;
export type Id27 = string | number | null;
/**
 * @maxItems 32
 */
export type Skip = string[];
export type Type26 = "recovery.snapshot";
export type Batch1 = string;
export type Id28 = string | number | null;
export type Role = string;
export type Runtime = string;
export type Type27 = "container_route.snapshot";
export type Force4 = boolean;
export type Id29 = string | number | null;
export type Type28 = "task_board.specs";
export type Force5 = boolean;
export type Id30 = string | number | null;
export type Spec = string;
export type Type29 = "task_board.snapshot";
export type Id31 = string | number | null;
export type Offset1 = number;
export type SnapshotId3 = number;
export type Type30 = "snapshot.page";

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
 * The first page of a screen snapshot's JSON text; `snapshot.page` reads the rest.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ScreenSnapshotReply".
 */
export interface ScreenSnapshotReply {
  age_seconds: AgeSeconds1;
  cached: Cached1;
  done: Done2;
  id: Id9;
  next: Next1;
  ok: Ok8;
  snapshot_id: SnapshotId;
  text: Text1;
  type: Type8;
  v: V8;
}
/**
 * The first page of a report body or a batch chronology as JSON text.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "PagedReply".
 */
export interface PagedReply {
  done: Done3;
  id: Id10;
  next: Next2;
  ok: Ok9;
  snapshot_id: SnapshotId1;
  text: Text2;
  type: Type9;
  v: V9;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "SnapshotPageReply".
 */
export interface SnapshotPageReply {
  done: Done4;
  id: Id11;
  next: Next3;
  ok: Ok10;
  text: Text3;
  type: Type10;
  v: V10;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationLockReply".
 */
export interface OrchestrationLockReply {
  error: Error1;
  id: Id12;
  lock: Lock;
  ok: Ok11;
  type: Type11;
  v: V11;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HomeSnapshotRequest".
 */
export interface HomeSnapshotRequest {
  force?: Force;
  id?: Id13;
  online?: Online;
  type: Type12;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HomeProblemsRequest".
 */
export interface HomeProblemsRequest {
  id?: Id14;
  offset: Offset;
  snapshot_id: SnapshotId2;
  type: Type13;
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
  id?: Id15;
  plan_digest?: PlanDigest;
  type: Type14;
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
  id?: Id16;
  job_id: JobId1;
  type: Type15;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobSubscribeRequest".
 */
export interface JobSubscribeRequest {
  cursor?: Cursor4;
  id?: Id17;
  job_id: JobId2;
  type: Type16;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobCancelRequest".
 */
export interface JobCancelRequest {
  confirmed?: Confirmed1;
  id?: Id18;
  job_id: JobId3;
  type: Type17;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobListRequest".
 */
export interface JobListRequest {
  id?: Id19;
  type: Type18;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "DecisionsSnapshotRequest".
 */
export interface DecisionsSnapshotRequest {
  id?: Id20;
  type: Type19;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationSubscribeRequest".
 */
export interface OrchestrationSubscribeRequest {
  cursor?: Cursor5;
  id?: Id21;
  type: Type20;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ReportsSnapshotRequest".
 */
export interface ReportsSnapshotRequest {
  force?: Force1;
  id?: Id22;
  online?: Online1;
  type: Type21;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ReportRequest".
 */
export interface ReportRequest {
  dispatch_id: DispatchId;
  id?: Id23;
  type: Type22;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "TimelineRequest".
 */
export interface TimelineRequest {
  batch_id: BatchId;
  id?: Id24;
  type: Type23;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationSnapshotRequest".
 */
export interface OrchestrationSnapshotRequest {
  force?: Force2;
  id?: Id25;
  type: Type24;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationLockRequest".
 */
export interface OrchestrationLockRequest {
  id?: Id26;
  type: Type25;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "RecoverySnapshotRequest".
 */
export interface RecoverySnapshotRequest {
  batch?: Batch;
  force?: Force3;
  id?: Id27;
  skip?: Skip;
  type: Type26;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ContainerRouteSnapshotRequest".
 */
export interface ContainerRouteSnapshotRequest {
  batch?: Batch1;
  id?: Id28;
  role?: Role;
  runtime?: Runtime;
  type: Type27;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "TaskBoardSpecsRequest".
 */
export interface TaskBoardSpecsRequest {
  force?: Force4;
  id?: Id29;
  type: Type28;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "TaskBoardSnapshotRequest".
 */
export interface TaskBoardSnapshotRequest {
  force?: Force5;
  id?: Id30;
  spec: Spec;
  type: Type29;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "SnapshotPageRequest".
 */
export interface SnapshotPageRequest {
  id?: Id31;
  offset: Offset1;
  snapshot_id: SnapshotId3;
  type: Type30;
}
