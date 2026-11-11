"""'integration collect-ci' of issue #535: tracker gate, sanitized immutable evidence, fallbacks.

Real ledger and Git (shared published-branch fixture); the CI service is a controlled in-memory
``CiSource``: no network, no secrets.
"""

from __future__ import annotations

import dataclasses
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from harness.orchestration import coordinator
from harness.orchestration.core import ci_source
from harness.orchestration.core.ci_source import CheckRun, CiObservation
from harness.orchestration.core.utils import CoordinatorError, JsonObject, _canonical
from harness.orchestration.workflow import integration, release_gate
from tests.orchestration import runtime_store_support as support
from tests.orchestration import test_verification_plan_dispatch as plan_dispatch
from tests.orchestration.test_integration_record import PublishedBranch

REPO = "owner/repo"
MERGE = "c" * 40
PR = 7


class FakeSource:
    def __init__(self, observation: CiObservation) -> None:
        self.observation = observation
        self.calls: list[tuple[str, int]] = []

    def observe(self, repository: str, pull_request: int) -> CiObservation:
        self.calls.append((repository, pull_request))
        return self.observation


def write_project(repo: Path, tracker: JsonObject | None, checks: object) -> None:
    data: JsonObject = {
        "language": "ru",
        "base_branch": "master",
        "branch_pattern": "^feature/.+",
        "qa_gate_commands": ["true"],
    }
    if tracker is not None:
        data["tracker"] = tracker
    if checks is not None:
        data["ci_required_checks"] = checks
    path = repo / ".harness" / "project.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


GITHUB = {"type": "github", "host": "github.com", "project": REPO}


class CollectCiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.branch = PublishedBranch()
        self.addCleanup(self.branch.close)
        self.branch.publish()
        self.prepared = self.branch.prepare()
        self.record_id = self.prepared["integration_record_id"]
        self.candidate = self.prepared["candidate_sha"]
        self.target = self.prepared["target_sha"]
        write_project(self.branch.repo, GITHUB, ["lint", "tests"])

    def observation(self, **changes: object) -> CiObservation:
        runs = tuple(
            CheckRun(
                name,
                MERGE,
                "completed",
                "success",
                str(index),
                f"https://github.com/{REPO}/runs/{index}",
            )
            for index, name in enumerate(("lint", "tests"), start=10)
        )
        base = CiObservation(
            repository=REPO,
            pull_request=PR,
            base_ref="master",
            candidate_sha=self.candidate,
            checkout="combined",
            merge_commit_sha=MERGE,
            merge_parents=(self.candidate, self.target),
            checks=runs,
        )
        return dataclasses.replace(base, **changes)  # type: ignore[arg-type]

    def collect(self, observation: CiObservation, **values: object) -> JsonObject:
        args = self.branch.args(
            record=self.record_id,
            ticket=None,
            branch=None,
            batch=None,
            pull_request=PR,
            ci_source=FakeSource(observation),
            **values,
        )
        return coordinator.integration_collect_ci(args)

    def evidence_files(self) -> list[Path]:
        directory = self.branch.records() / "reports" / "integration-evidence"
        return sorted(directory.glob("*.json"))

    def test_accepted_ci_is_recorded_as_sanitized_collector_evidence(self) -> None:
        result = self.collect(self.observation())

        self.assertEqual(result["outcome"], "accepted")
        self.assertTrue(result["recorded"])
        self.assertFalse(result["local_qa_required"])
        files = self.evidence_files()
        self.assertEqual(len(files), 1)
        document = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(document["kind"], "ci")
        self.assertEqual(document["result"], "passed")
        self.assertEqual(document["verification"], "collector-accepted")
        self.assertEqual(document["candidate_sha"], self.candidate)
        self.assertEqual(document["target_sha"], self.target)
        self.assertEqual(document["collector"]["merge_commit_sha"], MERGE)
        self.assertEqual(
            [c["name"] for c in document["collector"]["checks"]], ["lint", "tests"]
        )

    def test_collecting_again_is_idempotent(self) -> None:
        first = self.collect(self.observation())
        second = self.collect(self.observation())
        self.assertTrue(first["linked"])
        self.assertFalse(second["linked"])
        self.assertEqual(first["evidence_id"], second["evidence_id"])
        self.assertEqual(len(self.evidence_files()), 1)

    def test_a_failed_required_check_is_recorded_as_failed_evidence(self) -> None:
        runs = (
            CheckRun("lint", MERGE, "completed", "success", "10", None),
            CheckRun("tests", MERGE, "completed", "failure", "11", None),
        )
        result = self.collect(self.observation(checks=runs))
        self.assertEqual(result["outcome"], "failed")
        self.assertTrue(result["recorded"])
        document = json.loads(self.evidence_files()[0].read_text(encoding="utf-8"))
        self.assertEqual(document["result"], "failed")
        self.assertEqual(document["verification"], "collector-failed")

    def assert_nothing_recorded(self, result: JsonObject, reason: str) -> None:
        self.assertEqual(result["outcome"], "fallback")
        self.assertEqual(result["reason"], reason)
        self.assertFalse(result["recorded"])
        self.assertTrue(result["local_qa_required"])
        self.assertEqual(self.evidence_files(), [])

    def test_every_unproven_observation_records_nothing(self) -> None:
        cases = {
            "unavailable": self.observation(error="the CI service did not answer"),
            "wrong_repository": self.observation(repository="x/y"),
            "wrong_pull_request": self.observation(pull_request=8),
            "stale_candidate": self.observation(candidate_sha="d" * 40),
            "stale_target": self.observation(merge_parents=(self.candidate, "d" * 40)),
            "unknown_checkout": self.observation(checkout="unknown"),
            "missing_check": self.observation(checks=()),
            "head_only": self.observation(
                checks=(
                    CheckRun("lint", self.candidate, "completed", "success", "1", None),
                    CheckRun(
                        "tests", self.candidate, "completed", "success", "2", None
                    ),
                )
            ),
            "pending_check": self.observation(
                checks=(
                    CheckRun("lint", MERGE, "completed", "success", "1", None),
                    CheckRun("tests", MERGE, "in_progress", None, "2", None),
                )
            ),
        }
        for reason, observation in cases.items():
            with self.subTest(reason):
                self.assert_nothing_recorded(self.collect(observation), reason)

    def test_every_fallback_reason_names_its_next_action(self) -> None:
        """One deterministic table: wait for a pending check, otherwise name the local-QA
        condition ('absent' when CI cannot exist, 'unavailable' when it cannot be asked,
        'unusable' when it answered something that cannot confirm the pair)."""
        expected = {
            "pending_check": ("wait", None),
            "not_configured": ("local-qa", "absent"),
            "unsupported_tracker": ("local-qa", "absent"),
            "unavailable": ("local-qa", "unavailable"),
            **{
                reason: ("local-qa", "unusable")
                for reason in (
                    "head_only",
                    "unknown_checkout",
                    "stale_candidate",
                    "stale_target",
                    "missing_check",
                    "inconclusive_check",
                    "wrong_repository",
                    "wrong_pull_request",
                    "wrong_base",
                    "light_check",
                )
            },
        }
        fallbacks = (set(ci_source.REASONS) - {"failed_check"}) | {
            "unsupported_tracker"
        }
        self.assertEqual(set(expected), fallbacks)
        for reason, (action, condition) in expected.items():
            with self.subTest(reason):
                hint = integration.ci_next("fallback", reason)
                self.assertEqual(hint, {"action": action, "ci_condition": condition})

    def test_collect_ci_results_carry_the_next_hint(self) -> None:
        pending = self.observation(
            checks=(
                CheckRun("lint", MERGE, "completed", "success", "1", None),
                CheckRun("tests", MERGE, "in_progress", None, "2", None),
            )
        )
        self.assertEqual(
            self.collect(pending)["next"], {"action": "wait", "ci_condition": None}
        )
        self.assertEqual(
            self.collect(self.observation(error="down"))["next"],
            {"action": "local-qa", "ci_condition": "unavailable"},
        )
        failed = self.collect(
            self.observation(
                checks=(
                    CheckRun("lint", MERGE, "completed", "success", "10", None),
                    CheckRun("tests", MERGE, "completed", "failure", "11", None),
                )
            )
        )
        self.assertEqual(failed["next"], {"action": "route", "ci_condition": None})
        self.assertNotIn("next", self.collect(self.observation()))

    def test_a_pull_request_against_another_base_is_a_wrong_base_fallback(self) -> None:
        result = self.collect(self.observation(base_ref="release"))
        self.assert_nothing_recorded(result, "wrong_base")

    def test_unsupported_tracker_is_a_fallback_without_calling_ci(self) -> None:
        for tracker in (
            {"type": "gitlab", "host": "gitlab.example.test", "project": "g/p"},
            {"type": "local"},
        ):
            write_project(self.branch.repo, tracker, ["lint", "tests"])
            source = FakeSource(self.observation())
            args = self.branch.args(
                record=self.record_id,
                ticket=None,
                branch=None,
                batch=None,
                pull_request=PR,
                ci_source=source,
            )
            result = coordinator.integration_collect_ci(args)
            self.assert_nothing_recorded(result, "unsupported_tracker")
            self.assertEqual(source.calls, [])

    def test_unconfigured_required_checks_fall_back(self) -> None:
        for checks in (None, [], ["lint", "lint"], [""]):
            write_project(self.branch.repo, GITHUB, checks)
            self.assert_nothing_recorded(
                self.collect(self.observation()), "not_configured"
            )

    def test_a_light_check_never_confirms_a_pair_that_requires_full(self) -> None:
        light = tuple(
            CheckRun(name, MERGE, "completed", "success", str(index), None)
            for index, name in enumerate(("lint-light", "verify-light"), start=10)
        )
        write_project(self.branch.repo, GITHUB, ["lint-light", "verify-light"])

        result = self.collect(self.observation(checks=light))

        self.assert_nothing_recorded(result, "light_check")
        self.assertEqual(
            result["next"], {"action": "local-qa", "ci_condition": "unusable"}
        )

    def test_collect_changes_nothing_but_the_evidence_record(self) -> None:
        before = self.branch.snapshot()
        self.collect(self.observation())
        self.assertEqual(self.branch.snapshot(), before)

    def test_invalid_pull_request_number_is_refused(self) -> None:
        args = self.branch.args(
            record=self.record_id,
            ticket=None,
            branch=None,
            batch=None,
            pull_request=0,
            ci_source=FakeSource(self.observation()),
        )
        with self.assertRaises(CoordinatorError):
            coordinator.integration_collect_ci(args)

    def test_the_public_cli_reaches_collect_ci(self) -> None:
        parsed = coordinator.parser().parse_args(
            [
                "integration",
                "collect-ci",
                "--record",
                self.record_id,
                "--pull-request",
                "7",
            ]
        )
        self.assertIs(parsed.handler, coordinator.integration_collect_ci)
        self.assertEqual(parsed.pull_request, 7)

    def test_the_module_is_read_only_towards_the_tracker(self) -> None:
        text = Path(ci_source.__file__).read_text(encoding="utf-8")
        for forbidden in (
            "pr create",
            "pr merge",
            "-X POST",
            "-X PUT",
            "-X PATCH",
            "-X DELETE",
            "protection",
        ):
            self.assertNotIn(forbidden, text.replace("branch protection", ""))


def _light_observation(
    candidate: str, target: str, base_ref: str, names: tuple[str, ...]
) -> CiObservation:
    runs = tuple(
        CheckRun(name, MERGE, "completed", "success", str(index), None)
        for index, name in enumerate(names, start=10)
    )
    return CiObservation(
        repository=REPO,
        pull_request=PR,
        base_ref=base_ref,
        candidate_sha=candidate,
        checkout="combined",
        merge_commit_sha=MERGE,
        merge_parents=(candidate, target),
        checks=runs,
    )


class _LightPair(plan_dispatch.TicketDiffFixture):
    """A published and prepared pair into ``integration/it`` whose flag stored ``ticket-diff``."""

    required = ["lint-light", "verify-light"]

    def setUp(self) -> None:
        super().setUp()
        self._configure(self._on())
        self.branch = PublishedBranch(self.fx, self.integration_ref)
        self.fx.state_dir = self.fx.repo / ".harness/orchestration/state"
        self.branch.publish()
        self.prepared = self.branch.prepare()
        write_project(self.fx.repo, GITHUB, self.required)

    def collect(self, names: tuple[str, ...] | None = None) -> JsonObject:
        observation = _light_observation(
            self.prepared["candidate_sha"],
            self.prepared["target_sha"],
            self.integration_ref,
            names or tuple(self.required),
        )
        return coordinator.integration_collect_ci(
            self.branch.args(
                record=self.prepared["integration_record_id"],
                ticket=None,
                branch=None,
                batch=None,
                pull_request=PR,
                ci_source=FakeSource(observation),
            )
        )

    def pair_name(self) -> str:
        pair = release_gate.pair_id(
            self.prepared["candidate_sha"], self.prepared["target_sha"]
        )
        return f"reports/integration-pair/{pair}.json"

    def pair_path(self) -> Path:
        return self.branch.records() / self.pair_name()


class LightCiTests(_LightPair):
    """The light check of a pull request into ``integration/*`` (issue #937) confirms a pair only
    when the pair stored the QA selection ``ticket-diff``; anything else requires ``full``."""

    def test_the_pair_of_a_ticket_diff_selection_accepts_the_light_check(self) -> None:
        stored = json.loads(self.pair_path().read_text(encoding="utf-8"))
        self.assertEqual(stored["selection"], "ticket-diff")

        result = self.collect()

        self.assertEqual(result["outcome"], "accepted")
        self.assertTrue(result["recorded"])
        self.assertFalse(result["local_qa_required"])
        self.assertEqual(
            [c["name"] for c in result["verified"]["checks"]], self.required
        )

    def test_a_pair_of_the_first_contract_requires_full(self) -> None:
        stored = json.loads(self.pair_path().read_text(encoding="utf-8"))
        old = {k: v for k, v in stored.items() if k != "selection"}
        old["contract"] = 1
        self.pair_path().write_text(_canonical(old), encoding="utf-8")

        result = self.collect()

        self.assertEqual(
            (result["outcome"], result["reason"]), ("fallback", "light_check")
        )
        self.assertFalse(result["recorded"])

    def test_a_pair_that_is_not_recorded_requires_full(self) -> None:
        self.pair_path().unlink()

        result = self.collect()

        self.assertEqual(
            (result["outcome"], result["reason"]), ("fallback", "light_check")
        )
        self.assertFalse(result["recorded"])

    def test_a_forged_selection_requires_full(self) -> None:
        stored = json.loads(self.pair_path().read_text(encoding="utf-8"))
        self.pair_path().write_text(
            _canonical({**stored, "selection": "focused"}), encoding="utf-8"
        )

        result = self.collect()

        self.assertEqual(
            (result["outcome"], result["reason"]), ("fallback", "light_check")
        )

    def test_the_full_check_names_still_confirm_a_ticket_diff_pair(self) -> None:
        write_project(self.fx.repo, GITHUB, ["verify", "rust"])

        result = self.collect(("verify", "rust"))

        self.assertEqual(result["outcome"], "accepted")


class LightCiStoreEpochTests(_LightPair):
    """In the runtime-store epoch the pair record lives in the store, not in a file: the reader
    sees it only inside the ledger lock, where the store view is bound."""

    def setUp(self) -> None:
        support.runtime_binary()
        super().setUp()
        migrated = support.migrate(self.fx.repo)
        assert migrated.returncode == 0, migrated.stderr
        self.runtime = support.ServingRuntime(self.fx.repo)
        self.addCleanup(self.runtime.stop)
        environment = mock.patch.dict(
            os.environ, {"XDG_RUNTIME_DIR": str(self.runtime.xdg)}
        )
        environment.start()
        self.addCleanup(environment.stop)

    def test_the_stored_ticket_diff_pair_accepts_the_light_check(self) -> None:
        name = self.pair_name()
        stored = support.store_records(self.fx.repo, self.runtime, name)[name]
        self.assertEqual(stored["selection"], "ticket-diff")

        result = self.collect()

        self.assertEqual(result["outcome"], "accepted")
        self.assertTrue(result["recorded"])


class FullPairLightCiTests(plan_dispatch.TicketDiffFixture):
    """A pair into the default branch requires ``full``; the flag decides, not the check name."""

    def test_the_flag_off_pair_into_an_integration_ref_requires_full(self) -> None:
        self._configure(self._on(ticket_diff_selection=False))
        branch = PublishedBranch(self.fx, self.integration_ref)
        self.fx.state_dir = self.fx.repo / ".harness/orchestration/state"
        branch.publish()
        prepared = branch.prepare()
        write_project(self.fx.repo, GITHUB, ["verify-light"])
        observation = _light_observation(
            prepared["candidate_sha"],
            prepared["target_sha"],
            self.integration_ref,
            ("verify-light",),
        )

        result = coordinator.integration_collect_ci(
            branch.args(
                record=prepared["integration_record_id"],
                ticket=None,
                branch=None,
                batch=None,
                pull_request=PR,
                ci_source=FakeSource(observation),
            )
        )

        self.assertEqual(
            (result["outcome"], result["reason"]), ("fallback", "light_check")
        )
        self.assertFalse(result["recorded"])


if __name__ == "__main__":
    unittest.main()
