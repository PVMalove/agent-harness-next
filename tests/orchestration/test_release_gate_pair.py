"""The Release Gate pair record (ADR 0026, section 4): every pair the integration route checks
stores the tree of its candidate, written by ``dispatch publish``, ``integration prepare`` and
``integration refresh`` through one function.

Real ledger and real Git (a local bare remote) through the coordinator CLI functions; no mocks.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from harness.orchestration import coordinator
from harness.orchestration.core.utils import CoordinatorError, JsonObject, _canonical
from harness.orchestration.ledger import LifecycleLedger, ledger_ops
from harness.orchestration.workflow import release_gate, resolver_state
from tests.orchestration import test_verification_plan_dispatch as plan_dispatch
from tests.orchestration.test_integration_record import PublishedBranch, _git

CONTRACT_1_KEYS = {
    "pair_id",
    "contract",
    "candidate_sha",
    "target_sha",
    "candidate_tree_sha",
}
PAIR_KEYS = CONTRACT_1_KEYS | {"selection"}
FULL = "full"
TICKET_DIFF = "ticket-diff"


def _pair_id(candidate: str, target: str) -> str:
    members = {"candidate_sha": candidate, "target_sha": target}
    digest = hashlib.sha256(_canonical(members).encode("utf-8")).hexdigest()
    return f"pair-{digest[:32]}"


class ReleaseGatePairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.branch = PublishedBranch()
        self.addCleanup(self.branch.close)

    def pair_path(self, candidate: str, target: str) -> Path:
        return (
            self.branch.records()
            / "reports/integration-pair"
            / f"{_pair_id(candidate, target)}.json"
        )

    def stored_pair(self, candidate: str, target: str) -> JsonObject:
        stored: JsonObject = json.loads(
            self.pair_path(candidate, target).read_text(encoding="utf-8")
        )
        return stored

    def tree(self, commit: str) -> str:
        return _git(self.branch.repo, "rev-parse", f"{commit}^{{tree}}")

    def test_publish_records_the_pair_with_the_tree_of_its_candidate(self) -> None:
        published = self.branch.publish()
        target = _git(self.branch.repo, "rev-parse", "origin/master")

        pair = self.stored_pair(published["candidate"], target)

        self.assertEqual(set(pair), PAIR_KEYS)
        self.assertEqual(pair["contract"], 2)
        self.assertEqual(pair["selection"], FULL)
        self.assertEqual(pair["pair_id"], _pair_id(published["candidate"], target))
        self.assertEqual(pair["candidate_sha"], published["candidate"])
        self.assertEqual(pair["target_sha"], target)
        self.assertEqual(pair["candidate_tree_sha"], self.tree(published["candidate"]))
        written = [
            item
            for item in self.branch.audit_paths()
            if "reports/integration-pair/" in item
        ]
        self.assertEqual(len(written), 1)
        self.assertTrue(written[0].startswith("immutable-record:"))

    def test_prepare_shows_the_candidate_tree_of_its_pair(self) -> None:
        published = self.branch.publish()

        prepared = self.branch.prepare()

        self.assertEqual(
            prepared["candidate_tree_sha"], self.tree(published["candidate"])
        )
        status = coordinator.integration_status(
            self.branch.args(
                record=prepared["integration_record_id"],
                ticket=None,
                branch=None,
                batch=None,
            )
        )
        self.assertEqual(status["candidate_tree_sha"], prepared["candidate_tree_sha"])

    def test_prepare_completes_the_pair_of_a_record_prepared_before_it_existed(
        self,
    ) -> None:
        published = self.branch.publish()
        target = _git(self.branch.repo, "rev-parse", "origin/master")
        path = self.pair_path(published["candidate"], target)
        self.branch.prepare()
        # A record prepared before the pair record existed: only the pair is missing.
        path.unlink()

        repeat = self.branch.prepare()

        self.assertFalse(repeat["created"])
        self.assertEqual(
            self.stored_pair(published["candidate"], target)["candidate_tree_sha"],
            self.tree(published["candidate"]),
        )
        self.assertEqual(
            repeat["candidate_tree_sha"], self.tree(published["candidate"])
        )

    def test_refresh_records_the_pair_of_the_new_candidate(self) -> None:
        self.branch.publish()
        record_id = self.branch.prepare()["integration_record_id"]
        moved = self.branch.advance_integration_ref()

        refreshed = coordinator.integration_refresh(
            self.branch.args(record=record_id, ticket=None, branch=None, batch=None)
        )

        new = refreshed["new_candidate_sha"]
        self.assertEqual(
            self.stored_pair(new, moved)["candidate_tree_sha"], self.tree(new)
        )
        status = coordinator.integration_status(
            self.branch.args(record=record_id, ticket=None, branch=None, batch=None)
        )
        self.assertEqual(status["candidate_tree_sha"], self.tree(new))

    def test_recording_a_pair_again_is_idempotent_and_other_content_is_refused(
        self,
    ) -> None:
        published = self.branch.publish()
        target = _git(self.branch.repo, "rev-parse", "origin/master")
        ledger = LifecycleLedger(self.branch.state_root())
        audit = self.branch.audit_paths()

        with ledger_ops._ledger_lock(ledger):
            again = release_gate.record_pair(
                ledger, self.branch.repo, published["candidate"], target, FULL
            )

        self.assertEqual(again, self.stored_pair(published["candidate"], target))
        self.assertEqual(self.branch.audit_paths(), audit)
        path = self.pair_path(published["candidate"], target)
        forged = {**again, "candidate_tree_sha": "0" * 40}
        path.write_text(_canonical(forged), encoding="utf-8")
        with self.assertRaises(CoordinatorError) as raised:
            with ledger_ops._ledger_lock(ledger):
                release_gate.record_pair(
                    ledger, self.branch.repo, published["candidate"], target, FULL
                )
        self.assertIn("candidate_tree_sha", raised.exception.message)
        self.assertTrue(raised.exception.remedy.strip())

    def test_an_unknown_candidate_is_refused_and_writes_nothing(self) -> None:
        self.branch.publish()
        target = _git(self.branch.repo, "rev-parse", "origin/master")
        ledger = LifecycleLedger(self.branch.state_root())
        missing = "1" * 40

        with self.assertRaises(CoordinatorError):
            with ledger_ops._ledger_lock(ledger):
                release_gate.record_pair(
                    ledger, self.branch.repo, missing, target, FULL
                )

        self.assertFalse(self.pair_path(missing, target).exists())

    def record(self, candidate: str, target: str, selection: str) -> JsonObject:
        ledger = LifecycleLedger(self.branch.state_root())
        with ledger_ops._ledger_lock(ledger):
            return release_gate.record_pair(
                ledger, self.branch.repo, candidate, target, selection
            )

    def test_a_pair_the_flag_decided_as_ticket_diff_is_stored_as_such(self) -> None:
        published = self.branch.publish()
        target = "2" * 40

        stored = self.record(published["candidate"], target, TICKET_DIFF)

        self.assertEqual(stored, self.stored_pair(published["candidate"], target))
        self.assertEqual(set(stored), PAIR_KEYS)
        self.assertEqual((stored["contract"], stored["selection"]), (2, TICKET_DIFF))

    def test_a_pair_recorded_as_full_stays_full_when_it_is_decided_again(self) -> None:
        published = self.branch.publish()
        target = _git(self.branch.repo, "rev-parse", "origin/master")
        before = self.stored_pair(published["candidate"], target)

        for decided in (FULL, TICKET_DIFF):
            with self.subTest(decided=decided):
                again = self.record(published["candidate"], target, decided)
                self.assertEqual(again, before)
                self.assertEqual(
                    self.stored_pair(published["candidate"], target), before
                )

    def test_a_ticket_diff_pair_is_never_downgraded_to_full(self) -> None:
        published = self.branch.publish()
        target = "2" * 40
        stored = self.record(published["candidate"], target, TICKET_DIFF)

        with self.assertRaises(CoordinatorError) as raised:
            self.record(published["candidate"], target, FULL)

        self.assertIn("selection", raised.exception.message)
        self.assertIn("candidate_tree_sha", raised.exception.message)
        self.assertTrue(raised.exception.remedy.strip())
        self.assertEqual(self.stored_pair(published["candidate"], target), stored)
        self.assertEqual(
            self.record(published["candidate"], target, TICKET_DIFF), stored
        )

    def test_a_pair_of_the_old_contract_is_returned_unchanged_and_requires_full(
        self,
    ) -> None:
        published = self.branch.publish()
        target = _git(self.branch.repo, "rev-parse", "origin/master")
        path = self.pair_path(published["candidate"], target)
        old = {
            key: value
            for key, value in self.stored_pair(published["candidate"], target).items()
            if key != "selection"
        }
        old["contract"] = 1
        path.write_text(_canonical(old), encoding="utf-8")
        audit = self.branch.audit_paths()

        for decided in (FULL, TICKET_DIFF):
            with self.subTest(decided=decided):
                self.assertEqual(
                    self.record(published["candidate"], target, decided), old
                )

        self.assertEqual(self.stored_pair(published["candidate"], target), old)
        self.assertEqual(self.branch.audit_paths(), audit)

    def test_a_forged_selection_or_contract_is_refused(self) -> None:
        published = self.branch.publish()
        target = _git(self.branch.repo, "rev-parse", "origin/master")
        path = self.pair_path(published["candidate"], target)
        good = self.stored_pair(published["candidate"], target)
        forged = {
            "unknown selection": {**good, "selection": "focused"},
            "no selection under contract 2": {
                k: v for k, v in good.items() if k != "selection"
            },
            "selection under contract 1": {**good, "contract": 1},
            "contract 3": {**good, "contract": 3},
            "extra field": {**good, "requirement": FULL},
        }

        for name, record in forged.items():
            with self.subTest(forged=name):
                path.write_text(_canonical(record), encoding="utf-8")
                with self.assertRaises(CoordinatorError) as raised:
                    self.record(published["candidate"], target, FULL)
                self.assertTrue(raised.exception.remedy.strip())

    def test_required_selection_follows_the_frozen_flag_and_the_target_ref(
        self,
    ) -> None:
        repo = self.branch.repo
        cases = [
            ("flag on, integration target", True, "integration/web", TICKET_DIFF),
            ("flag on, default branch", True, "master", FULL),
            ("flag off, integration target", False, "integration/web", FULL),
        ]

        for name, flag, ref, expected in cases:
            with self.subTest(name):
                batch: JsonObject = {
                    "integration_ref": ref,
                    "verification_plan_policy": {"ticket_diff_selection": flag},
                }
                self.assertEqual(release_gate.required_selection(repo, batch), expected)
        legacy: JsonObject = {"integration_ref": "integration/web"}
        self.assertEqual(release_gate.required_selection(repo, legacy), FULL)
        self.assertEqual(
            release_gate.required_selection(
                repo,
                {"integration_ref": "integration/web", "verification_plan_policy": {}},
            ),
            FULL,
        )

    def selection_of(self, candidate: str, target: str) -> str:
        ledger = LifecycleLedger(self.branch.state_root())
        with ledger_ops._ledger_lock(ledger):
            return release_gate.pair_selection(ledger, candidate, target)

    def test_pair_selection_reads_the_stored_selection_of_the_pair(self) -> None:
        published = self.branch.publish()
        full_target = _git(self.branch.repo, "rev-parse", "origin/master")
        diff_target = "2" * 40
        self.record(published["candidate"], diff_target, TICKET_DIFF)

        self.assertEqual(self.selection_of(published["candidate"], full_target), FULL)
        self.assertEqual(
            self.selection_of(published["candidate"], diff_target), TICKET_DIFF
        )

    def test_pair_selection_is_full_when_the_pair_is_not_recorded(self) -> None:
        published = self.branch.publish()

        self.assertEqual(self.selection_of(published["candidate"], "3" * 40), FULL)
        self.assertEqual(self.selection_of("4" * 40, "3" * 40), FULL)

    def test_pair_selection_is_full_for_a_pair_of_the_first_contract(self) -> None:
        published = self.branch.publish()
        candidate = published["candidate"]
        target = "2" * 40
        stored = self.record(candidate, target, TICKET_DIFF)
        old = {k: v for k, v in stored.items() if k != "selection"}
        old["contract"] = 1
        self.pair_path(candidate, target).write_text(_canonical(old), encoding="utf-8")

        self.assertEqual(self.selection_of(candidate, target), FULL)

    def test_pair_selection_is_full_for_every_malformed_record(self) -> None:
        published = self.branch.publish()
        candidate = published["candidate"]
        target = "2" * 40
        good = self.record(candidate, target, TICKET_DIFF)
        path = self.pair_path(candidate, target)
        forged = {
            "unknown selection": {**good, "selection": "focused"},
            "no selection": {k: v for k, v in good.items() if k != "selection"},
            "contract 3": {**good, "contract": 3},
            "extra field": {**good, "requirement": TICKET_DIFF},
            "another pair": {**good, "target_sha": "5" * 40},
            "another pair id": {**good, "pair_id": "pair-" + "0" * 32},
            "no tree": {k: v for k, v in good.items() if k != "candidate_tree_sha"},
        }

        for name, record in forged.items():
            with self.subTest(forged=name):
                path.write_text(_canonical(record), encoding="utf-8")
                self.assertEqual(self.selection_of(candidate, target), FULL)
        for name, text in {"not json": "{", "not an object": "[]"}.items():
            with self.subTest(forged=name):
                path.write_text(text, encoding="utf-8")
                # Not under the lock: entering it validates the ledger and would refuse first.
                self.assertEqual(
                    release_gate.pair_selection(
                        LifecycleLedger(self.branch.state_root()), candidate, target
                    ),
                    FULL,
                )
        path.write_text(_canonical(good), encoding="utf-8")
        self.assertEqual(self.selection_of(candidate, target), TICKET_DIFF)


class SelectionOfTheWritersTests(plan_dispatch.TicketDiffFixture):
    """Every writer of a pair decides ``selection`` from the batch it holds: a ticket whose frozen
    flag is on and whose target is ``integration/*`` records ``ticket-diff``."""

    # Publish needs runtime QA evidence: a 1.x ledger (ADR 0036, section 5).
    file_ledger = True

    def setUp(self) -> None:
        super().setUp()
        self._configure(self._on())
        self.branch = PublishedBranch(self.fx, self.integration_ref)

    def pair(self, candidate: str, target: str) -> JsonObject:
        path = (
            self.branch.records()
            / "reports/integration-pair"
            / f"{_pair_id(candidate, target)}.json"
        )
        stored: JsonObject = json.loads(path.read_text(encoding="utf-8"))
        return stored

    def test_publish_prepare_refresh_and_resolution_record_ticket_diff(self) -> None:
        published = self.branch.publish()
        candidate = published["candidate"]
        target = _git(self.fx.repo, "rev-parse", "origin/integration/it")

        pair = self.pair(candidate, target)
        self.assertEqual((pair["contract"], pair["selection"]), (2, TICKET_DIFF))

        prepared = self.branch.prepare()
        self.assertEqual(self.pair(candidate, target), pair)
        record_id = prepared["integration_record_id"]
        moved = self.branch.advance_integration_ref()
        refreshed = coordinator.integration_refresh(
            self.branch.args(record=record_id, ticket=None, branch=None, batch=None)
        )
        after_refresh = self.pair(refreshed["new_candidate_sha"], moved)
        self.assertEqual(after_refresh["selection"], TICKET_DIFF)

        # A resolver batch is another batch: its own policy never decides the pair of the record.
        root = self.branch.state_root()
        ledger = LifecycleLedger(root)
        resolver_batch: JsonObject = {
            "resolver": {"integration_record_id": record_id, "target_sha": moved},
            "verification_plan_policy": {"ticket_diff_selection": False},
            "integration_ref": "master",
        }
        with ledger_ops._ledger_lock(ledger):
            resolver_state.record_resolution(
                ledger,
                self.fx.repo,
                root,
                resolver_batch,
                {"commit_sha": candidate},
                {},
            )
        resolved = self.pair(candidate, moved)
        self.assertEqual((resolved["contract"], resolved["selection"]), (2, TICKET_DIFF))


class FullSelectionOfTheWritersTests(plan_dispatch.TicketDiffFixture):
    """The flag off, or a default-branch target with the flag on, keeps ``full``."""

    # Publish needs runtime QA evidence: a 1.x ledger (ADR 0036, section 5).
    file_ledger = True

    def published_pair(self, ref: str) -> JsonObject:
        branch = PublishedBranch(self.fx, ref)
        published = branch.publish()
        target = _git(self.fx.repo, "rev-parse", f"origin/{ref}")
        path = (
            branch.records()
            / "reports/integration-pair"
            / f"{_pair_id(published['candidate'], target)}.json"
        )
        stored: JsonObject = json.loads(path.read_text(encoding="utf-8"))
        return stored

    def test_a_pair_into_an_integration_ref_with_the_flag_off_is_full(self) -> None:
        self._configure(self._on(ticket_diff_selection=False))

        pair = self.published_pair("integration/it")

        self.assertEqual((pair["contract"], pair["selection"]), (2, FULL))

    def test_a_pair_into_the_default_branch_with_the_flag_on_is_full(self) -> None:
        self._configure(self._on())

        pair = self.published_pair("master")

        self.assertEqual((pair["contract"], pair["selection"]), (2, FULL))


if __name__ == "__main__":
    unittest.main()
