"""SQLite-файл каталога FMEA и `harness fmea show` (ADR 0041)."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from harness.bin import harness as harness_cli
from harness.fmea import db as fmea_db
from harness.fmea.catalog import FmeaEntry, parse_catalog
from harness.fmea.db import FmeaDbError, build_db, find_entry
from scripts import fmea_catalog

GUID_A = "0b6f2a4e-3c1d-4e8a-9f2b-7d5c1a2b3c4d"
GUID_B = "5a1e9c3b-7f2d-4b6a-8c0e-1d2f3a4b5c6d"

CATALOG = f"""
[[failure_mode]]
id = "{GUID_A}"
title = "git-timeout"
mode = "git does not answer"
detection = "subprocess timeout"
recovery = "retry after checking the network"
test = "tests/core/test_git.py::test_timeout"
residual_risk = "a hung credential helper"

[[failure_mode]]
id = "{GUID_B}"
title = "bad-config"
mode = "config is not JSON"
detection = "json.JSONDecodeError"
recovery = "fix the file"
test = "tests/core/test_config.py::test_bad_json"
residual_risk = "none"
"""

GIT_TIMEOUT = FmeaEntry(
    id=GUID_A,
    title="git-timeout",
    mode="git does not answer",
    detection="subprocess timeout",
    recovery="retry after checking the network",
    test="tests/core/test_git.py::test_timeout",
    residual_risk="a hung credential helper",
)


def test_a_built_file_finds_an_entry_by_title(tmp_path: Path) -> None:
    db = tmp_path / "fmea.db"

    build_db(parse_catalog(CATALOG, "fixture"), db)

    assert find_entry("git-timeout", db) == GIT_TIMEOUT


def test_a_built_file_finds_an_entry_by_id(tmp_path: Path) -> None:
    db = tmp_path / "fmea.db"

    build_db(parse_catalog(CATALOG, "fixture"), db)

    assert find_entry(GUID_A, db) == GIT_TIMEOUT


def test_a_rebuild_of_the_same_catalog_gives_the_same_bytes(tmp_path: Path) -> None:
    db = tmp_path / "fmea.db"
    build_db(parse_catalog(CATALOG, "fixture"), db)
    first = db.read_bytes()

    build_db(parse_catalog(CATALOG, "fixture"), db)

    assert db.read_bytes() == first
    assert sorted(path.name for path in tmp_path.iterdir()) == ["fmea.db"]


def test_a_rebuild_drops_entries_removed_from_the_catalog(tmp_path: Path) -> None:
    db = tmp_path / "fmea.db"
    build_db(parse_catalog(CATALOG, "fixture"), db)

    build_db(parse_catalog("", "empty"), db)

    with pytest.raises(FmeaDbError):
        find_entry("git-timeout", db)


def test_a_corrupt_file_asks_to_rebuild_it(tmp_path: Path) -> None:
    db = tmp_path / "fmea.db"
    db.write_bytes(b"not a database")

    with pytest.raises(FmeaDbError) as error:
        find_entry("git-timeout", db)

    assert str(db) in error.value.message
    assert "python scripts/fmea_catalog.py db" in error.value.remedy


def test_a_build_into_an_unwritable_place_fails_with_a_remedy(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")

    with pytest.raises(FmeaDbError) as error:
        build_db(parse_catalog(CATALOG, "fixture"), blocker / "fmea.db")

    assert "cannot build FMEA database" in error.value.message
    assert error.value.remedy


@pytest.mark.parametrize("key", ["no-such-mode", GUID_B], ids=["title", "id"])
def test_an_unknown_key_in_an_empty_catalog_names_the_key_and_a_remedy(
    tmp_path: Path, key: str
) -> None:
    db = tmp_path / "fmea.db"
    build_db(parse_catalog("# comments only\n", "empty"), db)

    with pytest.raises(FmeaDbError) as error:
        find_entry(key, db)

    assert key in error.value.message
    assert "harness/fmea/catalog.toml" in error.value.remedy


def test_a_missing_file_asks_to_build_it(tmp_path: Path) -> None:
    db = tmp_path / "fmea.db"

    with pytest.raises(FmeaDbError) as error:
        find_entry("git-timeout", db)

    assert str(db) in error.value.message
    assert "python scripts/fmea_catalog.py db" in error.value.remedy
    assert not db.exists()


def test_the_build_script_writes_the_file_from_a_catalog(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.toml"
    catalog.write_text(CATALOG, encoding="utf-8")
    db = tmp_path / ".harness" / "fmea.db"

    code = fmea_catalog.main(["db", "--catalog", str(catalog), "--db", str(db)])

    assert code == 0
    assert find_entry("git-timeout", db) == GIT_TIMEOUT


def test_the_build_script_leaves_no_file_for_an_invalid_catalog(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    catalog = tmp_path / "catalog.toml"
    catalog.write_text("[[failure_mode]]\nid = 1\n", encoding="utf-8")
    db = tmp_path / "out.db"

    code = fmea_catalog.main(["db", "--catalog", str(catalog), "--db", str(db)])

    assert code == 2
    assert "REMEDY:" in capsys.readouterr().err
    assert not db.exists()


@pytest.fixture
def installed_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "fmea.db"
    build_db(parse_catalog(CATALOG, "fixture"), db)
    monkeypatch.setattr(fmea_db, "DB_PATH", db)
    return db


def run_cli(monkeypatch: pytest.MonkeyPatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["harness", *argv])
    return harness_cli.main()


@pytest.mark.parametrize("key", ["git-timeout", GUID_A], ids=["title", "id"])
def test_fmea_show_prints_the_entry(
    installed_db: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    key: str,
) -> None:
    code = run_cli(monkeypatch, "fmea", "show", key)

    assert code == 0
    assert capsys.readouterr().out == (
        f"FMEA: {GUID_A} (git-timeout)\n"
        "mode: git does not answer\n"
        "detection: subprocess timeout\n"
        "recovery: retry after checking the network\n"
        "test: tests/core/test_git.py::test_timeout\n"
        "residual_risk: a hung credential helper\n"
    )


def test_fmea_show_reports_an_unknown_key_with_a_remedy(
    installed_db: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = run_cli(monkeypatch, "fmea", "show", "no-such-mode")

    assert code == 2
    err = capsys.readouterr().err
    assert "ERROR: no FMEA entry with title or id 'no-such-mode'" in err
    assert "REMEDY: " in err


def test_fmea_show_without_a_built_file_asks_to_build_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(fmea_db, "DB_PATH", tmp_path / "fmea.db")

    code = run_cli(monkeypatch, "fmea", "show", "git-timeout")

    assert code == 2
    assert "REMEDY: build it from harness/fmea/catalog.toml" in capsys.readouterr().err


ROOT = Path(__file__).resolve().parents[2]


def _imported_modules(path: Path) -> set[str]:
    package = path.parent.relative_to(ROOT).parts
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), str(path))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = package[: len(package) - node.level + 1] if node.level else ()
            module = ".".join([*base, *([node.module] if node.module else [])])
            modules.add(module)
            modules.update(f"{module}.{alias.name}" for alias in node.names)
    return modules


def test_only_the_query_command_and_the_build_script_read_the_database() -> None:
    sources = [
        *ROOT.joinpath("harness").rglob("*.py"),
        *ROOT.joinpath("scripts").rglob("*.py"),
    ]

    readers = sorted(
        path.relative_to(ROOT).as_posix()
        for path in sources
        if "harness.fmea.db" in _imported_modules(path)
    )

    assert readers == ["harness/bin/harness.py", "scripts/fmea_catalog.py"]


def test_the_database_file_is_ignored_by_git() -> None:
    relative = fmea_db.DB_PATH.relative_to(ROOT).as_posix()

    result = subprocess.run(
        ["git", "-C", str(ROOT), "check-ignore", "-q", "--no-index", relative],
        check=False,
    )

    assert result.returncode == 0


def test_the_database_file_lies_outside_the_runtime_package() -> None:
    assert not fmea_db.DB_PATH.is_relative_to(ROOT / "harness")
