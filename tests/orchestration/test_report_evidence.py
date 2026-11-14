"""Report evidence validation without a repository, runtime, or report submission."""

from __future__ import annotations

import pytest

from harness.orchestration.core.report_evidence import (
    evidence_is_none,
    evidence_text,
    validate_evidence,
)
from harness.orchestration.core.utils import CoordinatorError

INVALID = (
    "none",
    "Нет. Всё сделано",
    "нет",
    " Нет. ",
    "отсутствуют",
    "Отсутствует",
    "нету",
    "нет!",
    "no",
    "n/a",
    "None.",
    "none. All done",
    {"status": "нет", "details": ""},
    {"status": "None", "details": ""},
    {"status": " none ", "details": ""},
    {"status": "absent", "details": ""},
    {"status": "none", "details": "Всё сделано"},
    {"status": "none", "details": " "},
    {"status": "present", "details": ""},
    {"status": "present", "details": " "},
    {"status": "present", "details": []},
    {"status": "none"},
    {"status": "none", "details": "", "extra": True},
    {"status": [], "details": ""},
)


@pytest.mark.parametrize("value", INVALID)
def test_invalid_evidence_is_rejected_with_an_actionable_owner(value: object) -> None:
    owner = "completion report blockers"
    with pytest.raises(CoordinatorError) as caught:
        validate_evidence(value, owner)
    assert owner in caught.value.message
    assert "none" in caught.value.remedy and "output" in caught.value.remedy
    assert not evidence_is_none(value)


def test_absence_and_human_details_are_separate() -> None:
    absent = {"status": "none", "details": ""}
    present = {"status": "present", "details": "Нет доступа к сети для проверки"}
    for value in (absent, present):
        validate_evidence(value, "report risks")
    assert evidence_is_none(absent)
    assert not evidence_is_none(present)
    assert evidence_text(absent) == "none"
    assert evidence_text(present) == "Нет доступа к сети для проверки"
