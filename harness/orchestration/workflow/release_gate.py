"""The Release Gate of a candidate (ADR 0026, section 4; ADR 0021, section 7).

The gate binds a candidate to the pair ``{candidate_sha, target_sha}`` its QA checked and to the
tree of that candidate. Python decides it from the Git facts it observes: the head of the issue
branch, the ancestry of the target and the tree a merge created. The runtime only judges the stored
QA evidence of the pair (``qa_evidence_verify``, on the wire ``qa.evidence.verify``), and only in the
runtime-store epoch: the file ledger has no runtime verdict and no Python stand-in for one. This
module keeps the one function that records a pair, so ``dispatch publish``, ``integration
prepare`` and ``integration refresh`` write the same immutable record.

The record also stores the QA selection the pair requires (contract 2, ``selection``): the writer
decides it once, from the target ref and the flag frozen in the batch, and the runtime judges the
stage evidence by the stored value alone (never by anything the caller of ``qa.evidence.verify``
says). A record of the first contract stores none and requires ``full``.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from harness.errors import INTERNAL_INVARIANT_REMEDY
from harness.orchestration import verification_plan
from harness.orchestration.core import state_view
from harness.orchestration.core.constants import (
    INTEGRATION_SHA_PATTERN,
    QaEvidenceVerdict,
    QaEvidenceViolation,
    ReleaseGateRefusal,
)
from harness.orchestration.core.git_utils import (
    _git,
    _git_is_ancestor,
    _remote_branch_tip,
    _run_git,
)
from harness.orchestration.core.utils import CoordinatorError, JsonObject, _read_object
from harness.orchestration.core.workspace import _integration_ref
from harness.orchestration.ledger.ledger_ops import _write_record
from harness.orchestration.ledger.lifecycle import (
    IntegrationPairRecord,
    LifecycleLedger,
    store_is_authority,
)

PAIR_RECORD_CONTRACT = 2
# The first contract has no ``selection`` field and always requires a full QA run.
FIRST_PAIR_RECORD_CONTRACT = 1
SELECTION_FULL = "full"
SELECTION_TICKET_DIFF = verification_plan.TICKET_DIFF
# The selections a contract-2 record may store, the stricter one first.
PAIR_SELECTIONS = (SELECTION_FULL, SELECTION_TICKET_DIFF)


def pair_id(candidate: str, target: str) -> str:
    """The id of the pair record: it derives from the pair alone."""
    return IntegrationPairRecord.derive_id(
        {"candidate_sha": candidate, "target_sha": target}
    )


def _pair_path(ledger: LifecycleLedger, candidate: str, target: str) -> Path:
    return (
        ledger.records_root()
        / IntegrationPairRecord.directory
        / f"{pair_id(candidate, target)}.json"
    )


def candidate_tree(repo: Path, candidate: str) -> str:
    """``git rev-parse <candidate>^{tree}``: the tree a merge of exactly the candidate lands."""
    if INTEGRATION_SHA_PATTERN.fullmatch(candidate) is None:
        raise CoordinatorError(
            f"the candidate {candidate!r} is not a full lowercase commit SHA",
            remedy="pass the full SHA of the published candidate",
        )
    tree = _git(repo, "rev-parse", "--verify", "--quiet", f"{candidate}^{{tree}}")
    if INTEGRATION_SHA_PATTERN.fullmatch(tree) is None:
        raise CoordinatorError(
            f"git answered {tree!r} for the tree of {candidate}",
            remedy="fetch the candidate commit into this repository and repeat the command",
        )
    return tree


def required_selection(repo: Path, batch: JsonObject) -> str:
    """The QA selection the pair of ``batch`` requires: ``ticket-diff`` exactly when the batch
    froze ``ticket_diff_selection`` and its target is an ``integration/*`` ref, else ``full``.

    The ref is read only when the frozen flag asks for it, as the verification plan does; a batch
    without a policy (a legacy batch) or with the flag off requires ``full``."""
    policy = batch.get("verification_plan_policy")
    if not isinstance(policy, dict) or not policy.get("ticket_diff_selection"):
        return SELECTION_FULL
    if verification_plan.ticket_diff_active(policy, _integration_ref(repo, batch)):
        return SELECTION_TICKET_DIFF
    return SELECTION_FULL


def _held_selection(path: Path, stored: JsonObject, members: JsonObject) -> str:
    """The selection a stored pair record requires; a record that is not exactly one of the two
    contracts for ``members`` is refused."""
    contract = stored.get("contract")
    if contract == FIRST_PAIR_RECORD_CONTRACT:
        expected: JsonObject = {**members, "contract": contract}
        held = SELECTION_FULL
    else:
        held = str(stored.get("selection"))
        expected = {**members, "contract": PAIR_RECORD_CONTRACT, "selection": held}
        if contract != PAIR_RECORD_CONTRACT or held not in PAIR_SELECTIONS:
            expected = {}
    if not expected or stored != expected:
        raise CoordinatorError(
            f"the Release Gate pair record {path.name} names another candidate_tree_sha, "
            "selection or fields than the candidate has",
            remedy="the pair record was changed after it was written -- "
            + INTERNAL_INVARIANT_REMEDY,
        )
    return held


def record_pair(
    ledger: LifecycleLedger,
    repo: Path,
    candidate: str,
    target: str,
    selection: str,
) -> JsonObject:
    """Record the pair ``{candidate, target}`` with the tree of ``candidate`` and the ``selection``
    its QA must have; idempotent.

    The caller holds the ledger lock (the store unit of its command) and decides ``selection``
    with ``required_selection``. A pair that is recorded already is returned as it is when it
    requires as much as ``selection`` does (a record of the first contract requires ``full``); a
    stored ``ticket-diff`` pair is never recorded as ``full``, and a stored pair with other
    content is refused."""
    if selection not in PAIR_SELECTIONS:
        raise CoordinatorError(
            f"the selection {selection!r} of the Release Gate pair of {candidate} is unknown",
            remedy=f"{INTERNAL_INVARIANT_REMEDY}",
        )
    try:
        tree = candidate_tree(repo, candidate)
    except CoordinatorError as exc:
        raise CoordinatorError(
            f"cannot record the Release Gate pair of {candidate}: {exc.message}",
            remedy=exc.remedy,
        ) from exc
    members: JsonObject = {
        "pair_id": pair_id(candidate, target),
        "candidate_sha": candidate,
        "target_sha": target,
        "candidate_tree_sha": tree,
    }
    path = _pair_path(ledger, candidate, target)
    if state_view.is_file(path):
        stored = _read_object(path, "Release Gate pair record")
        held = _held_selection(path, stored, members)
        if held == SELECTION_TICKET_DIFF and selection == SELECTION_FULL:
            raise CoordinatorError(
                f"the Release Gate pair record {path.name} stores selection {held!r}, but "
                f"{selection!r} is required for this candidate_tree_sha",
                remedy="the pair record is immutable and was decided by the batch's frozen "
                "ticket_diff_selection flag -- " + INTERNAL_INVARIANT_REMEDY,
            )
        return stored
    document: JsonObject = {
        **members,
        "contract": PAIR_RECORD_CONTRACT,
        "selection": selection,
    }
    _write_record(ledger, IntegrationPairRecord.from_dict(document))
    return document


def publish_pair(batch: JsonObject, dispatch: JsonObject) -> JsonObject:
    """The pair a publish pushes: its candidate and the integration base its batch checked."""
    return {
        "candidate_sha": dispatch["candidate_commit"],
        "target_sha": batch.get("integration_base_commit") or batch["base_commit"],
    }


def stored_pair(
    ledger: LifecycleLedger, candidate: str, target: str
) -> JsonObject | None:
    """The recorded pair ``{candidate, target}``, or ``None`` before it is recorded."""
    path = _pair_path(ledger, candidate, target)
    if not state_view.is_file(path):
        return None
    return _read_object(path, "Release Gate pair record")


def stored_tree(ledger: LifecycleLedger, pair: JsonObject) -> str | None:
    """The ``candidate_tree_sha`` of a recorded pair, or ``None`` before it is recorded."""
    stored = stored_pair(ledger, pair["candidate_sha"], pair["target_sha"])
    tree = None if stored is None else stored.get("candidate_tree_sha")
    return tree if isinstance(tree, str) else None


# How long the runtime may take to judge the evidence of a pair: one read snapshot.
VERIFY_TIMEOUT_SECONDS = 30.0


def qa_evidence_verify(repo: Path, pair: JsonObject) -> JsonObject:
    """``qa_evidence_verify`` (ADR 0021, section 7): the runtime's verdict on the stored QA
    evidence of ``pair``, ``{"verdict", "violations", "pair", "confirmed_by"}``.

    Read-only on both sides, so a repeat is safe. A runtime that cannot answer raises
    ``RuntimeClientError``; an answer outside the registry vocabularies is refused."""
    from harness.orchestration.runtime_client import QA_EVIDENCE_VERIFY, RuntimeClient

    reply = RuntimeClient(repo).call(
        QA_EVIDENCE_VERIFY,
        operation_id=f"{QA_EVIDENCE_VERIFY}-{uuid.uuid4().hex}",
        payload={
            "candidate_sha": pair["candidate_sha"],
            "target_sha": pair["target_sha"],
        },
        timeout_seconds=VERIFY_TIMEOUT_SECONDS,
    )
    answer = reply.result
    violations = answer.get("violations")
    known = (
        answer.get("verdict") in tuple(QaEvidenceVerdict)
        and isinstance(violations, list)
        and all(
            isinstance(item, dict) and item.get("code") in tuple(QaEvidenceViolation)
            for item in violations
        )
        and (answer["verdict"] == QaEvidenceVerdict.OK) == (not violations)
    )
    if not known:
        raise CoordinatorError(
            "qa.evidence.verify answered outside the qa_evidence vocabularies",
            remedy="update harness or harness-runtime so both speak the same protocol minor",
        )
    return answer


def violation_codes(answer: JsonObject) -> list[str]:
    """The violation codes of a verdict, in its order."""
    return [str(item["code"]) for item in answer["violations"]]


def require_evidence(repo: Path, root: Path, pair: JsonObject) -> JsonObject | None:
    """Refuse a push unless ``qa_evidence_verify`` answers ``ok`` for exactly ``pair``.

    Only the runtime-store epoch asks the runtime, as the operational hold does: there an
    unavailable or an older runtime refuses the push, and nothing stands in for its verdict. In the
    file-ledger epoch the runtime holds no evidence: ``None``, and the checks of the caller stay
    the gate."""
    if not store_is_authority(root):
        return None
    answer = qa_evidence_verify(repo, pair)
    if answer["verdict"] != QaEvidenceVerdict.OK:
        codes = violation_codes(answer)
        raise CoordinatorError(
            f"the Release Gate refuses {pair['candidate_sha']}: qa.evidence.verify found no "
            f"full QA run of the pair on {pair['target_sha']} ({', '.join(codes)})",
            remedy=f"[{','.join(codes)}] run a new full QA of exactly this candidate on this "
            "target and accept it, then repeat dispatch publish; the dispatch stays approved",
        )
    return answer


def git_refusals(repo: Path, remote: str, branch: str, pair: JsonObject) -> list[str]:
    """The Git facts that refuse the merge handoff of ``pair``: the remote issue branch is not
    the candidate, or the target is not in the history of the candidate."""
    refusals: list[str] = []
    if _remote_branch_tip(repo, remote, branch) != pair["candidate_sha"]:
        refusals.append(ReleaseGateRefusal.BRANCH_HEAD_MISMATCH)
    try:
        ancestor = _git_is_ancestor(repo, pair["target_sha"], pair["candidate_sha"])
    except CoordinatorError as exc:
        raise CoordinatorError(
            f"cannot check that {pair['target_sha']} is in the history of "
            f"{pair['candidate_sha']}: {exc.message}",
            remedy=f"git fetch {remote}, then repeat 'integration next'",
        ) from exc
    if not ancestor:
        refusals.append(ReleaseGateRefusal.TARGET_NOT_IN_CANDIDATE_HISTORY)
    return refusals


def handoff_gate(
    repo: Path, root: Path, remote: str, branch: str, pair: JsonObject
) -> tuple[list[str], JsonObject | None]:
    """The refusals of the merge handoff of ``pair`` and the runtime's verdict (``None`` in the
    file-ledger epoch). A runtime that cannot answer raises: there is no handoff without it."""
    refusals = git_refusals(repo, remote, branch, pair)
    if not store_is_authority(root):
        return refusals, None
    answer = qa_evidence_verify(repo, pair)
    if answer["verdict"] != QaEvidenceVerdict.OK:
        refusals.append(ReleaseGateRefusal.EVIDENCE_REFUSED)
    return refusals, answer


def merged_tree(repo: Path, remote: str, integration_ref: str, commit: str) -> str:
    """The tree of the commit a merge created; the commit must be in this repository."""
    if INTEGRATION_SHA_PATTERN.fullmatch(commit) is None:
        raise CoordinatorError(
            f"--merge-commit {commit!r} is not a full lowercase commit SHA",
            remedy="pass the full SHA of the commit the merge created on the target branch",
        )
    found = _run_git(repo, ("cat-file", "-e", f"{commit}^{{commit}}"))
    if found.returncode != 0:
        raise CoordinatorError(
            f"the merge commit {commit} is not in this repository",
            remedy=f"git fetch {remote} {integration_ref}, then repeat 'integration next'",
        )
    return candidate_tree(repo, commit)
