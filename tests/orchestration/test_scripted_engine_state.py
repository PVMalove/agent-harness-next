"""Readers of the fake engine must not observe an in-progress CLI state write."""

from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path

import pytest

from tests.orchestration.scripted_engine import ScriptedEngine, lock


def test_a_reader_waits_for_the_cli_to_finish_writing_its_state(tmp_path: Path) -> None:
    engine = ScriptedEngine(tmp_path / "engine")
    state = engine.state()
    state["calls"] = [["podman", "info"]]
    started = threading.Event()

    def read() -> object:
        started.set()
        return engine.state()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with engine.state_file.open("r+", encoding="utf-8") as writer:
            lock(writer, exclusive=True)
            writer.truncate()
            writer.flush()
            pending = pool.submit(read)
            try:
                assert started.wait(timeout=5)
                with pytest.raises(TimeoutError):
                    pending.result(timeout=0.1)
            finally:
                writer.seek(0)
                json.dump(state, writer)
                writer.flush()
        assert pending.result(timeout=5) == state
