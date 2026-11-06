"""The read-only tracker reader of the task board over a fake process runner: GitHub GraphQL and
`gh pr list`, GitLab REST pages through `glab api`, local `.scratch/` files, the failure reasons and
the read-only argv allowlist."""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

from harness.console.backend.application.ports import SpecNotFound, TrackerUnavailable
from harness.console.backend.domain.task_board import (
    MAX_SPECS,
    BlockerFact,
    PullRef,
    SpecList,
)
from harness.console.backend.infrastructure.task_board_tracker import (
    TrackerBoardReader,
    read_only,
)
from harness.health.project_tracker import ProjectTracker

GITHUB = ProjectTracker("github", "github.com", "acme/app", "config")
GITLAB = ProjectTracker("gitlab", "gitlab.example:8443", "group/sub/app", "config")
LOCAL = ProjectTracker("local", None, None, "config")

Handler = Callable[[list[str], Mapping[str, str] | None], tuple[int, str, str] | None]


class FakeRunner:
    """Records every argv and answers it with the handler's (rc, stdout, stderr)."""

    def __init__(self, handler: Handler) -> None:
        self.handler = handler
        self.calls: list[tuple[list[str], dict[str, str] | None, float]] = []

    def __call__(
        self,
        argv: list[str],
        *,
        timeout: float,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str] | None:
        self.calls.append((list(argv), env, timeout))
        answer = self.handler(argv, env)
        if answer is None:
            return None
        code, out, err = answer
        return subprocess.CompletedProcess(argv, code, out, err)


def _reader(
    tracker: ProjectTracker,
    handler: Handler,
    *,
    clock: Callable[[], float] = lambda: 0.0,
    which: Callable[[str], str | None] = lambda name: f"/usr/bin/{name}",
) -> tuple[TrackerBoardReader, FakeRunner]:
    runner = FakeRunner(handler)
    reader = TrackerBoardReader(
        runner=runner, clock=clock, resolve=lambda repo: tracker, which=which
    )
    return reader, runner


def _query(argv: list[str]) -> str:
    return next(arg[6:] for arg in argv if arg.startswith("query="))


def _issue(
    number: int, state: str, labels: list[str], body: str = "", **extra: object
) -> dict[str, object]:
    return {
        "number": number,
        "title": f"Ticket {number}",
        "url": f"https://github.com/acme/app/issues/{number}",
        "state": state,
        "body": body,
        "labels": {"nodes": [{"name": name} for name in labels]},
        "blockedBy": {"nodes": extra.get("blocked", [])},
    }


GITHUB_BOARD = {
    "data": {
        "repository": {
            "issue": {
                "number": 862,
                "title": "Web console",
                "url": "https://github.com/acme/app/issues/862",
                "body": "## Integration Branch\n`integration/web-console`\n",
                "subIssues": {
                    "nodes": [
                        _issue(
                            913,
                            "OPEN",
                            ["afk", "status::in-progress"],
                            "## Blocked by\n- Blocked by #882 — shell first\n",
                            blocked=[
                                {"number": 882, "title": "Shell", "state": "OPEN"}
                            ],
                        ),
                        _issue(882, "OPEN", ["status::ready"]),
                        _issue(880, "CLOSED", ["hitl"]),
                    ]
                },
            }
        }
    }
}

GITHUB_SPECS = {
    "data": {
        "repository": {
            "issues": {
                "pageInfo": {"hasNextPage": False, "endCursor": None},
                "nodes": [
                    {
                        "number": 862,
                        "title": "Web console",
                        "url": "https://github.com/acme/app/issues/862",
                        "body": "",
                        "subIssuesSummary": {"total": 3, "completed": 1},
                    },
                    {
                        "number": 900,
                        "title": "Plain issue",
                        "url": "https://github.com/acme/app/issues/900",
                        "body": "",
                        "subIssuesSummary": {"total": 0, "completed": 0},
                    },
                ],
            }
        }
    }
}

GITHUB_PRS = [
    {
        "number": 958,
        "url": "https://github.com/acme/app/pull/958",
        "headRefName": "feature/issue-913-board",
    },
    {
        "number": 959,
        "url": "https://github.com/acme/app/pull/959",
        "headRefName": "main-fix",
    },
]


def _github(argv: list[str], env: Mapping[str, str] | None) -> tuple[int, str, str]:
    if argv[:2] == ["gh", "pr"]:
        return 0, json.dumps(GITHUB_PRS), ""
    query = _query(argv)
    if "subIssues(" in query:
        return 0, json.dumps(GITHUB_BOARD), ""
    return 0, json.dumps(GITHUB_SPECS), ""


def test_github_specs_are_open_issues_with_sub_issues(tmp_path: Path) -> None:
    reader, runner = _reader(GITHUB, _github)

    listing = reader.specs(tmp_path)

    assert isinstance(listing, SpecList)
    assert listing.truncated is False
    assert [
        (spec.ref, spec.n, spec.tickets_total, spec.tickets_open)
        for spec in listing.specs
    ] == [("#862", 862, 3, 2)]
    argv = runner.calls[0][0]
    assert argv[:5] == ["gh", "api", "--hostname", "github.com", "graphql"]
    assert reader.tracker_type(tmp_path) == "github"


def test_github_board_reads_sub_issues_blockers_and_prs(tmp_path: Path) -> None:
    reader, runner = _reader(GITHUB, _github)

    board = reader.board(tmp_path, "#862")

    assert board.spec.ref == "#862"
    assert board.spec.title == "Web console"
    tickets = {ticket.ref: ticket for ticket in board.tickets}
    assert set(tickets) == {"#913", "#882", "#880"}
    assert tickets["#913"].labels == ("afk", "status::in-progress")
    assert tickets["#913"].native_blockers == (
        BlockerFact("#882", 882, "Shell", False),
    )
    assert tickets["#913"].pr == PullRef("#958", "https://github.com/acme/app/pull/958")
    assert tickets["#880"].closed is True
    assert board.blocker_states == {"#913": False, "#882": False, "#880": True}
    pr_call = next(argv for argv, _, _ in runner.calls if argv[:2] == ["gh", "pr"])
    assert "--repo" in pr_call and "github.com/acme/app" in pr_call


def test_github_board_retries_without_blocked_by(tmp_path: Path) -> None:
    def handler(argv: list[str], env: Mapping[str, str] | None) -> tuple[int, str, str]:
        if argv[:2] != ["gh", "pr"] and "blockedBy" in _query(argv):
            return 1, "", "Field 'blockedBy' doesn't exist on type 'Issue'"
        return _github(argv, env)

    reader, runner = _reader(GITHUB, handler)

    board = reader.board(tmp_path, "862")

    assert len(board.tickets) == 3
    queries = [_query(argv) for argv, _, _ in runner.calls if argv[:2] != ["gh", "pr"]]
    assert ["blockedBy" in query for query in queries] == [True, False]


def test_github_board_keeps_blocked_by_after_a_transient_failure(
    tmp_path: Path,
) -> None:
    def handler(argv: list[str], env: Mapping[str, str] | None) -> tuple[int, str, str]:
        if argv[:2] != ["gh", "pr"]:
            return 1, "", "HTTP 502: Bad Gateway"
        return _github(argv, env)

    reader, runner = _reader(GITHUB, handler)

    with pytest.raises(TrackerUnavailable) as raised:
        reader.board(tmp_path, "#862")

    assert raised.value.reason == "failed"
    queries = [_query(argv) for argv, _, _ in runner.calls if argv[:2] != ["gh", "pr"]]
    assert ["blockedBy" in query for query in queries] == [True]


def _variables(argv: list[str]) -> dict[str, str]:
    found = {}
    for flag, value in zip(argv, argv[1:], strict=False):
        if flag in {"-f", "-F"} and not value.startswith("query="):
            name, _, _ = value.partition("=")
            found[name] = flag
    return found


def test_github_strings_are_raw_fields_and_numbers_typed(tmp_path: Path) -> None:
    def handler(argv: list[str], env: Mapping[str, str] | None) -> tuple[int, str, str]:
        if argv[:2] == ["gh", "pr"] or "subIssues(" in _query(argv):
            return _github(argv, env)
        page = json.loads(json.dumps(GITHUB_SPECS))["data"]["repository"]["issues"]
        first = "cursor" not in _variables(argv)
        page["pageInfo"] = {"hasNextPage": first, "endCursor": "@abc" if first else None}
        return 0, json.dumps({"data": {"repository": {"issues": page}}}), ""

    tracker = ProjectTracker("github", "github.com", "123/true", "config")
    reader, runner = _reader(tracker, handler)

    reader.specs(tmp_path)
    reader.board(tmp_path, "#862")

    graphql = [argv for argv, _, _ in runner.calls if argv[:2] == ["gh", "api"]]
    assert [_variables(argv) for argv in graphql] == [
        {"owner": "-f", "name": "-f"},
        {"owner": "-f", "name": "-f", "cursor": "-f"},
        {"owner": "-f", "name": "-f", "number": "-F"},
    ]
    assert "owner=123" in graphql[0] and "name=true" in graphql[0]
    assert "cursor=@abc" in graphql[1]


def _spec_nodes(start: int, count: int) -> list[dict[str, object]]:
    return [
        {
            "number": number,
            "title": f"Spec {number}",
            "url": f"https://github.com/acme/app/issues/{number}",
            "body": "",
            "subIssuesSummary": {"total": 1, "completed": 0},
        }
        for number in range(start, start + count)
    ]


@pytest.mark.parametrize("per_page", [0, 100])
def test_github_specs_flag_a_listing_stopped_at_its_limit(
    tmp_path: Path, per_page: int
) -> None:
    pages = 0

    def handler(argv: list[str], env: Mapping[str, str] | None) -> tuple[int, str, str]:
        nonlocal pages
        pages += 1
        issues = {
            "pageInfo": {"hasNextPage": True, "endCursor": f"c{pages}"},
            "nodes": _spec_nodes(pages * 1000, per_page),
        }
        return 0, json.dumps({"data": {"repository": {"issues": issues}}}), ""

    reader, _ = _reader(GITHUB, handler)

    listing = reader.specs(tmp_path)

    assert listing.truncated is True
    assert len(listing.specs) == min(MAX_SPECS, per_page * pages)


@pytest.mark.parametrize("field", ["subIssues", "blockedBy"])
def test_github_board_flags_more_sub_issues_or_blockers(
    tmp_path: Path, field: str
) -> None:
    board = json.loads(json.dumps(GITHUB_BOARD))
    issue = board["data"]["repository"]["issue"]
    first = issue["subIssues"]["nodes"][0]
    target = issue["subIssues"] if field == "subIssues" else first["blockedBy"]
    target["pageInfo"] = {"hasNextPage": True}

    def handler(argv: list[str], env: Mapping[str, str] | None) -> tuple[int, str, str]:
        if argv[:2] == ["gh", "pr"]:
            return _github(argv, env)
        return 0, json.dumps(board), ""

    reader, _ = _reader(GITHUB, handler)

    assert reader.board(tmp_path, "#862").truncated is True
    assert _reader(GITHUB, _github)[0].board(tmp_path, "#862").truncated is False


def test_github_unknown_spec_is_not_found(tmp_path: Path) -> None:
    def handler(argv: list[str], env: Mapping[str, str] | None) -> tuple[int, str, str]:
        return 0, json.dumps({"data": {"repository": {"issue": None}}}), ""

    reader, _ = _reader(GITHUB, handler)

    with pytest.raises(SpecNotFound):
        reader.board(tmp_path, "#1")
    with pytest.raises(SpecNotFound):
        reader.board(tmp_path, "not-a-number")


def _gitlab_issue(
    iid: int, state: str, labels: list[str], description: str
) -> dict[str, object]:
    return {
        "iid": iid,
        "title": f"Issue {iid}",
        "web_url": f"https://gitlab.example:8443/group/sub/app/-/issues/{iid}",
        "state": state,
        "labels": labels,
        "description": description,
    }


GITLAB_ISSUES = [
    _gitlab_issue(10, "opened", [], "## Integration Branch\n`integration/x`\n"),
    _gitlab_issue(
        11,
        "opened",
        ["afk", "status::ready"],
        "## Parent: #10\n\n## Blocked by\nBlocked by #12 — first\n",
    ),
    _gitlab_issue(12, "closed", ["status::in-progress"], "## Parent: #10\n"),
    _gitlab_issue(13, "opened", [], "## Parent: #20\n"),
    _gitlab_issue(20, "closed", [], "closed spec"),
    _gitlab_issue(30, "opened", [], "## Parent: #300 is not 30\n"),
]

GITLAB_MRS = [
    {
        "iid": 5,
        "web_url": "https://gitlab.example:8443/group/sub/app/-/merge_requests/5",
        "source_branch": "feature/issue-11-x",
    }
]


def _gitlab(argv: list[str], env: Mapping[str, str] | None) -> tuple[int, str, str]:
    assert env is not None and env["GITLAB_HOST"] == "gitlab.example:8443"
    path = argv[2]
    assert path.startswith("projects/group%2Fsub%2Fapp/")
    page = int(path.rsplit("page=", 1)[1].split("&")[0])
    if "/merge_requests?" in path:
        return 0, json.dumps(GITLAB_MRS if page == 1 else []), ""
    return 0, json.dumps(GITLAB_ISSUES if page == 1 else []), ""


def test_gitlab_specs_are_open_parents_of_children(tmp_path: Path) -> None:
    reader, runner = _reader(GITLAB, _gitlab)

    listing = reader.specs(tmp_path)

    assert isinstance(listing, SpecList)
    assert listing.truncated is False
    assert [
        (spec.ref, spec.tickets_total, spec.tickets_open) for spec in listing.specs
    ] == [("#10", 2, 1)]
    for argv, _, _ in runner.calls:
        assert argv[:2] == ["glab", "api"] and len(argv) == 3


def test_gitlab_board_reads_children_blockers_and_mrs(tmp_path: Path) -> None:
    reader, _ = _reader(GITLAB, _gitlab)

    board = reader.board(tmp_path, "#10")

    tickets = {ticket.ref: ticket for ticket in board.tickets}
    assert set(tickets) == {"#11", "#12"}
    assert tickets["#11"].pr == PullRef("!5", str(GITLAB_MRS[0]["web_url"]))
    assert tickets["#12"].closed is True
    assert board.blocker_states["#12"] is True
    with pytest.raises(SpecNotFound):
        reader.board(tmp_path, "#99")


def _gitlab_many(total: int) -> Handler:
    """A GitLab project of `total` issues; spec #2400 is recent and has recent children."""
    issues = [
        _gitlab_issue(
            iid,
            "opened",
            [],
            "## Parent: #2400\n" if 2450 <= iid <= 2460 else f"issue {iid}",
        )
        for iid in range(1, total + 1)
    ]

    def handler(argv: list[str], env: Mapping[str, str] | None) -> tuple[int, str, str]:
        path = argv[2]
        page = int(path.rsplit("page=", 1)[1].split("&")[0])
        if "/merge_requests?" in path:
            return 0, "[]", ""
        ordered = issues[::-1] if "sort=desc" in path else issues
        return 0, json.dumps(ordered[(page - 1) * 100 : page * 100]), ""

    return handler


def test_gitlab_reads_the_newest_issues_and_flags_the_limit(tmp_path: Path) -> None:
    reader, _ = _reader(GITLAB, _gitlab_many(2500))

    listing = reader.specs(tmp_path)
    board = reader.board(tmp_path, "#2400")

    assert [spec.ref for spec in listing.specs] == ["#2400"]
    assert listing.truncated is True
    assert [ticket.n for ticket in board.tickets] == list(range(2450, 2461))
    assert board.truncated is True


def test_gitlab_listing_below_the_limit_is_not_truncated(tmp_path: Path) -> None:
    reader, _ = _reader(GITLAB, _gitlab_many(1999))

    assert reader.specs(tmp_path).truncated is False


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _local_tree(root: Path) -> None:
    spec = root / ".scratch" / "board"
    _write(
        spec / "spec.md", "# Board spec\n\n## Integration Branch\n`integration/board`\n"
    )
    _write(
        spec / "issues" / "01-first.md",
        "# 01 — First\n\n**What to build:** one\n**Workflow:** done\n**Execution:** afk\n",
    )
    _write(
        spec / "issues" / "02-second.md",
        "# 02 — Second\n\n**What to build:** two\n**Blocked by:** 01 — first one\n\n"
        "**Category:** type::feature\n**Workflow:** status::blocked\n**Execution:** afk\n"
        "**Story Points:** 3\n**Pipeline:** pipeline::fast\n\n- [ ] crit\n",
    )
    _write(
        root / ".scratch" / "finished" / "issues" / "01-x.md",
        "# x\n**Workflow:** done\n",
    )
    _write(root / "outside" / "issues" / "01-y.md", "# y\n")
    os.symlink(root / "outside", root / ".scratch" / "escape")


def _tree_state(root: Path) -> list[tuple[str, int, int]]:
    found = []
    for directory, dirs, files in os.walk(root):
        for name in sorted(dirs + files):
            path = Path(directory) / name
            info = path.lstat()
            found.append((str(path), info.st_size, info.st_mtime_ns))
    return sorted(found)


def test_local_specs_and_board_from_scratch_files(tmp_path: Path) -> None:
    _local_tree(tmp_path)
    before = _tree_state(tmp_path)
    reader, runner = _reader(LOCAL, lambda argv, env: None)

    listing = reader.specs(tmp_path)
    board = reader.board(tmp_path, "board")

    assert [
        (spec.ref, spec.n, spec.title, spec.tickets_total, spec.tickets_open)
        for spec in listing.specs
    ] == [("board", None, "Board spec", 2, 1)]
    first, second = board.tickets
    assert first.ref == ".scratch/board/issues/01-first.md"
    assert first.n == 1 and first.closed is True and first.title == "01 — First"
    assert second.labels == (
        "status::blocked",
        "afk",
        "pipeline::fast",
        "type::feature",
    )
    assert second.native_blockers == (
        BlockerFact(".scratch/board/issues/01-first.md", 1, "01 — First", True),
    )
    assert runner.calls == []
    assert _tree_state(tmp_path) == before
    for bad in ("escape", "finished-not", "../outside", ""):
        with pytest.raises(SpecNotFound):
            reader.board(tmp_path, bad)


# Hostile local files that a backtracking title or field pattern reads in seconds.
PARSE_SECONDS = 1.0


@pytest.mark.parametrize(
    "hostile",
    ["# a" + " " * 60000 + "x\n", "**a\n" * 16000, "# " + " " * 60000 + "\n"],
    ids=["title", "fields", "blank-title"],
)
def test_local_hostile_files_are_read_in_linear_time(
    tmp_path: Path, hostile: str
) -> None:
    _write(tmp_path / ".scratch" / "s" / "spec.md", hostile)
    _write(tmp_path / ".scratch" / "s" / "issues" / "01-x.md", hostile)
    reader, _ = _reader(LOCAL, lambda argv, env: None)

    started = time.perf_counter()
    listing = reader.specs(tmp_path)
    board = reader.board(tmp_path, "s")

    assert time.perf_counter() - started < PARSE_SECONDS
    assert [spec.ref for spec in listing.specs] == ["s"]
    assert board.tickets[0].title.strip() == board.tickets[0].title
    assert board.tickets[0].title in {"a" + " " * 60000 + "x", "01-x"}


def test_local_without_scratch_has_no_specs(tmp_path: Path) -> None:
    reader, _ = _reader(LOCAL, lambda argv, env: None)

    assert reader.specs(tmp_path) == SpecList(())


@pytest.mark.parametrize(
    ("answer", "which", "reason"),
    [
        (None, None, "tool_missing"),
        (None, "/usr/bin/gh", "timeout"),
        (
            (1, "", "To get started with GitHub CLI, please run:  gh auth login"),
            "/usr/bin/gh",
            "auth",
        ),
        ((1, "", "HTTP 500"), "/usr/bin/gh", "failed"),
        ((0, "not json", ""), "/usr/bin/gh", "bad_output"),
    ],
)
def test_failures_map_to_reasons(
    tmp_path: Path, answer: tuple[int, str, str] | None, which: str | None, reason: str
) -> None:
    reader, _ = _reader(GITHUB, lambda argv, env: answer, which=lambda name: which)

    with pytest.raises(TrackerUnavailable) as raised:
        reader.specs(tmp_path)

    assert raised.value.reason == reason


def test_exhausted_deadline_is_timeout(tmp_path: Path) -> None:
    ticks = iter([0.0, 0.0, 100.0, 100.0, 100.0])
    reader, _ = _reader(GITHUB, _github, clock=lambda: next(ticks))

    with pytest.raises(TrackerUnavailable) as raised:
        reader.board(tmp_path, "#862")

    assert raised.value.reason == "timeout"


def test_unconfigured_hosted_tracker(tmp_path: Path) -> None:
    reader, _ = _reader(ProjectTracker("github", None, None, "default"), _github)

    with pytest.raises(TrackerUnavailable) as raised:
        reader.specs(tmp_path)

    assert raised.value.reason == "not_configured"


def test_every_command_is_read_only(tmp_path: Path) -> None:
    github, github_runner = _reader(GITHUB, _github)
    github.specs(tmp_path)
    github.board(tmp_path, "#862")
    gitlab, gitlab_runner = _reader(GITLAB, _gitlab)
    gitlab.specs(tmp_path)
    gitlab.board(tmp_path, "#10")

    for argv, _, _ in github_runner.calls + gitlab_runner.calls:
        assert read_only(argv), argv


@pytest.mark.parametrize(
    "argv",
    [
        ["gh", "issue", "edit", "1", "--add-label", "x"],
        [
            "gh",
            "api",
            "--hostname",
            "github.com",
            "graphql",
            "-f",
            "query=mutation { x }",
        ],
        [
            "gh",
            "api",
            "--hostname",
            "github.com",
            "graphql",
            "-f",
            "query=query { a } mutation { x }",
        ],
        ["gh", "api", "repos/a/b/issues/1", "-X", "PATCH"],
        ["glab", "api", "--method", "POST", "projects/1/issues"],
        ["glab", "api", "projects/1/issues", "-f", "title=x"],
        ["glab", "issue", "close", "1"],
        ["git", "push"],
    ],
)
def test_non_read_commands_are_refused(tmp_path: Path, argv: list[str]) -> None:
    assert not read_only(argv)
