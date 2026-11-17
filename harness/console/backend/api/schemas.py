"""Pydantic models of the console WebSocket protocol and the exported schema documents.

The models describe the protocol the services already speak; the /ws route never parses frames
with them, so every reply stays byte-identical. Regenerate the committed documents with
`python -m harness.console.backend.api.schemas`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictInt, TypeAdapter

from ...kernel.protocol import (
    CONFIGURATION_VERSION_ID,
    MAX_ID_CHARS,
    MAX_PATH_CHARS,
    MAX_SKIPPED,
)
from .request_router import RequestRouter

REGENERATE = "python -m harness.console.backend.api.schemas"
HERE = Path(__file__).resolve().parent
OPENAPI_PATH = HERE / "openapi.json"
WS_SCHEMA_PATH = HERE / "ws-schema.json"

RequestId = Annotated[str, Field(max_length=64)] | StrictInt | None


# Pydantic's synthesized model signatures carry Any; as in harness/json_types.py the explicit-any
# rule is waived only on these model classes.
class _Strict(BaseModel):  # type: ignore[explicit-any]
    model_config = ConfigDict(extra="forbid")


# Requests: one model per type, with the field sets the services accept.


class HomeSnapshotRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["home.snapshot"]
    force: bool = False
    online: bool = False


class HomeProblemsRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["home.problems"]
    snapshot_id: int
    offset: Annotated[int, Field(ge=0)]


class JobStartRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["job.start"]
    command_id: str
    values: dict[str, JsonValue] = {}
    confirmed: bool = False
    confirmation: str | None = None
    plan_digest: Annotated[str, Field(pattern="^[0-9a-f]{64}$")] | None = None
    client: str = "unknown"


class JobGetRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["job.get"]
    job_id: str
    cursor: Annotated[int, Field(ge=0)] = 0


class JobSubscribeRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["job.subscribe"]
    job_id: str
    cursor: Annotated[int, Field(ge=0)] = 0


class JobCancelRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["job.cancel"]
    job_id: str
    confirmed: bool = False


class JobListRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["job.list"]


CommandSection = Literal[
    "harness",
    "diagnostics",
    "repo-map",
    "setup",
    "configuration",
    "memory",
    "decisions",
    "recovery",
    "update",
]
ReversibilityClass = Literal[
    "reversible",
    "deletes-local-data",
    "terminal-coordinator-action",
    "external-change",
    "overwrites-managed-files",
    "downloads-files",
]


class JobCatalogRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["job.catalog"]
    section: CommandSection


class DecisionsSnapshotRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["decisions.snapshot"]


class OrchestrationSubscribeRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["orchestration.subscribe"]
    cursor: str | None = None


ScreenId = Annotated[str, Field(min_length=1, max_length=MAX_ID_CHARS)]
OptionalScreenId = Annotated[str, Field(max_length=MAX_ID_CHARS)]


class ReportsSnapshotRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["reports.snapshot"]
    force: bool = False
    online: bool = False


class ReportRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["reports.report"]
    dispatch_id: ScreenId


class TimelineRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["reports.timeline"]
    batch_id: ScreenId


class OrchestrationSnapshotRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["orchestration.snapshot"]
    force: bool = False


class OrchestrationLockRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["orchestration.lock"]


class RecoverySnapshotRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["recovery.snapshot"]
    batch: OptionalScreenId = ""
    skip: Annotated[list[ScreenId], Field(max_length=MAX_SKIPPED)] = []
    force: bool = False


class ContainerRouteSnapshotRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["container_route.snapshot"]
    batch: OptionalScreenId = ""
    role: ScreenId = "developer"
    runtime: OptionalScreenId = ""


class RecoveryViewRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["recovery.view"]
    batch: OptionalScreenId = ""
    skip: Annotated[list[ScreenId], Field(max_length=MAX_SKIPPED)] = []
    force: bool = False


class ContainerRouteViewRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["container_route.view"]
    batch: OptionalScreenId = ""
    role: ScreenId = "developer"
    runtime: OptionalScreenId = ""


class TaskBoardSpecsRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["task_board.specs"]
    force: bool = False


class TaskBoardSnapshotRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["task_board.snapshot"]
    spec: ScreenId
    force: bool = False


class DiagnosticsSnapshotRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["diagnostics.snapshot"]
    online: bool = False
    force: bool = False


class HarnessSnapshotRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["harness.snapshot"]
    force: bool = False


class HarnessOverviewRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["harness.overview"]
    force: bool = False


class FeaturesSnapshotRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["features.snapshot"]
    force: bool = False


class HarnessMaintenanceRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["harness.maintenance"]
    force: bool = False


class RepoMapSnapshotRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["repo_map.snapshot"]
    force: bool = False


class OpenProjectSnapshotRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["open_project.snapshot"]
    force: bool = False


class HelpSnapshotRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["help.snapshot"]
    language: Literal["ru", "en"]


class UpdateHarnessSnapshotRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["update_harness.snapshot"]
    force: bool = False


class UpdateHarnessDiffRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["update_harness.diff"]
    path: Annotated[str, Field(min_length=1, max_length=MAX_PATH_CHARS)]
    force: bool = False


class ConfigurationSnapshotRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["configuration.snapshot"]
    force: bool = False
    # A saved version whose masked content the reply adds as `version`.
    version: (
        Annotated[str, Field(pattern=f"^{CONFIGURATION_VERSION_ID}$")] | None
    ) = None


AdvisorProvider = Literal["codex", "claude"]
AdvisorPathPart = Annotated[str, Field(pattern="^[A-Za-z0-9_.-]{1,64}$")]
RequiredId = Annotated[str, Field(min_length=1, max_length=64)] | StrictInt


class AdvisorCheckRequest(_Strict):  # type: ignore[explicit-any]
    """Checks CLI presence, version and login; never invokes a model."""

    id: RequestId = None
    type: Literal["advisor.check"]
    provider: AdvisorProvider


class AdvisorAskRequest(_Strict):  # type: ignore[explicit-any]
    """Asks for advice about one parameter; only the file and path travel, never a value."""

    id: RequiredId
    type: Literal["advisor.ask"]
    provider: AdvisorProvider
    file: Literal["project.json", "orchestration.json"]
    path: Annotated[list[AdvisorPathPart], Field(min_length=1, max_length=8)]


class AdvisorCancelRequest(_Strict):  # type: ignore[explicit-any]
    """Cancels an `advisor.ask` of the same connection."""

    id: RequestId = None
    type: Literal["advisor.cancel"]
    request_id: RequiredId


class SnapshotPageRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["snapshot.page"]
    snapshot_id: Annotated[int, Field(ge=0)]
    offset: Annotated[int, Field(ge=0)]


DispatchId = Annotated[
    str, Field(min_length=1, max_length=100, pattern="^[A-Za-z0-9][A-Za-z0-9_-]*$")
]


class WorkerStepsRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["worker.steps"]
    dispatch_id: DispatchId
    offset: Annotated[int, Field(ge=0)]


class WorkerSubscribeRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["worker.subscribe"]
    dispatch_id: DispatchId
    offset: Annotated[int, Field(ge=0)] = 0


class StepsSubscribeRequest(_Strict):  # type: ignore[explicit-any]
    id: RequestId = None
    type: Literal["steps.subscribe"]


ConsoleRequest = Annotated[
    HomeSnapshotRequest
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
    | StepsSubscribeRequest,
    Field(discriminator="type"),
]


# Replies: the envelope v, id, type, ok, then either the payload fields or an error.


class _Envelope(_Strict):  # type: ignore[explicit-any]
    v: Literal[1]
    id: RequestId


class ErrorBody(_Strict):  # type: ignore[explicit-any]
    code: str
    message: str
    job_id: str | None = None


class ErrorReply(_Envelope):  # type: ignore[explicit-any]
    type: str | None
    ok: Literal[False]
    error: ErrorBody


class LinkActivityPayload(_Strict):  # type: ignore[explicit-any]
    link: Literal["decision", "typed", "write", "launch", "audit", "receipts"]
    events_per_minute: float
    last_event_age_seconds: float | None


class HomeActivityPayload(_Strict):  # type: ignore[explicit-any]
    window_seconds: int
    events_per_minute: float
    links: list[LinkActivityPayload]
    last_event_age_seconds: float | None
    events_total_window: int


class HomeSnapshotReply(_Envelope):  # type: ignore[explicit-any]
    type: Literal["home.snapshot"]
    ok: Literal[True]
    cached: bool
    age_seconds: float
    snapshot: dict[str, JsonValue]
    problems_snapshot_id: int | None = None
    # Counted for this reply from the events the console observed, not cached with the
    # snapshot; null when they cannot be read. Older clients ignore the key.
    activity: HomeActivityPayload | None = None


class HomeProblemsReply(_Envelope):  # type: ignore[explicit-any]
    type: Literal["home.problems"]
    ok: Literal[True]
    text: str
    next: int
    done: bool


class JobSummary(_Strict):  # type: ignore[explicit-any]
    id: str
    command_id: str
    mutating: bool
    phase: Literal["running", "completed", "failed", "cancelled"]
    cursor: int
    done: bool
    truncated: bool
    returncode: int | None
    error: str | None


class JobListReply(_Envelope):  # type: ignore[explicit-any]
    type: Literal["job.list"]
    ok: Literal[True]
    jobs: list[JobSummary]


class CoordinatorInput(_Strict):  # type: ignore[explicit-any]
    dest: str
    flag: str
    required: bool
    repeatable: bool
    choices: list[str] | None
    help: str
    default: str | None
    takes_value: bool


class CommandDescriptor(_Strict):  # type: ignore[explicit-any]
    command_id: str
    title: str
    section: CommandSection
    reversibility: ReversibilityClass
    reversibility_label: str
    needs_confirmation: bool
    confirmation_reason: str | None
    typed_confirmation: str | None
    read_only: bool
    inputs: list[str]
    plan_required: bool
    available: bool
    fields: list[CoordinatorInput] | None = None


class JobCatalogReply(_Envelope):  # type: ignore[explicit-any]
    type: Literal["job.catalog"]
    ok: Literal[True]
    commands: list[CommandDescriptor]
    cancel_reason: str


class JobReply(_Envelope):  # type: ignore[explicit-any]
    type: Literal["job.start", "job.get", "job.subscribe", "job.cancel"]
    ok: Literal[True]
    job: dict[str, JsonValue]


class DecisionsSnapshotReply(_Envelope):  # type: ignore[explicit-any]
    type: Literal["decisions.snapshot"]
    ok: Literal[True]
    snapshot: dict[str, JsonValue]


class OrchestrationSourceReply(_Envelope):  # type: ignore[explicit-any]
    type: Literal["orchestration.subscribe"]
    ok: Literal[True]
    kind: Literal["source"]
    cursor: str | None
    source: dict[str, JsonValue] | None


class OrchestrationEventsReply(_Envelope):  # type: ignore[explicit-any]
    type: Literal["orchestration.subscribe"]
    ok: Literal[True]
    kind: Literal["events"]
    cursor: str
    events: list[JsonValue]


class ScreenSnapshotReply(_Envelope):  # type: ignore[explicit-any]
    """The first page of a screen snapshot's JSON text; `snapshot.page` reads the rest."""

    type: Literal[
        "reports.snapshot",
        "orchestration.snapshot",
        "recovery.snapshot",
        "container_route.snapshot",
        "recovery.view",
        "container_route.view",
        "task_board.specs",
        "task_board.snapshot",
        "diagnostics.snapshot",
        "harness.snapshot",
        "harness.maintenance",
        "repo_map.snapshot",
        "open_project.snapshot",
        "help.snapshot",
        "update_harness.snapshot",
        "configuration.snapshot",
    ]
    ok: Literal[True]
    snapshot_id: int
    text: str
    next: int
    done: bool
    cached: bool
    age_seconds: float


class HarnessStatePayload(_Strict):  # type: ignore[explicit-any]
    """What is installed in the project, read from `.harness/harness.lock`."""

    installed: bool
    installed_version: str
    capabilities: list[str]
    skills: Annotated[int, Field(ge=0)]
    managed_files: Annotated[int, Field(ge=0)]
    updated_at: str
    orchestration: bool


class PipelineUsage(_Strict):  # type: ignore[explicit-any]
    """Pipeline usage counted from the ledger; with `unavailable` every count is 0."""

    unavailable: str | None
    batches: Annotated[int, Field(ge=0)]
    tickets: Annotated[int, Field(ge=0)]
    dispatches: Annotated[int, Field(ge=0)]
    reports: Annotated[int, Field(ge=0)]


class StorePayload(_Strict):  # type: ignore[explicit-any]
    """The state authority read without the ledger lock; in the runtime-store epoch the audit count
    comes from a bounded `state.validate` of the running runtime. Unread facts are null and
    `reason` says why."""

    authority: Literal["file-ledger", "runtime-store", "none"]
    schema_: Annotated[int | None, Field(alias="schema")]
    generation: str | None
    audit_records: Annotated[int | None, Field(ge=0)]
    cutover_at: str | None
    reason: str


class AdapterPayload(_Strict):  # type: ignore[explicit-any]
    """One runtime adapter file of the installed capabilities."""

    path: str
    status: Literal["current", "outdated", "missing"]
    problem: str | None


class RuntimeStatusPayload(_Strict):  # type: ignore[explicit-any]
    """Whether the project's runtime answered an empty `state.read` (2 s, never started), with its
    store revision, or why it did not."""

    state: Literal["online", "offline"]
    revision: Annotated[int | None, Field(ge=0)]
    reason: str


class IntegrationPayload(_Strict):  # type: ignore[explicit-any]
    """One adapter of the Harness page: Claude Code or Codex (`runtime`: adapter files of the
    installed capabilities, CLI on PATH) or the project tracker (`tracker`: CLI on PATH, null for
    local work); nothing is checked online."""

    name: str
    kind: Literal["runtime", "tracker"]
    status: Literal["current", "outdated", "missing", "unknown"]
    cli: bool | None
    detail: str


class ContainersPayload(_Strict):  # type: ignore[explicit-any]
    """The read-only inventory of the configured container engine; a fact a probe could not
    give is null with the probe's reason beside it."""

    engine: str
    version: str | None
    cgroup_driver: str | None
    cgroup_version: str | None
    selinux: bool | None
    rootless: bool | None
    info_problem: str | None
    images: Annotated[int | None, Field(ge=0)]
    images_problem: str | None
    volumes: Annotated[int | None, Field(ge=0)]
    volumes_problem: str | None


class HarnessOverviewReply(_Envelope):  # type: ignore[explicit-any]
    """The Harness state, the package version, the drift state and file count, the state store,
    the runtime adapters (null: unreadable), the Claude Code, Codex and tracker adapters and the
    runtime status (null: not collected), the container engine inventory (null: not collected) and
    the pipeline usage."""

    type: Literal["harness.overview"]
    ok: Literal[True]
    state: HarnessStatePayload
    package_version: str
    drift: str
    drift_files: Annotated[int | None, Field(ge=0)]
    store: StorePayload | None
    adapters: list[AdapterPayload] | None
    integrations: list[IntegrationPayload] | None = None
    runtime: RuntimeStatusPayload | None = None
    containers: ContainersPayload | None
    usage: PipelineUsage
    cached: bool
    age_seconds: float


ConfigName = Literal["project.json", "orchestration.json"]


class FeatureSource(_Strict):  # type: ignore[explicit-any]
    kind: Literal[
        "capabilities",
        "hook",
        "agent",
        "project.json",
        "orchestration.json",
        "harness.lock",
        "runtime",
    ]
    path: str


class FeatureRequirement(_Strict):  # type: ignore[explicit-any]
    """One readiness requirement: a Russian title, its level and the paths or values behind it."""

    title: str
    state: Literal["ok", "warn", "err"]
    detail: str


class FeatureSetting(_Strict):  # type: ignore[explicit-any]
    """One configuration key the feature reads: its masked value as compact JSON clipped to 120
    characters, or the default text (null: none) when the key is absent."""

    file: ConfigName
    path: list[str]
    present: bool
    value: str | None


class FeatureToggle(_Strict):  # type: ignore[explicit-any]
    """The boolean configuration key that switches the feature, its current value and the
    kernel's forecast: the state and requirements of the feature once the key is flipped."""

    file: ConfigName
    path: Annotated[list[str], Field(min_length=1)]
    enabled: bool
    state_after: Literal["working", "partial", "not_working", "disabled"]
    requirements_after: list[FeatureRequirement]


class FeaturePayload(_Strict):  # type: ignore[explicit-any]
    id: str
    name: str
    category: Literal[
        "execution",
        "roles",
        "hooks",
        "context",
        "process",
        "publication",
        "capabilities",
        "platform",
    ]
    state: Literal["working", "partial", "not_working", "disabled"]
    description: str
    off_effect: str
    depends_on: list[str]
    required_by: list[str]
    sources: list[FeatureSource]
    requirements: list[FeatureRequirement]
    settings: list[FeatureSetting]
    toggle: FeatureToggle | None


class FeaturesSnapshotReply(_Envelope):  # type: ignore[explicit-any]
    """The Harness feature registry of Diagnostics, the SHA-256 digests of the configuration
    files it was read from (empty: missing file) and whether a configuration write is pending."""

    type: Literal["features.snapshot"]
    ok: Literal[True]
    features: list[FeaturePayload]
    config_digests: dict[ConfigName, str]
    transaction_pending: bool
    cached: bool
    age_seconds: float


class PagedReply(_Envelope):  # type: ignore[explicit-any]
    """The first page of a report body, a batch chronology or an update diff as JSON text."""

    type: Literal["reports.report", "reports.timeline", "update_harness.diff"]
    ok: Literal[True]
    snapshot_id: int
    text: str
    next: int
    done: bool


class SnapshotPageReply(_Envelope):  # type: ignore[explicit-any]
    type: Literal["snapshot.page"]
    ok: Literal[True]
    text: str
    next: int
    done: bool


class OrchestrationLockReply(_Envelope):  # type: ignore[explicit-any]
    type: Literal["orchestration.lock"]
    ok: Literal[True]
    lock: dict[str, JsonValue] | None
    error: str | None


class WorkerStep(_Strict):  # type: ignore[explicit-any]
    kind: str
    text: str


class WorkerStepsPage(_Strict):  # type: ignore[explicit-any]
    """Allowlisted worker steps from a log byte offset; never thinking, tool inputs or raw JSON."""

    dispatch_id: str
    source: Literal["structured", "plain", "none"]
    structure: Literal["available", "unavailable"]
    state: Literal["connected", "waiting", "unavailable"]
    reason: (
        Literal[
            "no_log",
            "log_missing",
            "log_unreadable",
            "log_outside_storage",
            "log_unrecognised",
        ]
        | None
    )
    message: str
    offset: Annotated[int, Field(ge=0)]
    reset: bool
    more: bool
    last_step_age_seconds: int | None
    steps: list[WorkerStep]


class WorkerStepsReply(_Envelope):  # type: ignore[explicit-any]
    type: Literal["worker.steps", "worker.subscribe"]
    ok: Literal[True]
    page: WorkerStepsPage


class RosterDispatch(_Strict):  # type: ignore[explicit-any]
    """A dispatch of the journal view; the timing is read for a live dispatch only ("" and
    false otherwise)."""

    dispatch_id: str
    batch_id: str
    ticket: str
    role: str
    state: str
    batch_state: str
    branch: str
    started_at: str
    last_event_at: str
    silent: bool


class StepsRosterReply(_Envelope):  # type: ignore[explicit-any]
    """The dispatches the live step list knows; `reset` drops the steps the client holds."""

    type: Literal["steps.subscribe"]
    ok: Literal[True]
    kind: Literal["roster"]
    reset: bool
    orchestration: Literal["available", "unavailable"]
    dispatches: list[RosterDispatch]


class AgentStep(_Strict):  # type: ignore[explicit-any]
    """A visible worker step: kind and text only, never thinking, tool inputs or raw JSON."""

    origin: Literal["agent"]
    dispatch_id: str
    batch_id: str
    role: str
    source: Literal["structured", "plain"]
    structure: Literal["available", "unavailable"]
    kind: str
    text: str
    observed_at: str


class OrchestrationStep(_Strict):  # type: ignore[explicit-any]
    """An orchestration event with the allowlisted fields its text needs."""

    origin: Literal["orchestration"]
    seq: int
    observed_at: str
    event: Literal[
        "batch.transition",
        "dispatch.transition",
        "gate.decision",
        "qa.run",
        "qa.attempt",
    ]
    batch_id: str | None
    dispatch_id: str | None
    ticket: str | None
    role: str | None
    from_state: str | None
    to_state: str | None
    decision: str | None
    next_role: str | None
    outcome: str | None
    stage: str | None
    message: str


class StepsReply(_Envelope):  # type: ignore[explicit-any]
    type: Literal["steps.subscribe"]
    ok: Literal[True]
    kind: Literal["steps"]
    steps: list[Annotated[AgentStep | OrchestrationStep, Field(discriminator="origin")]]


class CliStatusPayload(_Strict):  # type: ignore[explicit-any]
    """What the CLI check learned; null for a stage it did not reach."""

    provider: str
    found: bool
    version_supported: bool | None
    authorized: bool | None
    ready: bool
    message: str


class AdvisorCheckReply(_Envelope):  # type: ignore[explicit-any]
    type: Literal["advisor.check"]
    ok: Literal[True]
    status: CliStatusPayload


class AdviceComparison(_Strict):  # type: ignore[explicit-any]
    option: str
    tradeoff: str


class AdvicePayload(_Strict):  # type: ignore[explicit-any]
    value: JsonValue
    why: str
    impact: str
    comparison: Annotated[list[AdviceComparison], Field(max_length=4)]


class AdvisorAdviceReply(_Envelope):  # type: ignore[explicit-any]
    type: Literal["advisor.ask"]
    ok: Literal[True]
    outcome: Literal["advice"]
    advice: AdvicePayload


class AdvisorFallbackReply(_Envelope):  # type: ignore[explicit-any]
    """No advice: the ordinary hints are shown and the draft does not change."""

    type: Literal["advisor.ask"]
    ok: Literal[True]
    outcome: Literal["fallback"]
    cause: Literal["refused", "invalid", "timeout", "cancelled"]
    reason: str


class AdvisorCancelReply(_Envelope):  # type: ignore[explicit-any]
    type: Literal["advisor.cancel"]
    ok: Literal[True]
    cancelled: bool


ConsoleReply = (
    ErrorReply
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
    | AdvisorCancelReply
)

REQUESTS: TypeAdapter[ConsoleRequest] = TypeAdapter(ConsoleRequest)
REPLIES: TypeAdapter[ConsoleReply] = TypeAdapter(ConsoleReply)


def _text(document: object) -> str:
    return json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def websocket_schema() -> dict[str, JsonValue]:
    requests = REQUESTS.json_schema(ref_template="#/$defs/{model}")
    replies = REPLIES.json_schema(ref_template="#/$defs/{model}")
    definitions: dict[str, JsonValue] = {}
    for schema in (requests, replies):
        found = schema.pop("$defs", {})
        assert isinstance(found, dict)
        definitions.update(found)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Console WebSocket protocol",
        "description": "Text frames on /ws: one request object per frame, replies by id.",
        "$defs": {
            **definitions,
            "ConsoleRequest": requests,
            "ConsoleReply": replies,
        },
    }


class _StubRuntime:
    """Enough of a server for app.openapi(); nothing is served."""

    port = 1
    token = ""
    closing = False
    static_root = HERE / "no-build"

    @property
    def router(self) -> RequestRouter:
        raise RuntimeError("the schema stub serves no requests")

    def client_opened(self) -> None:
        raise RuntimeError("the schema stub serves no requests")

    def client_closed(self) -> None:
        raise RuntimeError("the schema stub serves no requests")


def render_schemas() -> tuple[str, str]:
    """The OpenAPI document and the WebSocket JSON Schema as deterministic text."""
    from .app import create_app

    return _text(create_app(_StubRuntime()).openapi()), _text(websocket_schema())


def main() -> None:
    openapi, websocket = render_schemas()
    OPENAPI_PATH.write_text(openapi, encoding="utf-8")
    WS_SCHEMA_PATH.write_text(websocket, encoding="utf-8")


if __name__ == "__main__":
    main()
