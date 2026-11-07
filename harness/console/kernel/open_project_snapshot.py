"""The «Открыть проект» facts of the one project a console server serves: its installation state
(the plan target and the blockers of every capability) and the candidate projects, each with the
command that starts the Web console there. The server never switches its project: another project
gets its own server. `OpenProjectFacts.to_payload` and `OpenProjectFacts.from_payload` are the
wire codec of an `open_project.snapshot` reply; reading it back is strict, so a reply off the
schema is a `ValueError`."""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from .project_target import ProjectTarget

# `harness console --web <path>`: the Web console of another project, started by its own server.
OPEN_ARGV = ("harness", "console", "--web")
Action = Literal["init", "adopt", "update"]
ACTIONS: tuple[Action, ...] = ("init", "adopt", "update")

_FIELDS = frozenset({"repo", "target", "error", "blockers", "candidates"})
_TARGET_FIELDS = frozenset({"repo", "action", "capabilities", "conflicts", "found"})
_CANDIDATE_FIELDS = frozenset({"path", "installed", "current", "command"})


def open_command(path: str) -> str:
    """The command line that starts the Web console in the project at `path`."""
    argv = [*OPEN_ARGV, path]
    return subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)


@dataclass(frozen=True)
class Candidate:
    """A project the operator may open: its path, whether Harness is installed there and whether
    it is the project this server serves."""

    path: str
    installed: bool
    current: bool

    @property
    def command(self) -> str:
        return open_command(self.path)


@dataclass(frozen=True)
class OpenProjectFacts:
    """What «Открыть проект» shows for the served project `repo`: `target` is None, with the
    reason in `error`, when the project cannot be installed into (not a Git project, a broken
    lock); `blockers` lists, per capability, the paths that stop its installation."""

    repo: str
    target: ProjectTarget | None
    error: str
    blockers: dict[str, tuple[str, ...]]
    candidates: tuple[Candidate, ...]

    def to_payload(self) -> dict[str, object]:
        """The JSON object of an `open_project.snapshot` reply."""
        target = self.target
        return {
            "repo": self.repo,
            "target": None
            if target is None
            else {
                "repo": str(target.repo),
                "action": target.action,
                "capabilities": list(target.capabilities),
                "conflicts": list(target.conflicts),
                "found": list(target.found),
            },
            "error": self.error,
            "blockers": {name: list(paths) for name, paths in self.blockers.items()},
            "candidates": [
                {
                    "path": item.path,
                    "installed": item.installed,
                    "current": item.current,
                    "command": item.command,
                }
                for item in self.candidates
            ],
        }

    @classmethod
    def from_payload(cls, payload: object) -> OpenProjectFacts:
        """The facts of an `open_project.snapshot` reply; anything off the schema is a
        `ValueError`."""
        found = _object(payload, _FIELDS)
        repo, error = found["repo"], found["error"]
        if not isinstance(repo, str) or not isinstance(error, str):
            raise ValueError("open project repo or error")
        blockers = _object(found["blockers"])
        return cls(
            repo,
            None if found["target"] is None else _target(found["target"]),
            error,
            {name: _strings(paths) for name, paths in blockers.items()},
            tuple(_candidate(item) for item in _list(found["candidates"])),
        )


def _object(value: object, fields: frozenset[str] | None = None) -> dict[str, object]:
    if not isinstance(value, dict) or (fields is not None and set(value) != fields):
        raise ValueError("open project snapshot off the schema")
    return cast(dict[str, object], value)


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise ValueError("open project snapshot list")
    return cast(list[object], value)


def _strings(value: object) -> tuple[str, ...]:
    items = _list(value)
    if not all(isinstance(item, str) for item in items):
        raise ValueError("open project snapshot strings")
    return tuple(cast(list[str], items))


def _target(value: object) -> ProjectTarget:
    found = _object(value, _TARGET_FIELDS)
    repo, action = found["repo"], found["action"]
    if not isinstance(repo, str) or action not in ACTIONS:
        raise ValueError("open project target")
    return ProjectTarget(
        Path(repo),
        action,
        _strings(found["capabilities"]),
        _strings(found["conflicts"]),
        _strings(found["found"]),
    )


def _candidate(value: object) -> Candidate:
    found = _object(value, _CANDIDATE_FIELDS)
    path, installed, current = found["path"], found["installed"], found["current"]
    if not (
        isinstance(path, str)
        and isinstance(installed, bool)
        and isinstance(current, bool)
        and isinstance(found["command"], str)
    ):
        raise ValueError("open project candidate")
    return Candidate(path, installed, current)
