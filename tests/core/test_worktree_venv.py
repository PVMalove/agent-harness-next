"""An issue worktree reuses the main checkout's venv only while both lock the same dependencies."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def git(repo: Path, *args: str) -> str:
    """Выполнить команду git в указанном репозитории и вернуть stdout."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


class WorktreeVenvTests(unittest.TestCase):
    """`harness worktree-venv` links or refuses the issue worktree venv."""

    def setUp(self) -> None:
        """Main checkout with a bootstrapped venv stamp and one issue worktree."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.repo = base / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-b", "main")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "config", "user.email", "test@example.invalid")
        (self.repo / ".gitignore").write_text("/.harness/\n", encoding="utf-8")
        (self.repo / "uv.lock").write_text("lock = 1\n", encoding="utf-8")
        (self.repo / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        (self.repo / "Makefile").write_text(
            ".harness/.venv/.requirements-installed: pyproject.toml uv.lock\n"
            "\t@echo bootstrap-needed; exit 1\n"
            "lint: .harness/.venv/.requirements-installed\n\t@echo lint-ran\n",
            encoding="utf-8",
        )
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "test: initial fixture")
        self.venv = self.repo / ".harness" / ".venv"
        self.venv.mkdir(parents=True)
        stamp = self.venv / ".requirements-installed"
        stamp.touch()
        os.utime(self.repo / "uv.lock", (1_000_000, 1_000_000))
        os.utime(self.repo / "pyproject.toml", (1_000_000, 1_000_000))
        os.utime(stamp, (2_000_000, 2_000_000))
        self.worktree = self.repo / ".harness/.sandboxes/worktrees/issue-1-demo"
        git(self.repo, "worktree", "add", "--no-track", "-b", "feature/issue-1-demo",
            str(self.worktree), "main")

    def run_cli(self) -> tuple[int, dict[str, str]]:
        """Run the CLI command and return its exit code and JSON answer."""
        result = subprocess.run(
            [sys.executable, "-m", "harness.bin.harness", "worktree-venv",
             str(self.repo), str(self.worktree)],
            capture_output=True, text=True, cwd=REPO_ROOT, check=False,
        )
        return result.returncode, json.loads(result.stdout)

    def test_same_lock_links_main_venv_and_make_lint_runs_without_bootstrap(self) -> None:
        """Совпадающий uv.lock: symlink на venv основного checkout, make lint без bootstrap."""
        code, answer = self.run_cli()

        self.assertEqual((code, answer["status"]), (0, "linked"))
        link = self.worktree / ".harness" / ".venv"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), self.venv.resolve())
        lint = subprocess.run(
            ["make", "-s", "lint"], cwd=self.worktree, capture_output=True, text=True,
            check=False,
        )
        self.assertEqual(lint.stdout.strip(), "lint-ran")
        self.assertEqual(git(self.worktree, "status", "--porcelain"), "")
        self.assertEqual(self.run_cli(), (0, {**answer, "status": "already_linked"}))

    def test_different_lock_refuses_without_link_and_names_remedy(self) -> None:
        """Отличающийся uv.lock: symlink не создаётся, ответ называет расхождение и remedy."""
        (self.worktree / "uv.lock").write_text("lock = 2\n", encoding="utf-8")

        code, answer = self.run_cli()

        self.assertEqual((code, answer["status"]), (1, "refused"))
        self.assertIn("uv.lock", answer["reason"])
        self.assertIn("UV_PROJECT_ENVIRONMENT=.harness/.venv uv sync --locked", answer["remedy"])
        self.assertFalse((self.worktree / ".harness" / ".venv").is_symlink())

    def test_link_not_ignored_by_git_is_rolled_back(self) -> None:
        """Если git не игнорирует .harness/.venv, ссылка удаляется и worktree остаётся чистым."""
        (self.worktree / ".gitignore").write_text("/.harness/.sandboxes/\n", encoding="utf-8")
        git(self.worktree, "commit", "-qam", "test: narrow ignore")
        git(self.repo, "checkout", "-q", "feature/issue-1-demo", "--", ".gitignore")
        git(self.repo, "commit", "-qm", "test: same ignore in main")

        code, answer = self.run_cli()

        self.assertEqual((code, answer["status"]), (1, "refused"))
        self.assertIn(".gitignore", answer["remedy"])
        self.assertFalse((self.worktree / ".harness" / ".venv").is_symlink())
        self.assertEqual(git(self.worktree, "status", "--porcelain"), "")


if __name__ == "__main__":
    unittest.main()
