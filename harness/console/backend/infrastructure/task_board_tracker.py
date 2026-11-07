"""The read-only tracker reader of the task board: open specs and their sub-tickets from GitHub
(`gh api graphql`, `gh pr list`), GitLab (`glab api` GET pages) or the local `.scratch/` files.

Every subprocess passes `read_only` first, so a collect can never change the tracker; the local
reader only opens files for reading. One collect has one deadline shared by all its commands."""

from __future__ import annotations

import json
import os
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from ....health.process import run_tool
from ....health.project_tracker import ProjectTracker, resolve_project_tracker
from ....reporting.delivery_stats import GLAB_AUTH_FAILURE, ticket_of_branch
from ..application.ports import SpecNotFound, TrackerUnavailable
from ..domain.task_board import (
    BODY_READ_BYTES,
    MAX_SPECS,
    BlockerFact,
    PullRef,
    SpecList,
    SpecTickets,
    TrackerSpec,
    TrackerTicket,
    parse_body,
)
from .clock import monotonic

DEADLINE_SECONDS = 20.0
_SPEC_PAGES = 10
_GITLAB_ISSUE_PAGES = 20
_GITLAB_MR_PAGES = 5
_PER_PAGE = 100
_WRITE_FLAGS = frozenset(
    {"--method", "-X", "-f", "-F", "--field", "--raw-field", "--input"}
)
_PARENT = re.compile(r"^## Parent: #(\d+)\b", re.MULTILINE)
_LOCAL_TICKET = re.compile(r"^(\d+)-.*\.md$")
# Local files are untrusted text: a field name never spans lines and the title has one
# quantifier over its spaces, so a long whitespace run is read in linear time.
_LOCAL_FIELD = re.compile(r"^\*\*([^*\n]+?):\*\*\s*(\S*)", re.MULTILINE)
_TITLE = re.compile(r"^# +(.+)$", re.MULTILINE)
_SPEC_REF = re.compile(r"^#?(\d{1,9})$")
_NOT_FOUND = re.compile(r"Could not resolve to an Issue", re.IGNORECASE)


def _title(body: str, fallback: str) -> str:
    match = _TITLE.search(body)
    return (match.group(1).strip() if match else "") or fallback


class Runner(Protocol):
    def __call__(
        self,
        argv: list[str],
        *,
        timeout: float,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> object: ...


def read_only(argv: list[str]) -> bool:
    """True only for the read commands the board runs: a GraphQL query through `gh api`, `gh pr
    list` and a GET `glab api` path."""
    if argv[:3] == ["gh", "pr", "list"]:
        return True
    if argv[:2] == ["gh", "api"]:
        rest = argv[2:]
        if rest[:1] == ["--hostname"]:
            rest = rest[2:]
        if rest[:1] != ["graphql"]:
            return False
        queries = [arg[6:] for arg in rest if arg.startswith("query=")]
        flags = {arg for arg in rest if arg.startswith("-")}
        return (
            len(queries) == 1
            and queries[0].lstrip().startswith("query")
            and "mutation" not in queries[0].casefold()
            and flags <= {"-f", "-F"}
            and not any(arg.startswith(("-X", "--method")) for arg in rest)
        )
    if argv[:2] == ["glab", "api"]:
        return (
            len(argv) == 3
            and not argv[2].startswith("-")
            and not (set(argv) & _WRITE_FLAGS)
        )
    return False


class _Collect:
    """One collect: its deadline and the read-only runner."""

    def __init__(
        self,
        repo: Path,
        runner: Runner,
        clock: Callable[[], float],
        deadline: float,
        which: Callable[[str], str | None],
    ) -> None:
        self._repo, self._runner, self._clock, self._which = repo, runner, clock, which
        self._end = clock() + deadline

    def run(self, argv: list[str], env: dict[str, str] | None = None) -> str:
        if not read_only(argv):
            raise TrackerUnavailable("failed", "refused non-read command")
        remaining = self._end - self._clock()
        if remaining <= 0:
            raise TrackerUnavailable("timeout", f"{argv[0]}: deadline exhausted")
        result = self._runner(argv, timeout=remaining, cwd=self._repo, env=env)
        if result is None:
            if self._which(argv[0]) is None:
                raise TrackerUnavailable("tool_missing", f"{argv[0]} is not installed")
            raise TrackerUnavailable("timeout", f"{argv[0]} did not answer in time")
        code = getattr(result, "returncode", 1)
        out = str(getattr(result, "stdout", "") or "")
        err = str(getattr(result, "stderr", "") or "")
        if code != 0:
            text = f"{err}\n{out}".strip()
            if GLAB_AUTH_FAILURE.search(text):
                raise TrackerUnavailable("auth", f"{argv[0]}: {text}")
            if _NOT_FOUND.search(text):
                raise SpecNotFound(text)
            raise TrackerUnavailable(
                "failed", f"{argv[0]}: {text or 'exit ' + str(code)}"
            )
        return out

    def json(self, argv: list[str], env: dict[str, str] | None = None) -> object:
        out = self.run(argv, env)
        try:
            return json.loads(out)
        except ValueError as exc:
            raise TrackerUnavailable(
                "bad_output", f"{argv[0]} returned non-JSON output"
            ) from exc


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _path(data: object, *keys: str) -> object:
    for key in keys:
        data = _dict(data).get(key)
    return data


def _spec_number(spec_ref: str) -> int:
    match = _SPEC_REF.match(spec_ref.strip())
    if match is None:
        raise SpecNotFound(spec_ref)
    return int(match.group(1))


_GH_SPECS = """query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    issues(states: OPEN, first: 100, after: $cursor, orderBy: {field: CREATED_AT, direction: ASC}) {
      pageInfo { hasNextPage endCursor }
      nodes { number title url body subIssuesSummary { total completed } }
    }
  }
}"""

_GH_BOARD = """query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    issue(number: $number) {
      number title url body
      subIssues(first: 100) {
        pageInfo { hasNextPage }
        nodes {
          number title url state body
          labels(first: 50) { nodes { name } }
          %BLOCKED%
        }
      }
    }
  }
}"""

_GH_BLOCKED = (
    "blockedBy(first: 20) { pageInfo { hasNextPage } nodes { number title state } }"
)


class _GitHub:
    def __init__(self, collect: _Collect, tracker: ProjectTracker) -> None:
        if tracker.project is None or "/" not in tracker.project:
            raise TrackerUnavailable("not_configured", "the GitHub project is unknown")
        self._collect = collect
        self._host = tracker.host or "github.com"
        self._owner, self._name = tracker.project.split("/", 1)

    def _graphql(self, query: str, **variables: str | int) -> object:
        argv = [
            "gh",
            "api",
            "--hostname",
            self._host,
            "graphql",
            "-f",
            f"query={query}",
        ]
        # `-F` would turn "123", "true" or "@file" into a number, a boolean or a file read.
        argv += ["-f", f"owner={self._owner}", "-f", f"name={self._name}"]
        for key, value in variables.items():
            argv += ["-F" if isinstance(value, int) else "-f", f"{key}={value}"]
        return self._collect.json(argv)

    def specs(self) -> SpecList:
        found: list[TrackerSpec] = []
        cursor: str | None = None
        more = False
        for _ in range(_SPEC_PAGES):
            variables: dict[str, str | int] = {"cursor": cursor} if cursor else {}
            issues = _path(
                self._graphql(_GH_SPECS, **variables), "data", "repository", "issues"
            )
            for node in _list(_path(issues, "nodes")):
                summary = _dict(_path(node, "subIssuesSummary"))
                total, completed = (
                    _int(summary.get("total")),
                    _int(summary.get("completed")),
                )
                number = _int(_path(node, "number"))
                if not total or number is None:
                    continue
                found.append(
                    TrackerSpec(
                        ref=f"#{number}",
                        n=number,
                        title=_text(_path(node, "title")),
                        url=_text(_path(node, "url")) or None,
                        body=_text(_path(node, "body")),
                        tickets_total=total,
                        tickets_open=total - (completed or 0),
                    )
                )
            page = _dict(_path(issues, "pageInfo"))
            cursor = _text(page.get("endCursor"))
            more = page.get("hasNextPage") is True and bool(cursor)
            if len(found) >= MAX_SPECS or not more:
                break
        return SpecList(tuple(found[:MAX_SPECS]), more or len(found) > MAX_SPECS)

    def _board_data(self, number: int) -> object:
        try:
            return self._graphql(
                _GH_BOARD.replace("%BLOCKED%", _GH_BLOCKED), number=number
            )
        except TrackerUnavailable as failure:
            if failure.reason != "failed" or "blockedBy" not in failure.message:
                raise
        # A host without the `blockedBy` field: blockers come from the body only.
        return self._graphql(_GH_BOARD.replace("%BLOCKED%", ""), number=number)

    def _pulls(self) -> dict[int, PullRef]:
        argv = [
            "gh", "pr", "list", "--repo", f"{self._host}/{self._owner}/{self._name}",
            "--state", "open", "--limit", "200", "--json", "number,url,headRefName",
        ]  # fmt: skip
        pulls: dict[int, PullRef] = {}
        for item in _list(self._collect.json(argv)):
            ticket = ticket_of_branch(_dict(item).get("headRefName"))
            number = _int(_dict(item).get("number"))
            if ticket is not None and number is not None:
                pulls.setdefault(
                    ticket, PullRef(f"#{number}", _text(_dict(item).get("url")) or None)
                )
        return pulls

    def board(self, spec_ref: str) -> SpecTickets:
        number = _spec_number(spec_ref)
        issue = _path(self._board_data(number), "data", "repository", "issue")
        if not isinstance(issue, dict):
            raise SpecNotFound(spec_ref)
        pulls = self._pulls()
        tickets: list[TrackerTicket] = []
        more = _path(issue, "subIssues", "pageInfo", "hasNextPage") is True
        for node in _list(_path(issue, "subIssues", "nodes")):
            n = _int(_path(node, "number"))
            if n is None:
                continue
            more = more or _path(node, "blockedBy", "pageInfo", "hasNextPage") is True
            blockers = tuple(
                BlockerFact(
                    f"#{bn}",
                    bn,
                    _text(_path(b, "title")),
                    _path(b, "state") == "CLOSED",
                )
                for b in _list(_path(node, "blockedBy", "nodes"))
                if (bn := _int(_path(b, "number"))) is not None
            )
            tickets.append(
                TrackerTicket(
                    ref=f"#{n}",
                    n=n,
                    title=_text(_path(node, "title")),
                    url=_text(_path(node, "url")) or None,
                    closed=_path(node, "state") == "CLOSED",
                    labels=tuple(
                        name
                        for label in _list(_path(node, "labels", "nodes"))
                        if (name := _text(_path(label, "name")))
                    ),
                    body=_text(_path(node, "body")),
                    native_blockers=blockers,
                    pr=pulls.get(n),
                )
            )
        spec = TrackerSpec(
            ref=f"#{number}",
            n=number,
            title=_text(issue.get("title")),
            url=_text(issue.get("url")) or None,
            body=_text(issue.get("body")),
            tickets_total=len(tickets),
            tickets_open=sum(not ticket.closed for ticket in tickets),
        )
        return SpecTickets(
            spec, tuple(tickets), {t.ref: t.closed for t in tickets}, more
        )


class _GitLab:
    def __init__(self, collect: _Collect, tracker: ProjectTracker) -> None:
        if tracker.host is None or tracker.project is None:
            raise TrackerUnavailable(
                "not_configured", "the GitLab host or project is unknown"
            )
        self._collect = collect
        # glab rejects a port in `api --hostname`; GITLAB_HOST keeps it.
        self._env = {**os.environ, "GITLAB_HOST": tracker.host}
        self._prefix = f"projects/{quote(tracker.project, safe='')}"

    def _pages(self, path: str, pages: int) -> tuple[list[dict[str, object]], bool]:
        """The items of at most `pages` pages and whether the last read page was full."""
        found: list[dict[str, object]] = []
        for page in range(1, pages + 1):
            items = _list(
                self._collect.json(
                    [
                        "glab",
                        "api",
                        f"{self._prefix}/{path}&per_page={_PER_PAGE}&page={page}",
                    ],
                    self._env,
                )
            )
            found.extend(item for item in items if isinstance(item, dict))
            if len(items) < _PER_PAGE:
                return found, False
        return found, True

    def _issues(self) -> tuple[list[dict[str, object]], bool]:
        """The newest issues, oldest first: a spec and its later children are read before an
        old closed issue when the page limit cuts the listing."""
        issues, more = self._pages(
            "issues?state=all&order_by=created_at&sort=desc", _GITLAB_ISSUE_PAGES
        )
        return issues[::-1], more

    @staticmethod
    def _children(
        issues: list[dict[str, object]],
    ) -> dict[int, list[dict[str, object]]]:
        children: dict[int, list[dict[str, object]]] = {}
        for issue in issues:
            match = _PARENT.search(_text(issue.get("description")))
            if match:
                children.setdefault(int(match.group(1)), []).append(issue)
        return children

    @staticmethod
    def _spec(issue: dict[str, object], kids: list[dict[str, object]]) -> TrackerSpec:
        iid = _int(issue.get("iid"))
        return TrackerSpec(
            ref=f"#{iid}",
            n=iid,
            title=_text(issue.get("title")),
            url=_text(issue.get("web_url")) or None,
            body=_text(issue.get("description")),
            tickets_total=len(kids),
            tickets_open=sum(kid.get("state") != "closed" for kid in kids),
        )

    def specs(self) -> SpecList:
        issues, more = self._issues()
        children = self._children(issues)
        specs = [
            self._spec(issue, children[iid])
            for issue in issues
            if (iid := _int(issue.get("iid"))) is not None
            and iid in children
            and issue.get("state") == "opened"
        ]
        return SpecList(tuple(specs[-MAX_SPECS:]), more or len(specs) > MAX_SPECS)

    def board(self, spec_ref: str) -> SpecTickets:
        number = _spec_number(spec_ref)
        issues, more = self._issues()
        spec_issue = next((i for i in issues if _int(i.get("iid")) == number), None)
        if spec_issue is None:
            raise SpecNotFound(spec_ref)
        kids = self._children(issues).get(number, [])
        pulls: dict[int, PullRef] = {}
        mrs, more_mrs = self._pages("merge_requests?state=opened", _GITLAB_MR_PAGES)
        for mr in mrs:
            ticket, iid = ticket_of_branch(mr.get("source_branch")), _int(mr.get("iid"))
            if ticket is not None and iid is not None:
                pulls.setdefault(
                    ticket, PullRef(f"!{iid}", _text(mr.get("web_url")) or None)
                )
        tickets = tuple(
            TrackerTicket(
                ref=f"#{iid}",
                n=iid,
                title=_text(kid.get("title")),
                url=_text(kid.get("web_url")) or None,
                closed=kid.get("state") == "closed",
                labels=tuple(
                    label
                    for label in _list(kid.get("labels"))
                    if isinstance(label, str)
                ),
                body=_text(kid.get("description")),
                pr=pulls.get(iid),
            )
            for kid in kids
            if (iid := _int(kid.get("iid"))) is not None
        )
        states = {
            f"#{iid}": issue.get("state") == "closed"
            for issue in issues
            if (iid := _int(issue.get("iid"))) is not None
        }
        return SpecTickets(
            self._spec(spec_issue, kids), tickets, states, more or more_mrs
        )


def _read(path: Path) -> str:
    with path.open("rb") as handle:
        return handle.read(BODY_READ_BYTES).decode("utf-8", errors="replace")


_LOCAL_LABELS = (
    ("workflow", "status::"),
    ("execution", ""),
    ("pipeline", "pipeline::"),
    ("category", "type::"),
)


def _local_labels(body: str) -> tuple[tuple[str, ...], bool]:
    fields: dict[str, str] = {}
    for name, value in _LOCAL_FIELD.findall(body):
        fields.setdefault(name.strip().casefold(), value.strip().strip("`"))
    labels: list[str] = []
    closed = False
    for key, prefix in _LOCAL_LABELS:
        value = fields.get(key, "")
        if not value:
            continue
        if key == "workflow" and value.removeprefix("status::") in {"done", "closed"}:
            closed = True
            continue
        labels.append(
            value if not prefix or value.startswith(prefix) else prefix + value
        )
    return tuple(labels), closed


class _Local:
    def __init__(self, repo: Path) -> None:
        self._repo = repo.resolve()
        self._root = self._repo / ".scratch"

    def _inside(self, path: Path) -> bool:
        return not path.is_symlink() and self._root in path.resolve().parents

    def _tickets(self, spec_dir: Path) -> list[TrackerTicket]:
        issues = spec_dir / "issues"
        if not issues.is_dir() or not self._inside(issues):
            return []
        files = sorted(
            (int(match.group(1)), path)
            for path in issues.iterdir()
            if (match := _LOCAL_TICKET.match(path.name))
            and path.is_file()
            and self._inside(path)
        )
        tickets: list[TrackerTicket] = []
        for number, path in files:
            body = _read(path)
            labels, closed = _local_labels(body)
            tickets.append(
                TrackerTicket(
                    ref=path.relative_to(self._repo).as_posix(),
                    n=number,
                    title=_title(body, path.stem),
                    url=None,
                    closed=closed,
                    labels=labels,
                    body=body,
                )
            )
        by_number = {ticket.n: ticket for ticket in tickets}
        resolved = []
        for ticket in tickets:
            blockers = tuple(
                BlockerFact(sibling.ref, sibling.n, sibling.title, sibling.closed)
                for _, number, _ in parse_body(ticket.body).blocked_by
                if (sibling := by_number.get(number)) is not None
            )
            resolved.append(
                TrackerTicket(
                    ticket.ref,
                    ticket.n,
                    ticket.title,
                    ticket.url,
                    ticket.closed,
                    ticket.labels,
                    ticket.body,
                    blockers,
                )  # fmt: skip
            )
        return resolved

    def _spec(self, spec_dir: Path) -> tuple[TrackerSpec, list[TrackerTicket]] | None:
        if not spec_dir.is_dir() or not self._inside(spec_dir):
            return None
        spec_file = spec_dir / "spec.md"
        has_spec = spec_file.is_file() and self._inside(spec_file)
        tickets = self._tickets(spec_dir)
        if not has_spec and not tickets:
            return None
        body = _read(spec_file) if has_spec else ""
        spec = TrackerSpec(
            ref=spec_dir.name,
            n=None,
            title=_title(body, spec_dir.name),
            url=None,
            body=body,
            tickets_total=len(tickets),
            tickets_open=sum(not ticket.closed for ticket in tickets),
        )
        return spec, tickets

    def specs(self) -> SpecList:
        if not self._root.is_dir() or self._root.is_symlink():
            return SpecList(())
        found = []
        for spec_dir in sorted(self._root.iterdir()):
            read = self._spec(spec_dir)
            if read is not None and (not read[1] or read[0].tickets_open):
                found.append(read[0])
        return SpecList(tuple(found[:MAX_SPECS]), len(found) > MAX_SPECS)

    def board(self, spec_ref: str) -> SpecTickets:
        if (
            not spec_ref
            or spec_ref in {".", ".."}
            or "/" in spec_ref
            or "\\" in spec_ref
        ):
            raise SpecNotFound(spec_ref)
        read = self._spec(self._root / spec_ref)
        if read is None:
            raise SpecNotFound(spec_ref)
        spec, tickets = read
        return SpecTickets(spec, tuple(tickets), {t.ref: t.closed for t in tickets})


class TrackerBoardReader:
    """The `TaskBoardReader` of the project's configured tracker."""

    def __init__(
        self,
        *,
        runner: Runner = run_tool,
        clock: Callable[[], float] = monotonic,
        deadline: float = DEADLINE_SECONDS,
        resolve: Callable[[Path], ProjectTracker] | None = None,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self._runner, self._clock, self._deadline = runner, clock, deadline
        self._resolve = resolve or (
            lambda repo: resolve_project_tracker(repo).effective
        )
        self._which = which

    def tracker_type(self, repo: Path) -> str:
        return self._resolve(repo).type

    def _source(self, repo: Path) -> _GitHub | _GitLab | _Local:
        tracker = self._resolve(repo)
        if tracker.type == "local":
            return _Local(repo)
        collect = _Collect(repo, self._runner, self._clock, self._deadline, self._which)
        if tracker.type == "gitlab":
            return _GitLab(collect, tracker)
        return _GitHub(collect, tracker)

    def specs(self, repo: Path) -> SpecList:
        try:
            return self._source(repo).specs()
        except OSError as exc:
            raise TrackerUnavailable("failed", str(exc) or type(exc).__name__) from exc

    def board(self, repo: Path, spec_ref: str) -> SpecTickets:
        try:
            return self._source(repo).board(spec_ref)
        except OSError as exc:
            raise TrackerUnavailable("failed", str(exc) or type(exc).__name__) from exc
