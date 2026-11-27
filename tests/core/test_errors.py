"""Remedy нарушения внутреннего инварианта ведёт в фазу RCA скилла diagnosing-bugs."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.errors import INTERNAL_INVARIANT_REMEDY, HarnessError, print_and_exit

ROOT = Path(__file__).resolve().parents[2]
DIAGNOSING_BUGS = ROOT / "skills" / "first-party" / "engineering" / "diagnosing-bugs" / "SKILL.md"


def test_an_internal_invariant_error_sends_the_agent_to_the_rca_phase(
    capsys: pytest.CaptureFixture[str],
) -> None:
    error = HarnessError("ledger row vanished", remedy=INTERNAL_INVARIANT_REMEDY)

    print_and_exit(error)

    stderr_lines = capsys.readouterr().err.splitlines()
    assert any(
        line.startswith("REMEDY: ") and "diagnosing-bugs" in line and "RCA phase" in line
        for line in stderr_lines
    ), stderr_lines


def test_the_remedy_names_a_phase_that_exists_in_diagnosing_bugs() -> None:
    lines = DIAGNOSING_BUGS.read_text(encoding="utf-8").splitlines()

    assert any(line.startswith("## RCA phase") for line in lines)
    assert "RCA phase" in INTERNAL_INVARIANT_REMEDY
