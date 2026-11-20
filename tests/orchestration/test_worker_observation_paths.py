"""The standalone adapters and the observation reader agree on the external worker log path."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from types import ModuleType

import pytest

from harness.orchestration.worker_observation import external_log_path

ADAPTERS = Path(__file__).resolve().parents[2] / "harness" / "adapters"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"adapter_under_test_{name}", ADAPTERS / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("adapter", ["codex_worker", "claude_worker"])
def test_adapter_log_path_is_the_observed_path(tmp_path: Path, adapter: str) -> None:
    module = _load(adapter)
    brief = {
        "dispatch_id": "dispatch-parity",
        "report_staging_path": str(
            tmp_path / ".harness/.sandboxes/scratch/inbox/dispatch-parity.json"
        ),
    }

    observed, reason = external_log_path(tmp_path, brief)

    assert reason is None and observed is not None
    assert module.log_path(brief).resolve() == observed
    assert not observed.parent.exists()  # computing the path creates nothing
    assert "log_path(brief)" in inspect.getsource(module.start)
