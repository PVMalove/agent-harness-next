"""SQLite-файл каталога FMEA только для чтения и запросов (ADR 0041).

Файл собирается из `harness/fmea/catalog.toml` командой `python scripts/fmea_catalog.py db`, не
коммитится и не участвует в обработке ошибок: ошибки читают каталог напрямую.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Sequence
from contextlib import closing, suppress
from pathlib import Path

from harness.errors import HarnessError
from harness.fmea.catalog import CATALOG_PATH, FIELDS, TABLE, FmeaEntry

# Вне runtime-пакета `harness/`: файл не меняет `harness_runtime_sha256` закреплённого батча.
DB_PATH = CATALOG_PATH.parents[2] / ".harness" / "fmea.db"
BUILD_COMMAND = "python scripts/fmea_catalog.py db"


class FmeaDbError(HarnessError):
    """SQLite-файл FMEA не собран, не читается или не содержит запрошенной записи."""


def build_db(entries: Sequence[FmeaEntry], db: Path) -> None:
    """Собрать SQLite-файл из записей каталога заново; одинаковый каталог даёт одинаковые байты."""
    temporary = db.with_name(f"{db.name}.tmp")
    columns = ", ".join(FIELDS)
    try:
        db.parent.mkdir(parents=True, exist_ok=True)
        temporary.unlink(missing_ok=True)
        with closing(sqlite3.connect(temporary)) as connection:
            connection.execute(
                f"CREATE TABLE {TABLE} ("
                + ", ".join(f"{name} TEXT NOT NULL" for name in FIELDS)
                + ", UNIQUE (id), UNIQUE (title))"
            )
            connection.executemany(
                f"INSERT INTO {TABLE} ({columns}) VALUES ({', '.join('?' for _ in FIELDS)})",
                [tuple(getattr(item, name) for name in FIELDS) for item in entries],
            )
            connection.commit()
        os.replace(temporary, db)
    except (OSError, sqlite3.Error) as error:
        with suppress(OSError):
            temporary.unlink(missing_ok=True)
        raise FmeaDbError(
            f"cannot build FMEA database {db}: {error}",
            remedy="make the directory of the file writable and run the build again",
        ) from error


def find_entry(key: str, db: Path) -> FmeaEntry:
    """Найти запись по `title` или `id`."""
    if not db.is_file():
        raise FmeaDbError(
            f"FMEA database {db} does not exist",
            remedy=f"build it from harness/fmea/catalog.toml with `{BUILD_COMMAND}`",
        )
    try:
        with closing(
            sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
        ) as connection:
            row = connection.execute(
                f"SELECT {', '.join(FIELDS)} FROM {TABLE} WHERE title = ? OR id = ?",
                (key, key),
            ).fetchone()
    except sqlite3.Error as error:
        raise FmeaDbError(
            f"cannot read FMEA database {db}: {error}",
            remedy=f"rebuild the file with `{BUILD_COMMAND}`",
        ) from error
    if row is None:
        raise FmeaDbError(
            f"no FMEA entry with title or id {key!r} in {db}",
            remedy="pass a title or id listed in harness/fmea/catalog.toml; if the catalog lists it, "
            f"rebuild the file with `{BUILD_COMMAND}`",
        )
    return FmeaEntry(**dict(zip(FIELDS, row, strict=True)))
