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


def test_a_session_event_reads_as_in_claude_cli() -> None:
    """A message or a tool call is a ● line after a blank line; its result hangs under it on
    └; a long line wraps under the text, not under the marker."""
    from harness.console.tui.screens.worker_observation import transcript_row

    assert _plain(transcript_row({"kind": "output", "text": "Читаю тикет"})) == [
        "",
        "● Читаю тикет",
    ]
    assert _plain(transcript_row({"kind": "tool", "text": "Read"})) == ["", "● Read"]
    assert _plain(transcript_row({"kind": "tool-result", "text": "4 passed"})) == [
        "  └  4 passed"
    ]
    assert _plain(transcript_row({"kind": "output", "text": "a\nb"})) == [
        "",
        "● a",
        "  b",
    ]
    assert _plain(transcript_row({"kind": "error", "text": "boom"})) == ["", "● boom"]
    assert _plain(transcript_row({"kind": "new-kind", "text": "x"})) == ["", "● x"]


def test_a_tool_result_with_line_numbers_shows_them_in_a_gutter() -> None:
    """Read output (`number<TAB>line` or `number→line`) keeps the numbers in a muted column
    apart from the code, so a numbered line no longer reads as text."""
    from harness.console.tui.screens.worker_observation import transcript_row

    text = "    38\t\n    45\tand, only\n   102→- refs"
    assert _plain(transcript_row({"kind": "tool-result", "text": text})) == [
        "  └   38",
        "      45  and, only",
        "     102  - refs",
    ]


def test_a_long_tool_result_folds_to_its_first_lines_until_expanded() -> None:
    from harness.console.tui.screens.worker_observation import (
        RESULT_LINES,
        transcript_row,
    )

    text = "\n".join(f"line {n}" for n in range(1, RESULT_LINES + 8))
    folded = _plain(transcript_row({"kind": "tool-result", "text": text}))
    assert folded[0] == "  └  line 1"
    assert folded[RESULT_LINES - 1] == f"     line {RESULT_LINES}"
    assert folded[RESULT_LINES:] == ["     … ещё 7 строк · ctrl+o"]
    english = _plain(transcript_row({"kind": "tool-result", "text": text}, "en"))
    assert english[-1] == "     … 7 more lines · ctrl+o"
    expanded = _plain(
        transcript_row({"kind": "tool-result", "text": text}, expanded=True)
    )
    assert len(expanded) == RESULT_LINES + 7
    assert expanded[-1] == f"     line {RESULT_LINES + 7}"


def test_a_diff_in_a_tool_result_marks_added_and_removed_lines() -> None:
    from rich.console import Console

    from harness.console.kernel import brand
    from harness.console.tui.screens.worker_observation import transcript_row

    text = "@@ -1,2 +1,2 @@\n-old line\n+new line\n same"
    console = Console(width=40)
    segments = list(
        console.render(transcript_row({"kind": "tool-result", "text": text}))
    )

    def colour(word: str) -> str:
        found = next(segment for segment in segments if word in segment.text)
        return str(found.style.color.name if found.style and found.style.color else "")

    assert colour("new line") == brand.PALETTE["success"].lower()
    assert colour("old line") == brand.PALETTE["error"].lower()


def test_a_finished_qa_stage_shows_its_result_under_the_stage() -> None:
    from harness.console.tui.screens.worker_observation import transcript_row

    def mark(text: str) -> str:
        return _plain(transcript_row({"kind": "stage-result", "text": text}))[0][:7]

    assert mark("pytest: pass · exit 0") == "  └  ● "
    assert mark("pytest: fail · exit 1") == "  └  ■ "
    assert mark("lint: not_run") == "  └  ○ "


def test_the_batch_timeline_shows_the_kind_and_the_role_as_icons_with_a_legend() -> None:
    from harness.console.tui.screens.worker_observation import timeline_legend, timeline_table

    rows = [
        ("13:01:04", "decision", "-", "политика auto: dispatch"),
        ("13:01:04", "dispatch", "architect", "architect: dispatch-b7fb27f0-e109-4359-a7d3-f9a12c2983ff, итог: reported"),
        ("13:03:01", "report", "architect", "отчёт architect: completed"),
        ("13:04:00", "dispatch", "developer", "developer: dispatch-c1"),
    ]
    assert _plain(timeline_table(rows), 80) == [
        "13:01:04 ◊   политика auto: dispatch",
        "13:01:04 ► ▲ architect: db7fb27f0, итог: reported",
        "13:03:01 ● ▲ отчёт architect: completed",
        "13:04:00 ► ■ developer: dispatch-c1",
    ]
    assert timeline_legend(rows).plain == "◊ решение   ► dispatch   ● отчёт   ▲ architect   ■ developer"
    assert timeline_legend(rows, "en").plain.startswith("◊ decision   ► dispatch   ● report")


def test_an_events_row_shows_the_chip_and_the_first_line() -> None:
    """The chip names the kind (its legend is under the tab), so no word repeats it."""
    from harness.console.tui.screens.worker_observation import event_row

    row = _plain(event_row({"kind": "tool", "text": "Bash pytest\nmore\nlines"}), 60)
    assert row == [" ♦  Bash pytest  +2"]
    assert _plain(event_row({"kind": "error", "text": "boom"}, "en"), 60) == [" ■  boom"]


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
    assert shown["Dispatch"] == "de98a4a72"
    # One fact per line, so the panel stays narrow: role, runtime, model and effort apart.
    assert shown["Роль"] == "developer"
    assert shown["Runtime"] == "Claude Code"
    assert shown["Модель"] == "opus"
    assert shown["Усилие"] == "high"
    assert shown["Сессия"] == "не наблюдалась"
    assert shown["Worktree"] == "…/feature-issue-887-kpi"


def test_the_status_lines_word_the_process_ledger_stream_and_heartbeat() -> None:
    from harness.console.tui.screens.worker_observation import (
        heartbeat_line,
        process_line,
    )

    snapshot = {
        "state": "working",
        "stream_state": "connected",
        "heartbeat_at": "2026-11-08T11:35:00+00:00",
        "last_event_age_seconds": 2,
    }
    assert (
        process_line(snapshot, "live", "ru").plain
        == "► процесс работает · ledger ► Выполняется · поток подключён"
    )
    assert process_line(snapshot, "absent", "en").plain.startswith(
        "○ process not found"
    )
    assert (
        heartbeat_line(snapshot, "ru").plain
        == "heartbeat 08.11.2026 11:35:00 UTC · событие 2 с назад"
    )
    assert heartbeat_line({}, "en").plain == "heartbeat not observed · no events yet"
