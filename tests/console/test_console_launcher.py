"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence
from unittest import mock

import pytest

from harness.console import launcher
from harness.console.pin import TEXTUAL_PIN


def test_find_uv_uses_shutil_which() -> None:
    with mock.patch("shutil.which", return_value=None) as which:
        assert launcher.find_uv() is None
        which.assert_called_once_with("uv")

    with mock.patch("shutil.which", return_value="/usr/local/bin/uv") as which:
        assert launcher.find_uv() == "/usr/local/bin/uv"
        which.assert_called_once_with("uv")


def test_build_relaunch_argv_pins_textual_and_never_touches_the_project() -> None:
    repo = Path("/tmp/some-repo")
    argv = launcher.build_relaunch_argv("/usr/local/bin/uv", repo)

    assert argv[0] == "/usr/local/bin/uv"
    assert argv[1] == "run"
    # --no-project: uv run must never install or lock the surrounding project's own dependencies.
    assert "--no-project" in argv
    # --python: reuse the interpreter that passed the Python >= 3.12 check, not uv's first find.
    assert argv[argv.index("--python") + 1] == sys.executable
    assert argv[argv.index("--with") + 1] == f"textual=={TEXTUAL_PIN}"
    assert argv[-2:] == ["console", str(repo)]
    assert str(launcher.BIN_HARNESS_PATH) in argv


def test_build_relaunch_argv_forwards_extra_argv() -> None:
    repo = Path("/tmp/some-repo")
    argv = launcher.build_relaunch_argv("/usr/local/bin/uv", repo, ["--foo", "bar"])
    assert argv[-2:] == ["--foo", "bar"]


def test_restart_console_reexecutes_current_python_for_selected_project() -> None:
    repo = Path("/tmp/selected project")
    with mock.patch("os.execv", side_effect=OSError("exec failed")) as execv:
        with pytest.raises(OSError, match="exec failed"):
            launcher.restart_console(repo)
    execv.assert_called_once_with(
        sys.executable,
        [sys.executable, str(launcher.BIN_HARNESS_PATH), "console", str(repo)],
    )


def test_run_console_already_relaunched_runs_the_injected_app_runner() -> None:
    """Proves the "already relaunched" branch never needs `find_uv`/`runner` and dispatches to
    `app_runner` - injected here without replacing modules in sys.modules."""
    repo = Path("/tmp/some-repo")
    calls: list[Path] = []

    def fake_app_runner(passed_repo: Path) -> int:
        calls.append(passed_repo)
        return 0

    with mock.patch.dict("os.environ", {launcher.RELAUNCH_ENV: "1"}):
        with mock.patch.object(launcher, "find_uv") as find_uv:
            exit_code = launcher.run_console(repo, app_runner=fake_app_runner)
            find_uv.assert_not_called()

    assert exit_code == 0
    assert calls == [repo]


def test_run_console_relaunches_via_the_injected_runner_when_uv_is_found() -> None:
    repo = Path("/tmp/some-repo")
    recorded_argv: list[str] = []
    recorded_env: dict[str, str] = {}

    def fake_runner(
        argv: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> "subprocess.CompletedProcess[str]":
        recorded_argv.extend(argv)
        if env is not None:
            recorded_env.update(env)
        return subprocess.CompletedProcess(list(argv), 0, "", "")

    with mock.patch.dict("os.environ"):
        os.environ.pop(launcher.RELAUNCH_ENV, None)
        with mock.patch.object(launcher, "find_uv", return_value="/usr/local/bin/uv"):
            exit_code = launcher.run_console(repo, runner=fake_runner)

    assert exit_code == 0
    assert recorded_argv[0] == "/usr/local/bin/uv"
    assert recorded_env[launcher.RELAUNCH_ENV] == "1"


def test_a_tui_failure_after_start_reports_the_exit_code_without_the_fallback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The fallback is for a failed start (no uv, offline, textual install failure): once the
    relaunched process reached the TUI, a non-zero exit is the TUI's own and only its code is
    reported, never "не удалось запустить textual"."""
    repo = Path("/tmp/some-repo")

    def started_then_failed(
        argv: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> "subprocess.CompletedProcess[str]":
        assert env is not None
        Path(
            env[launcher.STARTED_ENV]
        ).touch()  # what the relaunched process does on start
        return subprocess.CompletedProcess(list(argv), 3, "", "")

    with mock.patch.dict("os.environ"):
        os.environ.pop(launcher.RELAUNCH_ENV, None)
        with mock.patch.object(launcher, "find_uv", return_value="/usr/local/bin/uv"):
            exit_code = launcher.run_console(repo, runner=started_then_failed)

    out = capsys.readouterr().out
    assert exit_code == 3
    assert "завершился с кодом 3" in out
    assert "не удалось запустить" not in out
    assert "Итого:" not in out


def test_the_relaunched_process_marks_that_the_tui_started(tmp_path: Path) -> None:
    marker = tmp_path / "started"
    with mock.patch.dict(
        "os.environ", {launcher.RELAUNCH_ENV: "1", launcher.STARTED_ENV: str(marker)}
    ):
        assert launcher.run_console(tmp_path, app_runner=lambda _repo: 0) == 0
    assert marker.is_file()
