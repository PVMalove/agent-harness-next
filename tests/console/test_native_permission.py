"""Native permission answers as console decision commands: field checks, argv and the script entry.

The script's call into the coordinator is replaced by a fake; no test reaches a real ledger or a
live runtime.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from harness.console.backend.infrastructure import native_permission
from harness.console.backend.infrastructure.native_permission import (
    NATIVE_PERMISSION_COMMANDS,
)
from harness.console.kernel.catalog import Reversibility, process_argv
from harness.orchestration.core.utils import CoordinatorError
from harness.orchestration.workflow import delivery

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "harness" / "console" / "backend" / "infrastructure" / "native_permission.py"
SHA = "0123456789abcdef" * 4
DISPATCH = "dispatch-3ab1639f-18a3-4856-93f3-511c5b1c61dd"
VALUES = {"dispatch": DISPATCH, "request_id": "request-1", "request_sha256": SHA}
ENTRIES = {entry.key: entry for entry in NATIVE_PERMISSION_COMMANDS}


def test_allow_and_deny_are_confirmed_external_mutations() -> None:
    assert set(ENTRIES) == {"native-permission-allow", "native-permission-deny"}
    for entry in NATIVE_PERMISSION_COMMANDS:
        assert entry.reversibility is Reversibility.EXTERNAL_CHANGE
        assert entry.needs_confirmation
        assert not entry.read_only
        assert entry.title


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"dispatch": DISPATCH, "request_id": "request-1"},
        {**VALUES, "extra": "x"},
        {**VALUES, "request_id": "  "},
        {**VALUES, "request_sha256": SHA.upper()},
        {**VALUES, "request_sha256": SHA[:-1]},
        {**VALUES, "dispatch": "batch-1"},
        {**VALUES, "dispatch": "dispatch-x; rm"},
        {**VALUES, "request_id": "r" * 1000},
    ],
)
def test_accepts_only_the_exact_well_formed_fields(values: dict[str, str]) -> None:
    assert not ENTRIES["native-permission-allow"].accepts(values)


def test_accepts_a_well_formed_answer() -> None:
    assert ENTRIES["native-permission-deny"].accepts(VALUES)
    # The runtime stages request ids of up to 256 characters.
    assert ENTRIES["native-permission-deny"].accepts(
        {**VALUES, "request_id": "r" * 256}
    )
    assert not ENTRIES["native-permission-deny"].accepts(
        {**VALUES, "request_id": "r" * 257}
    )


@pytest.mark.parametrize(
    ("key", "flag"),
    [("native-permission-allow", "--allow"), ("native-permission-deny", "--deny")],
)
def test_cli_argv_runs_this_script_for_the_repository(
    tmp_path: Path, key: str, flag: str
) -> None:
    argv = ENTRIES[key].cli_argv(tmp_path, VALUES)
    assert argv == [
        "python",
        str(SCRIPT),
        "--repo",
        str(tmp_path),
        "--dispatch",
        DISPATCH,
        "--request-id",
        "request-1",
        "--request-sha256",
        SHA,
        flag,
    ]
    assert process_argv(argv, tmp_path)[0] == sys.executable
    assert ENTRIES[key].cli_line(tmp_path, VALUES).endswith(flag)


def test_available_only_with_the_project_coordinator(tmp_path: Path) -> None:
    entry = ENTRIES["native-permission-allow"]
    assert not entry.available(tmp_path)
    script = tmp_path / ".harness" / "orchestration" / "coordinator.py"
    script.parent.mkdir(parents=True)
    script.write_text("")
    assert entry.available(tmp_path)


@pytest.mark.parametrize(("flag", "allow"), [("--allow", True), ("--deny", False)])
def test_main_answers_through_the_coordinator_function(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    flag: str,
    allow: bool,
) -> None:
    calls: list[tuple[object, ...]] = []

    def fake(
        repo: Path, dispatch: str, request_id: str, sha: str, *, allow: bool
    ) -> dict[str, object]:
        calls.append((repo, dispatch, request_id, sha, allow))
        return {"request_id": request_id, "decision": "allow" if allow else "deny"}

    monkeypatch.setattr(delivery, "respond_native_permission", fake)
    argv = ENTRIES["native-permission-allow"].cli_argv(tmp_path, VALUES)[2:-1]
    code = native_permission.main([*argv, flag])
    assert code == 0
    assert calls == [(tmp_path, DISPATCH, "request-1", SHA, allow)]
    printed = json.loads(capsys.readouterr().out)
    assert printed["decision"] == ("allow" if allow else "deny")


def test_main_reports_a_refused_answer_without_a_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def refuse(*_: object, **__: object) -> dict[str, object]:
        raise CoordinatorError("request changed", remedy="read the request again")

    monkeypatch.setattr(delivery, "respond_native_permission", refuse)
    argv = ENTRIES["native-permission-deny"].cli_argv(tmp_path, VALUES)[2:]
    assert native_permission.main(argv) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "request changed" in captured.err
    assert "read the request again" in captured.err
    assert "Traceback" not in captured.err


def test_main_requires_exactly_one_answer(tmp_path: Path) -> None:
    argv = ENTRIES["native-permission-allow"].cli_argv(tmp_path, VALUES)[2:-1]
    with pytest.raises(SystemExit):
        native_permission.main(argv)
    with pytest.raises(SystemExit):
        native_permission.main([*argv, "--allow", "--deny"])


