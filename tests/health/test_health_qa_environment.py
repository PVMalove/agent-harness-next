"""Whether the agent environment can run the project's required QA commands (#1050).

`environment.qa_executables`, `environment.c_linker` and `environment.runtime_socket_path` only
read the environment: PATH, the repository files and the runtime directory variables."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from harness.health.checks import environment
from harness.health.context import HealthContext


def _repo(path: Path, qa_gate_commands: list[str] | None) -> Path:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    if qa_gate_commands is not None:
        (path / ".harness").mkdir()
        (path / ".harness" / "project.json").write_text(
            json.dumps({"qa_gate_commands": qa_gate_commands}), encoding="utf-8"
        )
    return path


def _context(repo: Path) -> HealthContext:
    return HealthContext(
        repo=repo, lock={"capabilities": ["backend-orchestration"]}, online=False
    )


def _executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":  # `which` finds a Windows executable by its PATHEXT suffix
        path = path.with_name(path.name + ".cmd")
        path.write_text("@exit /b 0\r\n", encoding="utf-8", newline="")
        return path
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _only_on_path(
    monkeypatch: pytest.MonkeyPatch, bin_dir: Path, *names: str
) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        _executable(bin_dir / name)
    monkeypatch.setenv("PATH", str(bin_dir))


# --- environment.qa_executables ----------------------------------------------------------------


def test_qa_executables_are_skipped_without_qa_gate_commands(tmp_path: Path) -> None:
    repo = _repo(tmp_path / "repo", None)

    result = environment.check_qa_executables(_context(repo))

    assert (result.id, result.status) == ("environment.qa_executables", "skipped")


def test_qa_executables_are_ok_when_every_first_word_is_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path / "repo", ["make lint", "cargo test --locked"])
    _only_on_path(monkeypatch, tmp_path / "bin", "make", "cargo")

    result = environment.check_qa_executables(_context(repo))

    assert result.status == "ok"
    assert result.fix is None


def test_a_qa_executable_missing_from_path_warns_with_its_name_and_a_remedy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path / "repo", ["make lint", "cargo test --locked"])
    _only_on_path(monkeypatch, tmp_path / "bin", "make")

    result = environment.check_qa_executables(_context(repo))

    assert result.status == "warn"
    assert "cargo" in result.message
    assert "make" not in result.message
    assert result.fix is not None and "cargo" in result.fix.text


def test_a_repository_relative_qa_executable_is_resolved_against_the_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = ".harness/.venv/bin/python" + (".cmd" if sys.platform == "win32" else "")
    repo = _repo(tmp_path / "repo", [f"{executable} -m pytest -q"])
    _only_on_path(monkeypatch, tmp_path / "bin")

    missing = environment.check_qa_executables(_context(repo))
    _executable(repo / ".harness" / ".venv" / "bin" / "python")
    present = environment.check_qa_executables(_context(repo))

    assert missing.status == "warn"
    assert executable in missing.message
    assert present.status == "ok"


# --- environment.c_linker ----------------------------------------------------------------------


def test_c_linker_is_skipped_when_the_project_builds_no_rust(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path / "repo", ["make lint"])
    _only_on_path(monkeypatch, tmp_path / "bin", "make")

    result = environment.check_c_linker(_context(repo))

    assert (result.id, result.status) == ("environment.c_linker", "skipped")


def test_a_native_cargo_manifest_with_cc_on_path_is_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path / "repo", ["make lint"])
    manifest = repo / "native" / "harness-runtime" / "Cargo.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("[workspace]\n", encoding="utf-8")
    _only_on_path(monkeypatch, tmp_path / "bin", "make", "cc")

    result = environment.check_c_linker(_context(repo))

    assert result.status == "ok"


@pytest.mark.parametrize(
    ("qa_gate_commands", "native_manifest"),
    [(["cargo test --locked"], False), (["make lint"], True)],
    ids=["cargo-in-qa-commands", "native-cargo-manifest"],
)
def test_a_rust_project_without_cc_warns_with_a_remedy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    qa_gate_commands: list[str],
    native_manifest: bool,
) -> None:
    repo = _repo(tmp_path / "repo", qa_gate_commands)
    if native_manifest:
        manifest = repo / "native" / "crate" / "Cargo.toml"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("[package]\n", encoding="utf-8")
    _only_on_path(monkeypatch, tmp_path / "bin", "make", "cargo")

    result = environment.check_c_linker(_context(repo))

    assert result.status == "warn"
    assert "cc" in result.message
    assert result.fix is not None and result.fix.text


# --- environment.runtime_socket_path -----------------------------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="a Windows runtime listens on a named pipe")
def test_a_runtime_socket_path_within_the_limit_is_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path / "repo", ["make lint"])
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")

    result = environment.check_runtime_socket_path(_context(repo))

    assert (result.id, result.status) == ("environment.runtime_socket_path", "ok")


@pytest.mark.skipif(os.name == "nt", reason="a Windows runtime listens on a named pipe")
def test_a_runtime_socket_path_over_100_bytes_warns_with_a_shorter_directory_remedy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path / "repo", ["make lint"])
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/" + "d" * 100)

    result = environment.check_runtime_socket_path(_context(repo))

    assert result.status == "warn"
    assert "/" + "d" * 100 + "/harness/" in result.message
    assert result.fix is not None and "XDG_RUNTIME_DIR" in result.fix.text


def test_the_runtime_socket_path_is_skipped_without_backend_orchestration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path / "repo", ["make lint"])
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/" + "d" * 100)
    context = HealthContext(repo=repo, lock={"capabilities": ["engineering-suite"]}, online=False)

    result = environment.check_runtime_socket_path(context)

    assert result.status == "skipped"


# --- review follow-ups -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    ["FOO=1 BAR=2 make test", "cd native && make test", "export X=1; make test"],
    ids=["assignment-prefix", "cd-builtin", "export-builtin"],
)
def test_assignments_and_shell_builtins_do_not_count_as_missing_executables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    repo = _repo(tmp_path / "repo", [command])
    _only_on_path(monkeypatch, tmp_path / "bin", "make")

    result = environment.check_qa_executables(_context(repo))

    assert result.status == "ok"


def test_an_unreadable_project_json_is_skipped_with_a_pointer_to_its_own_check(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path / "repo", None)
    (repo / ".harness").mkdir()
    (repo / ".harness" / "project.json").write_text("{not json", encoding="utf-8")

    result = environment.check_qa_executables(_context(repo))

    assert result.status == "skipped"
    assert "files.project_json" in result.message


def test_a_cargo_manifest_only_inside_a_build_target_does_not_count_as_rust(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path / "repo", ["make lint"])
    vendored = repo / "native" / "target" / "package" / "Cargo.toml"
    vendored.parent.mkdir(parents=True)
    vendored.write_text("[package]\n", encoding="utf-8")
    _only_on_path(monkeypatch, tmp_path / "bin", "make")

    result = environment.check_c_linker(_context(repo))

    assert result.status == "skipped"


@pytest.mark.skipif(os.name == "nt", reason="a Windows runtime listens on a named pipe")
@pytest.mark.parametrize("xdg", [None, "relative/run"], ids=["unset", "relative"])
def test_without_an_absolute_xdg_runtime_dir_the_socket_lives_in_tmp_harness_uid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, xdg: str | None
) -> None:
    if sys.platform == "win32":
        pytest.skip("os.getuid is POSIX-only")
    repo = _repo(tmp_path / "repo", ["make lint"])
    if xdg is None:
        monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    else:
        monkeypatch.setenv("XDG_RUNTIME_DIR", xdg)
    monkeypatch.setenv("TMPDIR", "/" + "t" * 200)

    result = environment.check_runtime_socket_path(_context(repo))

    assert result.status == "ok"
    assert f"/tmp/harness-{os.getuid()}/" in result.message


@pytest.mark.skipif(os.name == "nt", reason="a Windows runtime listens on a named pipe")
@pytest.mark.parametrize(("socket_bytes", "status"), [(100, "ok"), (101, "warn")])
def test_the_socket_path_limit_is_100_bytes_inclusive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, socket_bytes: int, status: str
) -> None:
    repo = _repo(tmp_path / "repo", ["make lint"])
    # The socket name is "<16 hex repo id>.sock" (21 bytes) under "$XDG_RUNTIME_DIR/harness/".
    tail = len("/harness/") + 16 + len(".sock")
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/" + "d" * (socket_bytes - tail - 1))

    result = environment.check_runtime_socket_path(_context(repo))

    assert result.status == status
