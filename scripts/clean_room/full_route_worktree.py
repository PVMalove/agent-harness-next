"""Полный маршрут `/implement`: тест-автор обслуживает worker checkout или остаётся выключенным.

In-process preflight отклоняет другой checkout. External developer использует собственный
установленный worker checkout с точным trust: guard разрешает только его test_paths, runner
проверяет его код, а основной checkout остаётся неизменным. Сценарий учитывает общее хранилище
логов linked worktree; по флагу live-пробы проверяет настоящий вызов developer → test-author.
"""

from __future__ import annotations

import hashlib
import os
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

from scripts.clean_room.claude_probe import claude_environment, project_environment
from scripts.clean_room.fast_implement_route import ShortRoute
from scripts.clean_room.isolated_test_runner import (
    SHELL,
    _assert_denied,
    _direct_execute,
    _guard,
    _hook,
    _install,
    _json_line,
    _preflight,
    _run_hook,
    _test_author_payload,
    _verify_guard_decisions,
    _verify_red_evidence,
)
from scripts.clean_room.support import run_step
from scripts.clean_room.test_author_cycle import Scenario, _module, verify_cycle
from scripts.clean_room.isolated_test_runner import _runner_execute

MISMATCH = {"status": "disabled", "reason": "checkout_mismatch"}
GIT_IDENTITY = [
    "-c",
    "user.name=clean-room",
    "-c",
    "user.email=clean-room@example.invalid",
]


def _fail(label: str, message: str) -> None:
    sys.exit(f"full-route worktree {label}: {message}")


def effective_answer(
    transport: str, run_preflight: Callable[[], dict[str, object]]
) -> dict[str, object]:
    """Both transports check their served checkout; unknown transports fail closed."""
    if transport not in {"external", "in-process"}:
        return {"status": "disabled", "reason": "transport_unsupported"}
    return run_preflight()


def snapshot(project: Path) -> dict[str, str]:
    """Digests of every file under `src/` and `tests/`, without bytecode caches."""
    return {
        path.relative_to(project).as_posix(): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for directory in ("src", "tests")
        for path in sorted((project / directory).rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def ensure_unchanged(label: str, project: Path, before: dict[str, str]) -> None:
    """Fail when a source or test file of the checkout changed, appeared or disappeared."""
    after = snapshot(project)
    if after != before:
        changed = sorted(set(after.items()) ^ set(before.items()))
        _fail(label, f"the main checkout changed: {[name for name, _ in changed]}")


def ordinary_in_worktree(
    main: Path, worktree: Path, answer: dict[str, object]
) -> ShortRoute:
    """Ordinary TDD in the worker checkout; the main checkout must stay byte-identical."""
    before = snapshot(main)
    scenario = Scenario(worktree, _direct_execute(worktree))
    module = _module("worker")
    route = ShortRoute(scenario, answer)
    test_id = route.begin(module, seam_agreed=True, script=[])
    route.finish(module, test_id)
    for name in (f"src/{module}.py", f"tests/{module}.py"):
        if not (worktree / name).is_file():
            _fail("ordinary route", f"{name} did not land in the worker checkout")
        (worktree / name).unlink()
    ensure_unchanged("ordinary route", main, before)
    return route


def _preflight_with(
    project: Path, *arguments: str, env: dict[str, str]
) -> dict[str, object]:
    label = "test-author preflight"
    command = [
        SHELL,
        str(project / ".claude" / "hooks" / "test-author-preflight.sh"),
        *arguments,
    ]
    environment = project_environment(project, env)
    return _json_line(label, _run_hook(label, command, project, env=environment))


def _git(project: Path, *arguments: str) -> str:
    result = run_step(
        ["git", *GIT_IDENTITY, *arguments],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
    )
    return str(result.stdout)


def _add_worktree(project: Path, worktree: Path) -> None:
    _git(project, "add", "src", "tests")
    _git(project, "commit", "-q", "-m", "scenario files")
    _git(
        project,
        "worktree",
        "add",
        "-q",
        "-b",
        "feature/issue-1-scenario",
        str(worktree),
    )


def run(ctx: SimpleNamespace) -> None:
    """Установленный проект и отдельный worktree: preflight, обычный TDD, guard, транспорты.

    Читает из контекста: `test_root`.
    """
    project = _install(ctx.test_root / "full_route_project")
    # Fixture setup: the main implementation differs before any developer/author work.
    (project / "src/calc.py").write_text(
        "def add(a, b):\n    return 99\n", encoding="utf-8"
    )
    worktree = ctx.test_root / "full_route_worktree"
    _add_worktree(project, worktree)
    environment = claude_environment(project)
    main_status = _git(project, "status", "--porcelain")
    main_snapshot = snapshot(project)

    answer = _preflight_with(project, "--worktree", str(worktree), env=environment)
    if answer != MISMATCH:
        _fail("mismatch", f"preflight answered {answer}, expected {MISMATCH}")

    served = _preflight(project, env=environment)
    matching = _preflight_with(project, "--worktree", str(project), env=environment)
    if matching != served:
        _fail(
            "matching worktree", f"{matching} differs from the zero-argument {served}"
        )

    route = ordinary_in_worktree(project, worktree, answer)
    if (route.route, route.reason) != ("ordinary", "checkout_mismatch"):
        _fail("ordinary route", f"unexpected route {route.route}: {route.reason!r}")

    leak = worktree / "tests" / "cyc_leak.py"
    _assert_denied(
        _guard(project, _test_author_payload("Write", {"file_path": str(leak)}))
    )

    verify_external_worktree(project, worktree)

    ensure_unchanged("scenario end", project, main_snapshot)
    if _git(project, "status", "--porcelain") != main_status:
        _fail("scenario end", "the main checkout status changed")
    print("full-route worktree: preflight, fallback and guard verified", flush=True)


def verify_external_worktree(main: Path, worktree: Path) -> None:
    """An external developer serves the installed worker, with exact-path trust and real runner."""
    before = snapshot(main)
    _install(worktree, existing_checkout=True)
    for trust in ("not-accepted", "other-project", "no-file"):
        environment = claude_environment(worktree, trust=trust)
        answer = _preflight_with(worktree, "--worktree", str(worktree), env=environment)
        if answer != {"status": "disabled", "reason": "project_untrusted"}:
            _fail("external trust", f"unexpected answer {answer}")
    environment = claude_environment(worktree)
    answer = effective_answer(
        "external",
        lambda: _preflight_with(worktree, "--worktree", str(worktree), env=environment),
    )
    if answer == {"status": "ok"}:
        _verify_guard_decisions(worktree)
        _verify_red_evidence(worktree)
        verify_cycle(worktree, _runner_execute(worktree))
        from scripts.clean_room.claude_probe import verify_worker_cycle

        verify_worker_cycle(main, worktree)
    elif os.environ.get("HARNESS_REQUIRE_TEST_SANDBOX") == "1":
        _fail("external isolation", f"preflight refused: {answer}")
    else:
        if _hook(worktree, "--probe").get("status") == "ok":
            _fail("external preflight", f"unexpected refusal: {answer}")
        print(
            f"full-route worktree: protected author unavailable ({answer.get('reason')})",
            flush=True,
        )
    ensure_unchanged("external end", main, before)
