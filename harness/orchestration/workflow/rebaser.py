"""The ``rebase`` route and its narrow ``rebaser`` role (issue #1010, ADR 0034).

When ``origin/<integration_ref>`` moves past the pinned integration base, an accepted candidate is
carried onto the new tip by the ``rebaser`` writer instead of a developer-retry: no new code, no
developer retry spent, and the accepted code-review keeps covering the rebased candidate, so QA
follows directly. This module computes the route, the brief section, the report contract and the
link from the previous candidate to the rebased one. It never creates a batch or a dispatch, so the
decision, dispatch, report and risk modules may import it.
"""

from __future__ import annotations

import hashlib
from functools import partial
from pathlib import Path

from harness.orchestration.core import config as core_config
from harness.orchestration.core.constants import RecoveryRoute
from harness.orchestration.core.git_utils import (
    _candidate_commit,
    _changed_files_between,
    _commit_changed_files,
    _commits_between,
    _merge_base,
    _patch_id,
)
from harness.orchestration.core.utils import CoordinatorError, JsonObject, _canonical
from harness.orchestration.core.workspace import _integration_ref
from harness.orchestration.workflow import commit_plan as plan_rules
from harness.orchestration.workflow import rebase

REBASER_ROLE = "rebaser"
REBASE_NEXT_ACTION = "rebase"
REPORT_FIELD = "rebase_check"
REBASE_CHECK_FIELDS = frozenset(
    {
        "rebase_target_commit",
        "previous_base_commit",
        "rebased",
        "dropped",
        "patch_id_mismatches",
        "resolved_conflicts",
        "generated_files",
        "range_diff",
    }
)
REBASED_FIELDS = frozenset({"rebased_from", "commit_sha", "patch_id_match"})
DROPPED_FIELDS = frozenset({"rebased_from", "dropped"})
MISMATCH_FIELDS = frozenset({"rebased_from", "commit_sha"})
MAX_RANGE_DIFF_CHARS = 20_000
REPORT_REMEDY = (
    "report rebase_check with exactly rebase_target_commit, previous_base_commit, rebased, "
    "dropped, patch_id_mismatches, resolved_conflicts, generated_files and range_diff "
    "(see .harness/orchestration/roles/rebaser.md)"
)


def available(repo: Path, config: JsonObject) -> bool:
    """Whether the rebaser can be dispatched: its manifest is installed and the project assigns
    it, or assigns no role at all (zero-config). Otherwise the moved base keeps the developer
    route of ADR 0012."""
    if not (core_config._roles_dir(repo) / f"{REBASER_ROLE}.md").is_file():
        return False
    plans = config.get("assignment_plans")
    return not plans or (isinstance(plans, dict) and REBASER_ROLE in plans)


def routing(
    repo: Path,
    config: JsonObject,
    batch: JsonObject,
    *,
    previous_role: str,
    candidate: str,
    reason_category: str | None,
    rationale: str,
) -> JsonObject | None:
    """The ``rebase`` routing record for ``candidate``, or ``None`` when the integration base did
    not move past it or the rebaser is not available."""
    if not available(repo, config):
        return None
    target = rebase.propose_target(repo, batch, candidate)
    if target is None:
        return None
    base = batch["integration_base_commit"]
    return {
        "route": RecoveryRoute.REBASE,
        "previous_role": previous_role,
        "reason_category": reason_category,
        "next_role": REBASER_ROLE,
        "next_action": REBASE_NEXT_ACTION,
        "rationale": f"{rationale} origin/{_integration_ref(repo, batch)} moved from {base} to "
        f"{target}: the rebaser carries the accepted candidate {candidate} onto {target} without "
        "new code, and QA of the rebased candidate follows without a new code-review.",
        "candidate_commit": candidate,
        "rebase_target_commit": target,
        "integration_base_commit": base,
    }


def brief_section(repo: Path, snapshot: str, target: str) -> JsonObject:
    """The ``rebaser`` brief section: the commits to carry onto ``target``, oldest first."""
    previous_base = _merge_base(repo, snapshot, target)
    return {
        "previous_base_commit": previous_base,
        "previous_commits": _commits_between(repo, previous_base, snapshot),
    }


def _strings(value: object, field: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise CoordinatorError(
            f"rebase_check {field} must be a list of non-empty strings",
            remedy=REPORT_REMEDY,
        )
    return [item.replace("\\", "/") for item in value]


def _entries(value: object, field: str, fields: frozenset[str]) -> list[JsonObject]:
    if not isinstance(value, list) or not all(
        isinstance(item, dict) and set(item) == fields for item in value
    ):
        raise CoordinatorError(
            f"rebase_check {field} entries must carry exactly: {', '.join(sorted(fields))}",
            remedy=REPORT_REMEDY,
        )
    return value


def _resolve(repo: Path, sha: object, field: str) -> str:
    if not isinstance(sha, str):
        raise CoordinatorError(
            f"rebase_check {field} must be a commit SHA", remedy=REPORT_REMEDY
        )
    try:
        return _candidate_commit(repo, sha)
    except CoordinatorError as exc:
        raise CoordinatorError(
            f"rebase_check {field} {sha!r} is not a commit of this repository",
            remedy=REPORT_REMEDY,
        ) from exc


def validate_report(repo: Path, dispatch: JsonObject, report: JsonObject) -> None:
    """The ``rebase_check`` block of a rebaser report, recomputed from Git: required on a
    completed rebaser report, forbidden on any other role's report."""
    block = report.get(REPORT_FIELD)
    if dispatch.get("role") != REBASER_ROLE:
        if REPORT_FIELD in report:
            raise CoordinatorError(
                "only a rebaser report carries the rebase_check block",
                remedy="drop the rebase_check field from this report",
            )
        return
    if report.get("outcome") != "completed" and block is None:
        return
    if not isinstance(block, dict) or set(block) != REBASE_CHECK_FIELDS:
        raise CoordinatorError(
            "a completed rebaser report must carry the rebase_check block with exactly: "
            + ", ".join(sorted(REBASE_CHECK_FIELDS)),
            remedy=REPORT_REMEDY,
        )
    target = plan_rules.rebase_target(dispatch)
    snapshot = dispatch.get("snapshot_commit")
    if target is None or not isinstance(snapshot, str):
        raise CoordinatorError(
            "the rebaser brief carries no rebase target or snapshot",
            remedy="create a new rebaser dispatch from the rebase route",
        )
    previous_base = _merge_base(repo, snapshot, target)
    if (
        _resolve(repo, block["rebase_target_commit"], "rebase_target_commit") != target
        or _resolve(repo, block["previous_base_commit"], "previous_base_commit")
        != previous_base
    ):
        raise CoordinatorError(
            "rebase_check names another rebase target or previous base than the brief",
            remedy=f"report rebase_target_commit {target} and previous_base_commit "
            f"{previous_base}",
        )
    head = _resolve(repo, report.get("commit_sha"), "commit_sha")
    rebased = [
        (
            _resolve(repo, entry["rebased_from"], "rebased[].rebased_from"),
            _resolve(repo, entry["commit_sha"], "rebased[].commit_sha"),
            entry["patch_id_match"],
        )
        for entry in _entries(block["rebased"], "rebased", REBASED_FIELDS)
    ]
    dropped = _entries(block["dropped"], "dropped", DROPPED_FIELDS)
    commit_map: list[object] = [
        {"commit_sha": copy, "rebased_from": original} for original, copy, _ in rebased
    ] + [
        {"rebased_from": entry["rebased_from"], "dropped": entry["dropped"]}
        for entry in dropped
    ]
    plan_rules.check_rebase_copies(
        commit_map,
        _commits_between(repo, target, head),
        _commits_between(repo, previous_base, snapshot),
        partial(_candidate_commit, repo),
    )
    mismatches: list[tuple[str, str]] = []
    for original, copy, reported in rebased:
        original_id = _patch_id(repo, original)
        match = original_id is not None and original_id == _patch_id(repo, copy)
        if reported is not match:
            raise CoordinatorError(
                f"rebase_check reports patch_id_match {reported!r} for {copy} (rebased from "
                f"{original}), but git patch-id --stable says {match}",
                remedy="recompute every pair with git patch-id --stable and report it again",
            )
        if not match:
            mismatches.append((original, copy))
    reported_mismatches = [
        (
            _resolve(repo, entry["rebased_from"], "patch_id_mismatches[].rebased_from"),
            _resolve(repo, entry["commit_sha"], "patch_id_mismatches[].commit_sha"),
        )
        for entry in _entries(
            block["patch_id_mismatches"], "patch_id_mismatches", MISMATCH_FIELDS
        )
    ]
    if reported_mismatches != mismatches:
        raise CoordinatorError(
            "rebase_check patch_id_mismatches must list exactly the pairs whose patch-id differs",
            remedy="list every rebased pair with patch_id_match false, in order",
        )
    allowed = set(_strings(block["resolved_conflicts"], "resolved_conflicts")) | set(
        _strings(block["generated_files"], "generated_files")
    )
    for original, copy in mismatches:
        files = sorted(
            set(_commit_changed_files(repo, original))
            | set(_commit_changed_files(repo, copy))
        )
        changed = [
            path
            for path in files
            if _patch_id(repo, original, path) != _patch_id(repo, copy, path)
            and path not in allowed
        ]
        if changed:
            raise CoordinatorError(
                f"the rebased copy {copy} of {original} changes files outside the resolved "
                f"conflicts and the generated files: {', '.join(changed)}",
                remedy="carry the commit without new changes, or list the file in "
                "resolved_conflicts or generated_files when the rebase really resolved or "
                "regenerated it; a change of behaviour belongs to a developer",
            )
    range_diff = block["range_diff"]
    if mismatches:
        if not isinstance(range_diff, str) or not range_diff.strip():
            raise CoordinatorError(
                "a rebase with patch-id mismatches must attach its git range-diff",
                remedy=f"report range_diff as the output of git range-diff {previous_base}.."
                f"{snapshot} {target}..{head}",
            )
        if len(range_diff) > MAX_RANGE_DIFF_CHARS:
            raise CoordinatorError(
                f"rebase_check range_diff exceeds {MAX_RANGE_DIFF_CHARS} characters",
                remedy="report the range-diff of the mismatched pairs only, within the limit",
            )
    elif range_diff is not None:
        raise CoordinatorError(
            "rebase_check range_diff is null when every patch-id matches",
            remedy="set range_diff to null",
        )


def record(
    repo: Path, batch: JsonObject, dispatch: JsonObject, report: JsonObject, moment: str
) -> None:
    """Pin the rebase target as the integration base and link the previous candidate to the
    rebased one: the accepted code-review of the previous candidate covers the new one."""
    target = plan_rules.rebase_target(dispatch)
    snapshot = dispatch["snapshot_commit"]
    if target is None:
        raise CoordinatorError(
            "the rebaser brief carries no rebase target",
            remedy="create a new rebaser dispatch from the rebase route",
        )
    candidate = _candidate_commit(repo, report["commit_sha"])
    batch["integration_base_commit"] = target
    batch.setdefault("rebases", []).append(
        {
            "dispatch_id": dispatch["dispatch_id"],
            "previous_candidate": snapshot,
            "candidate": candidate,
            "rebase_target_commit": target,
            "previous_base_commit": _merge_base(repo, snapshot, target),
            "changed_files": _changed_files_between(repo, target, candidate),
            "rebase_check_sha256": hashlib.sha256(
                _canonical(report[REPORT_FIELD]).encode("utf-8")
            ).hexdigest(),
            "recorded_at": moment,
        }
    )


def rebased_origins(batch: JsonObject, candidate: str) -> list[str]:
    """The earlier candidates ``candidate`` was rebased from by accepted rebases, newest first."""
    links = {
        link["candidate"]: link["previous_candidate"]
        for link in batch.get("rebases", [])
        if isinstance(link, dict)
    }
    origins: list[str] = []
    current = candidate
    while current in links and links[current] not in origins:
        current = links[current]
        origins.append(current)
    return origins
