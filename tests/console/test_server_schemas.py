"""The exported OpenAPI and WebSocket JSON Schema match the models, and the models match the
replies a real console server sends."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, TypeAdapter

from harness.console.backend.api import schemas
from harness.console.backend.api.protocol import events as orchestration_events
from harness.console.backend.api.protocol import jobs
from harness.console.backend.api.protocol import screens
from harness.console.backend.api.protocol import workers


def _drift_message(path: Path) -> str:
    return (
        f"{path.name} is out of date: run `{schemas.REGENERATE}` and commit the result."
    )


def test_committed_schema_documents_equal_the_rendered_models() -> None:
    openapi, websocket = schemas.render_schemas()
    for path, rendered in (
        (schemas.OPENAPI_PATH, openapi),
        (schemas.WS_SCHEMA_PATH, websocket),
    ):
        assert path.read_text(encoding="utf-8") == rendered, _drift_message(path)


def test_a_changed_model_makes_the_drift_comparison_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ChangedReply(schemas.ErrorReply):  # type: ignore[explicit-any]
        retry_after: int

    monkeypatch.setattr(
        schemas, "REPLIES", TypeAdapter(schemas.ConsoleReply | ChangedReply)
    )
    _, websocket = schemas.render_schemas()
    assert schemas.WS_SCHEMA_PATH.read_text(encoding="utf-8") != websocket
    assert schemas.REGENERATE in _drift_message(schemas.WS_SCHEMA_PATH)


def _fields(model: type[BaseModel]) -> set[str]:
    return set(model.model_fields)


def test_request_models_have_the_field_sets_of_the_services() -> None:
    by_type: dict[str, type[BaseModel]] = {
        "job.start": schemas.JobStartRequest,
        "job.get": schemas.JobGetRequest,
        "job.subscribe": schemas.JobSubscribeRequest,
        "job.cancel": schemas.JobCancelRequest,
        "job.list": schemas.JobListRequest,
        "job.catalog": schemas.JobCatalogRequest,
    }
    assert set(by_type) == set(jobs._FIELDS)
    for kind, model in by_type.items():
        assert _fields(model) == jobs._FIELDS[kind], kind
    assert (
        _fields(schemas.OrchestrationSubscribeRequest) == orchestration_events._FIELDS
    )
    assert _fields(schemas.DecisionsSnapshotRequest) == {"id", "type"}
    assert _fields(schemas.HomeSnapshotRequest) == {"id", "type", "force", "online"}
    assert _fields(schemas.HomeProblemsRequest) == {
        "id",
        "type",
        "snapshot_id",
        "offset",
    }
    models: list[type[BaseModel]] = [*by_type.values(), schemas.HomeSnapshotRequest]
    for model in models:
        assert model.model_config.get("extra") == "forbid"


def test_screen_request_models_have_the_field_sets_of_the_screen_protocol() -> None:
    by_type: dict[str, type[BaseModel]] = {
        "reports.snapshot": schemas.ReportsSnapshotRequest,
        "reports.report": schemas.ReportRequest,
        "reports.timeline": schemas.TimelineRequest,
        "orchestration.snapshot": schemas.OrchestrationSnapshotRequest,
        "orchestration.lock": schemas.OrchestrationLockRequest,
        "recovery.snapshot": schemas.RecoverySnapshotRequest,
        "container_route.snapshot": schemas.ContainerRouteSnapshotRequest,
        "recovery.view": schemas.RecoveryViewRequest,
        "container_route.view": schemas.ContainerRouteViewRequest,
        "snapshot.page": schemas.SnapshotPageRequest,
        "task_board.specs": schemas.TaskBoardSpecsRequest,
        "task_board.snapshot": schemas.TaskBoardSnapshotRequest,
        "diagnostics.snapshot": schemas.DiagnosticsSnapshotRequest,
        "harness.snapshot": schemas.HarnessSnapshotRequest,
        "harness.overview": schemas.HarnessOverviewRequest,
        "harness.maintenance": schemas.HarnessMaintenanceRequest,
        "repo_map.snapshot": schemas.RepoMapSnapshotRequest,
        "open_project.snapshot": schemas.OpenProjectSnapshotRequest,
        "help.snapshot": schemas.HelpSnapshotRequest,
        "update_harness.snapshot": schemas.UpdateHarnessSnapshotRequest,
        "update_harness.diff": schemas.UpdateHarnessDiffRequest,
        "configuration.snapshot": schemas.ConfigurationSnapshotRequest,
    }
    assert set(by_type) == screens.SCREEN_TYPES
    for kind, model in by_type.items():
        assert _fields(model) == {"id", "type"} | screens._FIELDS[kind], kind
        assert model.model_config.get("extra") == "forbid"


def test_screen_samples_parse_and_malformed_ones_are_refused() -> None:
    samples: list[dict[str, object]] = [
        {"id": 1, "type": "reports.snapshot", "online": True},
        {"id": 2, "type": "reports.report", "dispatch_id": "d-1"},
        {"id": 3, "type": "reports.timeline", "batch_id": "b-1"},
        {"id": 4, "type": "orchestration.snapshot", "force": True},
        {"id": 5, "type": "orchestration.lock"},
        {"id": 6, "type": "recovery.snapshot", "batch": "b-1", "skip": ["x"]},
        {"id": 7, "type": "container_route.snapshot", "batch": "b", "role": "qa"},
        {"id": 8, "type": "snapshot.page", "snapshot_id": 1, "offset": 10},
        {"id": 9, "type": "task_board.specs", "force": True},
        {"id": 10, "type": "task_board.snapshot", "spec": "#862"},
        {"id": 11, "type": "diagnostics.snapshot", "online": True, "force": True},
        {"id": 12, "type": "harness.snapshot", "force": True},
        {"id": 13, "type": "harness.maintenance"},
        {"id": 14, "type": "open_project.snapshot", "force": True},
        {"id": 15, "type": "help.snapshot", "language": "en"},
        {"id": 16, "type": "update_harness.snapshot", "force": True},
        {"id": 17, "type": "update_harness.diff", "path": "AGENTS.md", "force": True},
        {"id": 18, "type": "configuration.snapshot", "force": True},
        {"id": 19, "type": "harness.overview", "force": True},
        {"id": 20, "type": "recovery.view", "batch": "b-1", "skip": ["a1"]},
        {"id": 21, "type": "container_route.view", "batch": "b", "role": "qa"},
    ]
    for sample in samples:
        assert schemas.REQUESTS.validate_python(sample).type == sample["type"]
    for broken in (
        {"type": "reports.report", "dispatch_id": ""},
        {"type": "reports.timeline", "batch_id": "b" * 65},
        {"type": "recovery.snapshot", "skip": ["x"] * 33},
        {"type": "orchestration.lock", "force": True},
        {"type": "snapshot.page", "snapshot_id": 1, "offset": -1},
        {"type": "task_board.snapshot"},
        {"type": "task_board.snapshot", "spec": ""},
        {"type": "task_board.specs", "spec": "#1"},
        {"type": "harness.snapshot", "online": True},
        {"type": "harness.maintenance", "online": True},
        {"type": "harness.overview", "online": True},
        {"type": "open_project.snapshot", "repo": "/work/other"},
        {"type": "help.snapshot"},
        {"type": "help.snapshot", "language": "de"},
        {"type": "update_harness.snapshot", "path": "x"},
        {"type": "update_harness.diff"},
        {"type": "update_harness.diff", "path": ""},
        {"type": "update_harness.diff", "path": "a" * 513},
        {"type": "configuration.snapshot", "names": ["project.json"]},
        {"type": "recovery.view", "skip": [""]},
        {"type": "recovery.view", "online": True},
        {"type": "container_route.view", "role": ""},
        {"type": "container_route.view", "force": True},
    ):
        with pytest.raises(ValueError):
            schemas.REQUESTS.validate_python(broken)
    replies: list[dict[str, object]] = [
        {
            "v": 1, "id": 1, "type": "reports.snapshot", "ok": True, "snapshot_id": 1,
            "text": "{", "next": 1, "done": False, "cached": True, "age_seconds": 0.5,
        },
        {
            "v": 1, "id": 2, "type": "reports.report", "ok": True, "snapshot_id": 2,
            "text": "{}", "next": 2, "done": True,
        },
        {"v": 1, "id": 3, "type": "snapshot.page", "ok": True, "text": "}", "next": 2,
         "done": True},
        {"v": 1, "id": 4, "type": "orchestration.lock", "ok": True, "lock": None,
         "error": "boom"},
        {
            "v": 1, "id": 5, "type": "task_board.specs", "ok": True, "snapshot_id": 3,
            "text": "{}", "next": 2, "done": True, "cached": False, "age_seconds": 0.0,
        },
        {
            "v": 1, "id": 6, "type": "task_board.snapshot", "ok": True, "snapshot_id": 4,
            "text": "{", "next": 1, "done": False, "cached": True, "age_seconds": 12.5,
        },
    ]
    replies.extend(
        {
            "v": 1, "id": 7, "type": kind, "ok": True, "snapshot_id": 5,
            "text": "{}", "next": 2, "done": True, "cached": False, "age_seconds": 0.0,
        }
        for kind in (
            "diagnostics.snapshot",
            "harness.snapshot",
            "harness.maintenance",
            "update_harness.snapshot",
            "configuration.snapshot",
            "recovery.view",
            "container_route.view",
        )
    )
    replies.append(
        {
            "v": 1, "id": 8, "type": "update_harness.diff", "ok": True,
            "snapshot_id": 6, "text": "{}", "next": 2, "done": True,
        }
    )
    for reply in replies:
        assert schemas.REPLIES.validate_python(reply).type == reply["type"]


def test_the_harness_overview_reply_has_the_service_fields_and_refuses_others() -> None:
    state = {
        "installed": True, "installed_version": "1.0.0", "capabilities": ["core"],
        "skills": 3, "managed_files": 7, "updated_at": "t", "orchestration": True,
    }
    usage = {"unavailable": None, "batches": 2, "tickets": 1, "dispatches": 5,
             "reports": 4}
    store = {"authority": "file-ledger", "schema": 3, "generation": "g-1",
             "audit_records": 9, "cutover_at": None, "reason": ""}
    adapter = {"path": ".harness/adapters/a.json", "status": "current", "problem": None}
    containers = {
        "engine": "docker", "version": "27.4.1", "cgroup_driver": "systemd",
        "cgroup_version": "v2", "selinux": False, "rootless": True, "info_problem": None,
        "images": 3, "images_problem": None, "volumes": None, "volumes_problem": "no volume",
    }
    runtime = {"state": "online", "revision": 12, "reason": ""}
    integration = {"name": "GitHub", "kind": "tracker", "status": "current", "cli": True,
                   "detail": "github.com/o/r"}
    reply: dict[str, object] = {
        "v": 1, "id": 1, "type": "harness.overview", "ok": True, "state": state,
        "package_version": "1.0.1", "drift": "clean", "drift_files": 0,
        "store": store, "adapters": [adapter], "integrations": [integration],
        "runtime": runtime, "containers": containers, "usage": usage,
        "cached": False, "age_seconds": 0.0,
    }
    assert schemas.REPLIES.validate_python(reply).type == "harness.overview"
    assert schemas.REPLIES.validate_python(
        {**reply, "store": None, "adapters": None, "drift_files": None, "containers": None}
    ).type == "harness.overview"
    # An older server sends neither the runtime probe nor the adapters: both stay optional.
    older = {key: value for key, value in reply.items() if key not in {"runtime", "integrations"}}
    assert schemas.REPLIES.validate_python(older).type == "harness.overview"
    assert _fields(schemas.RuntimeStatusPayload) == set(runtime)
    assert _fields(schemas.IntegrationPayload) == set(integration)
    assert {
        field.alias or name
        for name, field in schemas.StorePayload.model_fields.items()
    } == set(store)
    assert _fields(schemas.AdapterPayload) == set(adapter)
    assert _fields(schemas.ContainersPayload) == set(containers)
    assert _fields(schemas.HarnessStatePayload) == set(state)
    assert _fields(schemas.PipelineUsage) == set(usage)
    assert _fields(schemas.HarnessOverviewReply) == set(reply)
    for broken in (
        {**reply, "ledger": {}},
        {**reply, "state": {**state, "extra": 1}},
        {**reply, "usage": {**usage, "batches": -1}},
        {**reply, "usage": {**usage, "qa_runs": 0}},
        {**reply, "store": {**store, "authority": "sqlite"}},
        {**reply, "adapters": [{**adapter, "status": "fine"}]},
        {**reply, "runtime": {**runtime, "state": "starting"}},
        {**reply, "integrations": [{**integration, "kind": "cloud"}]},
        {**reply, "drift_files": -1},
        {**reply, "containers": {**containers, "images": -1}},
        {**reply, "containers": {**containers, "extra": 1}},
    ):
        with pytest.raises(ValueError):
            schemas.REPLIES.validate_python(broken)




def test_every_documented_request_parses_as_its_model() -> None:
    samples: list[dict[str, object]] = [
        {"id": 1, "type": "home.snapshot", "force": True},
        {"id": "p", "type": "home.problems", "snapshot_id": 3, "offset": 0},
        {"id": "s", "type": "job.start", "command_id": "health", "confirmed": True},
        {"id": "g", "type": "job.get", "job_id": "j", "cursor": 2},
        {"id": None, "type": "job.list"},
        {"id": "o", "type": "orchestration.subscribe", "cursor": "abc-1"},
    ]
    for sample in samples:
        parsed = schemas.REQUESTS.validate_python(sample)
        assert parsed.type == sample["type"]
    with pytest.raises(ValueError):
        schemas.REQUESTS.validate_python({"type": "job.list", "extra": 1})


def test_the_job_catalog_models_match_the_job_service_replies(tmp_path: Path) -> None:
    """The section and class enums are those of the server; a real reply validates."""
    import asyncio
    import json
    from typing import get_args

    from harness.console.backend import composition
    from harness.console.backend.domain.jobs import COMMAND_SECTIONS
    from harness.console.kernel.catalog import Reversibility

    assert get_args(schemas.CommandSection) == COMMAND_SECTIONS
    assert set(get_args(schemas.ReversibilityClass)) == {
        member.value for member in Reversibility
    }

    async def idle(
        argv: object, *, cwd: Path, on_output: object, cancel_event: object
    ) -> int:
        return 0

    served = composition.job_service(tmp_path, executor=idle)

    async def answers() -> list[str]:
        out: list[str] = []
        for section in COMMAND_SECTIONS:
            raw = json.dumps({"id": 1, "type": "job.catalog", "section": section})
            out += [text async for text in jobs.replies(raw, served)]
        return out

    for text in asyncio.run(answers()):
        assert schemas.REPLIES.validate_json(text).type == "job.catalog"
    with pytest.raises(ValueError):
        schemas.REQUESTS.validate_python({"type": "job.catalog", "section": "nowhere"})


def test_worker_request_models_have_the_field_sets_of_the_worker_protocol() -> None:
    for model in (schemas.WorkerStepsRequest, schemas.WorkerSubscribeRequest):
        assert _fields(model) == workers._FIELDS
        assert model.model_config.get("extra") == "forbid"
    parsed = schemas.REQUESTS.validate_python(
        {"id": 1, "type": "worker.subscribe", "dispatch_id": "dispatch-a"}
    )
    assert parsed.type == "worker.subscribe"
    for broken in (
        {"type": "worker.steps", "dispatch_id": "dispatch-a"},
        {"type": "worker.steps", "dispatch_id": "../x", "offset": 0},
        {"type": "worker.steps", "dispatch_id": "d", "offset": -1},
        {"type": "worker.subscribe", "dispatch_id": "d", "follow": True},
    ):
        with pytest.raises(ValueError):
            schemas.REQUESTS.validate_python(broken)
    page = {
        "dispatch_id": "d", "source": "plain", "structure": "unavailable",
        "state": "connected", "reason": None, "message": "", "offset": 10,
        "reset": False, "more": False, "last_step_age_seconds": 1,
        "steps": [{"kind": "log", "text": "hi"}],
    }
    reply = {"v": 1, "id": 1, "type": "worker.steps", "ok": True, "page": page}
    assert schemas.REPLIES.validate_python(reply).type == "worker.steps"
    with pytest.raises(ValueError):
        schemas.REPLIES.validate_python(
            {**reply, "page": {**page, "steps": [{"kind": "tool", "text": "x", "input": {}}]}}
        )


def test_the_help_request_schema_accepts_exactly_the_languages_of_the_guide() -> None:
    from typing import get_args

    from harness.console.kernel.help_text import HELP_LANGUAGES

    annotation = schemas.HelpSnapshotRequest.model_fields["language"].annotation

    assert get_args(annotation) == HELP_LANGUAGES


def test_step_models_match_the_live_step_items_and_refuse_extra_fields() -> None:
    from harness.console.backend.api.protocol import steps
    from harness.console.backend.domain import live_steps

    assert _fields(schemas.StepsSubscribeRequest) == steps.FIELDS
    roster = live_steps.RosterDispatch("d", "b", "#1", "developer", "working")
    agent = live_steps.AgentStep(
        "d",
        "b",
        "developer",
        "plain",
        "unavailable",
        "log",
        "hi",
        "2026-11-06T10:00:00Z",
    )
    event = live_steps.orchestration_step(
        {"seq": 1, "event": "qa.run", "dispatch_id": "d", "outcome": "pass"}, [roster]
    )
    assert event is not None
    assert set(schemas.RosterDispatch.model_fields) == set(roster.to_wire())
    assert set(schemas.AgentStep.model_fields) == set(agent.to_wire())
    assert set(schemas.OrchestrationStep.model_fields) == set(event.to_wire())
    envelope = {"v": 1, "id": 1, "type": "steps.subscribe", "ok": True}
    reply = {**envelope, "kind": "steps", "steps": [agent.to_wire(), event.to_wire()]}
    assert schemas.REPLIES.validate_python(reply).type == "steps.subscribe"
    schemas.REPLIES.validate_python(
        {
            **envelope,
            "kind": "roster",
            "reset": True,
            "orchestration": "available",
            "dispatches": [roster.to_wire()],
        }
    )
    extras: tuple[dict[str, object], ...] = (
        {"thinking": "x"},
        {"input": {}},
        {"raw": "{}"},
    )
    for extra in extras:
        with pytest.raises(ValueError):
            schemas.REPLIES.validate_python(
                {**reply, "steps": [{**agent.to_wire(), **extra}]}
            )
    with pytest.raises(ValueError):
        schemas.REQUESTS.validate_python({"type": "steps.subscribe", "cursor": "x"})
