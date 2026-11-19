"""Candidate review accounts for the acceptance criteria in its brief."""

import unittest

import pytest

from harness.json_types import JsonObject
from harness.orchestration.core.utils import CoordinatorError
from harness.orchestration.workflow.reports import _validate_review
from tests.orchestration import test_coordinator as coordinator_tests


def test_spec_review_accepts_evidence_for_each_criterion() -> None:
    candidate = "a" * 40
    criteria = ["Save survives a restart", "Invalid input is rejected"]
    no_risk = {"status": "none", "details": ""}
    axis = {"severity": "clean", "findings": [], "risks": no_risk, "blockers": no_risk}
    review: JsonObject = {
        "candidate_commit": candidate,
        "scope": "full",
        "standards": axis,
        "spec": {
            **axis,
            "criteria": [
                {
                    "criterion": criteria[0],
                    "status": "met",
                    "evidence": "test_restart passes",
                },
                {
                    "criterion": criteria[1],
                    "status": "met",
                    "evidence": "test_invalid passes",
                },
            ],
        },
    }
    dispatch = {
        "candidate_commit": candidate,
        "review_scope": "full",
        "definition_of_done": criteria,
    }

    _validate_review(review, dispatch)

    review["spec"]["criteria"][1]["status"] = "missing"
    with pytest.raises(CoordinatorError, match="unresolved criteria"):
        _validate_review(review, dispatch)

    del review["spec"]["criteria"]
    with pytest.raises(CoordinatorError, match="spec evidence has an invalid schema"):
        _validate_review(review, dispatch)
    # A review that did not complete has not judged the criteria yet.
    _validate_review(review, dispatch, completed=False)


class SpecCriteriaSubmissionTests(unittest.TestCase):
    """A full review reaches the ledger only with a Spec row for every brief criterion."""

    def setUp(self) -> None:
        self.fx = coordinator_tests.CoordinatorRetryRoutingTests()
        self.fx.setUp()
        self.addCleanup(self.fx.tearDown)
        batch_id = self.fx._create_batch()["batch_id"]
        self.fx._accepted_architect(batch_id)
        candidate = self.fx._accepted_candidate(batch_id)
        self.brief = self.fx._dispatch(batch_id, "code-review", candidate=candidate)[
            "brief"
        ]
        self.fx._start(self.brief["dispatch_id"], checkout=self.fx.worktree)
        self.report = self.fx._base_report(
            self.brief,
            "code-review",
            checks_run=self.fx._checks(self.brief, "pass"),
            review={
                "candidate_commit": candidate,
                "scope": self.brief["review_scope"],
                **self.fx._axes(("clean", []), ("clean", [])),
            },
        )

    def test_a_full_spec_review_without_criteria_is_rejected(self) -> None:
        del self.report["review"]["spec"]["criteria"]

        with self.assertRaises(CoordinatorError) as caught:
            self.fx._submit(self.brief["dispatch_id"], self.report)

        self.assertIn("spec evidence has an invalid schema", caught.exception.message)

    def test_a_full_spec_review_with_every_criterion_is_recorded(self) -> None:
        rows = self.report["review"]["spec"]["criteria"]
        self.assertEqual(
            [row["criterion"] for row in rows], self.brief["definition_of_done"]
        )

        self.fx._submit(self.brief["dispatch_id"], self.report)
