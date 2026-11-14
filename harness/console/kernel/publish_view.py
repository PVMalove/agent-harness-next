"""The read-only publication view of the Web console: per batch, the candidate a review checked,
the target its QA ran on, what the local Git refs say about them and the PR receipt.

Nothing here writes, fetches or calls the network: the branch head is the local remote-tracking
ref (as old as the last fetch), and the Release Gate refusals are the two Git facts of
`release_gate.git_refusals` judged on those local refs. The runtime's QA evidence verdict is not
asked; a fact that cannot be read is None. Standard library only.

The `verdict` of an entry is the console's reading of these facts, never the runtime's gate:

- `blocked` when there is a refusal, or the latest review or QA report records a blocker or has an
  outcome other than `completed`;
- `ready` when the branch head matches the candidate, the target is in the candidate's history and
  the latest review and QA reports both exist, are `completed` and record no blocker;
- `unknown` otherwise (a Git fact could not be read, or a review or QA report is missing)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from ...orchestration.core.constants import ReleaseGateRefusal
from .json_fields import text
from .reports import LedgerView, ReportEntry

PUBLISH_LIMIT = 20
# The role names a review report is recorded under.
REVIEW_ROLES = ("code-review", "review")
REMOTE = "origin"
# The report outcome a review or QA report needs for a `ready` verdict.
COMPLETED = "completed"
_GIT_TIMEOUT_SECONDS = 5.0


class GitFacts(Protocol):
    def tip(self, branch: str) -> str | None:
        """The commit of the local remote-tracking ref of `branch`, or None."""
        ...

    def is_ancestor(self, older: str, newer: str) -> bool | None:
        """Whether `older` is in the history of `newer`; None when Git cannot tell."""
        ...


type GitRun = Callable[[Sequence[str]], tuple[int, str] | None]


def _run_git(argv: Sequence[str]) -> tuple[int, str] | None:
    """The exit code and standard output of `argv`; None when Git cannot run."""
    try:
        found = subprocess.run(
            list(argv), capture_output=True, text=True, timeout=_GIT_TIMEOUT_SECONDS
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return found.returncode, found.stdout


@dataclass(frozen=True)
class LocalGit:
    """The local refs of `repo`; never fetches."""

    repo: Path
    run: GitRun = _run_git

    def _git(self, *args: str) -> tuple[int, str] | None:
        return self.run(["git", "-C", str(self.repo), *args])

    def tip(self, branch: str) -> str | None:
        if not branch or branch.startswith("-"):
            return None
        found = self._git("rev-parse", "--verify", "--quiet", f"refs/remotes/{REMOTE}/{branch}")
        value = found[1].strip() if found is not None and found[0] == 0 else ""
        return value or None

    def is_ancestor(self, older: str, newer: str) -> bool | None:
        if not older or not newer or "-" in (older[:1], newer[:1]):
            return None
        found = self._git("merge-base", "--is-ancestor", older, newer)
        if found is None or found[0] not in (0, 1):
            return None
        return found[0] == 0


@dataclass(frozen=True)
class ReportRef:
    dispatch_id: str
    outcome: str
    has_blockers: bool


@dataclass(frozen=True)
class PublishEntry:
    batch_id: str
    ticket: str
    state: str
    branch: str
    candidate: str | None
    target: str | None
    integration_ref: str | None
    head: str | None
    head_matches: bool | None
    target_in_history: bool | None
    refusals: tuple[str, ...]
    review: ReportRef | None
    qa: ReportRef | None
    pr_url: str
    pr_state: str
    # "ready", "blocked" or "unknown": see the module docstring.
    verdict: str

    def to_payload(self) -> dict[str, object]:
        return {**asdict(self), "refusals": list(self.refusals)}


def _latest(reports: list[ReportEntry], *roles: str) -> ReportEntry | None:
    found = [entry for entry in reports if entry.role in roles]
    return max(found, key=lambda entry: entry.reported_at) if found else None


def _ref(entry: ReportEntry | None) -> ReportRef | None:
    if entry is None:
        return None
    blockers = entry.report.get("blockers")
    return ReportRef(
        entry.dispatch_id,
        entry.outcome,
        isinstance(blockers, dict) and blockers.get("status") == "present",
    )


def _candidate(review: ReportEntry | None, developer: ReportEntry | None) -> str | None:
    body = review.report.get("review") if review is not None else None
    if isinstance(body, dict) and text(body.get("candidate_commit")):
        return text(body.get("candidate_commit"))
    if developer is not None and text(developer.report.get("commit_sha")):
        return text(developer.report.get("commit_sha"))
    return None


def verdict(
    refusals: Sequence[str],
    review: ReportRef | None,
    qa: ReportRef | None,
    head_matches: bool | None,
    target_in_history: bool | None,
) -> str:
    """The Release Gate verdict of one entry, by the rule of the module docstring."""
    refs = [ref for ref in (review, qa) if ref is not None]
    if refusals or any(ref.has_blockers or ref.outcome != COMPLETED for ref in refs):
        return "blocked"
    if head_matches is True and target_in_history is True and len(refs) == 2:
        return "ready"
    return "unknown"


def publish_entries(view: LedgerView, git: GitFacts) -> tuple[PublishEntry, ...]:
    """The newest batches with a review report, at most `PUBLISH_LIMIT`; empty without a ledger."""
    if view.unavailable:
        return ()
    entries: list[PublishEntry] = []
    for batch in view.batches:
        reports = [entry for entry in view.reports if entry.batch_id == batch.batch_id]
        review = _latest(reports, *REVIEW_ROLES)
        if review is None:
            continue
        record = view._batch_records.get(batch.batch_id, {})
        candidate = _candidate(review, _latest(reports, "developer"))
        target = text(record.get("integration_base_commit")) or text(
            record.get("base_commit")
        )
        head = git.tip(batch.branch) if batch.branch else None
        matches = None if head is None or candidate is None else head == candidate
        ancestor = git.is_ancestor(target, candidate) if target and candidate else None
        refusals = tuple(
            refusal
            for refusal, refused in (
                (ReleaseGateRefusal.BRANCH_HEAD_MISMATCH.value, matches is False),
                (ReleaseGateRefusal.TARGET_NOT_IN_CANDIDATE_HISTORY.value, ancestor is False),
            )
            if refused
        )
        review_ref, qa_ref = _ref(review), _ref(_latest(reports, "qa"))
        entries.append(
            PublishEntry(
                batch_id=batch.batch_id,
                ticket=batch.ticket,
                state=batch.state,
                branch=batch.branch,
                candidate=candidate,
                target=target or None,
                integration_ref=text(record.get("integration_ref")) or None,
                head=head,
                head_matches=matches,
                target_in_history=ancestor,
                refusals=refusals,
                review=review_ref,
                qa=qa_ref,
                pr_url=batch.pr_url,
                pr_state=batch.pr_state,
                verdict=verdict(refusals, review_ref, qa_ref, matches, ancestor),
            )
        )
        if len(entries) == PUBLISH_LIMIT:
            break
    return tuple(entries)


def publish_payload(view: LedgerView, git: GitFacts) -> list[dict[str, object]]:
    return [entry.to_payload() for entry in publish_entries(view, git)]
