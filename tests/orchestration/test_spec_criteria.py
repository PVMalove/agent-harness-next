"""Candidate review accounts for the acceptance criteria in its brief."""

import pytest

from harness.json_types import JsonObject
from harness.orchestration.core.utils import CoordinatorError
from harness.orchestration.workflow.reports import _validate_review


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
