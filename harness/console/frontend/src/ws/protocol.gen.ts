/* Generated from harness/console/backend/api/ws-schema.json by scripts/gen-protocol.mjs.
   Do not edit: run `npm run gen:protocol` in harness/console/frontend. */

export type Path = string;
export type Problem = string | null;
export type Status = "current" | "outdated" | "missing";
export type Option = string;
export type Tradeoff = string;
/**
 * @maxItems 4
 */
export type Comparison =
  | []
  | [AdviceComparison]
  | [AdviceComparison, AdviceComparison]
  | [AdviceComparison, AdviceComparison, AdviceComparison]
  | [AdviceComparison, AdviceComparison, AdviceComparison, AdviceComparison];
export type Impact = string;
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JsonValue".
 */
export type JsonValue = unknown;
export type Why = string;
export type Id = string | number | null;
export type Ok = true;
export type Outcome = "advice";
export type Type = "advisor.ask";
export type V = 1;
export type File = "project.json" | "orchestration.json";
export type Id1 = string | number;
/**
 * @minItems 1
 * @maxItems 8
 */
export type Path1 =
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string]
  | [string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string];
export type Provider = "codex" | "claude";
export type Type1 = "advisor.ask";
export type Cancelled = boolean;
export type Id2 = string | number | null;
export type Ok1 = true;
export type Type2 = "advisor.cancel";
export type V1 = 1;
export type Id3 = string | number | null;
export type RequestId = string | number;
export type Type3 = "advisor.cancel";
export type Id4 = string | number | null;
export type Ok2 = true;
export type Authorized = boolean | null;
export type Found = boolean;
export type Message = string;
export type Provider1 = string;
export type Ready = boolean;
export type VersionSupported = boolean | null;
export type Type4 = "advisor.check";
export type V2 = 1;
export type Id5 = string | number | null;
export type Provider2 = "codex" | "claude";
export type Type5 = "advisor.check";
export type Cause = "refused" | "invalid" | "timeout" | "cancelled";
export type Id6 = string | number | null;
export type Ok3 = true;
export type Outcome1 = "fallback";
export type Reason = string;
export type Type6 = "advisor.ask";
export type V3 = 1;
export type BatchId = string;
export type DispatchId = string;
export type Kind = string;
export type ObservedAt = string;
export type Origin = "agent";
export type Role = string;
export type Source = "structured" | "plain";
export type Structure = "available" | "unavailable";
export type Text = string;
export type Available = boolean;
export type CommandId = string;
export type ConfirmationReason = string | null;
export type Fields = CoordinatorInput[] | null;
export type Choices = string[] | null;
export type Default = string | null;
export type Dest = string;
export type Flag = string;
export type Help = string;
export type Repeatable = boolean;
export type Required = boolean;
export type TakesValue = boolean;
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
export type Section =
  "harness" | "diagnostics" | "repo-map" | "setup" | "configuration" | "memory" | "decisions" | "recovery" | "update";
export type Title = string;
export type TypedConfirmation = string | null;
export type Force = boolean;
export type Id7 = string | number | null;
export type Type7 = "configuration.snapshot";
export type Version = string | null;
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
  | HarnessOverviewReply
  | FeaturesSnapshotReply
  | PagedReply
  | SnapshotPageReply
  | OrchestrationLockReply
  | WorkerStepsReply
  | StepsRosterReply
  | StepsReply
  | AdvisorCheckReply
  | AdvisorAdviceReply
  | AdvisorFallbackReply
  | AdvisorCancelReply;
export type Code = string;
export type JobId = string | null;
export type Message1 = string;
export type Id8 = string | number | null;
export type Ok4 = false;
export type Type8 = string | null;
export type V4 = 1;
export type EventsPerMinute = number;
export type EventsTotalWindow = number;
export type LastEventAgeSeconds = number | null;
export type EventsPerMinute1 = number;
export type LastEventAgeSeconds1 = number | null;
export type Link = "decision" | "typed" | "write" | "launch" | "audit" | "receipts";
export type Links = LinkActivityPayload[];
export type WindowSeconds = number;
export type AgeSeconds = number;
export type Cached = boolean;
export type Id9 = string | number | null;
export type Ok5 = true;
export type ProblemsSnapshotId = number | null;
export type Type9 = "home.snapshot";
export type V5 = 1;
export type Done = boolean;
export type Id10 = string | number | null;
export type Next = number;
export type Ok6 = true;
export type Text1 = string;
export type Type10 = "home.problems";
export type V6 = 1;
export type Id11 = string | number | null;
export type CommandId1 = string;
export type Cursor = number;
export type Done1 = boolean;
export type Error = string | null;
export type Id12 = string;
export type Mutating = boolean;
export type Phase = "running" | "completed" | "failed" | "cancelled";
export type Returncode = number | null;
export type Truncated = boolean;
export type Jobs = JobSummary[];
export type Ok7 = true;
export type Type11 = "job.list";
export type V7 = 1;
export type CancelReason = string;
export type Commands = CommandDescriptor[];
export type Id13 = string | number | null;
export type Ok8 = true;
export type Type12 = "job.catalog";
export type V8 = 1;
export type Id14 = string | number | null;
export type Ok9 = true;
export type Type13 = "job.start" | "job.get" | "job.subscribe" | "job.cancel";
export type V9 = 1;
export type Id15 = string | number | null;
export type Ok10 = true;
export type Type14 = "decisions.snapshot";
export type V10 = 1;
export type Cursor1 = string | null;
export type Id16 = string | number | null;
export type Kind1 = "source";
export type Ok11 = true;
export type Source1 = {
  [k: string]: JsonValue;
} | null;
export type Type15 = "orchestration.subscribe";
export type V11 = 1;
export type Cursor2 = string;
export type Events = JsonValue[];
export type Id17 = string | number | null;
export type Kind2 = "events";
export type Ok12 = true;
export type Type16 = "orchestration.subscribe";
export type V12 = 1;
export type AgeSeconds1 = number;
export type Cached1 = boolean;
export type Done2 = boolean;
export type Id18 = string | number | null;
export type Next1 = number;
export type Ok13 = true;
export type SnapshotId = number;
export type Text2 = string;
export type Type17 =
  | "reports.snapshot"
  | "orchestration.snapshot"
  | "recovery.snapshot"
  | "container_route.snapshot"
  | "recovery.view"
  | "container_route.view"
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
export type V13 = 1;
export type Adapters = AdapterPayload[] | null;
export type AgeSeconds2 = number;
export type Cached2 = boolean;
export type CgroupDriver = string | null;
export type CgroupVersion = string | null;
export type Engine = string;
export type Images = number | null;
export type ImagesProblem = string | null;
export type InfoProblem = string | null;
export type Rootless = boolean | null;
export type Selinux = boolean | null;
export type Version1 = string | null;
export type Volumes = number | null;
export type VolumesProblem = string | null;
export type Drift = string;
export type DriftFiles = number | null;
export type Id19 = string | number | null;
export type Integrations = IntegrationPayload[] | null;
export type Cli = boolean | null;
export type Detail = string;
export type Kind3 = "runtime" | "tracker";
export type Name = string;
export type Status1 = "current" | "outdated" | "missing" | "unknown";
export type Ok14 = true;
export type PackageVersion = string;
export type Reason1 = string;
export type Revision = number | null;
export type State = "online" | "offline";
export type Capabilities = string[];
export type Installed = boolean;
export type InstalledVersion = string;
export type ManagedFiles = number;
export type Orchestration = boolean;
export type Skills = number;
export type UpdatedAt = string;
export type AuditRecords = number | null;
export type Authority = "file-ledger" | "runtime-store" | "none";
export type CutoverAt = string | null;
export type Generation = string | null;
export type Reason2 = string;
export type Schema = number | null;
export type Type18 = "harness.overview";
export type Batches = number;
export type Dispatches = number;
export type Reports = number;
export type Tickets = number;
export type Unavailable = string | null;
export type V14 = 1;
export type AgeSeconds3 = number;
export type Cached3 = boolean;
export type Category =
  "execution" | "roles" | "hooks" | "context" | "process" | "publication" | "capabilities" | "platform";
export type DependsOn = string[];
export type Description = string;
export type Id20 = string;
export type Name1 = string;
export type OffEffect = string;
export type RequiredBy = string[];
export type Detail1 = string;
export type State1 = "ok" | "warn" | "err";
export type Title1 = string;
export type Requirements = FeatureRequirement[];
export type File1 = "project.json" | "orchestration.json";
export type Path2 = string[];
export type Present = boolean;
export type Value = string | null;
export type Settings = FeatureSetting[];
export type Kind4 =
  "capabilities" | "hook" | "agent" | "project.json" | "orchestration.json" | "harness.lock" | "runtime";
export type Path3 = string;
export type Sources = FeatureSource[];
export type State2 = "working" | "partial" | "not_working" | "disabled";
export type Enabled = boolean;
export type File2 = "project.json" | "orchestration.json";
/**
 * @minItems 1
 */
export type Path4 = [string, ...string[]];
export type RequirementsAfter = FeatureRequirement[];
export type StateAfter = "working" | "partial" | "not_working" | "disabled";
export type Features = FeaturePayload[];
export type Id21 = string | number | null;
export type Ok15 = true;
export type TransactionPending = boolean;
export type Type19 = "features.snapshot";
export type V15 = 1;
export type Done3 = boolean;
export type Id22 = string | number | null;
export type Next2 = number;
export type Ok16 = true;
export type SnapshotId1 = number;
export type Text3 = string;
export type Type20 = "reports.report" | "reports.timeline" | "update_harness.diff";
export type V16 = 1;
export type Done4 = boolean;
export type Id23 = string | number | null;
export type Next3 = number;
export type Ok17 = true;
export type Text4 = string;
export type Type21 = "snapshot.page";
export type V17 = 1;
export type Error1 = string | null;
export type Id24 = string | number | null;
export type Lock = {
  [k: string]: JsonValue;
} | null;
export type Ok18 = true;
export type Type22 = "orchestration.lock";
export type V18 = 1;
export type Id25 = string | number | null;
export type Ok19 = true;
export type DispatchId1 = string;
export type LastStepAgeSeconds = number | null;
export type Message2 = string;
export type More = boolean;
export type Offset = number;
export type Reason3 = ("no_log" | "log_missing" | "log_unreadable" | "log_outside_storage" | "log_unrecognised") | null;
export type Reset = boolean;
export type Source2 = "structured" | "plain" | "none";
export type State3 = "connected" | "waiting" | "unavailable";
export type Kind5 = string;
export type Text5 = string;
export type Steps = WorkerStep[];
export type Structure1 = "available" | "unavailable";
export type Type23 = "worker.steps" | "worker.subscribe";
export type V19 = 1;
export type BatchId1 = string;
export type BatchState = string;
export type Branch = string;
export type DispatchId2 = string;
export type LastEventAt = string;
export type Role1 = string;
export type Silent = boolean;
export type StartedAt = string;
export type State4 = string;
export type Ticket = string;
export type Dispatches1 = RosterDispatch[];
export type Id26 = string | number | null;
export type Kind6 = "roster";
export type Ok20 = true;
export type Orchestration1 = "available" | "unavailable";
export type Reset1 = boolean;
export type Type24 = "steps.subscribe";
export type V20 = 1;
export type Id27 = string | number | null;
export type Kind7 = "steps";
export type Ok21 = true;
export type BatchId2 = string | null;
export type Decision = string | null;
export type DispatchId3 = string | null;
export type Event = "batch.transition" | "dispatch.transition" | "gate.decision" | "qa.run" | "qa.attempt";
export type FromState = string | null;
export type Message3 = string;
export type NextRole = string | null;
export type ObservedAt1 = string;
export type Origin1 = "orchestration";
export type Outcome2 = string | null;
export type Role2 = string | null;
export type Seq = number;
export type Stage = string | null;
export type Ticket1 = string | null;
export type ToState = string | null;
export type Steps1 = (AgentStep | OrchestrationStep)[];
export type Type25 = "steps.subscribe";
export type V21 = 1;
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
  | RecoveryViewRequest
  | ContainerRouteViewRequest
  | TaskBoardSpecsRequest
  | TaskBoardSnapshotRequest
  | DiagnosticsSnapshotRequest
  | HarnessSnapshotRequest
  | HarnessOverviewRequest
  | FeaturesSnapshotRequest
  | HarnessMaintenanceRequest
  | RepoMapSnapshotRequest
  | OpenProjectSnapshotRequest
  | HelpSnapshotRequest
  | UpdateHarnessSnapshotRequest
  | UpdateHarnessDiffRequest
  | ConfigurationSnapshotRequest
  | AdvisorCheckRequest
  | AdvisorAskRequest
  | AdvisorCancelRequest
  | SnapshotPageRequest
  | WorkerStepsRequest
  | WorkerSubscribeRequest
  | StepsSubscribeRequest;
export type Force1 = boolean;
export type Id28 = string | number | null;
export type Online = boolean;
export type Type26 = "home.snapshot";
export type Id29 = string | number | null;
export type Offset1 = number;
export type SnapshotId2 = number;
export type Type27 = "home.problems";
export type Client = string;
export type CommandId2 = string;
export type Confirmation = string | null;
export type Confirmed = boolean;
export type Id30 = string | number | null;
export type PlanDigest = string | null;
export type Type28 = "job.start";
export type Cursor3 = number;
export type Id31 = string | number | null;
export type JobId1 = string;
export type Type29 = "job.get";
export type Cursor4 = number;
export type Id32 = string | number | null;
export type JobId2 = string;
export type Type30 = "job.subscribe";
export type Confirmed1 = boolean;
export type Id33 = string | number | null;
export type JobId3 = string;
export type Type31 = "job.cancel";
export type Id34 = string | number | null;
export type Type32 = "job.list";
export type Id35 = string | number | null;
export type Section1 =
  "harness" | "diagnostics" | "repo-map" | "setup" | "configuration" | "memory" | "decisions" | "recovery" | "update";
export type Type33 = "job.catalog";
export type Id36 = string | number | null;
export type Type34 = "decisions.snapshot";
export type Cursor5 = string | null;
export type Id37 = string | number | null;
export type Type35 = "orchestration.subscribe";
export type Force2 = boolean;
export type Id38 = string | number | null;
export type Online1 = boolean;
export type Type36 = "reports.snapshot";
export type DispatchId4 = string;
export type Id39 = string | number | null;
export type Type37 = "reports.report";
export type BatchId3 = string;
export type Id40 = string | number | null;
export type Type38 = "reports.timeline";
export type Force3 = boolean;
export type Id41 = string | number | null;
export type Type39 = "orchestration.snapshot";
export type Id42 = string | number | null;
export type Type40 = "orchestration.lock";
export type Batch = string;
export type Force4 = boolean;
export type Id43 = string | number | null;
/**
 * @maxItems 32
 */
export type Skip = string[];
export type Type41 = "recovery.snapshot";
export type Batch1 = string;
export type Id44 = string | number | null;
export type Role3 = string;
export type Runtime = string;
export type Type42 = "container_route.snapshot";
export type Batch2 = string;
export type Force5 = boolean;
export type Id45 = string | number | null;
/**
 * @maxItems 32
 */
export type Skip1 = string[];
export type Type43 = "recovery.view";
export type Batch3 = string;
export type Id46 = string | number | null;
export type Role4 = string;
export type Runtime1 = string;
export type Type44 = "container_route.view";
export type Force6 = boolean;
export type Id47 = string | number | null;
export type Type45 = "task_board.specs";
export type Force7 = boolean;
export type Id48 = string | number | null;
export type Spec = string;
export type Type46 = "task_board.snapshot";
export type Force8 = boolean;
export type Id49 = string | number | null;
export type Online2 = boolean;
export type Type47 = "diagnostics.snapshot";
export type Force9 = boolean;
export type Id50 = string | number | null;
export type Type48 = "harness.snapshot";
export type Force10 = boolean;
export type Id51 = string | number | null;
export type Type49 = "harness.overview";
export type Force11 = boolean;
export type Id52 = string | number | null;
export type Type50 = "features.snapshot";
export type Force12 = boolean;
export type Id53 = string | number | null;
export type Type51 = "harness.maintenance";
export type Force13 = boolean;
export type Id54 = string | number | null;
export type Type52 = "repo_map.snapshot";
export type Force14 = boolean;
export type Id55 = string | number | null;
export type Type53 = "open_project.snapshot";
export type Id56 = string | number | null;
export type Language = "ru" | "en";
export type Type54 = "help.snapshot";
export type Force15 = boolean;
export type Id57 = string | number | null;
export type Type55 = "update_harness.snapshot";
export type Force16 = boolean;
export type Id58 = string | number | null;
export type Path5 = string;
export type Type56 = "update_harness.diff";
export type Id59 = string | number | null;
export type Offset2 = number;
export type SnapshotId3 = number;
export type Type57 = "snapshot.page";
export type DispatchId5 = string;
export type Id60 = string | number | null;
export type Offset3 = number;
export type Type58 = "worker.steps";
export type DispatchId6 = string;
export type Id61 = string | number | null;
export type Offset4 = number;
export type Type59 = "worker.subscribe";
export type Id62 = string | number | null;
export type Type60 = "steps.subscribe";

/**
 * Text frames on /ws: one request object per frame, replies by id.
 */
export interface ConsoleWebSocketProtocol {
  [k: string]: unknown | undefined;
}
/**
 * One runtime adapter file of the installed capabilities.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "AdapterPayload".
 */
export interface AdapterPayload {
  path: Path;
  problem: Problem;
  status: Status;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "AdviceComparison".
 */
export interface AdviceComparison {
  option: Option;
  tradeoff: Tradeoff;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "AdvicePayload".
 */
export interface AdvicePayload {
  comparison: Comparison;
  impact: Impact;
  value: JsonValue;
  why: Why;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "AdvisorAdviceReply".
 */
export interface AdvisorAdviceReply {
  advice: AdvicePayload;
  id: Id;
  ok: Ok;
  outcome: Outcome;
  type: Type;
  v: V;
}
/**
 * Asks for advice about one parameter; only the file and path travel, never a value.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "AdvisorAskRequest".
 */
export interface AdvisorAskRequest {
  file: File;
  id: Id1;
  path: Path1;
  provider: Provider;
  type: Type1;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "AdvisorCancelReply".
 */
export interface AdvisorCancelReply {
  cancelled: Cancelled;
  id: Id2;
  ok: Ok1;
  type: Type2;
  v: V1;
}
/**
 * Cancels an `advisor.ask` of the same connection.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "AdvisorCancelRequest".
 */
export interface AdvisorCancelRequest {
  id?: Id3;
  request_id: RequestId;
  type: Type3;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "AdvisorCheckReply".
 */
export interface AdvisorCheckReply {
  id: Id4;
  ok: Ok2;
  status: CliStatusPayload;
  type: Type4;
  v: V2;
}
/**
 * What the CLI check learned; null for a stage it did not reach.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "CliStatusPayload".
 */
export interface CliStatusPayload {
  authorized: Authorized;
  found: Found;
  message: Message;
  provider: Provider1;
  ready: Ready;
  version_supported: VersionSupported;
}
/**
 * Checks CLI presence, version and login; never invokes a model.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "AdvisorCheckRequest".
 */
export interface AdvisorCheckRequest {
  id?: Id5;
  provider: Provider2;
  type: Type5;
}
/**
 * No advice: the ordinary hints are shown and the draft does not change.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "AdvisorFallbackReply".
 */
export interface AdvisorFallbackReply {
  cause: Cause;
  id: Id6;
  ok: Ok3;
  outcome: Outcome1;
  reason: Reason;
  type: Type6;
  v: V3;
}
/**
 * A visible worker step: kind and text only, never thinking, tool inputs or raw JSON.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "AgentStep".
 */
export interface AgentStep {
  batch_id: BatchId;
  dispatch_id: DispatchId;
  kind: Kind;
  observed_at: ObservedAt;
  origin: Origin;
  role: Role;
  source: Source;
  structure: Structure;
  text: Text;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "CommandDescriptor".
 */
export interface CommandDescriptor {
  available: Available;
  command_id: CommandId;
  confirmation_reason: ConfirmationReason;
  fields?: Fields;
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
 * via the `definition` "CoordinatorInput".
 */
export interface CoordinatorInput {
  choices: Choices;
  default: Default;
  dest: Dest;
  flag: Flag;
  help: Help;
  repeatable: Repeatable;
  required: Required;
  takes_value: TakesValue;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ConfigurationSnapshotRequest".
 */
export interface ConfigurationSnapshotRequest {
  force?: Force;
  id?: Id7;
  type: Type7;
  version?: Version;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ErrorReply".
 */
export interface ErrorReply {
  error: ErrorBody;
  id: Id8;
  ok: Ok4;
  type: Type8;
  v: V4;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ErrorBody".
 */
export interface ErrorBody {
  code: Code;
  job_id?: JobId;
  message: Message1;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HomeSnapshotReply".
 */
export interface HomeSnapshotReply {
  activity?: HomeActivityPayload | null;
  age_seconds: AgeSeconds;
  cached: Cached;
  id: Id9;
  ok: Ok5;
  problems_snapshot_id?: ProblemsSnapshotId;
  snapshot: Snapshot;
  type: Type9;
  v: V5;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HomeActivityPayload".
 */
export interface HomeActivityPayload {
  events_per_minute: EventsPerMinute;
  events_total_window: EventsTotalWindow;
  last_event_age_seconds: LastEventAgeSeconds;
  links: Links;
  window_seconds: WindowSeconds;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "LinkActivityPayload".
 */
export interface LinkActivityPayload {
  events_per_minute: EventsPerMinute1;
  last_event_age_seconds: LastEventAgeSeconds1;
  link: Link;
}
export interface Snapshot {
  [k: string]: JsonValue;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HomeProblemsReply".
 */
export interface HomeProblemsReply {
  done: Done;
  id: Id10;
  next: Next;
  ok: Ok6;
  text: Text1;
  type: Type10;
  v: V6;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobListReply".
 */
export interface JobListReply {
  id: Id11;
  jobs: Jobs;
  ok: Ok7;
  type: Type11;
  v: V7;
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
  id: Id12;
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
  id: Id13;
  ok: Ok8;
  type: Type12;
  v: V8;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobReply".
 */
export interface JobReply {
  id: Id14;
  job: Job;
  ok: Ok9;
  type: Type13;
  v: V9;
}
export interface Job {
  [k: string]: JsonValue;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "DecisionsSnapshotReply".
 */
export interface DecisionsSnapshotReply {
  id: Id15;
  ok: Ok10;
  snapshot: Snapshot1;
  type: Type14;
  v: V10;
}
export interface Snapshot1 {
  [k: string]: JsonValue;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationSourceReply".
 */
export interface OrchestrationSourceReply {
  cursor: Cursor1;
  id: Id16;
  kind: Kind1;
  ok: Ok11;
  source: Source1;
  type: Type15;
  v: V11;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationEventsReply".
 */
export interface OrchestrationEventsReply {
  cursor: Cursor2;
  events: Events;
  id: Id17;
  kind: Kind2;
  ok: Ok12;
  type: Type16;
  v: V12;
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
  id: Id18;
  next: Next1;
  ok: Ok13;
  snapshot_id: SnapshotId;
  text: Text2;
  type: Type17;
  v: V13;
}
/**
 * The Harness state, the package version, the drift state and file count, the state store,
 * the runtime adapters (null: unreadable), the Claude Code, Codex and tracker adapters and the
 * runtime status (null: not collected), the container engine inventory (null: not collected) and
 * the pipeline usage.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HarnessOverviewReply".
 */
export interface HarnessOverviewReply {
  adapters: Adapters;
  age_seconds: AgeSeconds2;
  cached: Cached2;
  containers: ContainersPayload | null;
  drift: Drift;
  drift_files: DriftFiles;
  id: Id19;
  integrations?: Integrations;
  ok: Ok14;
  package_version: PackageVersion;
  runtime?: RuntimeStatusPayload | null;
  state: HarnessStatePayload;
  store: StorePayload | null;
  type: Type18;
  usage: PipelineUsage;
  v: V14;
}
/**
 * The read-only inventory of the configured container engine; a fact a probe could not
 * give is null with the probe's reason beside it.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ContainersPayload".
 */
export interface ContainersPayload {
  cgroup_driver: CgroupDriver;
  cgroup_version: CgroupVersion;
  engine: Engine;
  images: Images;
  images_problem: ImagesProblem;
  info_problem: InfoProblem;
  rootless: Rootless;
  selinux: Selinux;
  version: Version1;
  volumes: Volumes;
  volumes_problem: VolumesProblem;
}
/**
 * One adapter of the Harness page: Claude Code or Codex (`runtime`: adapter files of the
 * installed capabilities, CLI on PATH) or the project tracker (`tracker`: CLI on PATH, null for
 * local work); nothing is checked online.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "IntegrationPayload".
 */
export interface IntegrationPayload {
  cli: Cli;
  detail: Detail;
  kind: Kind3;
  name: Name;
  status: Status1;
}
/**
 * Whether the project's runtime answered an empty `state.read` (2 s, never started), with its
 * store revision, or why it did not.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "RuntimeStatusPayload".
 */
export interface RuntimeStatusPayload {
  reason: Reason1;
  revision: Revision;
  state: State;
}
/**
 * What is installed in the project, read from `.harness/harness.lock`.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HarnessStatePayload".
 */
export interface HarnessStatePayload {
  capabilities: Capabilities;
  installed: Installed;
  installed_version: InstalledVersion;
  managed_files: ManagedFiles;
  orchestration: Orchestration;
  skills: Skills;
  updated_at: UpdatedAt;
}
/**
 * The state authority read without the ledger lock; in the runtime-store epoch the audit count
 * comes from a bounded `state.validate` of the running runtime. Unread facts are null and
 * `reason` says why.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "StorePayload".
 */
export interface StorePayload {
  audit_records: AuditRecords;
  authority: Authority;
  cutover_at: CutoverAt;
  generation: Generation;
  reason: Reason2;
  schema: Schema;
}
/**
 * Pipeline usage counted from the ledger; with `unavailable` every count is 0.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "PipelineUsage".
 */
export interface PipelineUsage {
  batches: Batches;
  dispatches: Dispatches;
  reports: Reports;
  tickets: Tickets;
  unavailable: Unavailable;
}
/**
 * The Harness feature registry of Diagnostics, the SHA-256 digests of the configuration
 * files it was read from (empty: missing file) and whether a configuration write is pending.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "FeaturesSnapshotReply".
 */
export interface FeaturesSnapshotReply {
  age_seconds: AgeSeconds3;
  cached: Cached3;
  config_digests: ConfigDigests;
  features: Features;
  id: Id21;
  ok: Ok15;
  transaction_pending: TransactionPending;
  type: Type19;
  v: V15;
}
export interface ConfigDigests {
  [k: string]: string | undefined;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "FeaturePayload".
 */
export interface FeaturePayload {
  category: Category;
  depends_on: DependsOn;
  description: Description;
  id: Id20;
  name: Name1;
  off_effect: OffEffect;
  required_by: RequiredBy;
  requirements: Requirements;
  settings: Settings;
  sources: Sources;
  state: State2;
  toggle: FeatureToggle | null;
}
/**
 * One readiness requirement: a Russian title, its level and the paths or values behind it.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "FeatureRequirement".
 */
export interface FeatureRequirement {
  detail: Detail1;
  state: State1;
  title: Title1;
}
/**
 * One configuration key the feature reads: its masked value as compact JSON clipped to 120
 * characters, or the default text (null: none) when the key is absent.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "FeatureSetting".
 */
export interface FeatureSetting {
  file: File1;
  path: Path2;
  present: Present;
  value: Value;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "FeatureSource".
 */
export interface FeatureSource {
  kind: Kind4;
  path: Path3;
}
/**
 * The boolean configuration key that switches the feature, its current value and the
 * kernel's forecast: the state and requirements of the feature once the key is flipped.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "FeatureToggle".
 */
export interface FeatureToggle {
  enabled: Enabled;
  file: File2;
  path: Path4;
  requirements_after: RequirementsAfter;
  state_after: StateAfter;
}
/**
 * The first page of a report body, a batch chronology or an update diff as JSON text.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "PagedReply".
 */
export interface PagedReply {
  done: Done3;
  id: Id22;
  next: Next2;
  ok: Ok16;
  snapshot_id: SnapshotId1;
  text: Text3;
  type: Type20;
  v: V16;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "SnapshotPageReply".
 */
export interface SnapshotPageReply {
  done: Done4;
  id: Id23;
  next: Next3;
  ok: Ok17;
  text: Text4;
  type: Type21;
  v: V17;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationLockReply".
 */
export interface OrchestrationLockReply {
  error: Error1;
  id: Id24;
  lock: Lock;
  ok: Ok18;
  type: Type22;
  v: V18;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "WorkerStepsReply".
 */
export interface WorkerStepsReply {
  id: Id25;
  ok: Ok19;
  page: WorkerStepsPage;
  type: Type23;
  v: V19;
}
/**
 * Allowlisted worker steps from a log byte offset; never thinking, tool inputs or raw JSON.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "WorkerStepsPage".
 */
export interface WorkerStepsPage {
  dispatch_id: DispatchId1;
  last_step_age_seconds: LastStepAgeSeconds;
  message: Message2;
  more: More;
  offset: Offset;
  reason: Reason3;
  reset: Reset;
  source: Source2;
  state: State3;
  steps: Steps;
  structure: Structure1;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "WorkerStep".
 */
export interface WorkerStep {
  kind: Kind5;
  text: Text5;
}
/**
 * The dispatches the live step list knows; `reset` drops the steps the client holds.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "StepsRosterReply".
 */
export interface StepsRosterReply {
  dispatches: Dispatches1;
  id: Id26;
  kind: Kind6;
  ok: Ok20;
  orchestration: Orchestration1;
  reset: Reset1;
  type: Type24;
  v: V20;
}
/**
 * A dispatch of the journal view; the timing is read for a live dispatch only ("" and
 * false otherwise).
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "RosterDispatch".
 */
export interface RosterDispatch {
  batch_id: BatchId1;
  batch_state: BatchState;
  branch: Branch;
  dispatch_id: DispatchId2;
  last_event_at: LastEventAt;
  role: Role1;
  silent: Silent;
  started_at: StartedAt;
  state: State4;
  ticket: Ticket;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "StepsReply".
 */
export interface StepsReply {
  id: Id27;
  kind: Kind7;
  ok: Ok21;
  steps: Steps1;
  type: Type25;
  v: V21;
}
/**
 * An orchestration event with the allowlisted fields its text needs.
 *
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationStep".
 */
export interface OrchestrationStep {
  batch_id: BatchId2;
  decision: Decision;
  dispatch_id: DispatchId3;
  event: Event;
  from_state: FromState;
  message: Message3;
  next_role: NextRole;
  observed_at: ObservedAt1;
  origin: Origin1;
  outcome: Outcome2;
  role: Role2;
  seq: Seq;
  stage: Stage;
  ticket: Ticket1;
  to_state: ToState;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HomeSnapshotRequest".
 */
export interface HomeSnapshotRequest {
  force?: Force1;
  id?: Id28;
  online?: Online;
  type: Type26;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HomeProblemsRequest".
 */
export interface HomeProblemsRequest {
  id?: Id29;
  offset: Offset1;
  snapshot_id: SnapshotId2;
  type: Type27;
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
  id?: Id30;
  plan_digest?: PlanDigest;
  type: Type28;
  values?: Values;
}
export interface Values {
  [k: string]: JsonValue;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobGetRequest".
 */
export interface JobGetRequest {
  cursor?: Cursor3;
  id?: Id31;
  job_id: JobId1;
  type: Type29;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobSubscribeRequest".
 */
export interface JobSubscribeRequest {
  cursor?: Cursor4;
  id?: Id32;
  job_id: JobId2;
  type: Type30;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobCancelRequest".
 */
export interface JobCancelRequest {
  confirmed?: Confirmed1;
  id?: Id33;
  job_id: JobId3;
  type: Type31;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobListRequest".
 */
export interface JobListRequest {
  id?: Id34;
  type: Type32;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "JobCatalogRequest".
 */
export interface JobCatalogRequest {
  id?: Id35;
  section: Section1;
  type: Type33;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "DecisionsSnapshotRequest".
 */
export interface DecisionsSnapshotRequest {
  id?: Id36;
  type: Type34;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationSubscribeRequest".
 */
export interface OrchestrationSubscribeRequest {
  cursor?: Cursor5;
  id?: Id37;
  type: Type35;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ReportsSnapshotRequest".
 */
export interface ReportsSnapshotRequest {
  force?: Force2;
  id?: Id38;
  online?: Online1;
  type: Type36;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ReportRequest".
 */
export interface ReportRequest {
  dispatch_id: DispatchId4;
  id?: Id39;
  type: Type37;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "TimelineRequest".
 */
export interface TimelineRequest {
  batch_id: BatchId3;
  id?: Id40;
  type: Type38;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationSnapshotRequest".
 */
export interface OrchestrationSnapshotRequest {
  force?: Force3;
  id?: Id41;
  type: Type39;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OrchestrationLockRequest".
 */
export interface OrchestrationLockRequest {
  id?: Id42;
  type: Type40;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "RecoverySnapshotRequest".
 */
export interface RecoverySnapshotRequest {
  batch?: Batch;
  force?: Force4;
  id?: Id43;
  skip?: Skip;
  type: Type41;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ContainerRouteSnapshotRequest".
 */
export interface ContainerRouteSnapshotRequest {
  batch?: Batch1;
  id?: Id44;
  role?: Role3;
  runtime?: Runtime;
  type: Type42;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "RecoveryViewRequest".
 */
export interface RecoveryViewRequest {
  batch?: Batch2;
  force?: Force5;
  id?: Id45;
  skip?: Skip1;
  type: Type43;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "ContainerRouteViewRequest".
 */
export interface ContainerRouteViewRequest {
  batch?: Batch3;
  id?: Id46;
  role?: Role4;
  runtime?: Runtime1;
  type: Type44;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "TaskBoardSpecsRequest".
 */
export interface TaskBoardSpecsRequest {
  force?: Force6;
  id?: Id47;
  type: Type45;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "TaskBoardSnapshotRequest".
 */
export interface TaskBoardSnapshotRequest {
  force?: Force7;
  id?: Id48;
  spec: Spec;
  type: Type46;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "DiagnosticsSnapshotRequest".
 */
export interface DiagnosticsSnapshotRequest {
  force?: Force8;
  id?: Id49;
  online?: Online2;
  type: Type47;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HarnessSnapshotRequest".
 */
export interface HarnessSnapshotRequest {
  force?: Force9;
  id?: Id50;
  type: Type48;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HarnessOverviewRequest".
 */
export interface HarnessOverviewRequest {
  force?: Force10;
  id?: Id51;
  type: Type49;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "FeaturesSnapshotRequest".
 */
export interface FeaturesSnapshotRequest {
  force?: Force11;
  id?: Id52;
  type: Type50;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HarnessMaintenanceRequest".
 */
export interface HarnessMaintenanceRequest {
  force?: Force12;
  id?: Id53;
  type: Type51;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "RepoMapSnapshotRequest".
 */
export interface RepoMapSnapshotRequest {
  force?: Force13;
  id?: Id54;
  type: Type52;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "OpenProjectSnapshotRequest".
 */
export interface OpenProjectSnapshotRequest {
  force?: Force14;
  id?: Id55;
  type: Type53;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "HelpSnapshotRequest".
 */
export interface HelpSnapshotRequest {
  id?: Id56;
  language: Language;
  type: Type54;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "UpdateHarnessSnapshotRequest".
 */
export interface UpdateHarnessSnapshotRequest {
  force?: Force15;
  id?: Id57;
  type: Type55;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "UpdateHarnessDiffRequest".
 */
export interface UpdateHarnessDiffRequest {
  force?: Force16;
  id?: Id58;
  path: Path5;
  type: Type56;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "SnapshotPageRequest".
 */
export interface SnapshotPageRequest {
  id?: Id59;
  offset: Offset2;
  snapshot_id: SnapshotId3;
  type: Type57;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "WorkerStepsRequest".
 */
export interface WorkerStepsRequest {
  dispatch_id: DispatchId5;
  id?: Id60;
  offset: Offset3;
  type: Type58;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "WorkerSubscribeRequest".
 */
export interface WorkerSubscribeRequest {
  dispatch_id: DispatchId6;
  id?: Id61;
  offset?: Offset4;
  type: Type59;
}
/**
 * This interface was referenced by `ConsoleWebSocketProtocol`'s JSON-Schema
 * via the `definition` "StepsSubscribeRequest".
 */
export interface StepsSubscribeRequest {
  id?: Id62;
  type: Type60;
}
