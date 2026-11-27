"""FMEA git-timeout: detection in _run_git and recovery after the Git lock is released (ADR 0041)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from harness.context_builder.context_builder import ContextPackageError, _run_git
from harness.fmea.catalog import find_entry
from harness.fmea.ids import FmeaId

RUN = "harness.context_builder.context_builder.subprocess.run"


@pytest.mark.fmea
def test_git_timeout_recovers_after_the_lock_is_released(tmp_path: Path) -> None:
    with (
        patch(RUN, side_effect=subprocess.TimeoutExpired(["git"], 60)),
        pytest.raises(ContextPackageError) as caught,
    ):
        _run_git(tmp_path, "rev-parse", "HEAD")

    entry = find_entry(FmeaId.GIT_TIMEOUT)
    assert entry is not None
    assert caught.value.fmea is FmeaId.GIT_TIMEOUT
    assert caught.value.remedy == entry.recovery

    released = subprocess.CompletedProcess(
        args=["git", "rev-parse", "HEAD"], returncode=0, stdout="ok\n", stderr=""
    )
    with patch(RUN, return_value=released):
        assert _run_git(tmp_path, "rev-parse", "HEAD") == "ok\n"
