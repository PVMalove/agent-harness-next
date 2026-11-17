"""`harness self-update` moves the harness source checkout to a fetched ref as a detached HEAD."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from harness.source_checkout import SourceCheckoutError, update_source_checkout


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


class SourceCheckoutUpdateTests(unittest.TestCase):
    """The source checkout follows `origin`; a dirty tree or an unknown ref leaves HEAD alone."""

    def setUp(self) -> None:
        """Origin with `main` and `release`, and a clone that plays the harness source."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.origin = base / "origin"
        self.origin.mkdir()
        git(self.origin, "init", "-q", "-b", "main")
        git(self.origin, "config", "user.name", "Test")
        git(self.origin, "config", "user.email", "test@example.invalid")
        self.commit_origin("first")
        git(self.origin, "branch", "release")
        self.source = base / "source"
        subprocess.run(
            ["git", "clone", "-q", str(self.origin), str(self.source)], check=True
        )
        self.start = git(self.source, "rev-parse", "HEAD")

    def commit_origin(self, name: str) -> str:
        """Добавить коммит в текущую ветку origin и вернуть его SHA."""
        (self.origin / f"{name}.txt").write_text(name + "\n", encoding="utf-8")
        git(self.origin, "add", ".")
        git(self.origin, "commit", "-q", "-m", f"test: {name}")
        return git(self.origin, "rev-parse", "HEAD")

    def test_default_ref_follows_origin_head_and_detaches(self) -> None:
        """Без --ref берётся ветка, на которую указывает origin/HEAD; HEAD отсоединён."""
        newer = self.commit_origin("second")

        answer = update_source_checkout(self.source, None)

        self.assertEqual(
            answer,
            {
                "ref": "main",
                "previous": self.start,
                "previous_head": "main",
                "current": newer,
            },
        )
        self.assertEqual(git(self.source, "rev-parse", "HEAD"), newer)
        self.assertEqual(
            subprocess.run(
                ["git", "-C", str(self.source), "symbolic-ref", "-q", "HEAD"],
                check=False,
            ).returncode,
            1,
        )

    def test_explicit_ref_selects_that_branch(self) -> None:
        """--ref release переводит источник на ветку release из origin."""
        self.commit_origin("second")
        git(self.origin, "checkout", "-q", "release")
        release = self.commit_origin("release-only")

        answer = update_source_checkout(self.source, "release")

        self.assertEqual(answer["current"], release)
        self.assertEqual(git(self.source, "rev-parse", "HEAD"), release)

    def test_dirty_tree_is_refused_without_moving_head(self) -> None:
        """Незакоммиченная правка в источнике: отказ, HEAD не меняется."""
        self.commit_origin("second")
        (self.source / "first.txt").write_text("local edit\n", encoding="utf-8")

        with self.assertRaises(SourceCheckoutError) as raised:
            update_source_checkout(self.source, None)

        self.assertIn("uncommitted", str(raised.exception))
        self.assertEqual(git(self.source, "rev-parse", "HEAD"), self.start)

    def test_unknown_ref_is_refused_without_moving_head(self) -> None:
        """Неизвестная ветка origin: отказ с её именем, HEAD не меняется."""
        with self.assertRaises(SourceCheckoutError) as raised:
            update_source_checkout(self.source, "no-such-branch")

        self.assertIn("no-such-branch", str(raised.exception))
        self.assertEqual(git(self.source, "rev-parse", "HEAD"), self.start)

    def test_missing_origin_head_asks_for_ref(self) -> None:
        """Без origin/HEAD и без --ref источник не двигается, ошибка называет --ref."""
        git(self.source, "remote", "set-head", "origin", "--delete")

        with self.assertRaises(SourceCheckoutError) as raised:
            update_source_checkout(self.source, None)

        self.assertIn("--ref", str(raised.exception))
        self.assertEqual(git(self.source, "rev-parse", "HEAD"), self.start)

    def test_unpushed_commit_on_branch_is_refused(self) -> None:
        """Ветка с коммитом, которого нет в origin: отказ, ветка и HEAD на месте."""
        git(self.source, "config", "user.name", "Test")
        git(self.source, "config", "user.email", "test@example.invalid")
        (self.source / "local.txt").write_text("local\n", encoding="utf-8")
        git(self.source, "add", ".")
        git(self.source, "commit", "-q", "-m", "test: local work")
        local = git(self.source, "rev-parse", "HEAD")

        with self.assertRaises(SourceCheckoutError) as raised:
            update_source_checkout(self.source, None)

        self.assertIn("not on origin", str(raised.exception))
        self.assertEqual(git(self.source, "rev-parse", "HEAD"), local)
        self.assertEqual(git(self.source, "symbolic-ref", "--short", "HEAD"), "main")

    def test_directory_inside_another_repository_is_refused(self) -> None:
        """Каталог внутри чужого репозитория не считается checkout харнесса."""
        nested = self.source / "vendored-harness"
        nested.mkdir()

        with self.assertRaises(SourceCheckoutError) as raised:
            update_source_checkout(nested, None)

        self.assertIn("not the top of a git checkout", str(raised.exception))
        self.assertEqual(git(self.source, "rev-parse", "HEAD"), self.start)

    def test_invalid_branch_name_is_refused(self) -> None:
        """--ref с недопустимым именем ветки (refspec) отклоняется до fetch."""
        with self.assertRaises(SourceCheckoutError) as raised:
            update_source_checkout(self.source, "main:evil")

        self.assertIn("not a branch name", str(raised.exception))
        self.assertEqual(
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.source),
                    "rev-parse",
                    "--verify",
                    "-q",
                    "refs/heads/evil",
                ],
                check=False,
            ).returncode,
            1,
        )


if __name__ == "__main__":
    unittest.main()
