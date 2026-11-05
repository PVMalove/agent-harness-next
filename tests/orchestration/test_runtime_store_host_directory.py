"""Real engine smoke can borrow the host runtime directory without deleting its state (#811)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

from tests.orchestration.runtime_store_support import (
    SHORT_TMP,
    ServingRuntime,
    coordinator_with,
    migrate,
    write_coordinator_state,
)


@pytest.mark.skipif(sys.platform == "win32", reason="the runtime uses a Unix socket")
def test_a_runtime_can_serve_in_the_host_directory_and_preserves_its_engine_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _ = write_coordinator_state(tmp_path)
    migrated = migrate(repo)
    assert migrated.returncode == 0, migrated.stderr
    with tempfile.TemporaryDirectory(prefix="host-xdg-", dir=SHORT_TMP) as directory:
        host_runtime_dir = Path(directory)
        engine_state = host_runtime_dir / "containers" / "networks" / "sentinel"
        engine_state.parent.mkdir(parents=True)
        engine_state.write_text("existing engine state", encoding="utf-8")
        monkeypatch.setenv("XDG_RUNTIME_DIR", directory)
        runtime = ServingRuntime(repo, host_runtime_dir=host_runtime_dir)
        try:
            # No fixture environment override: the client uses the real host directory.
            result = coordinator_with(repo, None, "batch", "list")
            assert result.returncode == 0, result.stderr
        finally:
            runtime.stop()

        assert engine_state.read_text(encoding="utf-8") == "existing engine state"
