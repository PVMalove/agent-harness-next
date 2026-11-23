"""Codex can propose one edit through either route without running the model in CI."""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from harness.health import codex_test_author, isolated_runner, test_author


@pytest.mark.parametrize("route", ["short", "brief", "outside", "scope", "no-isolation"])
def test_codex_proposal_stays_in_scope_and_runs_one_test(
    route: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path.resolve()
    subprocess.run(["git", "init", "-q", "--template=", str(repo)], check=True)
    (repo / "tests").mkdir()
    (repo / ".harness").mkdir()
    (repo / ".harness/project.json").write_text(json.dumps({
        "test_paths": ["tests/**"],
        "test_runner": {"command": ["python3", "-m", "pytest", "{test_id}"]},
        "test_author": {"runtime": "codex", "model": "short-model", "effort": "medium"},
    }), encoding="utf-8")
    prompt = repo / "prompt.txt"
    prompt.write_text("One behavioral requirement", encoding="utf-8")
    args = ["run", "--repo", str(repo), "--prompt-file", str(prompt)]
    if route in {"brief", "scope"}:
        brief = repo / "brief.json"
        brief.write_text(json.dumps({
            "role": "developer", "access": "write", "worktree": str(repo),
            "resolved_runtime": "codex", "resolved_model": "developer-model",
            "resolved_effort": "high", "allowed_tools": ["Agent(test-author)"],
            "coordinator_approval": {"approved_by": "fixture", "approved_at": "2026-11-22T00:00:00Z"},
            "write_paths": ["tests/other/**"] if route == "scope" else ["tests/**"],
            "allowed_paths": ["tests/**"],
        }), encoding="utf-8")
        args.extend(["--brief", str(brief)])

    path = "outside/test_behavior.py" if route == "outside" else "tests/test_behavior.py"
    node = path + "::test_behavior"
    content = "def test_behavior():\n    assert True\n"
    proposal = {"path": path, "before": "", "after": content, "test_id": node}
    launched: list[str] = []
    tested: list[str] = []

    def fake_command(
        binary: str, selection: Mapping[str, object], schema: Path, response: Path
    ) -> list[str]:
        launched.append(str(selection["model"]))
        return [
            sys.executable, "-c",
            "import pathlib, sys; sys.stdin.read(); pathlib.Path(sys.argv[1]).write_text(sys.argv[2])",
            str(response), json.dumps(proposal),
        ]

    def probe(checkout: Path, *, readonly_tests: bool) -> str | None:
        assert checkout == repo and readonly_tests
        return "bwrap_missing" if route == "no-isolation" else None

    def run(checkout: Path, test_id: str, *, readonly_tests: bool) -> isolated_runner.Outcome:
        assert checkout == repo and readonly_tests
        assert (repo / path).read_text(encoding="utf-8") == content
        tested.append(test_id)
        return isolated_runner.Outcome(test_id, "passed", "passed", exit_code=0)

    monkeypatch.setattr(shutil, "which", lambda name: name)
    monkeypatch.setattr(codex_test_author, "_command", fake_command)
    monkeypatch.setattr(isolated_runner, "probe", probe)
    monkeypatch.setattr(isolated_runner, "run_test", run)
    status = test_author.main(args)
    result = json.loads(capsys.readouterr().out)

    if route in {"short", "brief"}:
        assert status == 0
        assert result["result"] == "passed"
        assert tested == [node]
        assert launched == ["developer-model" if route == "brief" else "short-model"]
    else:
        reason = "isolation_unavailable" if route == "no-isolation" else "write_outside_test_paths"
        assert status == 3
        assert result == {"status": "disabled", "reason": reason}
        assert not tested and not (repo / path).exists()
        if route == "no-isolation":
            assert not launched
