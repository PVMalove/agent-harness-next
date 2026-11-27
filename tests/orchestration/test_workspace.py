#!/usr/bin/env python3
"""Regression tests for coordinator workspace invariants."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from harness.orchestration.core import config, workspace
from harness.orchestration.core.workspace import (
    _harness_runtime_sha256,
    _runtime_matches,
    _runtime_tree_sha256,
)


class HarnessRuntimeSnapshotTests(unittest.TestCase):
    def test_hash_ignores_generated_bytecode_and_state(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            runtime = Path(temporary) / ".harness" / "orchestration"
            runtime.mkdir(parents=True)
            source = runtime / "runner.py"
            source.write_text("VALUE = 1\n", encoding="utf-8")

            initial = _harness_runtime_sha256(Path(temporary))
            pycache = runtime / "__pycache__"
            pycache.mkdir()
            (pycache / "runner.cpython-312.pyc").write_bytes(b"first bytecode")
            state = runtime / "state"
            state.mkdir()
            (state / "ledger.json").write_text("{}", encoding="utf-8")

            self.assertEqual(_harness_runtime_sha256(Path(temporary)), initial)

            (pycache / "runner.cpython-312.pyc").write_bytes(b"changed bytecode")
            self.assertEqual(_harness_runtime_sha256(Path(temporary)), initial)

            source.write_text("VALUE = 2\n", encoding="utf-8")
            self.assertNotEqual(_harness_runtime_sha256(Path(temporary)), initial)

    def test_pin_covers_every_runtime_package_and_accepts_legacy_pins(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            repo = Path(temporary)
            package = repo / ".harness"
            (package / "orchestration").mkdir(parents=True)
            (package / "orchestration" / "runner.py").write_text(
                "A = 1\n", encoding="utf-8"
            )
            (package / "gate_runner").mkdir()
            (package / "gate_runner" / "__init__.py").write_text("", encoding="utf-8")
            gate = package / "gate_runner" / "gate.py"
            gate.write_text("B = 1\n", encoding="utf-8")
            (package / "skills").mkdir()
            skill = package / "skills" / "SKILL.md"
            skill.write_text("not runtime\n", encoding="utf-8")
            pinned = _harness_runtime_sha256(repo)
            legacy = _runtime_tree_sha256(package / "orchestration")

            skill.write_text("still not runtime\n", encoding="utf-8")
            self.assertTrue(_runtime_matches(repo, pinned))

            gate.write_text("B = 2\n", encoding="utf-8")
            self.assertFalse(_runtime_matches(repo, pinned))
            # A batch planned while the pin covered orchestration/ alone keeps its meaning.
            self.assertTrue(_runtime_matches(repo, legacy))


class GitIgnoredRuntimeFilesTests(unittest.TestCase):
    """A source checkout keeps git-ignored files (node_modules, build output) out of the pin."""

    def _checkout(self, root: Path, gitignore: str) -> Path:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / ".gitignore").write_text(gitignore, encoding="utf-8")
        package = root / ".harness"
        (package / "orchestration").mkdir(parents=True)
        (package / "orchestration" / "runner.py").write_text(
            "A = 1\n", encoding="utf-8"
        )
        (package / "console").mkdir()
        (package / "console" / "__init__.py").write_text("", encoding="utf-8")
        return package

    def _add_node_modules(self, package: Path) -> None:
        modules = package / "console" / "frontend" / "node_modules" / "tool"
        modules.mkdir(parents=True)
        (modules / "SKILL.md").write_text("vendored\n", encoding="utf-8")

    def test_git_ignored_files_change_neither_the_pin_nor_the_snapshot(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            repo = Path(temporary) / "repo"
            package = self._checkout(repo, "node_modules/\n")
            pinned = _harness_runtime_sha256(repo)

            self._add_node_modules(package)
            snapshot = workspace._store_runtime_snapshot(
                Path(temporary) / "state", package, pinned
            )

            self.assertEqual(_harness_runtime_sha256(repo), pinned)
            self.assertEqual(list((snapshot / "harness").rglob("SKILL.md")), [])
            self.assertTrue(
                (snapshot / "harness" / "orchestration" / "runner.py").is_file()
            )

    def test_an_untracked_module_that_git_does_not_ignore_stays_in_the_pin(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            repo = Path(temporary) / "repo"
            package = self._checkout(repo, "node_modules/\n")
            pinned = _harness_runtime_sha256(repo)

            (package / "console" / "new_module.py").write_text(
                "B = 1\n", encoding="utf-8"
            )

            self.assertNotEqual(_harness_runtime_sha256(repo), pinned)

    def test_an_installed_runtime_ignored_as_a_whole_still_counts_every_file(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            repo = Path(temporary) / "repo"
            package = self._checkout(repo, ".harness/\n")
            tracked = package / "console" / "__init__.py"
            subprocess.run(
                ["git", "-C", str(repo), "add", "-f", str(tracked)], check=True
            )
            pinned = _harness_runtime_sha256(repo)

            (package / "orchestration" / "runner.py").write_text(
                "A = 2\n", encoding="utf-8"
            )

            self.assertNotEqual(_harness_runtime_sha256(repo), pinned)


class RoleManifestSourceTests(unittest.TestCase):
    def test_roles_come_from_the_running_runtime(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            repo = Path(temporary) / "repo"
            (repo / ".harness" / "orchestration" / "roles").mkdir(parents=True)
            pinned = Path(temporary) / "snapshot" / "orchestration"
            (pinned / "roles").mkdir(parents=True)

            with mock.patch.object(
                workspace, "_runtime_snapshot_root", return_value=pinned
            ):
                self.assertEqual(config._roles_dir(repo), pinned / "roles")
            self.assertEqual(
                config._roles_dir(repo), repo / ".harness" / "orchestration" / "roles"
            )


if __name__ == "__main__":
    unittest.main()
