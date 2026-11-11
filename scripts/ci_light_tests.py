#!/usr/bin/env python3
"""The tests of the light CI job (issue #937): the tests of the pull request's own diff, nothing wider.

A pull request into an ``integration/*`` branch runs ``verify-light`` instead of the full suite
(ADR 0016, ADR 0023). This script selects its tests with ``ticket_diff_selection`` (issue #935):
the Python test modules and the ``cargo test`` targets that the diff itself adds or changes. It
never widens the selection to related tests or to the full suite; a diff without tests selects
nothing and passes. Only the full path (a pull request into the default branch, a push to it)
runs the whole suite, and only that evidence confirms a pair that requires the full selection.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

ROOT = Path(__file__).resolve().parent.parent
# Bound for the helper command (``git merge-base``); the selected tests themselves are unbounded.
HELPER_TIMEOUT_SECONDS = 300
# ``pytest`` reports "no tests collected" as exit code 5.
PYTEST_NO_TESTS_COLLECTED = 5

if TYPE_CHECKING:
    from harness.repo_map.change_impact import TicketDiffSelection

Runner = Callable[[Sequence[str], Path], int]


def merge_base(repo: Path, base: str, head: str) -> str:
    """The commit where the pull request branched off ``base``: the diff is the PR's own work.

    The base branch may have moved since the branch was cut, so a plain ``base..head`` diff would
    list the changes of the base branch too. A missing merge-base fails the job, never widens it."""
    try:
        done = subprocess.run(
            ["git", "-C", str(repo), "merge-base", base, head],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=HELPER_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        sys.exit(f"ci-light-tests: git merge-base failed: {exc}")
    found = done.stdout.strip()
    if done.returncode != 0 or not found:
        sys.exit(f"ci-light-tests: no merge-base of {base} and {head}")
    return found


def select(repo: Path, base: str, head: str) -> TicketDiffSelection:
    """The ``TicketDiffSelection`` of the pull request ``base..head``, measured from the merge-base."""
    sys.path.insert(0, str(ROOT))
    from harness.repo_map.change_impact import ticket_diff_selection

    return ticket_diff_selection(repo, merge_base(repo, base, head), head)


def commands(selection: TicketDiffSelection, python: str) -> list[list[str]]:
    """The commands that run exactly ``selection``: one pytest run, then one cargo run per target.

    ``--locked`` keeps Cargo.lock as committed, as every other cargo step of the workflow does."""
    found: list[list[str]] = []
    if selection.python_tests:
        found.append([python, "-m", "pytest", "-q", *selection.python_tests])
    for target in selection.cargo_targets:
        argv = target.argv()
        found.append([*argv[:2], "--locked", *argv[2:]])
    return found


def _run(command: Sequence[str], cwd: Path) -> int:
    return subprocess.run(list(command), cwd=cwd, check=False).returncode


def _is_pytest(command: Sequence[str]) -> bool:
    return list(command[1:3]) == ["-m", "pytest"]


def execute(selected: Sequence[Sequence[str]], cwd: Path, runner: Runner = _run) -> int:
    """Run every command (one failure does not hide the others); the first failing code wins.

    A pytest run that collects nothing is a notice: the default run deselects the ``docker_smoke``
    and ``podman_smoke`` markers, so a file made only of those has no test here. Any other command
    that fails, fails the job."""
    status = 0
    for command in selected:
        print(f"ci-light-tests: $ {' '.join(command)}", flush=True)
        code = runner(command, cwd)
        if code == PYTEST_NO_TESTS_COLLECTED and _is_pytest(command):
            print("ci-light-tests: no test was collected from the selected files")
            code = 0
        if code != 0 and status == 0:
            status = code
    return status


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0] if __doc__ else None
    )
    parser.add_argument(
        "--base", required=True, help="the base commit of the pull request"
    )
    parser.add_argument(
        "--head", default="HEAD", help="the head commit of the pull request"
    )
    parser.add_argument(
        "--repo", type=Path, default=ROOT, help="the checkout to run the tests in"
    )
    args = parser.parse_args(argv)
    selection = select(args.repo, args.base, args.head)
    if selection.empty:
        print("ci-light-tests: no tests in diff; nothing to run")
        return 0
    print(
        "ci-light-tests: selected "
        f"{len(selection.python_tests)} Python test file(s) and "
        f"{len(selection.cargo_targets)} cargo target(s) of the pull request's own diff"
    )
    return execute(commands(selection, sys.executable), args.repo)


if __name__ == "__main__":
    sys.exit(main())
