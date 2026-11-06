/* Generated from harness/console/backend/api/ws-schema.json by scripts/gen-protocol.mjs.
   Do not edit: run `npm run gen:protocol` in harness/console/frontend. */

export type Available = boolean;
export type CommandId = string;
export type ConfirmationReason = string | null;
export type Inputs = string[];
export type NeedsConfirmation = boolean;
export type PlanRequired = boolean;
export type ReadOnly = boolean;
export type Reversibility =
  | "reversible"
  | "deletes-local-data"
  | "terminal-coordinator-action"
  | "external-change"
  | "overwrites-managed-files"
  | "downloads-files";
export type ReversibilityLabel = string;
export type Section = "harness" | "diagnostics" | "repo-map" | "setup" | "configuration" | "memory";
export type Title = string;
export type TypedConfirmation = string | null;
export type Force = boolean;
export type Id = string | number | null;
export type Type = "configuration.snapshot";
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ConsoleReply".
 */
export type ConsoleReply =
  | ErrorReply
  | HomeSnapshotReply
  | HomeProblemsReply
  | JobListReply
  | JobCatalogReply
  | JobReply
  | DecisionsSnapshotReply
  | OrchestrationSourceReply
  | OrchestrationEventsReply
  | ScreenSnapshotReply
  | PagedReply
  | SnapshotPageReply
  | OrchestrationLockReply
  | WorkerStepsReply;
export type Code = string;
export type JobId = string | null;
export type Message = string;
export type Id1 = string | number | null;
export type Ok = false;
export type Type1 = string | null;
export type V = 1;
export type AgeSeconds = number;
export type Cached = boolean;
export type Id2 = string | number | null;
export type Ok1 = true;
export type ProblemsSnapshotId = number | null;
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JsonValue".
 */
export type JsonValue = unknown | undefined;
export type Type2 = "home.snapshot";
export type V1 = 1;
export type Done = boolean;
export type Id3 = string | number | null;
export type Next = number;
export type Ok2 = true;
export type Text = string;
export type Type3 = "home.problems";
export type V2 = 1;
export type Id4 = string | number | null;
export type CommandId1 = string;
export type Cursor = number;
export type Done1 = boolean;
export type Error = string | null;
export type Id5 = string;
export type Mutating = boolean;
export type Phase = "running" | "completed" | "failed" | "cancelled";
export type Returncode = number | null;
export type Truncated = boolean;
export type Jobs = JobSummary[];
export type Ok3 = true;
export type Type4 = "job.list";
export type V3 = 1;
export type CancelReason = string;
export type Commands = CommandDescriptor[];
export type Id6 = string | number | null;
export type Ok4 = true;
export type Type5 = "job.catalog";
export type V4 = 1;
export type Id7 = string | number | null;
export type Ok5 = true;
export type Type6 = "job.start" | "job.get" | "job.subscribe" | "job.cancel";
export type V5 = 1;
export type Id8 = string | number | null;
export type Ok6 = true;
export type Type7 = "decisions.snapshot";
export type V6 = 1;
export type Cursor1 = string | null;
export type Id9 = string | number | null;
export type Kind = "source";
export type Ok7 = true;
export type Source = {
  [k: string]: JsonValue | undefined;
} | null;
export type Type8 = "orchestration.subscribe";
export type V7 = 1;
export type Cursor2 = string;
export type Events = JsonValue | undefined[];
export type Id10 = string | number | null;
export type Kind1 = "events";
export type Ok8 = true;
export type Type9 = "orchestration.subscribe";
export type V8 = 1;
export type AgeSeconds1 = number;
export type Cached1 = boolean;
export type Done2 = boolean;
export type Id11 = string | number | null;
export type Next1 = number;
export type Ok9 = true;
export type SnapshotId = number;
export type Text1 = string;
export type Type10 =
  | "reports.snapshot"
  | "orchestration.snapshot"
  | "recovery.snapshot"
  | "container_route.snapshot"
  | "task_board.specs"
  | "task_board.snapshot"
  | "diagnostics.snapshot"
  | "harness.snapshot"
  | "harness.maintenance"
  | "repo_map.snapshot"
  | "open_project.snapshot"
  | "help.snapshot"
  | "update_harness.snapshot"
  | "configuration.snapshot";
export type V9 = 1;
export type Done3 = boolean;
export type Id12 = string | number | null;
export type Next2 = number;
export type Ok10 = true;
export type SnapshotId1 = number;
export type Text2 = string;
export type Type11 = "reports.report" | "reports.timeline" | "update_harness.diff";
export type V10 = 1;
export type Done4 = boolean;
export type Id13 = string | number | null;
export type Next3 = number;
export type Ok11 = true;
export type Text3 = string;
export type Type12 = "snapshot.page";
export type V11 = 1;
export type Error1 = string | null;
export type Id14 = string | number | null;
export type Lock = {
  [k: string]: JsonValue | undefined;
} | null;
export type Ok12 = true;
export type Type13 = "orchestration.lock";
export type V12 = 1;
export type Id15 = string | number | null;
export type Ok13 = true;
export type DispatchId = string;
export type LastStepAgeSeconds = number | null;
export type Message1 = string;
export type More = boolean;
export type Offset = number;
export type Reason = ("no_log" | "log_missing" | "log_unreadable" | "log_outside_storage" | "log_unrecognised") | null;
export type Reset = boolean;
export type Source1 = "structured" | "plain" | "none";
export type State = "connected" | "waiting" | "unavailable";
export type Kind2 = string;
export type Text4 = string;
export type Steps = WorkerStep[];
export type Structure = "available" | "unavailable";
export type Type14 = "worker.steps" | "worker.subscribe";
export type V13 = 1;
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
  | JobCatalogRequest
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
  | DiagnosticsSnapshotRequest
  | HarnessSnapshotRequest
  | HarnessMaintenanceRequest
  | RepoMapSnapshotRequest
  | OpenProjectSnapshotRequest
  | HelpSnapshotRequest
  | UpdateHarnessSnapshotRequest
  | UpdateHarnessDiffRequest
  | ConfigurationSnapshotRequest
  | SnapshotPageRequest
  | WorkerStepsRequest
  | WorkerSubscribeRequest;
export type Force1 = boolean;
export type Id16 = string | number | null;
export type Online = boolean;
export type Type15 = "home.snapshot";
export type Id17 = string | number | null;
export type Offset1 = number;
export type SnapshotId2 = number;
export type Type16 = "home.problems";
export type Client = string;
export type CommandId2 = string;
export type Confirmation = string | null;
export type Confirmed = boolean;
export type Id18 = string | number | null;
export type PlanDigest = string | null;
export type Type17 = "job.start";
export type Cursor3 = number;
export type Id19 = string | number | null;
export type JobId1 = string;
export type Type18 = "job.get";
export type Cursor4 = number;
export type Id20 = string | number | null;
export type JobId2 = string;
export type Type19 = "job.subscribe";
export type Confirmed1 = boolean;
export type Id21 = string | number | null;
export type JobId3 = string;
export type Type20 = "job.cancel";
export type Id22 = string | number | null;
export type Type21 = "job.list";
export type Id23 = string | number | null;
export type Section1 = "harness" | "diagnostics" | "repo-map" | "setup" | "configuration" | "memory";
export type Type22 = "job.catalog";
export type Id24 = string | number | null;
export type Type23 = "decisions.snapshot";
export type Cursor5 = string | null;
export type Id25 = string | number | null;
export type Type24 = "orchestration.subscribe";
export type Force2 = boolean;
export type Id26 = string | number | null;
export type Online1 = boolean;
export type Type25 = "reports.snapshot";
export type DispatchId1 = string;
export type Id27 = string | number | null;
export type Type26 = "reports.report";
export type BatchId = string;
export type Id28 = string | number | null;
export type Type27 = "reports.timeline";
export type Force3 = boolean;
export type Id29 = string | number | null;
export type Type28 = "orchestration.snapshot";
export type Id30 = string | number | null;
export type Type29 = "orchestration.lock";
export type Batch = string;
export type Force4 = boolean;
export type Id31 = string | number | null;
/**
 * @maxItems 32
 */
export type Skip = string[];
export type Type30 = "recovery.snapshot";
export type Batch1 = string;
export type Id32 = string | number | null;
export type Role = string;
export type Runtime = string;
export type Type31 = "container_route.snapshot";
export type Force5 = boolean;
export type Id33 = string | number | null;
export type Type32 = "task_board.specs";
export type Force6 = boolean;
export type Id34 = string | number | null;
export type Spec = string;
export type Type33 = "task_board.snapshot";
export type Force7 = boolean;
export type Id35 = string | number | null;
export type Online2 = boolean;
export type Type34 = "diagnostics.snapshot";
export type Force8 = boolean;
export type Id36 = string | number | null;
export type Type35 = "harness.snapshot";
export type Force9 = boolean;
export type Id37 = string | number | null;
export type Type36 = "harness.maintenance";
export type Force10 = boolean;
export type Id38 = string | number | null;
export type Type37 = "repo_map.snapshot";
export type Force11 = boolean;
export type Id39 = string | number | null;
export type Type38 = "open_project.snapshot";
export type Id40 = string | number | null;
export type Language = "ru" | "en";
export type Type39 = "help.snapshot";
export type Force12 = boolean;
export type Id41 = string | number | null;
export type Type40 = "update_harness.snapshot";
export type Force13 = boolean;
export type Id42 = string | number | null;
export type Path = string;
export type Type41 = "update_harness.diff";
export type Id43 = string | number | null;
export type Offset2 = number;
export type SnapshotId3 = number;
export type Type42 = "snapshot.page";
export type DispatchId2 = string;
export type Id44 = string | number | null;
export type Offset3 = number;
export type Type43 = "worker.steps";
export type DispatchId3 = string;
export type Id45 = string | number | null;
export type Offset4 = number;
export type Type44 = "worker.subscribe";

/**
 * Text frames on /ws: one request object per frame, replies by id.
 */
export interface ConsoleWebSocketProtocol {
  [k: string]: unknown | undefined;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "CommandDescriptor".
 */
export interface CommandDescriptor {
  available: Available;
  command_id: CommandId;
  confirmation_reason: ConfirmationReason;
  inputs: Inputs;
  needs_confirmation: NeedsConfirmation;
  plan_required: PlanRequired;
  read_only: ReadOnly;
  reversibility: Reversibility;
  reversibility_label: ReversibilityLabel;
  section: Section;
  title: Title;
  typed_confirmation: TypedConfirmation;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ConfigurationSnapshotRequest".
 */
export interface ConfigurationSnapshotRequest {
  force?: Force;
  id?: Id;
  type: Type;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ErrorReply".
 */
export interface ErrorReply {
  error: ErrorBody;
  id: Id1;
  ok: Ok;
  type: Type1;
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
  id: Id2;
  ok: Ok1;
  problems_snapshot_id?: ProblemsSnapshotId;
  snapshot: Snapshot;
  type: Type2;
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
  id: Id3;
  next: Next;
  ok: Ok2;
  text: Text;
  type: Type3;
  v: V2;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobListReply".
 */
export interface JobListReply {
  id: Id4;
  jobs: Jobs;
  ok: Ok3;
  type: Type4;
  v: V3;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobSummary".
 */
export interface JobSummary {
  command_id: CommandId1;
  cursor: Cursor;
  done: Done1;
  error: Error;
  id: Id5;
  mutating: Mutating;
  phase: Phase;
  returncode: Returncode;
  truncated: Truncated;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobCatalogReply".
 */
export interface JobCatalogReply {
  cancel_reason: CancelReason;
  commands: Commands;
  id: Id6;
  ok: Ok4;
  type: Type5;
  v: V4;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobReply".
 */
export interface JobReply {
  id: Id7;
  job: Job;
  ok: Ok5;
  type: Type6;
  v: V5;
}
export interface Job {
  [k: string]: JsonValue | undefined;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "DecisionsSnapshotReply".
 */
export interface DecisionsSnapshotReply {
  id: Id8;
  ok: Ok6;
  snapshot: Snapshot1;
  type: Type7;
  v: V6;
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
  id: Id9;
  kind: Kind;
  ok: Ok7;
  source: Source;
  type: Type8;
  v: V7;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationEventsReply".
 */
export interface OrchestrationEventsReply {
  cursor: Cursor2;
  events: Events;
  id: Id10;
  kind: Kind1;
  ok: Ok8;
  type: Type9;
  v: V8;
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
  id: Id11;
  next: Next1;
  ok: Ok9;
  snapshot_id: SnapshotId;
  text: Text1;
  type: Type10;
  v: V9;
}
/**
 * The first page of a report body, a batch chronology or an update diff as JSON text.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "PagedReply".
 */
export interface PagedReply {
  done: Done3;
  id: Id12;
  next: Next2;
  ok: Ok10;
  snapshot_id: SnapshotId1;
  text: Text2;
  type: Type11;
  v: V10;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "SnapshotPageReply".
 */
export interface SnapshotPageReply {
  done: Done4;
  id: Id13;
  next: Next3;
  ok: Ok11;
  text: Text3;
  type: Type12;
  v: V11;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationLockReply".
 */
export interface OrchestrationLockReply {
  error: Error1;
  id: Id14;
  lock: Lock;
  ok: Ok12;
  type: Type13;
  v: V12;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "WorkerStepsReply".
 */
export interface WorkerStepsReply {
  id: Id15;
  ok: Ok13;
  page: WorkerStepsPage;
  type: Type14;
  v: V13;
}
/**
 * Allowlisted worker steps from a log byte offset; never thinking, tool inputs or raw JSON.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "WorkerStepsPage".
 */
export interface WorkerStepsPage {
  dispatch_id: DispatchId;
  last_step_age_seconds: LastStepAgeSeconds;
  message: Message1;
  more: More;
  offset: Offset;
  reason: Reason;
  reset: Reset;
  source: Source1;
  state: State;
  steps: Steps;
  structure: Structure;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "WorkerStep".
 */
export interface WorkerStep {
  kind: Kind2;
  text: Text4;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HomeSnapshotRequest".
 */
export interface HomeSnapshotRequest {
  force?: Force1;
  id?: Id16;
  online?: Online;
  type: Type15;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HomeProblemsRequest".
 */
export interface HomeProblemsRequest {
  id?: Id17;
  offset: Offset1;
  snapshot_id: SnapshotId2;
  type: Type16;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobStartRequest".
 */
export interface JobStartRequest {
  client?: Client;
  command_id: CommandId2;
  confirmation?: Confirmation;
  confirmed?: Confirmed;
  id?: Id18;
  plan_digest?: PlanDigest;
  type: Type17;
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
  id?: Id19;
  job_id: JobId1;
  type: Type18;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobSubscribeRequest".
 */
export interface JobSubscribeRequest {
  cursor?: Cursor4;
  id?: Id20;
  job_id: JobId2;
  type: Type19;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobCancelRequest".
 */
export interface JobCancelRequest {
  confirmed?: Confirmed1;
  id?: Id21;
  job_id: JobId3;
  type: Type20;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobListRequest".
 */
export interface JobListRequest {
  id?: Id22;
  type: Type21;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobCatalogRequest".
 */
export interface JobCatalogRequest {
  id?: Id23;
  section: Section1;
  type: Type22;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "DecisionsSnapshotRequest".
 */
export interface DecisionsSnapshotRequest {
  id?: Id24;
  type: Type23;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationSubscribeRequest".
 */
export interface OrchestrationSubscribeRequest {
  cursor?: Cursor5;
  id?: Id25;
  type: Type24;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ReportsSnapshotRequest".
 */
export interface ReportsSnapshotRequest {
  force?: Force2;
  id?: Id26;
  online?: Online1;
  type: Type25;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ReportRequest".
 */
export interface ReportRequest {
  dispatch_id: DispatchId1;
  id?: Id27;
  type: Type26;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "TimelineRequest".
 */
export interface TimelineRequest {
  batch_id: BatchId;
  id?: Id28;
  type: Type27;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationSnapshotRequest".
 */
export interface OrchestrationSnapshotRequest {
  force?: Force3;
  id?: Id29;
  type: Type28;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationLockRequest".
 */
export interface OrchestrationLockRequest {
  id?: Id30;
  type: Type29;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "RecoverySnapshotRequest".
 */
export interface RecoverySnapshotRequest {
  batch?: Batch;
  force?: Force4;
  id?: Id31;
  skip?: Skip;
  type: Type30;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ContainerRouteSnapshotRequest".
 */
export interface ContainerRouteSnapshotRequest {
  batch?: Batch1;
  id?: Id32;
  role?: Role;
  runtime?: Runtime;
  type: Type31;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "TaskBoardSpecsRequest".
 */
export interface TaskBoardSpecsRequest {
  force?: Force5;
  id?: Id33;
  type: Type32;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "TaskBoardSnapshotRequest".
 */
export interface TaskBoardSnapshotRequest {
  force?: Force6;
  id?: Id34;
  spec: Spec;
  type: Type33;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "DiagnosticsSnapshotRequest".
 */
export interface DiagnosticsSnapshotRequest {
  force?: Force7;
  id?: Id35;
  online?: Online2;
  type: Type34;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HarnessSnapshotRequest".
 */
export interface HarnessSnapshotRequest {
  force?: Force8;
  id?: Id36;
  type: Type35;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HarnessMaintenanceRequest".
 */
export interface HarnessMaintenanceRequest {
  force?: Force9;
  id?: Id37;
  type: Type36;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "RepoMapSnapshotRequest".
 */
export interface RepoMapSnapshotRequest {
  force?: Force10;
  id?: Id38;
  type: Type37;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OpenProjectSnapshotRequest".
 */
export interface OpenProjectSnapshotRequest {
  force?: Force11;
  id?: Id39;
  type: Type38;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HelpSnapshotRequest".
 */
export interface HelpSnapshotRequest {
  id?: Id40;
  language: Language;
  type: Type39;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "UpdateHarnessSnapshotRequest".
 */
export interface UpdateHarnessSnapshotRequest {
  force?: Force12;
  id?: Id41;
  type: Type40;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "UpdateHarnessDiffRequest".
 */
export interface UpdateHarnessDiffRequest {
  force?: Force13;
  id?: Id42;
  path: Path;
  type: Type41;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "SnapshotPageRequest".
 */
export interface SnapshotPageRequest {
  id?: Id43;
  offset: Offset2;
  snapshot_id: SnapshotId3;
  type: Type42;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "WorkerStepsRequest".
 */
export interface WorkerStepsRequest {
  dispatch_id: DispatchId2;
  id?: Id44;
  offset: Offset3;
  type: Type43;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "WorkerSubscribeRequest".
 */
export interface WorkerSubscribeRequest {
  dispatch_id: DispatchId3;
  id?: Id45;
  offset?: Offset4;
  type: Type44;
}
