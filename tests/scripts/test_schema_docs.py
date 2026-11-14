"""Сверка публичных листовых полей и значений схем со справочником."""

import json
from pathlib import Path

import pytest

from scripts.verification import schema_docs

from scripts.verification.schema_docs import (
    SCHEMA_PAGES,
    documented_paths,
    missing_fields,
    missing_values,
    schema_fields,
)


def test_nested_fields_and_local_refs() -> None:
    schema: dict[str, object] = {
        "properties": {
            "tracker": {"properties": {"type": {"enum": ["github", "local"]}}},
            "plans": {"additionalProperties": {"$ref": "#/definitions/plan"}},
        },
        "definitions": {"plan": {"properties": {"transport": {"const": "external"}}}},
    }
    assert schema_fields(schema) == {
        "tracker.type": {"github", "local"},
        "plans.<ключ>.transport": {"external"},
    }


def test_arrays_scalar_dictionaries_and_defaults() -> None:
    assert schema_fields(
        {
            "properties": {
                "stages": {
                    "items": {"properties": {"kind": {"enum": ["lint", "pytest"]}}}
                },
                "modes": {
                    "additionalProperties": {"enum": ["read", "write"]},
                    "propertyNames": {"enum": ["developer", "review"]},
                },
                "enabled": {"default": False},
                "limits": {"type": "object", "default": {"size": 1}},
            }
        }
    ) == {
        "stages[].kind": {"lint", "pytest"},
        "modes": {"read", "write", "developer", "review"},
        "enabled": {"false"},
        "limits": set(),
    }


def test_only_exact_inline_paths_count(tmp_path: Path) -> None:
    page = tmp_path / "page.md"
    page.write_text('tracker.type in prose; `tracker`\n```json\n"tracker.type"\n```\n')
    schema: dict[str, object] = {
        "properties": {"tracker": {"properties": {"type": {"type": "string"}}}}
    }
    assert missing_fields((page,), schema) == ["tracker.type"]
    page.write_text("`tracker.type`")
    assert documented_paths((page,)) == {"tracker.type"}
    assert missing_fields((page,), schema) == []


def test_values_must_be_on_a_page_documenting_the_field(tmp_path: Path) -> None:
    page, other = tmp_path / "a.md", tmp_path / "b.md"
    page.write_text("`mode` `manual` `count` `1`")
    other.write_text("`auto`")
    schema: dict[str, object] = {
        "properties": {"mode": {"enum": ["manual", "auto"]}, "count": {"default": 1}}
    }
    assert missing_values((page, other), schema) == ["mode: auto"]
    page.write_text("`mode` `manual` `auto` `count` `1`")
    assert missing_values((page, other), schema) == []


def test_refs_are_reused_and_cycles_terminate() -> None:
    schema: dict[str, object] = {
        "properties": {
            "a": {"$ref": "#/definitions/item"},
            "b": {"$ref": "#/definitions/item"},
        },
        "definitions": {
            "item": {
                "properties": {
                    "name": {"type": "string"},
                    "next": {"$ref": "#/definitions/item"},
                }
            }
        },
    }
    assert schema_fields(schema) == {"a.name": set(), "b.name": set()}


def test_real_schemas_are_documented() -> None:
    for schema, pages in SCHEMA_PAGES.items():
        assert missing_fields(pages, schema) == []
        assert missing_values(pages, schema) == []


def test_dictionary_ref_to_scalar_array_remains_a_leaf() -> None:
    schema: dict[str, object] = {
        "properties": {
            "tools": {"additionalProperties": {"$ref": "#/definitions/toolList"}}
        },
        "definitions": {"toolList": {"type": "array", "items": {"type": "string"}}},
    }
    assert schema_fields(schema) == {"tools": set()}


def test_check_fails_with_actionable_field_and_value_messages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    schema, page = tmp_path / "schema.json", tmp_path / "page.md"
    schema.write_text(json.dumps({"properties": {"mode": {"enum": ["auto"]}}}))
    page.write_text("No description yet.")
    monkeypatch.setattr(schema_docs, "SCHEMA_PAGES", {schema: (page,)})
    with pytest.raises(SystemExit) as exc:
        schema_docs.check_schema_docs()
    assert exc.value.code == 1
    assert capsys.readouterr().out.splitlines() == [
        "site: field without description: mode",
        "site: value not documented: mode: auto",
    ]
