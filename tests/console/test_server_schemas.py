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
    }
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
        "snapshot.page": schemas.SnapshotPageRequest,
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
    ]
    for sample in samples:
        assert schemas.REQUESTS.validate_python(sample).type == sample["type"]
    for broken in (
        {"type": "reports.report", "dispatch_id": ""},
        {"type": "reports.timeline", "batch_id": "b" * 65},
        {"type": "recovery.snapshot", "skip": ["x"] * 33},
        {"type": "orchestration.lock", "force": True},
        {"type": "snapshot.page", "snapshot_id": 1, "offset": -1},
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
    ]
    for reply in replies:
        assert schemas.REPLIES.validate_python(reply).type == reply["type"]




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
