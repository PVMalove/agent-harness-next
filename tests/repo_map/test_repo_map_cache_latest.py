"""A cache entry of another commit is readable through the verified envelope only, for the
console's "stale for HEAD" card; the pinned read still refuses it."""

from __future__ import annotations

import json
from pathlib import Path

from harness.repo_map.cache import read_cache, read_cache_any_commit, write_cache
from tests.console._console_repo_map_fixture import map_payload


def _write(directory: Path, key: str, commit: str) -> str:
    payload = json.dumps(map_payload(commit))
    write_cache(directory, key, payload)
    return payload


def test_an_entry_of_another_commit_is_read_without_the_commit_pin(tmp_path: Path) -> None:
    payload = _write(tmp_path, "k1", "a" * 40)
    assert read_cache(tmp_path, "k1", "b" * 40) is None
    assert read_cache_any_commit(tmp_path, "k1") == payload


def test_a_corrupted_entry_is_refused_even_without_the_pin(tmp_path: Path) -> None:
    _write(tmp_path, "k1", "a" * 40)
    path = tmp_path / "k1.json"
    envelope = json.loads(path.read_text(encoding="utf-8"))
    envelope["payload"] = envelope["payload"].replace('"full"', '"minimal"', 1)
    path.write_text(json.dumps(envelope), encoding="utf-8")
    assert read_cache_any_commit(tmp_path, "k1") is None
    assert read_cache_any_commit(tmp_path, "missing") is None
