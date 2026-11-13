"""`harness ticket-status` through its process seam: the real CLI runs as a subprocess against a
temporary project whose `gh`/`glab` on PATH are fakes that record their argv and answer from a
fixture, so no test reaches a real tracker. The command reads fresh tracker and ledger facts,
enforces the transitions itself and writes exactly one `status::*` label."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

CLI = Path(__file__).resolve().parents[2] / "harness" / "bin" / "harness.py"

FAKE_TOOL = """\
import json, os, sys
folder = os.environ["FAKE_TRACKER_DIR"]
argv = [os.path.splitext(os.path.basename(sys.argv[0]))[0], *sys.argv[1:]]
with open(os.path.join(folder, "calls.jsonl"), "a", encoding="utf-8") as log:
    log.write(json.dumps(argv) + "\\n")
line = " ".join(argv)
with open(os.path.join(folder, "fixture.json"), encoding="utf-8") as handle:
    rules = json.load(handle)
for rule in rules:
    if all(part in line for part in rule["match"]):
        sys.stdout.write(rule.get("stdout", ""))
        sys.stderr.write(rule.get("stderr", ""))
        sys.exit(rule.get("code", 0))
sys.stderr.write("fake: no rule for " + line)
sys.exit(97)
"""


class Project:
    """A temporary project with a tracker config, fake tools and an optional ledger."""

    def __init__(self, root: Path, tracker: dict[str, str]) -> None:
        self.repo = root / "repo"
        self.tools = root / "tools"
        (self.repo / ".harness").mkdir(parents=True)
        (self.repo / ".harness" / "project.json").write_text(
            json.dumps({"tracker": tracker}), encoding="utf-8"
        )
        self.tools.mkdir()
        for name in ("gh", "glab"):
            tool = self.tools / name
            if sys.platform == "win32":
                script = self.tools / f"{name}.py"
                script.write_text(FAKE_TOOL, encoding="utf-8", newline="\n")
                tool.with_suffix(".cmd").write_text(
                    f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8", newline=""
                )
                continue
            tool.write_text(f"#!{sys.executable}\n{FAKE_TOOL}", encoding="utf-8")
            tool.chmod(0o755)
        self.rules: list[dict[str, object]] = []

    def answer(self, *match: str, stdout: object = "", code: int = 0, stderr: str = "") -> None:
        text = stdout if isinstance(stdout, str) else json.dumps(stdout)
        self.rules.append({"match": list(match), "stdout": text, "code": code, "stderr": stderr})

    def batch(self, ticket: str, state: str = "active") -> None:
        batches = self.repo / ".harness" / "orchestration" / "state" / "batches"
        batches.mkdir(parents=True, exist_ok=True)
        (batches / "batch-1.json").write_text(
            json.dumps(
                {
                    "batch_id": "batch-1",
                    "ticket": ticket,
                    "state": state,
                    "created_at": "2026-11-01T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )

    def run(self, spec: str, ticket: str, to: str) -> tuple[int, dict[str, object]]:
        (self.tools / "fixture.json").write_text(json.dumps(self.rules), encoding="utf-8")
        env = {
            **os.environ,
            "PATH": f"{self.tools}{os.pathsep}{os.environ.get('PATH', '')}",
            "FAKE_TRACKER_DIR": str(self.tools),
            "PYTHONIOENCODING": "utf-8",  # the CLI prints "…"; a piped Windows stdout is cp1252
        }
        done = subprocess.run(
            [sys.executable, str(CLI), "ticket-status", str(self.repo),
             "--spec", spec, "--ticket", ticket, "--to", to],
            capture_output=True, text=True, encoding="utf-8", env=env, timeout=60, check=False,
        )  # fmt: skip
        lines = [line for line in done.stdout.splitlines() if line.strip()]
        assert lines, done.stderr
        return done.returncode, json.loads(lines[-1])

    def calls(self) -> list[list[str]]:
        log = self.tools / "calls.jsonl"
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

    def writes(self) -> list[list[str]]:
        return [
            call
            for call in self.calls()
            if call[:3] in (["gh", "issue", "edit"], ["glab", "issue", "update"])
        ]


def _gh_node(
    number: int,
    labels: list[str],
    *,
    state: str = "OPEN",
    body: str = "",
    blocked: list[tuple[int, str]] = (),  # type: ignore[assignment]
    more_blocked: bool = False,
) -> dict[str, object]:
    return {
        "number": number,
        "title": f"Ticket {number}",
        "url": f"https://github.com/o/r/issues/{number}",
        "state": state,
        "body": body,
        "labels": {"nodes": [{"name": label} for label in labels]},
        "blockedBy": {
            "pageInfo": {"hasNextPage": more_blocked},
            "nodes": [
                {"number": n, "title": f"Ticket {n}", "state": s} for n, s in blocked
            ],
        },
    }


def _gh_board(*nodes: dict[str, object]) -> dict[str, object]:
    return {
        "data": {
            "repository": {
                "issue": {
                    "number": 1,
                    "title": "Spec",
                    "url": "https://github.com/o/r/issues/1",
                    "body": "",
                    "subIssues": {"pageInfo": {"hasNextPage": False}, "nodes": list(nodes)},
                }
            }
        }
    }


@pytest.fixture
def github(tmp_path: Path) -> Project:
    project = Project(tmp_path, {"type": "github", "host": "github.com", "project": "o/r"})
    project.answer("gh pr list", stdout=[])
    return project


def test_github_move_removes_every_old_status_label_in_one_edit(github: Project) -> None:
    github.answer(
        "gh api", "graphql",
        stdout=_gh_board(_gh_node(5, ["status::ready", "status::blocked", "type::feature"])),
    )  # fmt: skip
    github.answer("gh issue edit", stdout="")

    code, result = github.run("1", "#5", "progress")

    assert code == 0
    assert result["result"] == "changed"
    assert (result["ticket"], result["from"], result["to"]) == ("#5", "ready", "progress")
    assert github.writes() == [
        [
            "gh", "issue", "edit", "5", "--repo", "github.com/o/r",
            "--remove-label", "status::ready", "--remove-label", "status::blocked",
            "--add-label", "status::in-progress",
        ]
    ]  # fmt: skip


def test_backlog_to_ready_with_an_open_blocker_is_refused_without_a_write(
    github: Project,
) -> None:
    github.answer(
        "gh api", "graphql",
        stdout=_gh_board(
            _gh_node(5, ["status::blocked"], blocked=[(4, "OPEN"), (3, "CLOSED")]),
            _gh_node(4, ["status::ready"]),
        ),
    )  # fmt: skip

    code, result = github.run("1", "5", "ready")

    assert code == 3
    assert result["result"] == "refused"
    assert result["reason"] == "open_blockers"
    assert result["blockers"] == ["#4"]
    assert github.writes() == []


def test_a_blocker_outside_the_spec_is_read_and_a_closed_one_allows_the_move(
    github: Project,
) -> None:
    github.answer(
        "gh api", "graphql",
        stdout=_gh_board(_gh_node(5, ["status::blocked"], body="## Blocked by\n\n- #77\n")),
    )  # fmt: skip
    github.answer("gh issue view 77", stdout={"state": "CLOSED"})
    github.answer("gh issue edit", stdout="")

    code, result = github.run("1", "#5", "ready")

    assert code == 0, result
    assert ["gh", "issue", "view", "77", "--repo", "github.com/o/r", "--json", "state"] in (
        github.calls()
    )
    assert github.writes()[0][-2:] == ["--add-label", "status::ready"]


def test_a_blocker_whose_state_cannot_be_read_counts_as_open(github: Project) -> None:
    github.answer(
        "gh api", "graphql",
        stdout=_gh_board(_gh_node(5, ["status::blocked"], body="## Blocked by\n\n- #77\n")),
    )  # fmt: skip
    github.answer("gh issue view 77", code=1, stderr="not found")

    code, result = github.run("1", "#5", "ready")

    assert (code, result["reason"], result["blockers"]) == (3, "open_blockers", ["#77"])
    assert github.writes() == []


def test_an_open_blocker_past_the_display_cap_refuses_backlog_to_ready(
    github: Project,
) -> None:
    # 21 body blockers: the board shows 20, the command must not decide on that list.
    listed = "".join(f"- #{n}\n" for n in range(101, 122))
    github.answer(
        "gh api", "graphql",
        stdout=_gh_board(_gh_node(5, ["status::blocked"], body=f"## Blocked by\n\n{listed}")),
    )  # fmt: skip
    github.answer("gh issue view 121 ", stdout={"state": "OPEN"})
    github.answer("gh issue view", stdout={"state": "CLOSED"})
    github.answer("gh issue edit", stdout="")

    code, result = github.run("1", "#5", "ready")

    assert (code, result["result"], result["reason"]) == (3, "refused", "open_blockers")
    assert result["blockers"] == ["\u2026"]
    assert github.writes() == []


def test_a_native_blocker_list_with_more_pages_refuses_backlog_to_ready(
    github: Project,
) -> None:
    closed = [(n, "CLOSED") for n in range(101, 121)]
    github.answer(
        "gh api", "graphql",
        stdout=_gh_board(_gh_node(5, ["status::blocked"], blocked=closed, more_blocked=True)),
    )  # fmt: skip
    github.answer("gh issue edit", stdout="")

    code, result = github.run("1", "#5", "ready")

    assert (code, result["result"], result["reason"]) == (3, "refused", "open_blockers")
    assert result["blockers"] == ["\u2026"]
    assert github.writes() == []


def test_progress_to_ready_is_refused_while_the_ticket_has_an_active_batch(
    github: Project,
) -> None:
    github.answer(
        "gh api", "graphql", stdout=_gh_board(_gh_node(5, ["status::in-progress"]))
    )
    github.batch("#5")

    code, result = github.run("1", "#5", "ready")

    assert (code, result["reason"], result["batch"]) == (3, "active_batch", "batch-1")
    assert github.writes() == []


@pytest.mark.parametrize(
    ("labels", "state", "to", "reason"),
    [
        (["status::ready"], "OPEN", "review", "review_target"),
        (["status::ready"], "OPEN", "done", "done_target"),
        (["status::blocked"], "OPEN", "progress", "via_ready"),
        (["status::in-progress"], "OPEN", "backlog", "via_ready"),
        (["status::ready"], "CLOSED", "ready", "closed"),
        (["status::ready"], "OPEN", "ready", "same"),
    ],
)
def test_every_other_transition_is_refused_when_called_directly(
    github: Project, labels: list[str], state: str, to: str, reason: str
) -> None:
    github.answer("gh api", "graphql", stdout=_gh_board(_gh_node(5, labels, state=state)))

    code, result = github.run("1", "#5", to)

    assert (code, result["result"], result["reason"]) == (3, "refused", reason)
    assert result["message"]
    assert github.writes() == []


def test_a_ticket_outside_the_spec_is_refused(github: Project) -> None:
    github.answer("gh api", "graphql", stdout=_gh_board(_gh_node(5, ["status::ready"])))

    code, result = github.run("1", "#6", "progress")

    assert (code, result["reason"]) == (3, "not_found")
    assert github.writes() == []


def test_a_failed_tracker_write_is_a_write_error(github: Project) -> None:
    github.answer("gh api", "graphql", stdout=_gh_board(_gh_node(5, ["status::ready"])))
    github.answer("gh issue edit", code=1, stderr="label not found")

    code, result = github.run("1", "#5", "progress")

    assert (code, result["result"], result["reason"]) == (1, "write_error", "write_failed")
    assert "label not found" in str(result["message"])


def test_an_unreadable_tracker_is_a_write_error_without_a_write(github: Project) -> None:
    github.answer("gh api", "graphql", code=1, stderr="gh: authentication required")

    code, result = github.run("1", "#5", "progress")

    assert (code, result["result"], result["reason"]) == (1, "write_error", "tracker_unavailable")
    assert github.writes() == []


@pytest.mark.skipif(
    sys.platform == "win32", reason="a .cmd shim cannot take the & of a GitLab query"
)
def test_gitlab_move_unlabels_the_previous_status_explicitly(tmp_path: Path) -> None:
    project = Project(
        tmp_path, {"type": "gitlab", "host": "gitlab.example.com", "project": "g/p"}
    )
    project.answer(
        "glab api", "/issues?",
        stdout=[
            {"iid": 1, "title": "Spec", "web_url": "u1", "state": "opened",
             "labels": [], "description": "Spec body"},
            {"iid": 5, "title": "Ticket", "web_url": "u5", "state": "opened",
             "labels": ["status::ready", "afk"], "description": "## Parent: #1\n"},
        ],
    )  # fmt: skip
    project.answer("glab api", "merge_requests", stdout=[])
    project.answer("glab issue update", stdout="")

    code, result = project.run("1", "#5", "progress")

    assert code == 0, result
    assert project.writes() == [
        [
            "glab", "issue", "update", "5", "-R", "https://gitlab.example.com/g/p",
            "--label", "status::in-progress", "--unlabel", "status::ready",
        ]
    ]  # fmt: skip


def _local_ticket(repo: Path, name: str, body: str) -> Path:
    issues = repo / ".scratch" / "feature" / "issues"
    issues.mkdir(parents=True, exist_ok=True)
    path = issues / name
    path.write_text(body, encoding="utf-8")
    return path


def test_local_move_rewrites_the_workflow_line(tmp_path: Path) -> None:
    project = Project(tmp_path, {"type": "local"})
    _local_ticket(project.repo, "01-base.md", "# Base\n\n**Workflow:** done\n")
    ticket = _local_ticket(
        project.repo,
        "02-next.md",
        "# Next\n\n**Workflow:** status::blocked\n**Execution:** afk\n\n## Blocked by\n\n- #1\n",
    )

    code, result = project.run("feature", ".scratch/feature/issues/02-next.md", "ready")

    assert code == 0, result
    text = ticket.read_text(encoding="utf-8")
    assert "**Workflow:** status::ready\n" in text
    assert "status::blocked" not in text
    assert "**Execution:** afk" in text
    assert project.calls() == []


def test_local_move_inserts_a_missing_workflow_line_after_the_title(tmp_path: Path) -> None:
    project = Project(tmp_path, {"type": "local"})
    ticket = _local_ticket(project.repo, "03-x.md", "# X\n\nbody\n")

    code, _ = project.run("feature", ".scratch/feature/issues/03-x.md", "ready")

    assert code == 0
    assert ticket.read_text(encoding="utf-8") == "# X\n**Workflow:** status::ready\n\nbody\n"
