"""The QA docker executor with a runtime the autostart hook started (ADR 0031; DoD 1 of #1088).

The runtime is not started by the test: the installed ``runtime-autostart`` handler of the
settings template runs before a coordinator command as Claude Code runs it (``/bin/sh -c`` in a
new session) and starts ``harness-runtime serve``. The scripted ``docker`` is first on the
``PATH`` of the hook, so the runtime finds it as it would find the real engine. ``qa run`` then
runs every QA command in its own container of that runtime.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tests.orchestration.runtime_store_support import (
    HookStartedRuntime,
    RuntimeHandle,
    store_call,
)
from tests.orchestration.test_qa_container import (
    SECRET,
    SECRET_NAME,
    ContainerQa,
    _flag,
)

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="container QA runs only on Linux",
)


def test_qa_run_works_with_the_runtime_the_autostart_hook_started(tmp_path: Path) -> None:
    started: list[HookStartedRuntime] = []

    def hook_runtime(repo: Path, environ: dict[str, str]) -> RuntimeHandle:
        started.append(HookStartedRuntime(repo, tmp_path / "project", environ))
        return started[-1]

    qa = ContainerQa(tmp_path / "q", engine="docker", runtime_factory=hook_runtime)
    try:
        [runtime] = started
        for stage in ("gate-1", "gate-2", "gate-3"):
            qa.engine.script(stage, stdout=f"{stage} ok\n", exit_code=0)

        code, result, err = qa.qa_run()

        assert code == 0 and result is not None, err
        assert qa.report()["outcome"] == "completed"
        runs = qa.engine.runs()
        assert len(runs) == 3
        for run in runs:
            assert run[:4] == ["docker", "run", "--rm", "--init"]
            # The variable reached the runtime through the hook and the container by name only.
            assert SECRET not in json.dumps(run)
            assert _flag(run, "--env").count(SECRET_NAME) == 1
        # The runtime that answers is the one the hook reported to the developer.
        assert store_call(qa.repo, runtime, "status")["pid"] == runtime.pid
        assert "harness-runtime serve" in runtime.message

        # A later coordinator command reuses it silently.
        again = runtime.pre_tool("qa status")
        assert again.returncode == 0 and again.stdout.strip() == "", again.stderr
        assert store_call(qa.repo, runtime, "status")["pid"] == runtime.pid

        # The end of the turn releases the owner; the idle store lets the runtime stop.
        runtime.stop()
        assert not runtime.socket_exists()
    finally:
        qa.close()
