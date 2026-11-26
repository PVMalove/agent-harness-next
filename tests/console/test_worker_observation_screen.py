"""The «Ход работы» poll shows a running external worker whatever the console server does (#1281)."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from harness.console.kernel.reports import BatchSummary, LedgerView, StageEntry
from harness.console.tui.client import ConnectionLost, WorkerSteps
from harness.console.tui.screens import worker_observation
from harness.console.tui.screens.worker_observation import (
    Poll,
    PollGate,
    poll_worker,
    session_choices,
    session_options,
)

DISPATCH = "dispatch-18b68696-832e-437d-9721-c80114285a64"
REPO = Path("/repo")


def _working(offset: int) -> dict[str, object]:
    """What the observer reads for a live external worker from its `stdout.log`."""
    events = (
        [
            {"kind": "tool", "text": "Bash"},
            {"kind": "output", "text": "verify.py вернул rc=1; ищу упавший шаг."},
        ]
        if offset == 0
        else []
    )
    return {
        "dispatch_id": DISPATCH,
        "ticket": "#1028",
        "state": "working",
        "startup": {"observation": {"state": "live"}},
        "heartbeat_at": "2026-11-26T13:11:45Z",
        "events": events,
        "next_offset": 392703,
        "reset": False,
        "stream_state": "connected",
        "last_event_age_seconds": 3,
    }


def _observer(repo: Path, dispatch: str, offset: int) -> dict[str, object]:
    return _working(offset)


def _poll(reader: object, **offsets: object) -> Poll:
    arguments = {"observer_offset": 0, "server_offset": 0, "steps_failure": None}
    return poll_worker(REPO, DISPATCH, _observer, reader, **{**arguments, **offsets})  # type: ignore[arg-type]


def _page(offset: int) -> WorkerSteps:
    return WorkerSteps(
        source="structured",
        structure="available",
        state="connected",
        reason=None,
        message="",
        offset=offset,
        reset=False,
        more=False,
        last_step_age_seconds=1,
        steps=(("tool", "Read"),),
    )


@pytest.mark.parametrize("server", ["none", "unknown_dispatch", "busy", "broken"])
def test_a_running_external_worker_shows_its_facts_and_observer_steps_without_a_server_page(
    monkeypatch: pytest.MonkeyPatch, server: str
) -> None:
    monkeypatch.setattr(worker_observation, "STEPS_WAIT_SECONDS", 0.05)
    held = threading.Event()  # another screen holds the console connection
    calls: list[tuple[str, int]] = []

    def steps(dispatch: str, offset: int) -> WorkerSteps | None:
        calls.append((dispatch, offset))
        if server == "busy":
            held.wait(10)
        if server == "broken":
            raise ConnectionLost("соединение с сервером консоли потеряно")
        return None  # the server ledger does not know the dispatch

    try:
        first = _poll(None if server == "none" else steps)
    finally:
        held.set()

    shown = first.snapshot
    assert (shown["state"], shown["heartbeat_at"], shown["stream_state"]) == (
        "working",
        "2026-11-26T13:11:45Z",
        "connected",
    )
    assert [event["text"] for event in shown["events"]] == [
        "Bash",
        "verify.py вернул rc=1; ищу упавший шаг.",
    ]
    assert "steps_reason" not in shown
    assert first.observer_offset == 392703
    assert first.steps_failure is not None

    # The next poll follows the observer from its own offset and does not ask the server again.
    calls.clear()
    second = _poll(
        steps, observer_offset=first.observer_offset, steps_failure=first.steps_failure
    )
    assert calls == []
    assert second.snapshot["events"] == []
    assert second.steps_failure == first.steps_failure


def test_a_server_page_replaces_the_observer_events_and_keeps_both_offsets() -> None:
    result = _poll(lambda dispatch, offset: _page(offset + 10), server_offset=5)

    assert result.snapshot["events"] == [{"kind": "tool", "text": "Read"}]
    assert result.snapshot["next_offset"] == 15
    assert result.observer_offset == 392703
    assert result.steps_failure is None


def test_a_failed_observer_is_an_observation_error_never_a_silent_stop() -> None:
    def failing(repo: Path, dispatch: str, offset: int) -> dict[str, object]:
        raise TimeoutError("runtime store did not answer")

    result = poll_worker(
        REPO,
        DISPATCH,
        failing,
        None,
        observer_offset=7,
        server_offset=0,
        steps_failure=None,
    )

    assert result.snapshot == {"dispatch_id": DISPATCH, "observation_error": True}
    assert result.observer_offset == 7


def test_a_hung_poll_is_reported_as_stalled_and_a_new_view_polls_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker_observation, "POLL_STALL_SECONDS", 10.0)
    now = [100.0]
    gate = PollGate(clock=lambda: now[0])

    assert gate.begin(0)
    assert not gate.begin(0)
    assert not gate.stalled(0)
    now[0] = 110.0
    assert gate.stalled(0)
    # Another session or a reconnect starts a new view while the old poll still hangs.
    assert gate.begin(1)
    gate.finish(0)  # the late poll of the old view releases nothing
    assert not gate.begin(1)
    gate.finish(1)
    assert gate.begin(1)


def test_the_session_list_puts_running_sessions_first_and_keeps_a_dispatch_the_ledger_lacks() -> (
    None
):
    view = LedgerView(
        batches=[BatchSummary("batch-1", "#1028", "open", "2026-11-26T10:00:00Z")],
        stages=[
            StageEntry(
                "dispatch-old",
                "batch-1",
                "#1028",
                "qa",
                "abandoned",
                "2026-11-26T12:00:00Z",
            ),
            StageEntry(
                "dispatch-run",
                "batch-1",
                "#1028",
                "developer",
                "working",
                "2026-11-26T11:00:00Z",
            ),
            StageEntry(
                "dispatch-new",
                "batch-1",
                "#1028",
                "code-review",
                "working",
                "2026-11-26T13:00:00Z",
            ),
        ],
    )

    found = session_choices(view, "dispatch-missing")

    assert [value for _, value in found.choices] == [
        "dispatch-missing",
        "dispatch-new",
        "dispatch-run",
        "dispatch-old",
    ]
    assert found.choices[1][0] == "#1028 · code-review"
    assert found.batches == frozenset({"batch-1"})
    assert set(found.stages) == {"dispatch-old", "dispatch-run", "dispatch-new"}
    assert session_choices(LedgerView(), None).choices == []


def test_each_session_is_one_option_with_its_card_and_the_dispatch_as_its_id() -> None:
    from rich.text import Text

    choices = [(f"#{n} · developer", f"dispatch-{n}") for n in range(800)]

    options = session_options(
        choices, lambda label, dispatch: Text(f"{label}\n{dispatch}")
    )

    shown = [option for option in options if option is not None]
    assert [option.id for option in shown] == [dispatch for _, dispatch in choices]
    assert str(shown[1].prompt) == "#1 · developer\ndispatch-1"
    # A separator follows every card, as the border under each list row did.
    assert options[1::2] == [None] * len(choices)
    assert session_options([], lambda label, dispatch: Text(label)) == []


def _plain(renderable: object, width: int = 40) -> list[str]:
    from rich.console import Console

    console = Console(width=width, record=True, color_system=None)
    console.print(renderable)
    return [line.rstrip() for line in console.export_text().splitlines()]


def test_a_session_event_is_one_chip_and_its_text_with_a_hanging_indent() -> None:
    from harness.console.tui.screens.worker_observation import transcript_row

    assert _plain(transcript_row({"kind": "output", "text": "Читаю тикет"})) == [
        " ●  Читаю тикет"
    ]
    assert _plain(
        transcript_row({"kind": "tool", "text": "Bash uv sync\n--locked"})
    ) == [" ◆  Bash uv sync", "    --locked"]
    assert _plain(transcript_row({"kind": "error", "text": "boom"})) == [" ✖  boom"]
    assert _plain(transcript_row({"kind": "new-kind", "text": "x"})) == [" ○  x"]


def test_a_finished_qa_stage_shows_its_result_as_the_chip() -> None:
    from harness.console.tui.screens.worker_observation import transcript_row

    def chip(text: str) -> str:
        return _plain(transcript_row({"kind": "stage-result", "text": text}))[0][:3]

    assert chip("pytest: pass · exit 0") == " ✔ "
    assert chip("pytest: fail · exit 1") == " ✖ "
    assert chip("lint: not_run") == " ○ "


def test_an_events_row_shows_the_chip_the_kind_and_the_first_line() -> None:
    from harness.console.tui.screens.worker_observation import event_row

    row = _plain(event_row({"kind": "tool", "text": "Bash pytest\nmore\nlines"}), 60)
    assert row == [" ◆  инструмент  Bash pytest  +2"]
    # The kind column is as wide as the longest label of the language: «stage result».
    assert _plain(event_row({"kind": "error", "text": "boom"}, "en"), 60) == [
        " ✖  error        boom"
    ]


def test_the_legend_names_every_chip_and_never_splits_a_pair() -> None:
    from harness.console.tui.screens.worker_observation import EVENT_KINDS, legend_text

    lines = _plain(legend_text(), 60)
    text = "\n".join(lines)
    for glyph, label, _english, _colour in EVENT_KINDS.values():
        assert f"{glyph}  {label}" in text


def test_the_context_names_the_block_reason_first_and_fits_long_values() -> None:
    from harness.console.tui.screens.worker_observation import context_rows

    rows = context_rows(
        {
            "dispatch_id": "dispatch-e98a4a72-50ac-4fd8-b421-1db55c17f287",
            "role": "developer",
            "runtime": "claude",
            "model": "opus",
            "effort": "high",
            "access_mode": "container",
            "failure": {"error": "permission denied"},
            "worktree": "/work/project/.harness/.sandboxes/worktrees/feature-issue-887-kpi",
        },
        30,
        lambda text: text,
    )
    shown = {label: value.plain for label, value in rows}
    assert rows[0][0] == "Причина" and shown["Причина"] == "permission denied"
    assert shown["Dispatch"] == "dispatch-e98a4a72-50ac-4fd8-b…"
    assert shown["Роль"] == "developer · Claude Code"
    assert shown["Модель"] == "opus · high"
    assert shown["Сессия"] == "не наблюдалась"
    assert shown["Worktree"] == "…/feature-issue-887-kpi"
