"""Unit tests of console logic; no application startup or external processes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable, Mapping, Sequence, cast
from unittest import mock

import pytest

from harness.console import launcher
from harness.console.kernel.discovery import ServerEndpoint
from harness.console.pin import TEXTUAL_PIN, WEBSOCKETS_PIN
from harness.console.tui.client import (
    ConsoleClient,
    HomeClient,
)
from tests.console._home_client import FakeHomeClient

# The real functions: tests/console/conftest.py replaces the module attributes with a fake.
CONNECT_CONSOLE = launcher.connect_console
DISCOVER_CONSOLE = launcher.discover_console


UvAt = Callable[[str | None], None]


@pytest.fixture
def uv_at(monkeypatch: pytest.MonkeyPatch) -> UvAt:
    """Выбирает, где `find_uv` находит `uv` (None — не находит), и снимает `RELAUNCH_ENV`."""
    monkeypatch.delenv(launcher.RELAUNCH_ENV, raising=False)

    def choose(path: str | None) -> None:
        monkeypatch.setattr(launcher, "find_uv", lambda: path)

    return choose


def _ready_server(_repo: Path, _uv: str) -> ServerEndpoint:
    return ServerEndpoint(port=1, token="00" * 32)


def _fake_client(repo: Path) -> ConsoleClient:
    return cast(ConsoleClient, FakeHomeClient(repo))


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


def test_build_relaunch_argv_adds_the_websockets_pin_for_the_server_client() -> None:
    argv = launcher.build_relaunch_argv("/usr/local/bin/uv", Path("/tmp/some-repo"))
    pins = [argv[index + 1] for index, arg in enumerate(argv) if arg == "--with"]
    assert pins == [f"textual=={TEXTUAL_PIN}", f"websockets=={WEBSOCKETS_PIN}"]


def test_build_server_argv_pins_the_server_requirements_and_never_touches_the_project() -> (
    None
):
    repo = Path("/tmp/some-repo")
    argv = launcher.build_server_argv("/usr/local/bin/uv", repo)

    assert argv == [
        "/usr/local/bin/uv",
        "run",
        "--no-project",
        "--python",
        sys.executable,
        "--with",
        "fastapi==0.162.0",
        "--with",
        "starlette==1.10.0",
        "--with",
        "uvicorn==0.54.0",
        "--with",
        "pydantic==2.14.3",
        "--with",
        "websockets==17.3",
        "python",
        str(launcher.BIN_HARNESS_PATH),
        "console-server",
        str(repo),
    ]


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
    calls: list[tuple[Path, HomeClient]] = []
    client = FakeHomeClient(repo)

    def fake_app_runner(passed_repo: Path, passed_client: HomeClient) -> int:
        calls.append((passed_repo, passed_client))
        return 0

    with mock.patch.dict("os.environ", {launcher.RELAUNCH_ENV: "1"}):
        with mock.patch.object(launcher, "find_uv") as find_uv:
            exit_code = launcher.run_console(
                repo,
                app_runner=fake_app_runner,
                client_connector=lambda _repo: cast(ConsoleClient, client),
            )
            find_uv.assert_not_called()

    assert exit_code == 0
    assert calls == [(repo, client)]
    assert client.closed


def test_the_outer_process_exits_one_without_a_second_message_after_the_fallback(
    capsys: pytest.CaptureFixture[str], uv_at: UvAt
) -> None:
    def fell_back(
        argv: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> "subprocess.CompletedProcess[str]":
        assert env is not None
        Path(env[launcher.FALLBACK_ENV]).touch()
        return subprocess.CompletedProcess(list(argv), 1, "", "")

    uv_at("/usr/local/bin/uv")
    exit_code = launcher.run_console(
        Path("/tmp/some-repo"), runner=fell_back, server_starter=_ready_server
    )

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "не удалось запустить textual" not in out and "Итого:" not in out


def test_run_console_relaunches_via_the_injected_runner_when_uv_is_found(
    uv_at: UvAt,
) -> None:
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

    uv_at("/usr/local/bin/uv")
    exit_code = launcher.run_console(
        repo, runner=fake_runner, server_starter=_ready_server
    )

    assert exit_code == 0
    assert recorded_argv[0] == "/usr/local/bin/uv"
    assert recorded_env[launcher.RELAUNCH_ENV] == "1"


def test_a_tui_failure_after_start_reports_the_exit_code_without_the_fallback(
    capsys: pytest.CaptureFixture[str],
    uv_at: UvAt,
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

    uv_at("/usr/local/bin/uv")
    exit_code = launcher.run_console(
        repo, runner=started_then_failed, server_starter=_ready_server
    )

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
        assert (
            launcher.run_console(
                tmp_path,
                app_runner=lambda _repo, _client: 0,
                client_connector=_fake_client,
            )
            == 0
        )
    assert marker.is_file()
