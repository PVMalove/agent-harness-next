"""Every item of the ticket-diff selection, checked through the coordinator CLI as a process (#935).

The ledger, the git repository and the briefs come from the real coordinator fixture; each assertion
is made on the output of `python coordinator.py ...` run as a separate process, so it proves the
shipped command line and not only the functions behind it. The offline parser bundle is not
installed for the child process: the import graph is then degraded, which a ticket-diff plan must
ignore and a flag-off plan answers with a full pytest stage.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

from harness.gate_runner import stage_evidence
from harness.gate_runner.gate_runner import parse_evidence_trailer
from harness.orchestration import coordinator
from harness.orchestration.core.utils import JsonObject
from tests.orchestration.test_coordinator import ORCHESTRATION_ROOT
from tests.orchestration.test_verification_plan_dispatch import (
    TicketDiffFixture,
    _stage,
)

# A policy whose stages succeed anywhere: `python -c pass` stands for lint and for the pytest run.
CLI_POLICY: JsonObject = {
    "max_related_tests": 5,
    "stages": [
        {
            "stage_id": "lint",
            "kind": "lint",
            "argv": ["python", "-c", "pass"],
            "timeout_seconds": 600,
        },
        {
            "stage_id": "tests",
            "kind": "pytest",
            "argv": ["python", "-c", "pass"],
            "timeout_seconds": 1800,
        },
    ],
}


# A bare launcher lets the gate select the checkout's Python on either platform.
PASS = shlex.join(["python", "-c", "pass"])

class TicketDiffCliTests(TicketDiffFixture):
    def _on(self, **changes: object) -> JsonObject:
        return {**CLI_POLICY, "ticket_diff_selection": True, **changes}

    def _process(self, *argv: str) -> tuple[int, str, str]:
        # The QA lane is repository-scoped and refuses an explicit --state-dir.
        state = [] if argv[0] == "qa" else ["--state-dir", str(self.fx.state_dir)]
        done = subprocess.run(
            [
                sys.executable, str(ORCHESTRATION_ROOT / "coordinator.py"),
                "--repo", str(self.fx.repo), *state, *argv,
            ],
            capture_output=True,
            text=True,
            check=False,
        )  # fmt: skip
        return done.returncode, done.stdout, done.stderr

    def _propose(self, batch_id: str, role: str, candidate: str) -> JsonObject:
        code, out, err = self._process(
            "dispatch", "propose", "--batch", batch_id, "--role", role,
            "--candidate-commit", candidate, "--runtime", "claude",
            "--model", "sonnet", "--effort", "high",
        )  # fmt: skip
        self.assertEqual(code, 0, err)
        proposal: JsonObject = json.loads(out)
        return proposal

    def _reviewed(self, policy: JsonObject) -> tuple[str, str]:
        self._configure(policy)
        batch_id, candidate = self._assessed_candidate_with_test()
        self.fx._reported_review(batch_id, candidate)
        self.fx._decide(batch_id, "accept")
        return batch_id, candidate

    def test_a_review_and_a_qa_proposal_select_exactly_the_tests_of_the_diff(
        self,
    ) -> None:
        batch_id, candidate = self._reviewed(self._on())

        for role in ("code-review", "qa"):
            with self.subTest(role=role):
                proposal = self._propose(batch_id, role, candidate)
                plan = proposal["verification_plan"]
                tests = _stage(plan, "tests")
                self.assertEqual(tests["selection"], "ticket-diff")
                self.assertEqual(tests["nodeids"], ["services/test_y.py"])
                self.assertEqual(_stage(plan, "lint")["selection"], "full")
                self.assertEqual(
                    proposal["transition"]["verification_commands"],
                    [
                        PASS,
                        f"{PASS} services/test_y.py",
                    ],
                )

    def test_a_default_branch_target_and_a_disabled_flag_keep_the_full_qa_plan(
        self,
    ) -> None:
        cases = {
            "flag off on an integration target": (False, "integration/it"),
            "flag on on the default branch": (True, "master"),
        }
        for case, (flag, ref) in cases.items():
            with self.subTest(case=case):
                self.fx._reset()
                self._write_test()
                self._publish_integration_ref()
                self.integration_ref = ref
                batch_id, candidate = self._reviewed(
                    self._on(ticket_diff_selection=flag)
                )

                plan = self._propose(batch_id, "qa", candidate)["verification_plan"]

                self.assertEqual(_stage(plan, "tests")["selection"], "full")
                self.assertNotIn("ticket_diff", plan)

    def test_a_config_edit_after_batch_create_does_not_change_the_plan(self) -> None:
        batch_id, candidate = self._reviewed(self._on())
        self._configure(self._on(ticket_diff_selection=False))

        plan = self._propose(batch_id, "qa", candidate)["verification_plan"]

        self.assertEqual(_stage(plan, "tests")["selection"], "ticket-diff")

    def test_a_diff_without_tests_runs_no_test_and_is_never_widened(self) -> None:
        self._configure(self._on())
        fx = self.fx
        batch_id = fx._create_batch(integration_ref=self.integration_ref)["batch_id"]
        fx._accepted_architect(batch_id)
        first = fx._dispatch(batch_id, "developer")["brief"]
        fx._start(first["dispatch_id"])
        candidate, changed = fx._developer_commit("x")
        fx._submit(
            first["dispatch_id"], fx._developer_report(first, candidate, changed)
        )
        fx._decide(batch_id, "accept")
        fx._assess(batch_id, candidate, changed)
        fx._reported_review(batch_id, candidate)
        fx._decide(batch_id, "accept")

        proposal = self._propose(batch_id, "qa", candidate)

        tests = _stage(proposal["verification_plan"], "tests")
        self.assertEqual((tests["selection"], tests["nodeids"]), ("ticket-diff", []))
        self.assertEqual(
            proposal["transition"]["verification_commands"],
            [PASS],
        )

    def test_the_impact_gate_accepts_the_real_plan_through_dispatch_create(
        self,
    ) -> None:
        batch_id, candidate = self._reviewed(self._on())
        proposal = self._propose(batch_id, "code-review", candidate)

        code, out, err = self._process(
            "dispatch", "create", "--batch", batch_id, "--role", "code-review",
            "--candidate-commit", candidate, "--runtime", "claude",
            "--model", "sonnet", "--effort", "high",
            "--transition-digest", str(proposal["transition_digest"]),
            "--approved-by", "Malove", "--approved-at", self.fx.APPROVED_AT,
        )  # fmt: skip

        self.assertEqual(code, 0, err)
        brief = json.loads(out)["brief"]
        self.assertEqual(
            _stage(brief["verification_plan"], "tests")["nodeids"],
            ["services/test_y.py"],
        )

    def test_qa_run_records_the_selection_and_explicit_nodeids_in_stage_evidence(
        self,
    ) -> None:
        # The QA lane is repository-scoped: its ledger is the repository's own state directory.
        self.fx.state_dir = self.fx.repo / coordinator.STATE_REL
        batch_id, candidate = self._reviewed(self._on())
        brief = self.fx._dispatch(batch_id, "qa", candidate=candidate)["brief"]

        code, out, err = self._process("qa", "run", "--dispatch", brief["dispatch_id"])

        self.assertEqual(code, 0, err)
        log = Path(json.loads(out)["artifact"])
        linked = parse_evidence_trailer(log.read_text(encoding="utf-8").splitlines())
        assert linked is not None
        document = log.parent.parent / linked[0]
        stages = stage_evidence.parse(document.read_text(encoding="utf-8")).stages
        self.assertEqual(
            [(s.stage_id, s.kind, s.selection, s.nodeids, s.result) for s in stages],
            [
                ("gate-1", "lint", "full", None, "pass"),
                ("gate-2", "pytest", "ticket-diff", ("services/test_y.py",), "pass"),
            ],
        )
