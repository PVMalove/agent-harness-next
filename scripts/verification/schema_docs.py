"""Сверить листовые поля и допустимые значения JSON-схем со страницами настроек."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import cast

from scripts.verification.paths import ROOT, SITE_DOCS

SETTINGS = SITE_DOCS / "getting-started" / "settings"
SCHEMA_PAGES = {
    ROOT / "harness/project/project.schema.json": (SETTINGS / "project.md",),
    ROOT / "harness/orchestration/orchestration.schema.json": tuple(
        SETTINGS / "orchestration" / name
        for name in (
            "index.md",
            "roles.md",
            "policies.md",
            "access.md",
            "verification.md",
        )
    ),
}


def _object(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _scalar(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return json.dumps(value)
    return None


def _values(node: dict[str, object]) -> set[str]:
    values: list[object] = []
    enum = node.get("enum")
    if isinstance(enum, list):
        values.extend(enum)
    values.extend(node[key] for key in ("const", "default") if key in node)
    return {text for value in values if (text := _scalar(value)) is not None}


def schema_fields(schema: dict[str, object]) -> dict[str, set[str]]:
    """Развернуть локальные ссылки, массивы и словари, сохранив только листья."""
    found: dict[str, set[str]] = {}

    def walk(node: dict[str, object], path: str, refs: frozenset[str]) -> None:
        reference = node.get("$ref")
        if isinstance(reference, str):
            if not reference.startswith("#/"):
                raise ValueError(f"unsupported schema reference: {reference}")
            if reference in refs:
                return
            target: object = schema
            for segment in reference[2:].split("/"):
                target = _object(target)[segment.replace("~1", "/").replace("~0", "~")]
            walk(
                {**_object(target), **{k: v for k, v in node.items() if k != "$ref"}},
                path,
                refs | {reference},
            )
            return
        properties = _object(node.get("properties"))
        if properties:
            for name, child in properties.items():
                walk(_object(child), f"{path}.{name}" if path else name, refs)
            return
        items = _object(node.get("items"))
        if items and ("properties" in items or "$ref" in items):
            walk(items, path + "[]", refs)
            return
        additional = _object(node.get("additionalProperties"))
        shape = additional
        seen: set[str] = set()
        while isinstance(shape.get("$ref"), str):
            ref = str(shape["$ref"])
            if ref in seen or not ref.startswith("#/"):
                break
            seen.add(ref)
            target_shape: object = schema
            for part in ref[2:].split("/"):
                target_shape = _object(target_shape)[part]
            shape = _object(target_shape)
        if additional and "properties" in shape:
            walk(additional, path + ".<ключ>", refs)
            return
        if path:
            found.setdefault(path, set()).update(
                _values(node)
                | _values(additional)
                | _values(shape)
                | _values(_object(node.get("propertyNames")))
            )

    walk(schema, "", frozenset())
    return found


def _codes(page: Path) -> set[str]:
    """Читать inline-код, не принимая примеры JSON за описание полей."""
    text = re.sub(
        r"(?m)^\s*```[^\n]*\n.*?^\s*```[^\n]*$",
        "",
        page.read_text(encoding="utf-8"),
        flags=re.S,
    )
    return set(re.findall(r"(?<!`)`([^`\n]+)`(?!`)", text))


def documented_paths(pages: tuple[Path, ...]) -> set[str]:
    """Собрать точные имена, оформленные inline-кодом."""
    return set().union(*(_codes(page) for page in pages))


def _fields(schema: Path | dict[str, object]) -> dict[str, set[str]]:
    return (
        schema_fields(_object(json.loads(schema.read_text(encoding="utf-8"))))
        if isinstance(schema, Path)
        else schema_fields(schema)
    )


def missing_fields(
    pages: tuple[Path, ...], schema: Path | dict[str, object]
) -> list[str]:
    """Вернуть отсортированные пути без точного описания."""
    return sorted(set(_fields(schema)) - documented_paths(pages))


def missing_values(
    pages: tuple[Path, ...], schema: Path | dict[str, object]
) -> list[str]:
    """Искать значения лишь на страницах с соответствующим листовым полем."""
    codes = [_codes(page) for page in pages]
    return sorted(
        f"{path}: {value}"
        for path, values in _fields(schema).items()
        for value in values
        if not any(path in page and value in page for page in codes)
    )


def check_schema_docs() -> None:
    """Завершить проверку кодом 1 при расхождении документации со схемами."""
    issues: list[str] = []
    for schema, pages in SCHEMA_PAGES.items():
        issues.extend(
            f"site: field without description: {path}"
            for path in missing_fields(pages, schema)
        )
        issues.extend(
            f"site: value not documented: {value}"
            for value in missing_values(pages, schema)
        )
    if issues:
        print("\n".join(issues))
        sys.exit(1)


def main(argv: list[str] | None = None) -> int:
    """Запустить сверку из командной строки."""
    if argv:
        raise ValueError("schema_docs takes no arguments")
    check_schema_docs()
    print("site: schemas and settings pages agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
