"""The selection a Release Gate pair requires is decided by the pair record, never by the request
(ADR 0023, section 7; ADR 0026, section 4).

The request ``qa.evidence.verify`` carries exactly ``{candidate_sha, target_sha}``: the runtime
refuses any other field with ``malformed_request`` (pinned in the Rust tests), and the Python
client never sends one.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from harness.orchestration import coordinator, runtime_client
from harness.orchestration.core.utils import JsonObject
from harness.orchestration.workflow import release_gate
from tests.orchestration import test_verification_plan_dispatch as plan_dispatch
from tests.orchestration.test_ci_collect import GITHUB, PR, write_project
from tests.orchestration.test_integration_record import PublishedBranch, _git

CANDIDATE = "c" * 40
TARGET = "1" * 40


class RecordingClient:
    """Stands in for the transport only: it records what the coordinator would send."""

    calls: list[tuple[str, JsonObject]] = []

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def call(
        self, operation: str, *, payload: JsonObject, **_: object
    ) -> runtime_client.RuntimeReply:
        RecordingClient.calls.append((operation, payload))
        return runtime_client.RuntimeReply(
            hello={}, result={"verdict": "ok", "violations": []}, revision=None
        )


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, JsonObject]]:
    RecordingClient.calls = []
    monkeypatch.setattr(runtime_client, "RuntimeClient", RecordingClient)
    return RecordingClient.calls


def test_the_verify_request_carries_exactly_the_pair(
    recorded: list[tuple[str, JsonObject]], tmp_path: Path
) -> None:
    release_gate.qa_evidence_verify(
        tmp_path, {"candidate_sha": CANDIDATE, "target_sha": TARGET}
    )

    assert recorded == [
        (
            runtime_client.QA_EVIDENCE_VERIFY,
            {"candidate_sha": CANDIDATE, "target_sha": TARGET},
        )
    ]


def test_a_stray_requirement_in_the_pair_never_reaches_the_request(
    recorded: list[tuple[str, JsonObject]], tmp_path: Path
) -> None:
    release_gate.qa_evidence_verify(
        tmp_path,
        {
            "candidate_sha": CANDIDATE,
            "target_sha": TARGET,
            "requirement": release_gate.SELECTION_TICKET_DIFF,
            "selection": release_gate.SELECTION_TICKET_DIFF,
        },
    )

    ((_, payload),) = recorded
    assert set(payload) == {"candidate_sha", "target_sha"}


def test_the_client_cannot_ask_for_a_requirement() -> None:
    parameters = inspect.signature(release_gate.qa_evidence_verify).parameters

    assert list(parameters) == ["repo", "pair"]
    assert list(inspect.signature(release_gate.require_evidence).parameters) == [
        "repo",
        "root",
        "pair",
    ]
    assert list(inspect.signature(release_gate.handoff_gate).parameters) == [
        "repo",
        "root",
        "remote",
        "branch",
        "pair",
    ]


# -- the flag and the target ref change the selection, never the tree comparison ----------------


def _tree(repo: Path, commit: str) -> str:
    return _git(repo, "rev-parse", f"{commit}^{{tree}}")


def _commit_tree(repo: Path, tree: str, parent: str) -> str:
    return _git(repo, "commit-tree", tree, "-p", parent, "-m", "merged")


class DiffPairTreeComparisonTests(plan_dispatch.TicketDiffFixture):
    """A pair that accepts ticket-diff evidence still blocks a merge of another tree.

    A published and prepared branch into ``integration/it``; its merge is checked by tree."""

    ref = "integration/it"
    flag = True
    expected = release_gate.SELECTION_TICKET_DIFF

    def setUp(self) -> None:
        super().setUp()
        self._configure(self._on(ticket_diff_selection=self.flag))
        self.branch = PublishedBranch(self.fx, self.ref)
        self.fx.state_dir = self.fx.repo / ".harness/orchestration/state"
        self.published = self.branch.publish()
        self.prepared = self.branch.prepare()
        write_project(self.fx.repo, GITHUB, ["lint", "tests"])

    def pair(self) -> JsonObject:
        path = (
            self.branch.records()
            / "reports/integration-pair"
            / f"{release_gate.pair_id(self.published['candidate'], self.prepared['target_sha'])}.json"
        )
        stored: JsonObject = json.loads(path.read_text(encoding="utf-8"))
        return stored

    def merged(self, merge_commit: str) -> JsonObject:
        return coordinator.integration_next(
            self.branch.args(
                record=self.prepared["integration_record_id"],
                ticket=None,
                branch=None,
                batch=None,
                pull_request=PR,
                merge_commit=merge_commit,
            )
        )

    def land(self, commit: str) -> None:
        _git(
            self.fx.repo,
            "push",
            "-f",
            "origin",
            f"{commit}:refs/heads/{self.ref}",
        )

    def test_the_pair_requires_the_selection_its_flag_and_target_decide(self) -> None:
        self.assertEqual(self.pair()["selection"], self.expected)

    def test_a_squash_merge_with_the_candidate_tree_is_merged(self) -> None:
        repo, candidate = self.fx.repo, self.published["candidate"]
        squash = _commit_tree(repo, _tree(repo, candidate), self.prepared["target_sha"])
        self.land(squash)

        result = self.merged(squash)

        self.assertEqual(result["step"], "merged")
        self.assertEqual(result["merged_tree_sha"], _tree(repo, candidate))

    def test_a_merge_with_another_tree_is_a_blocker_whatever_the_selection(
        self,
    ) -> None:
        repo, target = self.fx.repo, self.prepared["target_sha"]
        other = _commit_tree(repo, _tree(repo, target), target)
        self.land(other)

        result = self.merged(other)

        self.assertEqual(result["step"], "merge-tree-mismatch")
        self.assertEqual(result["refusals"], ["merged_tree_mismatch"])
        self.assertIn("new full QA", result["next"][0])


class FlagOffPairTreeComparisonTests(DiffPairTreeComparisonTests):
    """The flag off: the pair into an integration branch requires full, as before."""

    flag = False
    expected = release_gate.SELECTION_FULL
