"""The ticket status-change rules of the task board: which column a ticket may move to, the reason
of every refusal and the `status::*` labels a move replaces. Pure tables, no I/O."""

from __future__ import annotations

import pytest

from harness.console.backend.domain.ticket_status import (
    STATUS_LABEL,
    Move,
    MoveFacts,
    decide,
    moves,
    relabel,
)

COLUMNS = ("backlog", "ready", "progress", "review", "done")

# The expected reason of every (from, to) pair for a ticket without blockers or a batch; None is
# an allowed move.
MATRIX = {
    ("backlog", "backlog"): "same",
    ("backlog", "ready"): None,
    ("backlog", "progress"): "via_ready",
    ("backlog", "review"): "review_target",
    ("backlog", "done"): "done_target",
    ("ready", "backlog"): None,
    ("ready", "ready"): "same",
    ("ready", "progress"): None,
    ("ready", "review"): "review_target",
    ("ready", "done"): "done_target",
    ("progress", "backlog"): "via_ready",
    ("progress", "ready"): None,
    ("progress", "progress"): "same",
    ("progress", "review"): "review_target",
    ("progress", "done"): "done_target",
    ("review", "backlog"): "in_review",
    ("review", "ready"): "in_review",
    ("review", "progress"): "in_review",
    ("review", "review"): "same",
    ("review", "done"): "done_target",
    ("done", "backlog"): "closed",
    ("done", "ready"): "closed",
    ("done", "progress"): "closed",
    ("done", "review"): "review_target",
    ("done", "done"): "same",
}


@pytest.mark.parametrize(("source", "target"), sorted(MATRIX))
def test_every_pair_of_columns_has_one_rule(source: str, target: str) -> None:
    move = decide(MoveFacts(source), target, strict=True)
    expected = MATRIX[(source, target)]
    assert move.to == target
    assert move.allowed is (expected is None)
    assert move.reason == expected


def test_backlog_to_ready_is_refused_while_a_blocker_is_open() -> None:
    move = decide(MoveFacts("backlog", open_blockers=("#3", "#7")), "ready", strict=True)
    assert move == Move("ready", False, "open_blockers", blockers=("#3", "#7"))


def test_a_blocker_of_unknown_state_blocks_only_the_strict_check() -> None:
    facts = MoveFacts("backlog", open_blockers=("#3",), unknown_blockers=("#9",))
    assert decide(facts, "ready", strict=True).blockers == ("#3", "#9")
    assert decide(facts, "ready", strict=False).blockers == ("#3",)
    unknown_only = MoveFacts("backlog", unknown_blockers=("#9",))
    assert decide(unknown_only, "ready", strict=True).reason == "open_blockers"
    assert decide(unknown_only, "ready", strict=False).allowed


def test_progress_to_ready_is_refused_while_the_ticket_has_an_active_batch() -> None:
    move = decide(MoveFacts("progress", batch="batch-1"), "ready", strict=True)
    assert move == Move("ready", False, "active_batch", batch="batch-1")


def test_a_ticket_left_off_the_board_counts_as_closed() -> None:
    assert decide(MoveFacts(None), "ready", strict=True).reason == "closed"


def test_an_unknown_target_is_rejected() -> None:
    with pytest.raises(ValueError):
        decide(MoveFacts("ready"), "archive", strict=True)


def test_moves_lists_every_column_in_board_order() -> None:
    listed = moves(MoveFacts("ready"), strict=False)
    assert [move.to for move in listed] == list(COLUMNS)
    assert [move.allowed for move in listed] == [True, False, True, False, False]


def test_each_writable_column_has_one_status_label() -> None:
    assert STATUS_LABEL == {
        "backlog": "status::blocked",
        "ready": "status::ready",
        "progress": "status::in-progress",
    }


def test_relabel_removes_every_other_status_label_and_adds_the_target() -> None:
    remove, add = relabel(
        ("type::feature", "status::ready", "status::blocked", "priority::p1"), "progress"
    )
    assert remove == ("status::ready", "status::blocked")
    assert add == "status::in-progress"


def test_relabel_keeps_the_target_label_when_it_is_already_set() -> None:
    remove, add = relabel(("status::ready", "status::in-progress"), "ready")
    assert remove == ("status::in-progress",)
    assert add == "status::ready"


def test_relabel_refuses_a_column_without_a_label() -> None:
    with pytest.raises(ValueError):
        relabel(("status::ready",), "review")
