"""``integration local-qa`` against a runtime-store state root and the real ``harness-runtime``.

The integration record is prepared on the file ledger, the state is cut over to the store, and
the coordinator CLI then runs local QA through the runtime: its QA log goes into the store, and
the runtime's verdict on the pair is recorded beside the result.
"""

from __future__ import annotations

import json
import unittest

from harness.orchestration.core.utils import JsonObject
from harness.orchestration.ledger.lifecycle import IntegrationLocalQaRecord
from harness.orchestration.workflow import release_gate
from tests.orchestration import runtime_store_support as support
from tests.orchestration.test_integration_record import PublishedBranch

LOCAL_QA = "reports/integration-local-qa"


class LocalQaInTheStoreEpoch(unittest.TestCase):
    def setUp(self) -> None:
        support.runtime_binary()
        self.branch = PublishedBranch()
        self.addCleanup(self.branch.close)
        self.branch.fixture.state_dir = (
            self.branch.repo / ".harness/orchestration/state"
        )
        self.branch.publish()
        self.prepared = self.branch.prepare()
        migrated = support.migrate(self.branch.repo)
        self.assertEqual(migrated.returncode, 0, migrated.stderr)
        self.runtime = support.ServingRuntime(self.branch.repo)
        self.addCleanup(self.runtime.stop)

    def local_qa(self) -> JsonObject:
        result = support.coordinator_with(
            self.branch.repo,
            self.runtime,
            "integration",
            "local-qa",
            "--record",
            self.prepared["integration_record_id"],
            "--ci-condition",
            "absent",
            "--reason",
            "No combined CI",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        answer: JsonObject = json.loads(result.stdout)
        return answer

    @staticmethod
    def verdict(answer: JsonObject) -> object:
        pair_verdict = answer["pair_verdict"]
        assert isinstance(pair_verdict, dict)
        return pair_verdict["verdict"]

    def test_the_log_is_stored_and_the_pair_verdict_is_recorded(self) -> None:
        result = self.local_qa()

        self.assertEqual(
            (result["state"], result["verification"]), ("completed", "verified")
        )
        request_id = str(result["request_id"])
        verdict_id = IntegrationLocalQaRecord.derive_id(
            {"request_id": request_id, "event": "pair-verdict"}
        )
        paths = (
            f"{LOCAL_QA}/{result['local_qa_id']}.json",
            f"{LOCAL_QA}/{verdict_id}.json",
        )
        records = support.store_records(self.branch.repo, self.runtime, *paths)
        self.assertEqual(records[paths[0]]["verification"], "verified")
        verdict = records[paths[1]]
        self.assertEqual(verdict["event"], "pair-verdict")
        self.assertEqual(verdict["verdict"], "ok")
        self.assertEqual(verdict["violation_codes"], [])
        confirmed = verdict["confirmed_by"]
        assert isinstance(confirmed, dict)
        self.assertEqual(confirmed["source"], "local-qa")
        self.assertEqual(self.verdict(result), "ok")
        # The runtime itself finds the stored log, its trailer and the stage evidence.
        answer = support.store_call(
            self.branch.repo,
            self.runtime,
            "qa.evidence.verify",
            {
                "candidate_sha": result["candidate_sha"],
                "target_sha": result["target_sha"],
            },
        )
        self.assertEqual(answer["verdict"], "ok", answer["violations"])

    def test_a_repeat_answers_the_recorded_result_and_verdict(self) -> None:
        first = self.local_qa()

        again = self.local_qa()

        self.assertEqual(again["request_id"], first["request_id"])
        self.assertEqual(again["verification"], "verified")
        self.assertEqual(self.verdict(again), "ok")
        self.assertEqual(
            release_gate.SELECTION_FULL,
            support.store_records(
                self.branch.repo,
                self.runtime,
                f"reports/integration-pair/{release_gate.pair_id(str(first['candidate_sha']), str(first['target_sha']))}.json",
            ).popitem()[1]["selection"],
        )
