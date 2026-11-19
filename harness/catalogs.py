"""Browse project catalog sources and load explicitly authorised pinned presets."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath
from typing import TypeGuard

from harness.configuration import (
    inside_project,
    parse_object,
    read_limited,
    reject_secrets,
)
from harness.json_types import JsonObject
from harness.presets import PRESET_ID

REGISTRY = Path(".harness/catalogs.json")
_SHA256 = re.compile(r"[0-9a-f]{64}")
ACCESS = ("discovery-only", "install-allowed")


def _relative(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not value or any(c in value for c in "\\:\0"):
        raise ValueError("catalog paths must be canonical relative JSON paths")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or str(path) != value
        or path.suffix != ".json"
    ):
        raise ValueError("catalog paths must be canonical relative JSON paths")
    return path


def _read(repo: Path, path: Path, *, optional: bool = False) -> bytes | None:
    safe = inside_project(repo, path)
    if safe.exists() and not safe.is_file():
        raise ValueError("catalog path must name a regular file")
    raw = read_limited(safe)
    if raw is None and not optional:
        raise ValueError(f"catalog file is missing: {safe.relative_to(repo)}")
    return raw


def _digest(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _id(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and PRESET_ID.fullmatch(value) is not None


def _sources(repo: Path) -> dict[str, JsonObject]:
    raw = _read(repo, repo / REGISTRY, optional=True)
    if raw is None:
        return {}
    registry = parse_object(raw, REGISTRY.name)
    sources = registry.get("sources")
    version = registry.get("schema_version", 1)
    if (
        set(registry) - {"schema_version", "sources"}
        or type(version) is not int
        or version != 1
        or not isinstance(sources, list)
        or len(sources) > 32
    ):
        raise ValueError(
            "catalog registry requires up to 32 sources under schema version 1"
        )
    reject_secrets(registry)
    result: dict[str, JsonObject] = {}
    for source in sources:
        if not isinstance(source, dict) or set(source) - {
            "id",
            "index",
            "access",
            "sha256",
        }:
            raise ValueError("catalog sources require id, index and access")
        identifier, access = source.get("id"), source.get("access")
        if not _id(identifier) or identifier in result or access not in ACCESS:
            raise ValueError("catalog source needs a unique id and known access mode")
        _relative(source.get("index"))
        if (access == "install-allowed" or "sha256" in source) and not _digest(
            source.get("sha256")
        ):
            raise ValueError(
                "an install-allowed source requires a pinned catalog SHA-256"
            )
        result[identifier] = source
    return result


def _entries(repo: Path, source: JsonObject) -> list[JsonObject]:
    path = repo / _relative(source["index"])
    raw = _read(repo, path)
    assert raw is not None
    if "sha256" in source and hashlib.sha256(raw).hexdigest() != source["sha256"]:
        raise ValueError(f"catalog SHA-256 mismatch: {source['id']}")
    index = parse_object(raw, path.name)
    rows = index.get("presets")
    if set(index) != {"presets"} or not isinstance(rows, list) or len(rows) > 256:
        raise ValueError("catalog index requires up to 256 preset records")
    reject_secrets(index)
    ids: set[str] = set()
    entries = []
    for entry in rows:
        if not isinstance(entry, dict) or set(entry) != {
            "id",
            "description",
            "file",
            "sha256",
        }:
            raise ValueError("catalog presets require id, description, file and sha256")
        identifier, description = entry["id"], entry["description"]
        if (
            not _id(identifier)
            or identifier in ids
            or not isinstance(description, str)
            or not description.strip()
            or len(description) > 300
            or not _digest(entry["sha256"])
        ):
            raise ValueError("invalid catalog preset metadata")
        _relative(entry["file"])
        ids.add(identifier)
        entries.append(entry)
    return entries


def list_catalogs(repo: Path, source_id: str | None = None) -> JsonObject:
    sources = _sources(repo)
    if source_id is not None:
        if source_id not in sources:
            raise ValueError(f"unknown catalog source: {source_id}")
        sources = {source_id: sources[source_id]}
    return {
        "schema_version": 1,
        "catalogs": [
            {
                "id": identifier,
                "access": source["access"],
                "presets": sorted(
                    _entries(repo, source), key=lambda entry: entry["id"]
                ),
            }
            for identifier, source in sorted(sources.items())
        ],
    }


def load_preset(repo: Path, source_id: str, preset_id: str) -> JsonObject:
    source = _sources(repo).get(source_id)
    if source is None:
        raise ValueError(f"unknown catalog source: {source_id}")
    if source["access"] != "install-allowed":
        raise ValueError(f"catalog source is discovery-only: {source_id}")
    entry = next(
        (item for item in _entries(repo, source) if item["id"] == preset_id), None
    )
    if entry is None:
        raise ValueError(f"unknown preset in catalog {source_id}")
    path = (repo / _relative(source["index"])).parent / _relative(entry["file"])
    raw = _read(repo, path)
    assert raw is not None
    if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError(f"preset SHA-256 mismatch: {preset_id}")
    preset = parse_object(raw, path.name)
    if preset.get("id") != preset_id:
        raise ValueError("preset id differs from the catalog entry")
    return preset
