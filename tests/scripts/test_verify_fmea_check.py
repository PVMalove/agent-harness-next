"""scripts/verify.py runs the FMEA drift check among its static checks (ADR 0041)."""

from __future__ import annotations

import pytest

from scripts import verify

FMEA_SCRIPT = str(verify.ROOT / "scripts" / "fmea_catalog.py")


def test_static_checks_run_the_fmea_drift_check(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def record(command: list[str], **_: object) -> None:
        calls.append(list(command))

    monkeypatch.setattr(verify, "run_ok", record)
    for helper in (
        "_check_private_terms",
        "_check_python_syntax",
        "_check_global_skills",
        "_check_documentation",
    ):
        monkeypatch.setattr(verify, helper, lambda *_args: None)

    verify._static_checks({})

    fmea = [index for index, call in enumerate(calls) if FMEA_SCRIPT in call]
    assert len(fmea) == 1
    assert calls[fmea[0]][-2:] == ["generate", "--check"]
    registry = next(index for index, call in enumerate(calls) if "skills/REGISTRY.md" in call)
    assert registry < fmea[0]


def test_the_fmea_script_is_compiled_before_the_stages() -> None:
    assert FMEA_SCRIPT in verify._compiled_sources()
