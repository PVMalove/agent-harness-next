"""The one writer of a ticket's `status::*` label: `gh issue edit` on GitHub, `glab issue update`
with an explicit `--unlabel` on GitLab, and the `**Workflow:**` line of the ticket file in the
local `.scratch/` tracker. It also reads the state of a blocker the board could not resolve.

Every subprocess passes `status_command` first, so nothing but these label writes and state reads
can reach the tracker; a local write stays inside `.scratch/`, never follows a symlink and
replaces the file atomically."""

from __future__ import annotations

import json
import os
import re
import tempfile
from collections.abc import Callable
from pathlib import Path
from urllib.parse import quote

from ....health.process import run_tool
from ....health.project_tracker import ProjectTracker, resolve_project_tracker
from ..domain.task_board import TrackerTicket
from .task_board_tracker import Runner

TIMEOUT_SECONDS = 30.0
_NUMBER = re.compile(r"^#?(\d{1,9})$")
_STATUS = re.compile(r"^status::[a-z][a-z-]{0,40}$")
_WORKFLOW = re.compile(r"^\*\*Workflow:\*\*[^\n]*$", re.MULTILINE)
_H1 = re.compile(r"^# [^\n]*$", re.MULTILINE)


class StatusWriteError(Exception):
    """The tracker did not take the status change; nothing is known to be written."""


def _pairs(rest: list[str], allowed: dict[str, int]) -> bool:
    """`rest` is `flag value` pairs with status-label values, each flag at most its count."""
    if len(rest) % 2:
        return False
    seen = dict.fromkeys(allowed, 0)
    for flag, value in zip(rest[::2], rest[1::2], strict=True):
        if flag not in allowed or not _STATUS.match(value):
            return False
        seen[flag] += 1
    return all(seen[flag] <= limit for flag, limit in allowed.items() if limit)


def status_command(argv: list[str]) -> bool:
    """True only for the commands of a status change: one `status::*` label written by
    `gh issue edit` (with `--remove-label`s) or `glab issue update` (with `--unlabel`s), and the
    state read of one issue (`gh issue view --json state`, a GET `glab api` issue path)."""
    if len(argv) < 6 or not argv[3].isdigit():
        return argv[:2] == ["glab", "api"] and len(argv) == 3 and (
            re.fullmatch(r"projects/[^/\s?&-][^/\s?&]*/issues/\d{1,9}", argv[2]) is not None
        )
    head, repo_flag, rest = argv[:3], argv[4], argv[6:]
    if head == ["gh", "issue", "edit"] and repo_flag == "--repo":
        return _pairs(rest, {"--remove-label": 0, "--add-label": 1}) and (
            rest[::2].count("--add-label") == 1
        )
    if head == ["glab", "issue", "update"] and repo_flag == "-R":
        return _pairs(rest, {"--label": 1, "--unlabel": 0}) and rest[::2].count("--label") == 1
    if head == ["gh", "issue", "view"] and repo_flag == "--repo":
        return rest == ["--json", "state"]
    return False


class TrackerStatusWriter:
    """Writes the status label of the project's configured tracker."""

    def __init__(
        self,
        *,
        runner: Runner = run_tool,
        resolve: Callable[[Path], ProjectTracker] | None = None,
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        self._runner, self._timeout = runner, timeout
        self._resolve = resolve or (lambda repo: resolve_project_tracker(repo).effective)

    def _run(self, repo: Path, argv: list[str], env: dict[str, str] | None = None) -> str:
        if not status_command(argv):
            raise StatusWriteError("refused a command outside the status change")
        result = self._runner(argv, timeout=self._timeout, cwd=repo, env=env)
        if result is None:
            raise StatusWriteError(f"{argv[0]} is not installed or did not answer in time")
        code = getattr(result, "returncode", 1)
        out = str(getattr(result, "stdout", "") or "")
        if code != 0:
            err = str(getattr(result, "stderr", "") or "")
            raise StatusWriteError(f"{argv[0]}: {(err or out).strip() or f'exit {code}'}")
        return out

    @staticmethod
    def _remote(tracker: ProjectTracker) -> tuple[str, str]:
        if tracker.project is None or (tracker.type == "gitlab" and tracker.host is None):
            raise StatusWriteError(f"the {tracker.type} project is not configured")
        host = tracker.host or "github.com"
        return host, tracker.project

    @staticmethod
    def _number(ref: str) -> str:
        match = _NUMBER.match(ref.strip())
        if match is None:
            raise StatusWriteError(f"not a tracker issue: {ref}")
        return match.group(1)

    def write(
        self, repo: Path, ticket: TrackerTicket, remove: tuple[str, ...], add: str
    ) -> None:
        """Replace the ticket's status labels: remove `remove`, add `add`."""
        tracker = self._resolve(repo)
        if tracker.type == "local":
            _write_local(repo, ticket.ref, add)
            return
        number = self._number(ticket.ref)
        host, project = self._remote(tracker)
        if tracker.type == "gitlab":
            argv = ["glab", "issue", "update", number, "-R", f"https://{host}/{project}"]
            argv += ["--label", add]
            for label in remove:
                argv += ["--unlabel", label]
            self._run(repo, argv, {**os.environ, "GITLAB_HOST": host})
            return
        argv = ["gh", "issue", "edit", number, "--repo", f"{host}/{project}"]
        for label in remove:
            argv += ["--remove-label", label]
        self._run(repo, [*argv, "--add-label", add])

    def blocker_closed(self, repo: Path, ref: str) -> bool | None:
        """Whether the issue `ref` of a remote tracker is closed; None when it cannot be read."""
        tracker = self._resolve(repo)
        match = _NUMBER.match(ref.strip())
        if tracker.type == "local" or match is None:
            return None
        try:
            host, project = self._remote(tracker)
            if tracker.type == "gitlab":
                out = self._run(
                    repo,
                    ["glab", "api", f"projects/{quote(project, safe='')}/issues/{match[1]}"],
                    {**os.environ, "GITLAB_HOST": host},
                )
            else:
                out = self._run(
                    repo,
                    ["gh", "issue", "view", match[1], "--repo", f"{host}/{project}",
                     "--json", "state"],
                )  # fmt: skip
            state = json.loads(out).get("state")
        except (StatusWriteError, ValueError, AttributeError):
            return None
        if not isinstance(state, str):
            return None
        return state.casefold() == "closed"


def _write_local(repo: Path, ref: str, add: str) -> None:
    root = repo.resolve() / ".scratch"
    path = repo / ref
    try:
        inside = (
            not path.is_symlink()
            and path.is_file()
            and root in path.resolve().parents
            and not root.is_symlink()
        )
        if not inside:
            raise StatusWriteError(f"not a ticket file of the local tracker: {ref}")
        text = path.read_text(encoding="utf-8")
        line = f"**Workflow:** {add}"
        if _WORKFLOW.search(text):
            text = _WORKFLOW.sub(lambda _m: line, text, count=1)
        elif (title := _H1.search(text)) is not None:
            text = f"{text[: title.end()]}\n{line}{text[title.end() :]}"
        else:
            text = f"{line}\n{text}"
        handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=".status-", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="") as out:
                out.write(text)
            os.chmod(temporary, path.stat().st_mode & 0o7777)
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
    except OSError as exc:
        raise StatusWriteError(f"local write failed: {exc}") from exc
