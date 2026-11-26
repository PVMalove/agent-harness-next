"""The integration record of an epic's ``integration/*`` branch (issue #1278).

The pull request of an integration branch into ``base_branch`` passes the same Release Gate steps
as a ticket pull request, without a publish batch: ``integration prepare`` records the pair of the
remote head of the branch and the remote head of its target. Real ledger and real Git (a local
bare remote); CI is a controlled in-memory ``CiSource``.
"""

from __future__ import annotations

import json
import sys
import unittest

import pytest

from harness.orchestration import coordinator
from harness.orchestration.core.ci_source import CheckRun, CiObservation
from harness.orchestration.core.utils import CoordinatorError, JsonObject
from harness.orchestration.ledger import LifecycleLedger, ledger_ops
from harness.orchestration.workflow import integration, release_gate
from tests.orchestration.test_ci_collect import GITHUB, MERGE, PR, REPO, FakeSource
from tests.orchestration.test_ci_collect import write_project
from tests.orchestration import runtime_store_support as support
from tests.orchestration.test_integration_record import PublishedBranch, _git

EPIC = "#1022"
BRANCH = "integration/epic"
EPIC_BODY = (
    "## Problem Statement\n\n...\n\n## Integration Branch\n\n"
    f"- Branch: `{BRANCH}`\n- Created from: `integration/parent`\n\n## Further Notes\n"
)


def epic_source(body: str = EPIC_BODY) -> object:
    """A tracker that answers every epic with ``body``; it records which tickets it read."""

    def read(_repo: object, ticket: str) -> str:
        read.tickets.append(ticket)  # type: ignore[attr-defined]
        return body

    read.tickets = []  # type: ignore[attr-defined]
    return read


class IntegrationBranchFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.branch = PublishedBranch()
        self.branch.keep_state_in_repo()
        self.addCleanup(self.branch.close)
        write_project(self.branch.repo, GITHUB, ["lint", "tests"])
        self.target = _git(self.branch.repo, "rev-parse", "origin/master")
        self.head = self.push_integration_commit("first")

    def push_integration_commit(self, name: str) -> str:
        """One more child merge on the integration branch, pushed to the remote."""
        repo = self.branch.repo
        parent = _git(repo, "ls-remote", "origin", f"refs/heads/{BRANCH}").split()
        base = parent[0] if parent else self.target
        _git(repo, "checkout", "-q", "--detach", base)
        (repo / f"child-{name}.txt").write_text(f"{name}\n", encoding="utf-8")
        _git(repo, "add", f"child-{name}.txt")
        _git(repo, "commit", "-q", "-m", f"child {name}")
        commit = _git(repo, "rev-parse", "HEAD")
        _git(repo, "push", "origin", f"{commit}:refs/heads/{BRANCH}")
        _git(repo, "checkout", "-q", "master")
        return commit

    def prepare(self, **overrides: object) -> JsonObject:
        values: JsonObject = {
            "ticket": EPIC,
            "branch": BRANCH,
            "batch": None,
            "candidate_commit": None,
            "remote": "origin",
            "target": None,
            "epic_source": epic_source(),
        }
        values.update(overrides)
        return coordinator.integration_prepare(self.branch.args(**values))

    def record_args(self, record_id: str, **values: object) -> JsonObject:
        return {
            "record": record_id,
            "ticket": None,
            "branch": None,
            "batch": None,
            **values,
        }

    def next(
        self, record_id: str, pull_request: int | None = None, **values: object
    ) -> JsonObject:
        return coordinator.integration_next(
            self.branch.args(
                **self.record_args(record_id, pull_request=pull_request, **values)
            )
        )

    def collect(self, record_id: str, pair: JsonObject, *checks: str) -> JsonObject:
        runs = tuple(
            CheckRun(name, MERGE, "completed", "success", str(index), None)
            for index, name in enumerate(checks, start=10)
        )
        observation = CiObservation(
            repository=REPO,
            pull_request=PR,
            base_ref="master",
            candidate_sha=pair["candidate_sha"],
            checkout="combined",
            merge_commit_sha=MERGE,
            merge_parents=(pair["candidate_sha"], pair["target_sha"]),
            checks=runs,
        )
        return coordinator.integration_collect_ci(
            self.branch.args(
                **self.record_args(
                    record_id, pull_request=PR, ci_source=FakeSource(observation)
                )
            )
        )


class IntegrationBranchPrepareTests(IntegrationBranchFixture):
    def test_prepare_records_the_branch_head_and_target_without_a_batch(self) -> None:
        prepared = self.prepare()

        self.assertTrue(prepared["created"])
        self.assertEqual(
            (
                prepared["ticket"],
                prepared["branch"],
                prepared["source_batch_id"],
                prepared["candidate_sha"],
                prepared["target_sha"],
                prepared["integration_ref"],
            ),
            (EPIC, BRANCH, None, self.head, self.target, "master"),
        )
        self.assertEqual(prepared["source_kind"], "integration-branch")
        self.assertEqual(
            prepared["source_evidence"],
            {
                "epic": {"ticket": EPIC, "integration_branch": BRANCH},
                "pair": {"candidate_sha": self.head, "target_sha": self.target},
            },
        )
        ledger = LifecycleLedger(self.branch.state_root())
        with ledger_ops._ledger_lock(ledger):
            selection = release_gate.pair_selection(ledger, self.head, self.target)
        self.assertEqual(selection, release_gate.SELECTION_FULL)

    def test_a_repeat_is_idempotent_and_a_moved_head_or_target_is_a_new_pair(
        self,
    ) -> None:
        first = self.prepare()
        again = self.prepare()

        self.assertFalse(again["created"])
        self.assertEqual(again["integration_record_id"], first["integration_record_id"])

        moved_head = self.push_integration_commit("second")
        after_head = self.prepare()
        self.assertTrue(after_head["created"])
        self.assertEqual(after_head["candidate_sha"], moved_head)
        self.assertNotEqual(
            after_head["integration_record_id"], first["integration_record_id"]
        )

        moved_target = self.branch.advance_integration_ref()
        after_target = self.prepare()
        self.assertTrue(after_target["created"])
        self.assertEqual(after_target["target_sha"], moved_target)
        self.assertNotIn(
            after_target["integration_record_id"],
            {first["integration_record_id"], after_head["integration_record_id"]},
        )

    def test_the_target_is_base_branch_or_another_integration_branch(self) -> None:
        for target, refusal in (
            ("feature/issue-1-x", "cannot target"),
            (BRANCH, "cannot target"),
            ("integration/absent", "is not a branch of remote"),
        ):
            with self.subTest(target=target):
                with self.assertRaisesRegex(CoordinatorError, refusal):
                    self.prepare(target=target)
        _git(
            self.branch.repo,
            "push",
            "origin",
            f"{self.target}:refs/heads/integration/parent",
        )

        nested = self.prepare(target="integration/parent")

        self.assertEqual(nested["integration_ref"], "integration/parent")

    def test_two_targets_at_one_sha_are_two_records(self) -> None:
        """The pull request target is part of the record: ``integration/parent`` at the SHA of
        ``master`` is another pull request than the one into ``master``."""
        _git(
            self.branch.repo,
            "push",
            "origin",
            f"{self.target}:refs/heads/integration/parent",
        )

        into_base = self.prepare()
        into_parent = self.prepare(target="integration/parent")

        self.assertNotEqual(
            into_base["integration_record_id"], into_parent["integration_record_id"]
        )
        self.assertEqual(
            (into_base["integration_ref"], into_parent["integration_ref"]),
            ("master", "integration/parent"),
        )
        self.assertTrue(into_parent["created"])

    def test_the_epic_must_name_the_branch(self) -> None:
        for body, refusal in (
            (EPIC_BODY.replace(BRANCH, "integration/other"), "integration/other"),
            ("## Problem Statement\n\nno branch here\n", "None"),
        ):
            with self.subTest(refusal=refusal):
                with self.assertRaisesRegex(CoordinatorError, refusal):
                    self.prepare(epic_source=epic_source(body))
        reader = epic_source()

        self.prepare(epic_source=reader)

        self.assertEqual(reader.tickets, [EPIC])  # type: ignore[attr-defined]

    def test_a_ticket_branch_refuses_a_target(self) -> None:
        with self.assertRaisesRegex(CoordinatorError, "--target"):
            self.prepare(
                ticket="#244", branch=self.branch.branch, target="integration/parent"
            )

    def test_a_batch_or_another_candidate_is_refused(self) -> None:
        with self.assertRaisesRegex(CoordinatorError, "no batch published it"):
            self.prepare(batch="batch-0123")
        with self.assertRaisesRegex(CoordinatorError, "is not the remote head"):
            self.prepare(candidate_commit=self.target)


class IntegrationBranchNextTests(IntegrationBranchFixture):
    def setUp(self) -> None:
        super().setUp()
        self.record_id = str(self.prepare()["integration_record_id"])
        self.pair = {"candidate_sha": self.head, "target_sha": self.target}

    def test_without_a_check_the_pr_is_confirmed_pending_its_verification(
        self,
    ) -> None:
        status = coordinator.integration_status(
            self.branch.args(**self.record_args(self.record_id))
        )
        before_pr = self.next(self.record_id)
        after_pr = self.next(self.record_id, PR)

        self.assertEqual(status["source_kind"], "integration-branch")
        self.assertEqual(
            (status["verification"]["required"], status["verification"]["satisfied"]),
            (True, False),
        )
        self.assertEqual(
            (before_pr["step"], before_pr["qa_source"]),
            ("confirm-pr", "verification-pending-after-pr"),
        )
        self.assertEqual(after_pr["step"], "verify")

    def test_collected_full_ci_hands_the_pair_over(self) -> None:
        collected = self.collect(self.record_id, self.pair, "lint", "tests")

        result = self.next(self.record_id, PR)

        self.assertEqual(collected["outcome"], "accepted")
        self.assertEqual(result["step"], "handoff")
        self.assertEqual(result["handoff"]["qa_source"], "ci")
        self.assertEqual(result["handoff"]["candidate_sha"], self.head)

    def test_a_light_ci_check_never_confirms_the_pair(self) -> None:
        write_project(self.branch.repo, GITHUB, ["lint-light", "tests-light"])

        collected = self.collect(self.record_id, self.pair, "lint-light", "tests-light")
        result = self.next(self.record_id, PR)

        self.assertEqual(
            (collected["outcome"], collected["reason"]), ("fallback", "light_check")
        )
        self.assertEqual(result["step"], "verify")

    def test_a_local_qa_of_the_pair_hands_it_over(self) -> None:
        local = coordinator.integration_local_qa(
            self.branch.args(
                record=self.record_id,
                ci_condition="absent",
                reason="No combined CI",
                request=None,
                retry=False,
                lease_seconds=None,
            )
        )

        result = self.next(self.record_id, PR)

        self.assertEqual(local["state"], "completed")
        self.assertEqual(result["step"], "handoff")
        self.assertEqual(result["handoff"]["qa_source"], "local-qa")

    def test_the_merged_tree_is_checked_as_for_a_ticket_pr(self) -> None:
        repo = self.branch.repo
        tree = _git(repo, "rev-parse", f"{self.head}^{{tree}}")
        squash = _git(repo, "commit-tree", tree, "-p", self.target, "-m", "release")
        other = _git(
            repo,
            "commit-tree",
            _git(repo, "rev-parse", f"{self.target}^{{tree}}"),
            "-p",
            self.target,
            "-m",
            "other",
        )

        merged = self.next(self.record_id, PR, merge_commit=squash)
        mismatch = self.next(self.record_id, PR, merge_commit=other)

        self.assertEqual(merged["step"], "merged")
        self.assertEqual(mismatch["step"], "merge-tree-mismatch")

    def test_a_moved_target_asks_for_a_new_prepare_never_a_refresh(self) -> None:
        self.branch.advance_integration_ref()

        result = self.next(self.record_id, PR)

        self.assertEqual(result["step"], "refresh")
        self.assertIn("integration prepare", " ".join(result["next"]))
        self.assertNotIn("integration refresh", " ".join(result["next"]))
        for command in (coordinator.integration_refresh, coordinator.integration_resolve):
            with self.subTest(command=command.__name__):
                with self.assertRaisesRegex(CoordinatorError, "integration branch"):
                    command(self.branch.args(**self.record_args(self.record_id)))


if __name__ == "__main__":
    unittest.main()


class EpicIntegrationBranchTests(unittest.TestCase):
    def test_the_branch_line_wins_over_other_integration_names(self) -> None:
        self.assertEqual(integration.epic_integration_branch(EPIC_BODY), BRANCH)

    def test_a_bare_name_in_the_section_is_found(self) -> None:
        body = "## Integration Branch\n\n`integration/x-1`\n\nChild branches...\n"

        self.assertEqual(integration.epic_integration_branch(body), "integration/x-1")

    def test_a_name_outside_the_section_is_not_taken(self) -> None:
        body = "## Integration Branch\n\nnone yet\n\n## Notes\n\nsee integration/x\n"

        self.assertIsNone(integration.epic_integration_branch(body))


@pytest.mark.skipif(sys.platform == "win32", reason="the runtime uses a Unix socket")
def test_the_runtime_store_verdict_confirms_the_collected_ci_of_the_branch_pair() -> None:
    """In the runtime-store epoch the handoff of an integration-branch pair needs the runtime's
    ``qa.evidence.verify`` verdict ``ok``: the CI that ``integration collect-ci`` accepted for
    exactly that pair confirms it, as for a ticket pair (ADR 0021, section 7)."""
    support.runtime_binary()
    fixture = IntegrationBranchNextTests()
    fixture.setUp()
    runtime = None
    try:
        fixture.collect(fixture.record_id, fixture.pair, "lint", "tests")
        migrated = support.migrate(fixture.branch.repo)
        assert migrated.returncode == 0, migrated.stderr
        runtime = support.ServingRuntime(fixture.branch.repo)

        done = support.coordinator_with(
            fixture.branch.repo,
            runtime,
            "integration",
            "next",
            "--record",
            fixture.record_id,
            "--pull-request",
            str(PR),
        )

        assert done.returncode == 0, done.stderr
        result = json.loads(done.stdout)
        assert result["step"] == "handoff", result
        assert result["handoff"]["qa_source"] == "ci"
        # The runtime's verdict; the file-ledger epoch has none.
        assert result["handoff"]["qa_evidence"]["source"] == "ci"
    finally:
        if runtime is not None:
            runtime.stop()
        fixture.doCleanups()
