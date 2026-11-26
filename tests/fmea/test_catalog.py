"""Catalog parsing: format, empty catalog, id and title rules, enum member names (ADR 0041)."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.errors import HarnessError
from harness.fmea.catalog import (
    FmeaCatalogError,
    FmeaEntry,
    load_catalog,
    member_name,
    parse_catalog,
)

GUID_A = "0b6f2a4e-3c1d-4e8a-9f2b-7d5c1a2b3c4d"
GUID_B = "5a1e9c3b-7f2d-4b6a-8c0e-1d2f3a4b5c6d"
REAL_CATALOG = Path(__file__).resolve().parents[2] / "harness" / "fmea" / "catalog.toml"


def entry(guid: str = GUID_A, title: str = "git-timeout", **extra: str) -> str:
    fields = {
        "id": guid,
        "title": title,
        "mode": "Git hangs",
        "detection": "timeout",
        "recovery": "retry",
        "test": "tests/x.py::test_y",
        "residual_risk": "low",
        **extra,
    }
    body = "".join(f'{key} = "{value}"\n' for key, value in fields.items())
    return f"[[failure_mode]]\n{body}"


def parse(text: str) -> tuple[FmeaEntry, ...]:
    return parse_catalog(text, "catalog.toml")


def test_empty_text_is_an_empty_catalog() -> None:
    assert parse("") == ()


def test_comment_only_catalog_is_empty() -> None:
    assert parse("# header\n# more\n") == ()


def test_the_shipped_catalog_parses() -> None:
    assert isinstance(load_catalog(REAL_CATALOG), tuple)


def test_entries_keep_file_order_and_all_fields(tmp_path: Path) -> None:
    path = tmp_path / "catalog.toml"
    path.write_text(entry() + "\n" + entry(GUID_B, "lock-busy"), encoding="utf-8")

    entries = load_catalog(path)

    assert [item.title for item in entries] == ["git-timeout", "lock-busy"]
    assert entries[0] == FmeaEntry(
        id=GUID_A,
        title="git-timeout",
        mode="Git hangs",
        detection="timeout",
        recovery="retry",
        test="tests/x.py::test_y",
        residual_risk="low",
    )


def test_error_is_a_harness_error_with_remedy() -> None:
    with pytest.raises(HarnessError) as info:
        parse(entry(guid="nope"))
    assert isinstance(info.value, FmeaCatalogError)
    assert info.value.remedy


def test_invalid_toml_is_rejected() -> None:
    with pytest.raises(FmeaCatalogError, match="catalog.toml"):
        parse("[[failure_mode]\n")


def test_unknown_top_level_key_is_rejected() -> None:
    with pytest.raises(FmeaCatalogError, match="other"):
        parse('other = "x"\n' + entry())


def test_failure_mode_must_be_an_array_of_tables() -> None:
    with pytest.raises(FmeaCatalogError, match="failure_mode"):
        parse('failure_mode = "x"\n')


def test_unknown_entry_key_is_rejected() -> None:
    with pytest.raises(FmeaCatalogError, match=r"\[0\].*severity"):
        parse(entry(severity="high"))


def test_missing_entry_key_is_rejected() -> None:
    text = entry().replace('residual_risk = "low"\n', "")
    with pytest.raises(FmeaCatalogError, match="residual_risk"):
        parse(text)


def test_non_string_field_is_rejected() -> None:
    text = entry().replace('mode = "Git hangs"', "mode = 3")
    with pytest.raises(FmeaCatalogError, match=r"\[0\].*mode"):
        parse(text)


@pytest.mark.parametrize(
    "guid",
    [
        "not-a-uuid",
        "0b6f2a4e3c1d4e8a9f2b7d5c1a2b3c4d",  # valid UUID, not canonical form
        GUID_A.upper(),  # canonical only in lower case
        "0b6f2a4e-3c1d-1e8a-9f2b-7d5c1a2b3c4d",  # version 1
    ],
)
def test_id_must_be_a_canonical_uuid4(guid: str) -> None:
    with pytest.raises(FmeaCatalogError, match=r"\[0\].*id"):
        parse(entry(guid=guid))


def test_duplicate_id_is_rejected() -> None:
    with pytest.raises(FmeaCatalogError, match=r"\[1\].*id"):
        parse(entry() + entry(title="lock-busy"))


def test_duplicate_title_is_rejected() -> None:
    with pytest.raises(FmeaCatalogError, match=r"\[1\].*title"):
        parse(entry() + entry(GUID_B))


@pytest.mark.parametrize(
    "title", ["", "Git-timeout", "1git", "git timeout", "git--timeout", "git-", "git.timeout"]
)
def test_title_must_be_a_slug(title: str) -> None:
    with pytest.raises(FmeaCatalogError, match=r"\[0\].*title"):
        parse(entry(title=title))


@pytest.mark.parametrize(
    ("title", "name"),
    [("git-timeout", "GIT_TIMEOUT"), ("lock_busy", "LOCK_BUSY"), ("a1-b2_c3", "A1_B2_C3")],
)
def test_member_name_is_derived_from_title(title: str, name: str) -> None:
    assert member_name(title) == name
    assert member_name(title) == member_name(title)


def test_member_name_collision_is_rejected() -> None:
    with pytest.raises(FmeaCatalogError, match="GIT_TIMEOUT"):
        parse(entry() + entry(GUID_B, "git_timeout"))
