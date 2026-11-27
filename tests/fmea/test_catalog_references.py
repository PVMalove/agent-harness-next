"""Shared FMEA catalog checks: code references and the recovery test of every entry (ADR 0041)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from harness.fmea.catalog import FIELDS, FmeaEntry, load_catalog
from harness.fmea.ids import FmeaId

ROOT = Path(__file__).resolve().parents[2]
IDS_MODULE = ROOT / "harness" / "fmea" / "ids.py"
ENTRIES = load_catalog()


def _python_files(*directories: str) -> list[Path]:
    return sorted(
        path
        for directory in directories
        for path in (ROOT / directory).rglob("*.py")
        if path != IDS_MODULE
    )


def _fmea_references(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "FmeaId"
    }


def _is_fmea_marker(decorator: ast.expr) -> bool:
    return ast.unparse(decorator) == "pytest.mark.fmea"


def _fmea_tests(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and any(_is_fmea_marker(decorator) for decorator in node.decorator_list)
    }


def test_every_fmea_reference_in_code_is_in_the_catalog() -> None:
    unknown = {
        f"{path.relative_to(ROOT)}: FmeaId.{name}"
        for path in _python_files("harness", "scripts")
        for name in _fmea_references(path)
        if name not in FmeaId.__members__
    }

    assert not unknown, sorted(unknown)


@pytest.mark.parametrize("entry", ENTRIES, ids=[entry.title for entry in ENTRIES])
def test_every_catalog_entry_names_an_existing_fmea_recovery_test(entry: FmeaEntry) -> None:
    values = {name: getattr(entry, name) for name in FIELDS}
    assert all(values.values()), [name for name, value in values.items() if not value]

    path, separator, function = values["test"].partition("::")
    assert separator and path and function and "::" not in function, values["test"]
    test_file = ROOT / path
    assert test_file.is_file(), path
    assert function in _fmea_tests(test_file), values["test"]


def test_every_fmea_marked_test_is_named_by_a_catalog_entry() -> None:
    named = {entry.test for entry in ENTRIES}
    orphans = {
        f"{path.relative_to(ROOT).as_posix()}::{function}"
        for path in _python_files("tests")
        for function in _fmea_tests(path)
    } - named

    assert not orphans, sorted(orphans)
