"""The selection a Release Gate pair requires is decided by the pair record, never by the request
(ADR 0023, section 7; ADR 0026, section 4).

The request ``qa.evidence.verify`` carries exactly ``{candidate_sha, target_sha}``: the runtime
refuses any other field with ``malformed_request`` (pinned in the Rust tests), and the Python
client never sends one.

A coordinator CLI test drives ``dispatch publish`` against a real ``harness-runtime serve``: the
QA evidence of the ticket's diff lets the pair into an ``integration/*`` branch through and is
refused for the pair into the default branch.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
from pathlib import Path

import pytest

from harness.gate_runner import gate_runner
from harness.orchestration import coordinator, qa_lane, runtime_client
from harness.orchestration.core.utils import JsonObject
from harness.orchestration.ledger import LifecycleLedger, ledger_ops
from harness.orchestration.workflow import release_gate
from tests.orchestration import runtime_store_support as support
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
    # Publish needs runtime QA evidence: a 1.x ledger (ADR 0036, section 5).
    file_ledger = True

    def setUp(self) -> None:
        super().setUp()
        self._configure(self._on(ticket_diff_selection=self.flag))
        self.branch = PublishedBranch(self.fx, self.ref)
        self.branch.keep_state_in_repo()
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


# -- the coordinator CLI against a real runtime ---------------------------------------------------


def _ls_remote(repo: Path, branch: str) -> str:
    return _git(repo, "ls-remote", "origin", f"refs/heads/{branch}")


class StoreProof(plan_dispatch.PlanFixture):
    """``dispatch publish`` of a candidate whose accepted QA ran the ticket's diff.

    The QA evidence is written the way the QA lane writes it (log, stage-evidence document and
    streams), so the runtime verifies the real chain; the pair is recorded by the publish itself.
    """

    ref = "master"
    selections: dict[str, str] = {"gate-1": "ticket-diff"}

    def setUp(self) -> None:
        super().setUp()
        support.runtime_binary()
        self._configure({**plan_dispatch.POLICY, "ticket_diff_selection": True})

    def accepted_qa_with_evidence(self, batch_id: str, candidate: str) -> None:
        fx = self.fx
        brief = fx._dispatch(batch_id, "qa", candidate=candidate)["brief"]
        root = ledger_ops._state_root(fx._args(), fx.repo)
        ledger = LifecycleLedger(root)
        dispatch = ledger_ops._load_dispatch(root, brief["dispatch_id"])
        commands = dispatch["verification_commands"]
        context = qa_lane.evidence_context(fx.repo, candidate, dispatch)
        entries = [
            (
                f"gate-{index}",
                gate_runner.StageCommand(
                    command, command, 0, "ok\n", stdout="ok\n", duration_ms=5
                ),
            )
            for index, command in enumerate(commands, start=1)
        ]
        bundle = gate_runner.build_stage_evidence(
            context, entries, selections=self.selections
        )
        text = "".join(gate_runner.format_command_log(c, 0, "ok\n") for c in commands)
        with ledger_ops._ledger_lock(ledger):
            text += qa_lane.persist_stage_evidence(ledger, bundle)
            checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
            artifact = qa_lane._artifact_path(ledger, checksum)
            qa_lane._write_artifact(ledger, artifact, text)
        report = qa_lane._qa_report(dispatch, fx._checks(brief), artifact, checksum)
        fx._stage_report(batch_id, brief["dispatch_id"], report, via_qa_lane=True)
        fx._decide(batch_id, "accept")

    def approved_publish(self) -> tuple[Path, str, str, str]:
        fx = self.fx
        fx.state_dir = fx.repo / ".harness/orchestration/state"
        batch_id = fx._create_batch(integration_ref=self.ref)["batch_id"]
        fx._accepted_architect(batch_id)
        candidate = fx._accepted_candidate(batch_id, "x")
        fx._reported_review(batch_id, candidate)
        fx._decide(batch_id, "accept")
        self.accepted_qa_with_evidence(batch_id, candidate)
        publish = fx._dispatch(
            batch_id, "developer", purpose="publish", candidate=candidate
        )["brief"]
        target = _git(fx.repo, "rev-parse", f"origin/{self.ref}")
        return fx.repo, candidate, publish["dispatch_id"], target

    def publish_through_the_runtime(
        self,
    ) -> tuple[subprocess.CompletedProcess[str], JsonObject, str, str, str]:
        repo, candidate, dispatch_id, target = self.approved_publish()
        migrated = support.migrate(repo)
        assert migrated.returncode == 0, migrated.stderr
        runtime = support.ServingRuntime(repo)
        self.addCleanup(runtime.stop)
        remote_before = _ls_remote(repo, self.fx.branch)

        result = support.coordinator_with(
            repo,
            runtime,
            "dispatch",
            "publish",
            "--dispatch",
            dispatch_id,
            "--remote",
            "origin",
        )

        pair = (
            f"reports/integration-pair/{release_gate.pair_id(candidate, target)}.json"
        )
        recorded = support.store_records(repo, runtime, pair)[pair]
        return (
            result,
            recorded,
            candidate,
            remote_before,
            _ls_remote(repo, self.fx.branch),
        )


class DiffPairIntoIntegrationTests(StoreProof, plan_dispatch.TicketDiffFixture):
    """The ticket's pair into ``integration/*``: diff evidence confirms it and the push happens."""

    ref = "integration/it"
    selections: dict[str, str] = {}

    def test_diff_evidence_lets_the_pair_into_an_integration_branch_through(
        self,
    ) -> None:
        result, recorded, candidate, before, after = self.publish_through_the_runtime()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (recorded["contract"], recorded["selection"]),
            (2, release_gate.SELECTION_TICKET_DIFF),
        )
        self.assertNotEqual(before, after)
        self.assertTrue(after.startswith(candidate))


class DiffPairIntoDefaultBranchTests(StoreProof):
    """The same kind of evidence for the pair into the default branch is refused."""

    def test_diff_evidence_is_refused_for_a_pair_into_the_default_branch(self) -> None:
        result, recorded, _, before, after = self.publish_through_the_runtime()

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("[selection_not_full", result.stderr)
        self.assertEqual(
            (recorded["contract"], recorded["selection"]),
            (2, release_gate.SELECTION_FULL),
        )
        self.assertEqual(before, after)
