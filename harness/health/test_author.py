"""Resolve the test author's executor from an approved developer or project configuration."""

from __future__ import annotations

from collections.abc import Mapping
import argparse
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import subprocess
from subprocess import run as execute
import sys
from pathlib import Path

# Installed stdlib entry point: do not import the target project's Python packages.
if __package__ in (None, ""):
    for name, path in (
        ("harness", Path(__file__).resolve().parents[1]),
        ("harness.health", Path(__file__).resolve().parent),
    ):
        spec = importlib.machinery.ModuleSpec(name, None, is_package=True)
        spec.submodule_search_locations = [str(path)]
        sys.modules[name] = importlib.util.module_from_spec(spec)

from harness.configuration import (
    EFFORT_LEVELS,
    MODEL_ID,
    parse_object,
    read_config_file,
    reject_secrets,
)

FIELDS = frozenset({"runtime", "model", "effort"})
RUNTIME_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
# These are protected runtime adapters, not executor defaults. Selection happens first.
ADAPTERS = {"claude": ".claude/hooks/test-author-preflight.sh"}
PREFLIGHT_REASONS = frozenset(
    {
        "checkout_mismatch",
        "project_untrusted",
        "claude_code_unsupported",
        "agent_missing",
        "scoped_hook_unsupported",
        "test_paths_missing",
        "test_runner_missing",
        "config_invalid",
        "write_zone_rejected",
        "guard_hook_unavailable",
        "isolation_unavailable",
        "runner_unavailable",
        "test_author_missing",
        "test_author_config_invalid",
        "runtime_unsupported",
        "orchestration_unavailable",
        "selector_unavailable",
    }
)


def preflight_reason(result: subprocess.CompletedProcess[str]) -> str:
    if result.returncode != 0 or len(result.stdout) > 512:
        return "preflight_failed"
    try:
        answer = json.loads(result.stdout)
    except (ValueError, RecursionError):
        return "preflight_failed"
    if answer == {"status": "ok"}:
        return "ok"
    if isinstance(answer, dict) and answer.get("status") == "disabled":
        reason = answer.get("reason")
        if isinstance(reason, str) and reason in PREFLIGHT_REASONS:
            return reason
    return "preflight_failed"


def profile_problems(value: object) -> list[str]:
    """The schema and runtime validator share this exact executor contract."""
    if not isinstance(value, dict) or set(value) != FIELDS:
        return ["test_author must contain exactly runtime, model and effort"]
    runtime, model, effort = value["runtime"], value["model"], value["effort"]
    if not isinstance(runtime, str) or RUNTIME_ID.fullmatch(runtime) is None:
        return ["test_author.runtime must be a runtime ID"]
    if not isinstance(model, str) or MODEL_ID.fullmatch(model) is None:
        return ["test_author.model must be a CLI model ID or alias without spaces"]
    if not isinstance(effort, str) or effort not in EFFORT_LEVELS:
        return ["test_author.effort must be a configured effort level"]
    try:
        reject_secrets(value)
    except ValueError:
        return ["test_author must not contain secrets"]
    return []


class AuthorUnavailable(Exception):
    """A fixed, sanitized reason, without authored config values."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def select_author(
    project: Mapping[str, object], *, developer: Mapping[str, object] | None = None
) -> dict[str, object]:
    """Select an executor without a runtime or model default."""
    value: object
    if developer is not None:
        if developer.get("role") != "developer":
            raise AuthorUnavailable("test_author_config_invalid")
        value = {field: developer.get(f"resolved_{field}") for field in FIELDS}
        source = "developer"
    else:
        if "test_author" not in project:
            raise AuthorUnavailable("test_author_missing")
        value = project["test_author"]
        source = "project"
    if profile_problems(value):
        raise AuthorUnavailable("test_author_config_invalid")
    assert isinstance(value, dict)
    return {**value, "source": source}


def _object(path: Path) -> dict[str, object]:
    try:
        raw = read_config_file(path)
        value = {} if raw is None else parse_object(raw)
        reject_secrets(value)
        return value
    except (OSError, ValueError, RecursionError):
        raise AuthorUnavailable("test_author_config_invalid") from None


def read_author(
    repo: Path, *, brief: Path | None = None, planned: bool = False
) -> dict[str, object]:
    """Use an immutable brief for work; planned settings are only for Health/probe diagnostics."""
    project = _object(repo / ".harness/project.json")
    if brief is not None:
        return select_author(project, developer=_object(brief))
    if planned:
        orchestration = _object(repo / ".harness/orchestration.json")
        plans = orchestration.get("assignment_plans")
        if isinstance(plans, dict) and "developer" in plans:
            try:
                from harness.orchestration.contract import (
                    ContractError,
                    resolve_runtime_name,
                )
            except ImportError:
                raise AuthorUnavailable("orchestration_unavailable") from None
            plan = plans["developer"]
            if not isinstance(plan, dict):
                raise AuthorUnavailable("test_author_config_invalid")
            try:
                runtime = resolve_runtime_name(plan, None)
            except ContractError:
                raise AuthorUnavailable("test_author_config_invalid") from None
            runtimes = plan.get("runtimes")
            value = runtimes.get(runtime) if isinstance(runtimes, dict) else None
            if not isinstance(value, dict):
                raise AuthorUnavailable("test_author_config_invalid")
            selection = select_author(
                project,
                developer={
                    "role": "developer",
                    "resolved_runtime": runtime,
                    "resolved_model": value.get("model"),
                    "resolved_effort": value.get("effort"),
                },
            )
            selection["source"] = "orchestration.developer (planned)"
            return selection
    return select_author(project)


def adapter_for(selection: Mapping[str, object]) -> str:
    runtime = selection.get("runtime")
    if not isinstance(runtime, str) or runtime not in ADAPTERS:
        raise AuthorUnavailable("runtime_unsupported")
    return ADAPTERS[runtime]


def preflight_author(
    repo: Path,
    selection: Mapping[str, object],
    *,
    brief: Path | None = None,
    planned: bool = False,
) -> None:
    """Dispatch readiness to the selected protected adapter, preserving sanitized refusals."""
    preflight = adapter_for(selection)
    bash = shutil.which("bash")
    if bash is None:
        raise AuthorUnavailable("runner_unavailable")
    context = ["--brief", str(brief)] if brief else ["--planned"] if planned else []
    env = dict(os.environ)
    if brief is not None:
        # A full-route native Agent serves its parent's checkout. Never manufacture that
        # identity as Health (diagnostics) or the short external launcher may do.
        identity = env.get("CLAUDE_PROJECT_DIR")
        if not identity or Path(identity).resolve() != repo:
            raise AuthorUnavailable("checkout_mismatch")
    else:
        env["CLAUDE_PROJECT_DIR"] = str(repo)
    try:
        checked = execute(
            [bash, str(repo / preflight), "--worktree", str(repo), *context],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=135,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise AuthorUnavailable("preflight_failed") from None
    reason = preflight_reason(checked)
    if reason != "ok":
        raise AuthorUnavailable(reason)


def run_author(
    repo: Path,
    selection: Mapping[str, object],
    prompt: str,
    *,
    brief: Path | None = None,
) -> int:
    """Run the selected protected adapter; unavailable adapters never fall back to another CLI."""
    if profile_problems({key: selection.get(key) for key in FIELDS}):
        raise AuthorUnavailable("test_author_config_invalid")
    adapter_for(selection)
    binary = shutil.which(str(selection["runtime"]))
    if binary is None:
        raise AuthorUnavailable("runtime_unavailable")
    preflight_author(repo, selection, brief=brief)
    from harness.storage import storage_path

    try:
        result = execute(
            [
                binary,
                "--print",
                "--agent",
                "test-author",
                "--model",
                str(selection["model"]),
                "--effort",
                str(selection["effort"]),
                "--permission-mode",
                "dontAsk",
                "--allowed-tools",
                "Read,Write,Edit,Bash,Grep,Glob",
                "--add-dir",
                str(storage_path(repo, "runs")),
                "--no-session-persistence",
            ],
            input=prompt,
            text=True,
            cwd=repo,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo)},
            timeout=240,
            check=False,
        )
        return result.returncode
    except (OSError, subprocess.TimeoutExpired):
        raise AuthorUnavailable("author_unavailable") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("resolve", "check", "preflight", "run"))
    parser.add_argument("--repo", type=Path, required=True)
    context = parser.add_mutually_exclusive_group()
    context.add_argument("--brief", type=Path)
    context.add_argument("--planned", action="store_true")
    parser.add_argument("--prompt-file", type=Path)
    args = parser.parse_args(argv)
    try:
        repo = args.repo.resolve()
        project = _object(repo / ".harness/project.json")
        for field in ("test_paths", "test_runner"):
            if field not in project:
                raise AuthorUnavailable(f"{field}_missing")
        if args.action == "run" and args.planned:
            raise AuthorUnavailable("test_author_config_invalid")
        selection = read_author(repo, brief=args.brief, planned=args.planned)
        if args.action == "resolve":
            print(json.dumps(selection, separators=(",", ":")))
            return 0
        adapter_for(selection)
        if args.action == "preflight":
            preflight_author(repo, selection, brief=args.brief, planned=args.planned)
        if args.action in {"check", "preflight"}:
            print('{"status":"ok"}')
            return 0
        if args.prompt_file is None:
            raise AuthorUnavailable("prompt_missing")
        try:
            prompt = args.prompt_file.read_text(encoding="utf-8")
        except (OSError, ValueError):
            raise AuthorUnavailable("prompt_unavailable") from None
        return run_author(repo, selection, prompt, brief=args.brief)
    except AuthorUnavailable as exc:
        print(
            json.dumps(
                {"status": "disabled", "reason": exc.reason}, separators=(",", ":")
            )
        )
        return 3 if args.action == "run" else 0


if __name__ == "__main__":
    raise SystemExit(main())
