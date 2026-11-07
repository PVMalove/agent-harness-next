#!/usr/bin/env python3
"""Tests for scripts/check_license_headers.py: the core registry and the exact header match."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_license_headers.py"


def _load() -> types.ModuleType:
    loader = importlib.machinery.SourceFileLoader(
        "check_license_headers_under_test", str(SCRIPT)
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


headers = _load()


def _write(root: Path, relative: str, lines: list[str]) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class RepositoryRegistryTests(unittest.TestCase):
    def test_every_protected_file_carries_the_header(self) -> None:
        self.assertEqual([], headers.check(ROOT))

    def test_the_registry_is_consistent(self) -> None:
        self.assertEqual([], headers.registry_problems())
        for relative in headers.PROTECTED_FILES:
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())

    def test_both_languages_are_represented(self) -> None:
        suffixes = {Path(relative).suffix for relative in headers.PROTECTED_FILES}
        self.assertEqual({".py", ".rs"}, suffixes)

    def test_the_cli_reports_success_for_the_repository(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            code = headers.main(["--root", str(ROOT)])
        self.assertEqual(0, code)
        self.assertIn("License header check passed", output.getvalue())


class HeaderMatchTests(unittest.TestCase):
    def test_a_missing_header_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "harness/bin/harness.py", ['"""Entry point."""'])

            problems = headers.header_problems(root, "harness/bin/harness.py")

        self.assertEqual(["harness/bin/harness.py: missing license header"], problems)

    def test_a_missing_protected_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            problems = headers.header_problems(Path(tmp), "harness/bin/harness.py")

        self.assertEqual(
            ["harness/bin/harness.py: protected file is missing"], problems
        )

    def test_an_altered_line_is_reported_with_its_number(self) -> None:
        relative = "harness/bin/harness.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lines = list(headers.expected_lines(relative))
            lines[2] = "# Licensed under some other terms."
            _write(root, relative, [*lines, ""])

            problems = headers.header_problems(root, relative)

        self.assertEqual(1, len(problems))
        self.assertTrue(problems[0].startswith(f"{relative}:3: header line differs"))

    def test_a_truncated_header_is_reported(self) -> None:
        relative = "harness/bin/harness.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lines = list(headers.expected_lines(relative))[:3]
            _write(root, relative, lines)

            problems = headers.header_problems(root, relative)

        self.assertEqual(1, len(problems))
        self.assertTrue(problems[0].startswith(f"{relative}:4: header is truncated"))

    def test_a_header_after_a_shebang_is_accepted(self) -> None:
        relative = "harness/bin/harness.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lines = ["#!/usr/bin/env python3", *headers.expected_lines(relative), ""]
            _write(root, relative, lines)

            problems = headers.header_problems(root, relative)

        self.assertEqual([], problems)

    def test_rust_files_use_line_comments(self) -> None:
        lines = headers.expected_lines("native/harness-runtime/crates/state/src/lib.rs")
        self.assertEqual(
            "// Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)", lines[0]
        )
        self.assertEqual("// SPDX-License-Identifier: BUSL-1.1", lines[1])

    def test_the_cli_fails_for_a_directory_without_headers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            error = io.StringIO()
            with redirect_stderr(error), redirect_stdout(io.StringIO()):
                code = headers.main(["--root", tmp])

        self.assertEqual(1, code)
        self.assertIn("License header check failed", error.getvalue())


if __name__ == "__main__":
    unittest.main()
