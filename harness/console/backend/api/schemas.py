"""Pydantic models of the console WebSocket protocol and the exported schema documents.

The models describe the protocol the services already speak; the /ws route never parses frames
with them, so every reply stays byte-identical. Regenerate the committed documents with
`python -m harness.console.backend.api.schemas`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter

from ...kernel.protocol import MAX_ID_CHARS, MAX_PATH_CHARS, MAX_SKIPPED
from .request_router import RequestRouter

REGENERATE = "python -m harness.console.backend.api.schemas"
HERE = Path(__file__).resolve().parent
OPENAPI_PATH = HERE / "openapi.json"
WS_SCHEMA_PATH = HERE / "ws-schema.json"

RequestId = Annotated[str, Field(max_length=64)] | int | None


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
    "harness", "diagnostics", "repo-map", "setup", "configuration", "memory"
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
    | WorkerSubscribeRequest,
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


class HomeSnapshotReply(_Envelope):  # type: ignore[explicit-any]
    type: Literal["home.snapshot"]
    ok: Literal[True]
    cached: bool
    age_seconds: float
    snapshot: dict[str, JsonValue]
    problems_snapshot_id: int | None = None


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


class CommandDescriptor(_Strict):  # type: ignore[explicit-any]
    command_id: str
    title: str
    section: CommandSection
    reversibility: ReversibilityClass
    needs_confirmation: bool
    typed_confirmation: str | None
    read_only: bool
    inputs: list[str]
    plan_required: bool
    available: bool


class JobCatalogReply(_Envelope):  # type: ignore[explicit-any]
    type: Literal["job.catalog"]
    ok: Literal[True]
    commands: list[CommandDescriptor]


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
    | PagedReply
    | SnapshotPageReply
    | OrchestrationLockReply
    | WorkerStepsReply
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
