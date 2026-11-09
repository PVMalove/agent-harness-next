"""The read-only publication view: candidate, target, local Git facts and Release Gate refusals."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from harness.console.kernel.publish_view import (
    LocalGit,
    PublishEntry,
    ReportRef,
    publish_entries,
)
from harness.console.kernel.reports import BatchSummary, LedgerView, ReportEntry


class Git:
    def __init__(self, tip: str | None, ancestor: bool | None) -> None:
        self._tip, self._ancestor = tip, ancestor
        self.asked: list[str] = []

    def tip(self, branch: str) -> str | None:
        self.asked.append(branch)
        return self._tip

    def is_ancestor(self, older: str, newer: str) -> bool | None:
        return self._ancestor


def _view() -> LedgerView:
    review = ReportEntry(
        "d-rev",
        "b-1",
        "#1",
        "code-review",
        "completed",
        "2026-11-08T10:00:00+00:00",
        {"review": {"candidate_commit": "abc1234"}},
    )
    qa = ReportEntry(
        "d-qa",
        "b-1",
        "#1",
        "qa",
        "completed",
        "2026-11-08T11:00:00+00:00",
        {"blockers": {"status": "present", "details": "x"}},
    )
    return LedgerView(
        reports=[qa, review],
        batches=[
            BatchSummary("b-2", "#2", "active", "2026-11-09", branch="feature/b"),
            BatchSummary(
                "b-1", "#1", "active", "2026-11-08", branch="feature/a", pr_state="open"
            ),
        ],
        _batch_records={"b-1": {"base_commit": "base000", "integration_ref": "main"}},
    )


def test_a_moved_branch_and_a_foreign_target_are_refused_without_the_network() -> None:
    git = Git("other99", False)
    (entry,) = publish_entries(_view(), git)
    assert entry == PublishEntry(
        batch_id="b-1",
        ticket="#1",
        state="active",
        branch="feature/a",
        candidate="abc1234",
        target="base000",
        integration_ref="main",
        head="other99",
        head_matches=False,
        target_in_history=False,
        refusals=("branch_head_mismatch", "target_not_in_candidate_history"),
        review=ReportRef("d-rev", "completed", False),
        qa=ReportRef("d-qa", "completed", True),
        pr_url="",
        pr_state="open",
    )
    # A batch without a review report has nothing to publish yet.
    assert git.asked == ["feature/a"]


def test_unknown_git_facts_refuse_nothing() -> None:
    (entry,) = publish_entries(_view(), Git(None, None))
    assert (entry.head_matches, entry.target_in_history, entry.refusals) == (None, None, ())


def test_an_unavailable_ledger_has_no_publication() -> None:
    assert publish_entries(LedgerView(unavailable="none"), Git("x", True)) == ()


def test_local_git_reads_remote_tracking_refs_only() -> None:
    calls: list[list[str]] = []
    answers = {
        "rev-parse": (0, "abc1234\n"),
        "merge-base": (1, ""),
    }

    def run(argv: Sequence[str]) -> tuple[int, str] | None:
        calls.append(list(argv))
        return answers[argv[3]]

    local = LocalGit(Path("/repo"), run)
    assert local.tip("feature/a") == "abc1234"
    assert local.is_ancestor("base000", "abc1234") is False
    assert calls == [
        ["git", "-C", "/repo", "rev-parse", "--verify", "--quiet", "refs/remotes/origin/feature/a"],
        ["git", "-C", "/repo", "merge-base", "--is-ancestor", "base000", "abc1234"],
    ]
    assert local.tip("--all") is None and local.is_ancestor("-x", "y") is None
    assert LocalGit(Path("/repo"), lambda argv: None).tip("feature/a") is None
