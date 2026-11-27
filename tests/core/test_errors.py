"""Remedy нарушения внутреннего инварианта ведёт в фазу RCA скилла diagnosing-bugs."""

from __future__ import annotations

from enum import StrEnum
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


GUID_KNOWN = "0b6f2a4e-3c1d-4e8a-9f2b-7d5c1a2b3c4d"
GUID_UNKNOWN = "5a1e9c3b-7f2d-4b6a-8c0e-1d2f3a4b5c6d"


class SampleFmeaId(StrEnum):
    KNOWN = GUID_KNOWN
    UNKNOWN = GUID_UNKNOWN


@pytest.fixture
def sample_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    catalog = tmp_path / "catalog.toml"
    catalog.write_text(
        "[[failure_mode]]\n"
        f'id = "{GUID_KNOWN}"\n'
        'title = "sample-mode"\n'
        'mode = "it fails"\n'
        'detection = "a timeout"\n'
        'recovery = "release the lock, then retry"\n'
        'test = "tests/x.py::test_y"\n'
        'residual_risk = "low"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("harness.fmea.catalog.CATALOG_PATH", catalog)
    return catalog


def test_an_error_without_remedy_or_fmea_is_a_type_error() -> None:
    with pytest.raises(TypeError, match="exactly one of remedy and fmea"):
        HarnessError("m")  # type: ignore[call-overload]


def test_an_error_with_both_remedy_and_fmea_is_a_type_error(sample_catalog: Path) -> None:
    with pytest.raises(TypeError, match="exactly one of remedy and fmea"):
        HarnessError("m", remedy="r", fmea=SampleFmeaId.KNOWN)  # type: ignore[call-overload]


def test_an_fmea_error_takes_its_remedy_and_title_from_the_catalog(sample_catalog: Path) -> None:
    error = HarnessError("git hung", fmea=SampleFmeaId.KNOWN)  # type: ignore[call-overload]

    assert error.remedy == "release the lock, then retry"
    assert error.fmea is SampleFmeaId.KNOWN
    assert error.fmea_title == "sample-mode"


def test_an_unknown_fmea_id_raises_an_internal_invariant_error(sample_catalog: Path) -> None:
    with pytest.raises(HarnessError) as caught:
        HarnessError("git hung", fmea=SampleFmeaId.UNKNOWN)  # type: ignore[call-overload]

    assert caught.value.remedy == INTERNAL_INVARIANT_REMEDY
    assert GUID_UNKNOWN in caught.value.message
    assert caught.value.fmea is None


def test_print_and_exit_adds_the_fmea_line_for_an_fmea_error(
    sample_catalog: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    error = HarnessError("git hung", fmea=SampleFmeaId.KNOWN)  # type: ignore[call-overload]

    code = print_and_exit(error)

    assert code == 2
    assert capsys.readouterr().err.splitlines() == [
        "ERROR: git hung",
        "REMEDY: release the lock, then retry",
        f"FMEA: {GUID_KNOWN} (sample-mode)",
    ]


def test_print_and_exit_prints_only_two_lines_for_a_legacy_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = print_and_exit(HarnessError("boom", remedy="fix it"))

    assert code == 2
    assert capsys.readouterr().err == "ERROR: boom\nREMEDY: fix it\n"
