"""`harness branch-delete` removes a merged ticket's local branch only when nothing is lost (#1196)."""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from harness.branch_delete import BranchDeleteRefused, delete_merged_branch
from harness.health.project_tracker import ProjectTracker, resolve_project_tracker

REPO_ROOT = Path(__file__).resolve().parents[2]
BRANCH = "feature/issue-7-demo"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


class BranchDeleteTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.origin = self.base / "origin.git"
        git(self.base, "init", "--bare", "-b", "main", str(self.origin))
        self.repo = self.base / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "config", "user.email", "test@example.invalid")
        (self.repo / ".gitignore").write_text("/.harness/\n", encoding="utf-8")
        git(self.repo, "add", ".gitignore")
        git(self.repo, "commit", "-m", "test: initial fixture")
        git(self.repo, "remote", "add", "origin", str(self.origin))
        git(self.repo, "push", "origin", "main")
        (self.repo / ".harness").mkdir()
        (self.repo / ".harness" / "project.json").write_text(
            json.dumps({"branch_pattern": "^feature/issue-[0-9]+-.+"}), encoding="utf-8"
        )
        git(self.repo, "branch", BRANCH, "main")
        git(self.repo, "commit", "--allow-empty", "-m", "feat: ticket work")
        git(self.repo, "branch", "-f", BRANCH, "HEAD")
        git(self.repo, "reset", "--hard", "origin/main")
        self.tip = git(self.repo, "rev-parse", BRANCH)

    def refused(self, branch: str = BRANCH) -> str:
        with self.assertRaises(BranchDeleteRefused) as caught:
            delete_merged_branch(self.repo, branch)
        self.assertEqual(
            git(self.repo, "branch", "--list", "--format=%(refname:short)", branch),
            branch,
        )
        return str(caught.exception)

    def test_deletes_a_branch_whose_tip_is_on_origin(self) -> None:
        git(self.repo, "push", "origin", BRANCH)
        git(self.repo, "fetch", "origin")

        result = delete_merged_branch(self.repo, BRANCH)

        self.assertEqual(result["status"], "deleted")
        self.assertEqual(result["tip"], self.tip)
        self.assertIn(f"refs/remotes/origin/{BRANCH}", result["evidence"])
        self.assertEqual(git(self.repo, "branch", "--list", BRANCH), "")

    def test_refuses_a_branch_outside_the_pattern(self) -> None:
        git(self.repo, "branch", "scratch", BRANCH)
        self.assertIn("branch_pattern", self.refused("scratch"))

    def test_refuses_a_checked_out_branch(self) -> None:
        git(self.repo, "push", "origin", BRANCH)
        git(self.repo, "fetch", "origin")
        tree = self.base / "tree"
        git(self.repo, "worktree", "add", str(tree), BRANCH)
        self.assertIn("checked out in worktree", self.refused())

    def test_refuses_unsaved_commits(self) -> None:
        self.assertIn("not preserved", self.refused())

    def test_deletes_a_squash_merged_branch_by_the_merged_pull_request(self) -> None:
        """The remote branch is gone; only the tracker knows the merged head commit."""
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "gh"
        fake.write_text(
            "#!/bin/sh\n"
            f'echo \'[{{"number": 42, "headRefOid": "{self.tip}"}}]\'\n',
            encoding="utf-8",
        )
        fake.chmod(0o755)
        tracker = ProjectTracker("github", "github.com", "owner/repo", "config")
        resolution = resolve_project_tracker(self.repo)
        with (
            mock.patch.dict(
                os.environ, {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
            ),
            mock.patch(
                "harness.health.project_tracker.resolve_project_tracker",
                return_value=dataclasses.replace(resolution, effective=tracker),
            ),
        ):
            result = delete_merged_branch(self.repo, BRANCH)

        self.assertEqual(result["status"], "deleted")
        self.assertIn("merged PR/MR 42", result["evidence"])

    def test_refuses_when_the_merged_pull_request_has_another_head(self) -> None:
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "gh"
        fake.write_text(
            "#!/bin/sh\necho '[{\"number\": 42, \"headRefOid\": \"0000\"}]'\n",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        tracker = ProjectTracker("github", "github.com", "owner/repo", "config")
        resolution = resolve_project_tracker(self.repo)
        with (
            mock.patch.dict(
                os.environ, {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
            ),
            mock.patch(
                "harness.health.project_tracker.resolve_project_tracker",
                return_value=dataclasses.replace(resolution, effective=tracker),
            ),
        ):
            self.assertIn("not preserved", self.refused())

    def test_cli_prints_the_refusal_and_exits_one(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "harness.bin.harness", "branch-delete",
             str(self.repo), BRANCH],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )  # fmt: skip
        self.assertEqual(result.returncode, 1, result.stderr)
        answer = json.loads(result.stdout)
        self.assertEqual(answer["status"], "refused")
        self.assertIn("not preserved", answer["reason"])


if __name__ == "__main__":
    unittest.main()
