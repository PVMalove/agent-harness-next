"""Live activity of the console (#1296): decisions and stops of the auto policy in the event
journal, the stages of a container QA run while it runs, and what the runtime observes of an
execution, with the cadence the step feed asks it at."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import cast

from harness.console.backend.application.live_steps import (
    EXECUTION_AFTER_END_SECONDS,
    EXECUTION_SECONDS,
    LiveSteps,
)
from harness.console.backend.domain.events import BatchFacts, Observation, compact, diff
from harness.console.backend.domain.live_steps import (
    RosterDispatch,
    execution_summary,
    orchestration_step,
)
from harness.console.backend.domain.worker_steps import (
    WorkerFacts,
    no_log_page,
    page_from_reading,
    select_source,
)
from harness.console.backend.infrastructure.orchestration_reader import _observation
from harness.console.backend.infrastructure.worker_steps import read_execution_summary
from harness.orchestration.ledger.lifecycle import JsonObject
from harness.orchestration.worker_observation import (
    QA_STAGE_STRIDE,
    QA_TAIL_LINES,
    read_qa_stage_steps,
)

AUTO_DECISION: JsonObject = {
    "sequence": 1,
    "kind": "decision",
    "dispatch_id": "dispatch-d",
    "approved_by": "policy:auto",
    "approved_at": "2026-11-26T10:00:00Z",
    "rationale": "a clean developer report",
    "evidence": {"decision": "accept"},
}
AUTO_STOP: JsonObject = {
    "category": "no-automatic-route",
    "reason": "carried-items-not-closed",
    "detected_at": "2026-11-26T10:05:00Z",
    "detected_by": "batch auto-decide",
}


def _observed(*decisions: JsonObject, stop: JsonObject | None = None) -> Observation:
    return Observation(
        "file",
        {
            "batch-1": BatchFacts(
                ticket="#885",
                state="active",
                dispatches=(("dispatch-d", "developer", "reported"),),
                decisions=(),
                auto_decisions=tuple(decisions),
                auto_stop=stop,
            )
        },
    )


def _auto_events(events: list[dict[str, object]]) -> list[dict[str, object]]:
    return [event for event in events if str(event["event"]).startswith("auto.")]


def test_a_new_batch_gives_its_auto_decisions_and_stop() -> None:
    events = _auto_events(diff({}, _observed(AUTO_DECISION, stop=AUTO_STOP)))

    assert events == [
        {
            "event": "auto.decision",
            "batch_id": "batch-1",
            "dispatch_id": "dispatch-d",
            "decision": "accept",
            "kind": "decision",
            "approved_by": "policy:auto",
            "approved_at": "2026-11-26T10:00:00Z",
            "message": "a clean developer report",
        },
        {
            "event": "auto.stop",
            "batch_id": "batch-1",
            "category": "no-automatic-route",
            "message": "carried-items-not-closed",
            "detected_at": "2026-11-26T10:05:00Z",
        },
    ]


def test_only_new_auto_decisions_and_a_new_stop_are_events() -> None:
    before = compact(_observed(AUTO_DECISION))
    later: JsonObject = {**AUTO_DECISION, "sequence": 2, "kind": "dispatch", "evidence": {}}

    events = _auto_events(diff(before, _observed(AUTO_DECISION, later, stop=AUTO_STOP)))

    assert [(event["event"], event.get("decision")) for event in events] == [
        ("auto.decision", "dispatch"),
        ("auto.stop", None),
    ]
    assert _auto_events(diff(compact(_observed(AUTO_DECISION, stop=AUTO_STOP)), _observed(AUTO_DECISION, stop=AUTO_STOP))) == []


def test_a_view_from_before_the_auto_fields_replays_no_history() -> None:
    """A journal written by an older server holds no counts: the first poll after the upgrade
    shows only what happens from then on."""
    old = compact(_observed(AUTO_DECISION, stop=AUTO_STOP))
    for batch in cast(dict[str, dict[str, object]], old["batches"]).values():
        del batch["auto_decisions"], batch["auto_stop"]

    assert _auto_events(diff(old, _observed(AUTO_DECISION, stop=AUTO_STOP))) == []


def test_the_reader_takes_auto_decisions_and_the_stop_from_the_batch_record() -> None:
    observation = _observation(
        "file",
        {
            "batches/batch-1.json": {
                "batch_id": "batch-1",
                "ticket": "#885",
                "state": "paused",
                "dispatches": [],
                "auto_decisions": [AUTO_DECISION, "not a record"],
                "auto_stop": AUTO_STOP,
            }
        },
        {},
        {},
        lambda _dispatch: None,
    )

    batch = observation.batches["batch-1"]
    assert batch.auto_decisions == (AUTO_DECISION,)
    assert batch.auto_stop == AUTO_STOP


def test_an_auto_step_carries_its_approver_and_a_stop_its_category() -> None:
    roster = (RosterDispatch("dispatch-d", "batch-1", "#885", "developer", "working"),)
    events = diff({}, _observed(AUTO_DECISION, stop=AUTO_STOP))
    steps = [
        orchestration_step({**event, "seq": index, "observed_at": "now"}, roster)
        for index, event in enumerate(_auto_events(events))
    ]

    assert steps[0] is not None and steps[1] is not None
    assert (steps[0].event, steps[0].approved_by, steps[0].role) == (
        "auto.decision",
        "policy:auto",
        "developer",
    )
    assert (steps[1].event, steps[1].category, steps[1].message) == (
        "auto.stop",
        "no-automatic-route",
        "carried-items-not-closed",
    )


# -- the stages of a container QA run --------------------------------------------------------


def _record(directory: Path, index: int, stage: str, code: int, **extra: object) -> None:
    record = {
        "index": index,
        "stage_id": stage,
        "result": "ran",
        "exit_code": code,
        "domain": None if code == 0 else "code_test",
        "duration_ms": 1500,
        **extra,
    }
    (directory / f"{index:03}.json").write_text(json.dumps(record), encoding="utf-8")


def _kinds(page: dict[str, object]) -> list[tuple[str, str]]:
    steps = cast(list[dict[str, str]], page["steps"])
    return [(step["kind"], step["text"]) for step in steps]


def test_a_running_qa_run_shows_finished_stages_and_the_running_ones_tail(tmp_path: Path) -> None:
    (tmp_path / "lint.stdout.log").write_text("ruff: ok\n", encoding="utf-8")
    _record(tmp_path, 0, "lint", 0)
    (tmp_path / "tests.stdout.log").write_text(
        "\x1b[32m...\x1b[0m\nAPI_TOKEN=s3cr3t-value\n", encoding="utf-8"
    )

    first = read_qa_stage_steps(tmp_path, 0, 48 * 1024)

    assert first["source"] == "stages" and first["state"] == "connected"
    steps = _kinds(first)
    assert steps[:5] == [
        ("stage", "lint"),
        ("output", "ruff: ok"),
        ("stage-result", "lint: pass · exit 0 · 1.5 s"),
        ("stage", "tests"),
        ("output", "..."),
    ]
    kind, secret_line = steps[5]
    assert kind == "output" and secret_line.startswith("API_TOKEN=")
    assert "s3cr3t-value" not in json.dumps(first)
    offset = first["offset"]
    assert isinstance(offset, int) and offset // QA_STAGE_STRIDE == 1

    with (tmp_path / "tests.stdout.log").open("a", encoding="utf-8") as log:
        log.write("1 failed\n")
    _record(tmp_path, 1, "tests", 1)
    second = read_qa_stage_steps(tmp_path, offset, 48 * 1024)

    assert _kinds(second) == [
        ("output", "1 failed"),
        ("stage-result", "tests: fail · exit 1 · 1.5 s · code_test"),
    ]
    assert second["offset"] == 2 * QA_STAGE_STRIDE
    assert _kinds(read_qa_stage_steps(tmp_path, cast(int, second["offset"]), 48 * 1024)) == []


def test_a_stage_shows_only_the_tail_of_its_output(tmp_path: Path) -> None:
    lines = "".join(f"line {index}\n" for index in range(100))
    (tmp_path / "tests.stdout.log").write_text(lines, encoding="utf-8")

    page = read_qa_stage_steps(tmp_path, 0, 48 * 1024)

    output = [text for kind, text in _kinds(page) if kind == "output"]
    assert output == [f"line {index}" for index in range(100 - QA_TAIL_LINES, 100)]


def test_before_the_run_starts_the_page_waits_and_fewer_records_reset_it(tmp_path: Path) -> None:
    waiting = read_qa_stage_steps(tmp_path / "commands", 0, 48 * 1024)
    assert (waiting["state"], waiting["steps"]) == ("waiting", [])

    _record(tmp_path, 0, "lint", 0)
    reset = read_qa_stage_steps(tmp_path, 5 * QA_STAGE_STRIDE, 48 * 1024)
    assert reset["reset"] is True
    assert ("stage-result", "lint: pass · exit 0 · 1.5 s") in _kinds(reset)


def test_a_container_qa_run_has_stages_and_a_host_run_says_why_it_has_none() -> None:
    container = WorkerFacts("dispatch-q", {"role": "qa", "qa_execution": {"x": 1}}, None)
    host = WorkerFacts("dispatch-q", {"role": "qa", "resolved_transport": "external"}, None)

    assert select_source(container) == "stages"
    assert select_source(host) == "none"
    page = no_log_page("dispatch-q", 0, qa=True)
    assert (page.reason, page.structure) == ("qa_on_host", "unavailable")
    stages = page_from_reading("dispatch-q", {"source": "stages", "state": "waiting"})
    assert (stages.source, stages.structure) == ("stages", "available")


# -- what the runtime observes of an execution -----------------------------------------------


def test_an_execution_summary_keeps_the_facts_a_screen_shows() -> None:
    summary = execution_summary(
        {
            "kind": "container",
            "state": "exited",
            "engine": "docker",
            "container_id": "c" * 64,
            "execution_deadline": "2026-11-26T11:00:00Z",
            "launch": {"images": {"worker": "sha256:abc"}},
            "observation": {"observed_at": "2026-11-26T10:30:00Z"},
            "exit": {"code": 137, "stopped_by": "deadline", "oom_killed": False},
        },
        {"removed": True},
        [f"line {index}" for index in range(8)],
    )

    assert summary.to_wire() == {
        "kind": "container",
        "state": "exited",
        "engine": "docker",
        "image": "sha256:abc",
        "container_id": "c" * 64,
        "deadline": "2026-11-26T11:00:00Z",
        "observed_at": "2026-11-26T10:30:00Z",
        "exit_code": 137,
        "stopped_by": "deadline",
        "oom_killed": False,
        "teardown": "removed",
        "stderr_tail": [f"line {index}" for index in range(3, 8)],
    }


def test_the_file_ledger_has_no_execution_to_observe(tmp_path: Path) -> None:
    facts = WorkerFacts("dispatch-d", {"execution": {"supervisor": "harness-runtime"}}, None)

    assert read_execution_summary(tmp_path, facts) is None


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_the_feed_asks_the_runtime_at_a_bounded_cadence() -> None:
    """A live execution is asked at most every `EXECUTION_SECONDS`; one that ended while it was
    followed for `EXECUTION_AFTER_END_SECONDS` more; one never seen live is never asked."""
    clock = _Clock()
    asked: list[str] = []
    summary = execution_summary({"kind": "process", "state": "running"}, None, [])

    async def execution(dispatch_id: str):  # type: ignore[no-untyped-def]
        asked.append(dispatch_id)
        return summary

    feed = LiveSteps(
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        now=lambda: "now",
        live_states={"working"},
        execution=execution,
        monotonic=clock,
    )
    live = RosterDispatch("dispatch-live", "batch-1", "#885", "developer", "working")
    old = RosterDispatch("dispatch-old", "batch-1", "#885", "architect", "reported")

    def tick() -> tuple[RosterDispatch, ...]:
        return asyncio.run(feed._executed((live, old)))

    first = tick()
    assert asked == ["dispatch-live"]
    assert first[0].execution == summary and first[1].execution is None
    clock.now = EXECUTION_SECONDS / 2
    tick()
    assert asked == ["dispatch-live"]
    clock.now = EXECUTION_SECONDS
    tick()
    assert asked == ["dispatch-live"] * 2
    live = RosterDispatch("dispatch-live", "batch-1", "#885", "developer", "reported")
    tick()
    assert asked == ["dispatch-live"] * 3  # its state changed: asked at once
    clock.now += EXECUTION_AFTER_END_SECONDS + 1
    ended = tick()
    assert asked == ["dispatch-live"] * 3
    assert ended[0].execution == summary


# -- the batch timeline and the TUI's «Ход работы» tabs ----------------------------------------


def _timeline_view() -> object:
    from harness.console.kernel import reports

    batch: JsonObject = {
        "batch_id": "batch-1",
        "auto_decisions": [AUTO_DECISION],
        "auto_stop": AUTO_STOP,
        "recovery_events": [
            {
                "kind": "pause",
                "approved_by": "policy:auto",
                "approved_at": "2026-11-26T10:05:01Z",
                "note": "no-automatic-route: carried-items-not-closed",
            }
        ],
    }
    return reports.LedgerView(
        batches=[reports.BatchSummary("batch-1", "#885", "paused", "2026-11-26T09:00:00Z")],
        _batch_records={"batch-1": batch},
    )


def test_the_batch_timeline_shows_the_automatic_path() -> None:
    from harness.console.kernel import reports

    view = cast(reports.LedgerView, _timeline_view())
    timeline = view.timeline("batch-1")

    assert timeline is not None
    texts = [event.text for event in timeline.events]
    assert "политика auto: accept (dispatch-d) — a clean developer report" in texts
    assert (
        "автоматический путь остановлен: no-automatic-route — carried-items-not-closed"
        in texts
    )
    assert (
        "восстановление: pause (policy:auto) — no-automatic-route: carried-items-not-closed"
        in texts
    )


def test_the_tui_tabs_word_the_execution_and_the_timeline() -> None:
    from harness.console.kernel import reports
    from harness.console.tui.screens.worker_observation import (
        execution_lines,
        timeline_rows,
    )

    summary = execution_summary(
        {
            "kind": "container",
            "state": "running",
            "engine": "podman",
            "container_id": "abcdef1234567890",
            "launch": {"images": {"worker": "sha256:abc"}},
        },
        None,
        ["Error: no model"],
    )

    lines = execution_lines(summary, lambda text: text)

    assert lines[:4] == [
        "Контейнер worker: running",
        "Движок: podman",
        "Образ: sha256:abc",
        "ID контейнера: abcdef123456",
    ]
    assert "Завершение: ещё не завершилось" in lines
    assert lines[-2:] == ["Последние строки stderr:", "  Error: no model"]
    assert execution_lines(None, lambda text: text) == [
        "Runtime не надзирает за этим dispatch или не ответил."
    ]
    timeline = cast(reports.LedgerView, _timeline_view()).timeline("batch-1")
    shown = timeline_rows(timeline, limit=2)
    assert len(shown) == 2
    at, kind, _role, text = shown[-1]
    assert (at, kind) == ("10:05:01", "decision") and "восстановление: pause" in text
