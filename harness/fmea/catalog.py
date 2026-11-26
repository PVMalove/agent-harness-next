"""Разбор и проверка каталога FMEA `harness/fmea/catalog.toml` (ADR 0041).

Формат описан в шапке самого каталога. Модуль только читает каталог: генерацию `FmeaId` и
добавление записей выполняет build-time скрипт `scripts/fmea_catalog.py`.
"""

from __future__ import annotations

import re
import tomllib
import uuid
from dataclasses import dataclass, fields
from pathlib import Path

from harness.errors import HarnessError

CATALOG_PATH = Path(__file__).resolve().with_name("catalog.toml")
TABLE = "failure_mode"
TITLE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$")
FORMAT_REMEDY = "fix the catalog to match the format described in the header of harness/fmea/catalog.toml"


class FmeaCatalogError(HarnessError):
    """Каталог FMEA не соответствует формату или правилам `id`/`title`."""


@dataclass(frozen=True)
class FmeaEntry:
    """Одна запись каталога: режим отказа с постоянным GUID."""

    id: str
    title: str
    mode: str
    detection: str
    recovery: str
    test: str
    residual_risk: str


FIELDS = tuple(field.name for field in fields(FmeaEntry))


def member_name(title: str) -> str:
    """Имя члена `FmeaId` из `title`: верхний регистр, `-` заменяется на `_`."""
    return title.upper().replace("-", "_")


def load_catalog(path: Path = CATALOG_PATH) -> tuple[FmeaEntry, ...]:
    """Прочитать и проверить каталог из файла."""
    return parse_catalog(path.read_text(encoding="utf-8"), str(path))


def parse_catalog(text: str, source: str) -> tuple[FmeaEntry, ...]:
    """Разобрать текст каталога; записи возвращаются в порядке файла."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise FmeaCatalogError(f"{source}: invalid TOML: {error}", remedy=FORMAT_REMEDY) from error
    unknown = sorted(set(data) - {TABLE})
    if unknown:
        raise FmeaCatalogError(
            f"{source}: unknown top-level keys: {', '.join(unknown)}", remedy=FORMAT_REMEDY
        )
    tables = data.get(TABLE, [])
    if not isinstance(tables, list) or not all(isinstance(table, dict) for table in tables):
        raise FmeaCatalogError(
            f"{source}: {TABLE} must be an array of tables [[{TABLE}]]", remedy=FORMAT_REMEDY
        )
    entries: list[FmeaEntry] = []
    for index, table in enumerate(tables):
        entries.append(_parse_entry(table, f"{source}: {TABLE}[{index}]"))
    _check_unique(entries, source)
    return tuple(entries)


def _parse_entry(table: dict[str, object], where: str) -> FmeaEntry:
    unknown = sorted(set(table) - set(FIELDS))
    if unknown:
        raise FmeaCatalogError(f"{where}: unknown keys: {', '.join(unknown)}", remedy=FORMAT_REMEDY)
    values: dict[str, str] = {}
    for name in FIELDS:
        value = table.get(name)
        if not isinstance(value, str):
            raise FmeaCatalogError(
                f"{where}: field {name} must be a string", remedy=FORMAT_REMEDY
            )
        values[name] = value
    item = FmeaEntry(**values)
    if not _is_canonical_uuid4(item.id):
        raise FmeaCatalogError(
            f"{where}: field id {item.id!r} is not a canonical lower-case uuid4",
            remedy="never type an id by hand: add entries with `python scripts/fmea_catalog.py new <title>`",
        )
    if not TITLE_PATTERN.fullmatch(item.title):
        raise FmeaCatalogError(
            f"{where}: field title {item.title!r} does not match {TITLE_PATTERN.pattern}",
            remedy="use lower-case letters and digits separated by single '-' or '_'",
        )
    return item


def _is_canonical_uuid4(value: str) -> bool:
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        return False
    return str(parsed) == value and parsed.version == 4


def _check_unique(entries: list[FmeaEntry], source: str) -> None:
    ids: set[str] = set()
    titles: set[str] = set()
    members: dict[str, str] = {}
    for index, item in enumerate(entries):
        where = f"{source}: {TABLE}[{index}]"
        if item.id in ids:
            raise FmeaCatalogError(
                f"{where}: field id {item.id} is duplicated",
                remedy="give the entry a fresh id: re-add it with `python scripts/fmea_catalog.py new <title>`",
            )
        if item.title in titles:
            raise FmeaCatalogError(
                f"{where}: field title {item.title!r} is duplicated",
                remedy="choose a unique title",
            )
        name = member_name(item.title)
        if name in members:
            raise FmeaCatalogError(
                f"{where}: field title {item.title!r} gives FmeaId member {name}, "
                f"already used by title {members[name]!r}",
                remedy="choose a title whose member name differs from every other entry",
            )
        ids.add(item.id)
        titles.add(item.title)
        members[name] = item.title
