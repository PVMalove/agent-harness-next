"""The exported OpenAPI and WebSocket JSON Schema match the models, and the models match the
replies a real console server sends."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel, TypeAdapter

from harness.console.backend.api import schemas
from harness.console.backend.api.protocol import events as orchestration_events
from harness.console.backend.api.protocol import jobs


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
