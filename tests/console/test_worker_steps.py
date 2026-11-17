"""Worker steps for console clients: source selection, query, follow and the lock-free reader."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from harness.console.backend.application.worker_steps import (
    WorkerNotFound,
    WorkerStepsQuery,
)
from harness.console.backend.domain.worker_steps import (
    STEP_BUDGET_BYTES,
    StepsPage,
    WorkerFacts,
    page_from_reading,
    select_source,
    valid_dispatch_id,
)
from harness.console.backend.infrastructure.worker_steps import (
    read_worker_checkpoints,
    read_worker_facts,
    read_worker_log,
)
from harness.console.kernel.protocol import MESSAGE_BYTES
from harness.console.tui.client import WorkerSteps
from harness.console.tui.screens.worker_observation import with_server_steps
from harness.orchestration.workflow.delivery import (
    IN_PROCESS_STREAM_REASON,
    execution_operation_id,
)

RECEIPT = {
    "protocol": "harness-worker-v1",
    "dispatch_id": "dispatch-a",
    "log_path": "/x/events.jsonl",
}


def _facts(
    dispatch: Mapping[str, object] | None = None,
    status: Mapping[str, object] | None = None,
) -> WorkerFacts:
    return WorkerFacts(
        dispatch_id="dispatch-a",
        dispatch=dict(dispatch or {"dispatch_id": "dispatch-a"}),
        status=None if status is None else dict(status),
    )


def test_bound_runtime_receipt_selects_structured_steps() -> None:
    facts = _facts(
        {"dispatch_id": "dispatch-a", "resolved_transport": "external"},
        {"adapter_receipt": RECEIPT},
    )

    assert select_source(facts) == "structured"


def test_external_transport_without_receipt_selects_plain_log() -> None:
    assert select_source(_facts({"resolved_transport": "external"})) == "plain"


def test_supervised_dispatch_selects_structured_steps_before_any_receipt() -> None:
    facts = _facts(
        {
            "dispatch_id": "dispatch-a",
            "resolved_transport": "external",
            "execution": {"supervisor": "harness-runtime"},
        }
    )

    assert select_source(facts) == "structured"


def test_foreign_receipt_and_in_process_transport_select_no_log() -> None:
    foreign = {**RECEIPT, "dispatch_id": "dispatch-b"}

    assert select_source(_facts(status={"adapter_receipt": foreign})) == "none"
    assert select_source(_facts({"resolved_transport": "in-process"})) == "none"


def test_dispatch_ids_are_single_safe_names() -> None:
    assert valid_dispatch_id("dispatch-2d309eaf-4c1f")
    for bad in ("", "../x", "a/b", "x" * 101, ".", "a b"):
        assert not valid_dispatch_id(bad)


def test_page_clips_the_message_and_keeps_only_step_fields() -> None:
    page = page_from_reading(
        "dispatch-a",
        {
            "source": "plain",
            "structure": "unavailable",
            "state": "unavailable",
            "reason": "log_missing",
            "message": "m" * 1000,
            "steps": [{"kind": "log", "text": "hello", "raw": "{}"}],
            "offset": 5,
            "reset": False,
            "more": False,
            "last_step_age_seconds": None,
        },
    )

    wire = page.to_wire()
    assert len(page.message.encode()) <= MESSAGE_BYTES
    assert wire["steps"] == [{"kind": "log", "text": "hello"}]
    assert wire["dispatch_id"] == "dispatch-a"
    assert set(wire) == {
        "dispatch_id",
        "source",
        "structure",
        "state",
        "reason",
        "message",
        "offset",
        "reset",
        "more",
        "last_step_age_seconds",
        "steps",
    }


class FakeFacts:
    def __init__(self, facts: WorkerFacts | None) -> None:
        self.facts = facts
        self.calls: list[str] = []

    def __call__(self, repo: Path, dispatch_id: str, /) -> WorkerFacts | None:
        self.calls.append(dispatch_id)
        return self.facts


class FakeLog:
    def __init__(self, pages: list[dict[str, object]]) -> None:
        self.pages = pages
        self.calls: list[tuple[str, int, int]] = []

    def __call__(
        self, repo: Path, facts: WorkerFacts, source: str, offset: int, budget: int, /
    ) -> Mapping[str, object]:
        self.calls.append((source, offset, budget))
        return self.pages.pop(0) if self.pages else _reading(offset)


def _reading(offset: int, *texts: str, **extra: object) -> dict[str, object]:
    return {
        "source": "structured",
        "structure": "available",
        "state": "connected",
        "reason": None,
        "message": "",
        "steps": [{"kind": "output", "text": text} for text in texts],
        "offset": offset,
        "reset": False,
        "more": False,
        "last_step_age_seconds": 0,
        **extra,
    }


def _query(facts: FakeFacts, log: FakeLog) -> WorkerStepsQuery:
    async def no_sleep(_: float) -> None:
        return None

    return WorkerStepsQuery(
        Path("/repo"), facts=facts, log=log, checkpoints=_no_checkpoints, sleep=no_sleep
    )


def _no_checkpoints(_repo: Path, _facts: WorkerFacts) -> list[Mapping[str, object]]:
    return []


def test_query_reads_the_selected_source_from_the_offset() -> None:
    log = FakeLog([_reading(42, "hi")])
    query = _query(
        FakeFacts(_facts(status={"adapter_receipt": RECEIPT})),
        log,
    )

    page = asyncio.run(query.read("dispatch-a", 7))

    assert log.calls == [("structured", 7, STEP_BUDGET_BYTES)]
    assert [step.text for step in page.steps] == ["hi"]
    assert page.offset == 42


def test_query_without_a_log_is_explicitly_unavailable() -> None:
    log = FakeLog([])
    page = asyncio.run(_query(FakeFacts(_facts()), log).read("dispatch-a", 3))

    assert log.calls == []
    assert (page.source, page.state, page.reason) == ("none", "unavailable", "no_log")
    assert page.offset == 3 and page.message


def test_unknown_dispatch_is_not_found() -> None:
    with pytest.raises(WorkerNotFound):
        asyncio.run(_query(FakeFacts(None), FakeLog([])).read("dispatch-a", 0))


def test_follow_sends_new_steps_and_state_changes_only() -> None:
    log = FakeLog(
        [
            _reading(10, "one"),
            _reading(10),
            _reading(20, "two"),
            _reading(20, state="unavailable", reason="log_missing", message="gone"),
            _reading(20, state="unavailable", reason="log_missing", message="gone"),
            _reading(0, "fresh", reset=True),
        ]
    )
    query = _query(FakeFacts(_facts(status={"adapter_receipt": RECEIPT})), log)

    async def collect() -> list[StepsPage]:
        pages: list[StepsPage] = []
        async for page in query.follow("dispatch-a", 0):
            pages.append(page)
            if len(pages) == 4:
                break
        return pages

    pages = asyncio.run(collect())

    assert [[s.text for s in page.steps] for page in pages] == [
        ["one"],
        ["two"],
        [],
        ["fresh"],
    ]
    assert pages[2].reason == "log_missing"
    assert pages[3].reset is True
    assert [call[1] for call in log.calls] == [0, 10, 10, 20, 20, 20]


def _ledger(repo: Path) -> Path:
    root = repo / ".harness/orchestration/state"
    (root / "dispatches").mkdir(parents=True)
    (root / "dispatch-status").mkdir()
    return root


def test_infrastructure_reads_records_without_a_lock_and_changes_nothing(
    tmp_path: Path,
) -> None:
    root = _ledger(tmp_path)
    dispatch = {
        "dispatch_id": "dispatch-a",
        "state": "working",
        "resolved_transport": "external",
        "report_staging_path": str(
            tmp_path / ".harness/.sandboxes/scratch/inbox/dispatch-a.json"
        ),
    }
    (root / "dispatches/dispatch-a.json").write_text(json.dumps(dispatch))
    (root / "dispatch-status/dispatch-a.json").write_text(
        json.dumps({"dispatch_id": "dispatch-a", "state": "working"})
    )
    logs = tmp_path / ".harness/.sandboxes/scratch/worker-logs"
    logs.mkdir(parents=True)
    (logs / "dispatch-a.log").write_text("[t] codex\nworking on it\n")
    before = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    facts = read_worker_facts(tmp_path, "dispatch-a")
    assert facts is not None
    reading = read_worker_log(
        tmp_path, facts, select_source(facts), 0, STEP_BUDGET_BYTES
    )

    assert reading["source"] == "plain"
    assert reading["structure"] == "unavailable"
    assert reading["steps"] == [{"kind": "log", "text": "working on it"}]
    after = {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert read_worker_facts(tmp_path, "dispatch-b") is None


def test_infrastructure_reads_the_run_log_of_a_supervised_worker_while_it_grows(
    tmp_path: Path,
) -> None:
    root = _ledger(tmp_path)
    dispatch = {
        "dispatch_id": "dispatch-a",
        "state": "working",
        "resolved_transport": "external",
        "execution": {"supervisor": "harness-runtime"},
    }
    (root / "dispatches/dispatch-a.json").write_text(json.dumps(dispatch))
    (root / "dispatch-status/dispatch-a.json").write_text(
        json.dumps({"dispatch_id": "dispatch-a", "state": "working"})
    )
    log = root / "executions" / execution_operation_id(dispatch) / "stdout.log"
    log.parent.mkdir(parents=True)
    log.write_text(json.dumps({"type": "system", "subtype": "init"}) + "\n")
    facts = read_worker_facts(tmp_path, "dispatch-a")
    assert facts is not None

    first = read_worker_log(tmp_path, facts, select_source(facts), 0, STEP_BUDGET_BYTES)
    with log.open("a") as stream:
        stream.write(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "text", "text": "half way"}]},
                }
            )
            + "\n"
        )
    second = read_worker_log(
        tmp_path, facts, "structured", int(str(first["offset"])), STEP_BUDGET_BYTES
    )

    assert (first["source"], first["state"]) == ("structured", "connected")
    assert first["steps"] == [{"kind": "system", "text": "Runtime session connected"}]
    assert second["steps"] == [{"kind": "output", "text": "half way"}]
    assert second["offset"] == log.stat().st_size


def test_infrastructure_reads_the_checkpoints_this_dispatch_recorded_and_skips_unusable_ones(
    tmp_path: Path,
) -> None:
    root = _ledger(tmp_path)
    (root / "batches").mkdir()
    (root / "checkpoints").mkdir()
    (root / "dispatches/dispatch-a.json").write_text(
        json.dumps(
            {
                "dispatch_id": "dispatch-a",
                "batch_id": "batch-1",
                "state": "working",
                "resolved_transport": "in-process",
            }
        )
    )
    (root / "batches/batch-1.json").write_text(
        json.dumps(
            {
                "batch_id": "batch-1",
                "state": "active",
                "checkpoints": [
                    {"checkpoint_id": "cp-1", "dispatch_id": "dispatch-a"},
                    {"checkpoint_id": "cp-2", "dispatch_id": "dispatch-b"},
                    {"checkpoint_id": "cp-missing", "dispatch_id": "dispatch-a"},
                    {"checkpoint_id": "../cp-1", "dispatch_id": "dispatch-a"},
                    "not an entry",
                    {"checkpoint_id": "cp-broken", "dispatch_id": "dispatch-a"},
                    {"checkpoint_id": "cp-3", "dispatch_id": "dispatch-a"},
                ],
            }
        )
    )
    (root / "checkpoints/cp-broken.json").write_text("{not json")
    for checkpoint_id, sha, created in (
        ("cp-1", "1111111aaaa", "2026-11-05T10:02:00+00:00"),
        ("cp-2", "2222222bbbb", "2026-11-05T10:03:00+00:00"),
        ("cp-3", "3333333cccc", "2026-11-05T10:04:00+00:00"),
    ):
        (root / f"checkpoints/{checkpoint_id}.json").write_text(
            json.dumps(
                {
                    "checkpoint_id": checkpoint_id,
                    "batch_id": "batch-1",
                    "commit_sha": sha,
                    "created_at": created,
                }
            )
        )
    facts = read_worker_facts(tmp_path, "dispatch-a")
    assert facts is not None

    sut = read_worker_checkpoints(tmp_path, facts)

    assert sut == [
        {
            "checkpoint_id": "cp-1",
            "commit_sha": "1111111aaaa",
            "created_at": "2026-11-05T10:02:00+00:00",
        },
        {
            "checkpoint_id": "cp-3",
            "commit_sha": "3333333cccc",
            "created_at": "2026-11-05T10:04:00+00:00",
        },
    ]


@pytest.mark.parametrize("batch_id", [None, "../batch-1", "batch-gone"])
def test_infrastructure_reads_no_checkpoints_without_a_usable_batch(
    tmp_path: Path, batch_id: str | None
) -> None:
    _ledger(tmp_path)
    facts = WorkerFacts(
        dispatch_id="dispatch-a",
        dispatch={"dispatch_id": "dispatch-a", "batch_id": batch_id},
        status=None,
    )

    assert read_worker_checkpoints(tmp_path, facts) == []


def test_infrastructure_reports_typed_reasons_for_unusable_paths(
    tmp_path: Path,
) -> None:
    _ledger(tmp_path)
    outside = WorkerFacts(
        dispatch_id="dispatch-a",
        dispatch={
            "dispatch_id": "dispatch-a",
            "resolved_transport": "external",
            "report_staging_path": str(tmp_path / "elsewhere/inbox/x.json"),
        },
        status=None,
    )
    missing = WorkerFacts(
        dispatch_id="dispatch-a",
        dispatch={
            "dispatch_id": "dispatch-a",
            "resolved_transport": "external",
            "report_staging_path": str(
                tmp_path / ".harness/.sandboxes/scratch/inbox/x.json"
            ),
        },
        status=None,
    )

    assert (
        read_worker_log(tmp_path, outside, "plain", 0, 100)["reason"]
        == "log_outside_storage"
    )
    assert read_worker_log(tmp_path, missing, "plain", 0, 100)["reason"] == (
        "log_missing"
    )


def test_external_text_log_without_codex_sections_keeps_its_typed_reason(
    tmp_path: Path,
) -> None:
    _ledger(tmp_path)
    logs = tmp_path / ".harness/.sandboxes/scratch/worker-logs"
    logs.mkdir(parents=True)
    (logs / "dispatch-a.log").write_text("claude text output SECRET\n")
    facts = WorkerFacts(
        dispatch_id="dispatch-a",
        dispatch={
            "dispatch_id": "dispatch-a",
            "resolved_transport": "external",
            "report_staging_path": str(
                tmp_path / ".harness/.sandboxes/scratch/inbox/x.json"
            ),
        },
        status=None,
    )

    page = page_from_reading(
        "dispatch-a", read_worker_log(tmp_path, facts, "plain", 0, 4096)
    )

    assert (page.source, page.structure, page.state, page.reason) == (
        "plain",
        "unavailable",
        "unavailable",
        "log_unrecognised",
    )
    assert page.steps == ()
    assert page.message
    assert "SECRET" not in json.dumps(page.to_wire())


def test_server_steps_keep_the_in_process_reason_and_drop_the_observer_stream_reason() -> (
    None
):
    snapshot = {
        "dispatch_id": "dispatch-a",
        "stream_state": "absent",
        "stream_reason": IN_PROCESS_STREAM_REASON,
        "checkpoints": [],
    }
    page = WorkerSteps(
        source="none",
        structure="unavailable",
        state="unavailable",
        reason="no_log",
        message="",
        offset=0,
        reset=False,
        more=False,
        last_step_age_seconds=None,
        steps=(),
    )

    for steps, failure in ((None, "no_server"), (page, "no_dispatch")):
        shown = with_server_steps(snapshot, steps, failure)
        assert shown["stream_reason"] == IN_PROCESS_STREAM_REASON
        assert shown["checkpoints"] == []

    observer = {
        **snapshot,
        "stream_reason": "event stream is missing or unreadable; worker outcome is independent",
    }
    assert "stream_reason" not in with_server_steps(observer, None, "no_server")


def test_query_observes_an_in_process_dispatch_and_reads_no_checkpoints_for_another(
    tmp_path: Path,
) -> None:
    checkpoint = {
        "checkpoint_id": "cp-1",
        "commit_sha": "1111111aaaa",
        "created_at": "2026-11-05T10:02:00+00:00",
    }
    transports = {"dispatch-a": "in-process", "dispatch-b": "external"}
    asked: list[str] = []

    def facts(_repo: Path, dispatch_id: str) -> WorkerFacts | None:
        if dispatch_id not in transports:
            return None
        return WorkerFacts(
            dispatch_id=dispatch_id,
            dispatch={
                "dispatch_id": dispatch_id,
                "resolved_transport": transports[dispatch_id],
            },
            status={"dispatch_id": dispatch_id, "state": "working"},
        )

    def checkpoints(_repo: Path, found: WorkerFacts) -> list[Mapping[str, object]]:
        asked.append(found.dispatch_id)
        return [checkpoint]

    sut = WorkerStepsQuery(
        tmp_path, facts=facts, log=read_worker_log, checkpoints=checkpoints
    )

    observed = asyncio.run(sut.observation("dispatch-a"))
    external = asyncio.run(sut.observation("dispatch-b"))
    unknown = asyncio.run(sut.observation("dispatch-c"))

    assert observed is not None
    assert observed.to_wire()["checkpoints"] == [checkpoint]
    assert (external, unknown) == (None, None)
    assert asked == ["dispatch-a"]
