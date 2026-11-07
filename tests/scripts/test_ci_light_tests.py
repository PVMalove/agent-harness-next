#!/usr/bin/env python3
"""Tests for scripts/ci_light_tests.py (issue #937): the light CI job runs the tests of the pull
request's own diff, selected by ``ticket_diff_selection`` (issue #935), and nothing wider.

Real Git repositories and a real pytest run in a temporary directory; no mocks.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import subprocess
import sys
import tempfile
import types
import unittest
from collections.abc import Sequence
from contextlib import redirect_stdout
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ci_light_tests.py"
CRATE = "native/harness-runtime/crates/state"
PASSING = "def test_value():\n    assert True\n"
FAILING = "def test_value():\n    assert False\n"


def _load() -> types.ModuleType:
    loader = importlib.machinery.SourceFileLoader(
        "ci_light_tests_under_test", str(SCRIPT)
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


light = _load()


class Repo:
    """A throwaway repository with a ``master`` branch and a helper to commit files."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.git("init", "-b", "master")
        self.git("config", "user.email", "ci@example.test")
        self.git("config", "user.name", "ci")

    def git(self, *args: str) -> str:
        done = subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True,
            text=True,
            check=True,
        )
        return done.stdout.strip()

    def commit(self, files: dict[str, str], message: str = "change") -> str:
        for name, text in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-m", message)
        return self.git("rev-parse", "HEAD")


class LightTestsCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.repo = Repo(Path(directory.name))
        self.base = self.repo.commit(
            {
                "services/x.py": "VALUE = 1\n",
                "tests/test_related.py": "import services.x\n\n" + PASSING,
                f"{CRATE}/Cargo.toml": '[package]\nname = "state"\nversion = "0.1.0"\n',
                f"{CRATE}/src/lib.rs": "pub fn value() -> u8 { 1 }\n",
                "native/harness-runtime/Cargo.toml": "[workspace]\n",
            },
            "base",
        )
        self.repo.git("checkout", "-b", "feature")


class SelectionTests(LightTestsCase):
    def test_only_the_tests_of_the_diff_are_selected_never_the_related_ones(
        self,
    ) -> None:
        head = self.repo.commit(
            {"services/x.py": "VALUE = 2\n", "tests/test_new.py": PASSING}
        )

        selection = light.select(self.repo.root, self.base, head)

        self.assertEqual(selection.python_tests, ("tests/test_new.py",))
        self.assertEqual(
            light.commands(selection, "python"),
            [["python", "-m", "pytest", "-q", "tests/test_new.py"]],
        )

    def test_a_changed_crate_selects_its_cargo_target_with_a_locked_lockfile(
        self,
    ) -> None:
        head = self.repo.commit({f"{CRATE}/src/lib.rs": "pub fn value() -> u8 { 2 }\n"})

        selection = light.select(self.repo.root, self.base, head)

        self.assertEqual(
            light.commands(selection, "python"),
            [
                [
                    "cargo",
                    "test",
                    "--locked",
                    "--manifest-path",
                    "native/harness-runtime/Cargo.toml",
                    "-p",
                    "state",
                    "--lib",
                ]
            ],
        )

    def test_python_tests_run_before_the_cargo_targets(self) -> None:
        head = self.repo.commit(
            {
                "tests/test_new.py": PASSING,
                f"{CRATE}/tests/contract.rs": "#[test]\nfn t() {}\n",
            }
        )

        selection = light.select(self.repo.root, self.base, head)

        names = [command[0] for command in light.commands(selection, "python")]
        self.assertEqual(names, ["python", "cargo"])
        self.assertIn("--test", light.commands(selection, "python")[1])

    def test_a_diff_without_tests_selects_nothing_and_never_widens(self) -> None:
        head = self.repo.commit({"services/x.py": "VALUE = 3\n", "README.md": "text\n"})

        selection = light.select(self.repo.root, self.base, head)

        self.assertTrue(selection.empty)
        self.assertEqual(light.commands(selection, "python"), [])

    def test_the_diff_starts_at_the_merge_base_not_at_the_moved_base(self) -> None:
        head = self.repo.commit({"tests/test_mine.py": PASSING})
        self.repo.git("checkout", "master")
        moved = self.repo.commit({"tests/test_theirs.py": PASSING}, "master moved")
        self.repo.git("checkout", "feature")

        selection = light.select(self.repo.root, moved, head)

        self.assertEqual(selection.python_tests, ("tests/test_mine.py",))


class ExecuteTests(unittest.TestCase):
    def test_every_command_runs_and_one_failure_fails_the_job(self) -> None:
        seen: list[Sequence[str]] = []
        codes = iter([1, 0])

        def runner(command: Sequence[str], cwd: Path) -> int:
            seen.append(command)
            return next(codes)

        status = light.execute([["a"], ["b"]], Path("."), runner)

        self.assertEqual(status, 1)
        self.assertEqual(seen, [["a"], ["b"]])

    def test_all_passing_commands_pass(self) -> None:
        self.assertEqual(light.execute([["a"]], Path("."), lambda *_: 0), 0)

    def test_pytest_without_a_collected_test_is_a_notice_not_a_failure(self) -> None:
        # The default run deselects the docker_smoke and podman_smoke markers: a file of only
        # those collects nothing (pytest exit code 5). Another command never gets this reading.
        pytest_command = [sys.executable, "-m", "pytest", "-q", "tests/test_smoke.py"]
        output = io.StringIO()

        with redirect_stdout(output):
            self.assertEqual(
                light.execute([pytest_command], Path("."), lambda *_: 5), 0
            )
            self.assertEqual(
                light.execute([["cargo", "test"]], Path("."), lambda *_: 5), 5
            )

        self.assertIn("no test was collected", output.getvalue())


class MainTests(LightTestsCase):
    def run_main(self, base: str, head: str) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output):
            status = light.main(
                ["--repo", str(self.repo.root), "--base", base, "--head", head]
            )
        return status, output.getvalue()

    def test_a_passing_test_of_the_diff_passes_the_job(self) -> None:
        head = self.repo.commit({"tests/test_new.py": PASSING})

        status, output = self.run_main(self.base, head)

        self.assertEqual(status, 0, output)
        self.assertIn("tests/test_new.py", output)

    def test_a_failing_test_of_the_diff_fails_the_job(self) -> None:
        head = self.repo.commit({"tests/test_new.py": FAILING})

        status, output = self.run_main(self.base, head)

        self.assertNotEqual(status, 0, output)

    def test_a_failing_related_test_outside_the_diff_is_not_run(self) -> None:
        self.repo.git("checkout", "master")
        self.base = self.repo.commit({"tests/test_related.py": FAILING}, "broken")
        self.repo.git("checkout", "-B", "feature")
        head = self.repo.commit({"tests/test_new.py": PASSING})

        status, output = self.run_main(self.base, head)

        self.assertEqual(status, 0, output)
        self.assertNotIn("test_related", output)

    def test_a_diff_without_tests_passes_and_says_so(self) -> None:
        head = self.repo.commit({"README.md": "text\n"})

        status, output = self.run_main(self.base, head)

        self.assertEqual(status, 0)
        self.assertIn("no tests in diff", output)

    def test_an_unknown_base_fails_closed(self) -> None:
        head = self.repo.commit({"tests/test_new.py": PASSING})

        with self.assertRaises(SystemExit) as raised:
            self.run_main("0" * 40, head)

        self.assertIn("merge-base", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
