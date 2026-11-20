# Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
# SPDX-License-Identifier: BUSL-1.1
# Licensed under the Business Source License 1.1 (BSL-1.1).
# Commercial use, sale, or use in commercial application development is strictly
# prohibited without prior written permission from the copyright holder.
# Removing or altering this header is prohibited and voids all license rights.


"""Render project-owned lifecycle events into native runtime settings."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from harness.configuration import reject_secrets
from harness.configuration_store import _atomic, _lock, _unlock
from harness.health.runtime_contract import (
    CANONICAL_EVENTS,
    NATIVE_ADAPTERS,
    NativeAdapter,
)
from harness.json_types import JsonObject

MANIFEST = Path(".harness/runtime-events.json")
OWNERSHIP = Path(".harness/runtime-events.lock.json")
SYNC_LOCK = Path(".harness/.sandboxes/runtime-events/sync.lock")


def adapter_inventory() -> list[JsonObject]:
    return [asdict(adapter) for adapter in NATIVE_ADAPTERS]


def _path(repo: Path, relative: Path) -> Path:
    for part in reversed((relative, *relative.parents[:-1])):
        path = repo / part
        if path.is_symlink() or path.is_junction():
            raise ValueError(f"runtime events refuse linked path: {part}")
    return repo / relative


def _read(path: Path, default: JsonObject) -> JsonObject:
    if not path.exists():
        return default
    if not path.is_file():
        raise ValueError(f"{path.name} must be a regular file")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _write(path: Path, value: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic(
        path, (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )


def _fingerprint(event: str, entry: object) -> str:
    data = json.dumps([event, entry], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _manifest(repo: Path) -> tuple[list[str], dict[str, list[str]]]:
    manifest = _read(_path(repo, MANIFEST), {})
    runtimes = manifest.get("runtimes", [])
    events = manifest.get("events", {})
    if (
        set(manifest) - {"runtimes", "events"}
        or not isinstance(runtimes, list)
        or any(
            runtime not in [adapter.runtime for adapter in NATIVE_ADAPTERS]
            for runtime in runtimes
        )
        or not isinstance(events, dict)
        or set(events) - set(CANONICAL_EVENTS)
    ):
        raise ValueError("runtime-events.json has unknown runtimes, events or fields")
    for commands in events.values():
        if not isinstance(commands, list) or any(
            not isinstance(command, str) or not command.strip() for command in commands
        ):
            raise ValueError(
                "runtime event commands must be a list of non-empty strings"
            )
    reject_secrets(manifest)
    return runtimes, events


def _render(
    adapter: NativeAdapter,
    document: JsonObject,
    events: dict[str, list[str]],
    previous: set[str],
) -> tuple[JsonObject, set[str]]:
    hooks = document.get("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"{adapter.config} hooks must be an object")
    result = dict(hooks)
    owned: set[str] = set()
    for canonical, native in adapter.events.items():
        entries = hooks.get(native, [])
        if not isinstance(entries, list):
            raise ValueError(f"{adapter.config} hooks.{native} must be a list")
        wanted = {
            command: adapter.hook(command) for command in events.get(canonical, [])
        }
        wanted_ids = {_fingerprint(native, entry) for entry in wanted.values()}
        present: set[str] = set()
        merged = []
        for entry in entries:
            digest = _fingerprint(native, entry)
            if (
                digest in previous
                and digest not in wanted_ids
                and digest not in present
            ):
                present.add(digest)
                continue
            if digest in previous and digest in wanted_ids:
                owned.add(digest)
            present.add(digest)
            merged.append(entry)
        configured_commands = {
            command for entry in merged for command in adapter.commands(entry)
        }
        for command, entry in wanted.items():
            digest = _fingerprint(native, entry)
            if command not in configured_commands:
                merged.append(entry)
                owned.add(digest)
        if merged:
            result[native] = merged
        elif entries:
            result.pop(native, None)
    native_config = {**document, "hooks": result}
    if adapter.flat_hooks:
        native_config.setdefault("version", 1)
    return native_config, owned


def owned_configs(repo: Path) -> dict[str, str]:
    """Native config of every runtime that holds Harness-written lifecycle entries."""
    ownership = _read(_path(repo, OWNERSHIP), {})
    return {
        adapter.runtime: adapter.config
        for adapter in NATIVE_ADAPTERS
        if ownership.get(adapter.runtime)
    }


def _sync(repo: Path, *, release: bool) -> list[str]:
    runtimes, events = ([], {}) if release else _manifest(repo)
    ownership_path = _path(repo, OWNERSHIP)
    baseline = _read(ownership_path, {})
    changes = []
    next_ownership: JsonObject = {}
    journal = dict(baseline)
    for adapter in NATIVE_ADAPTERS:
        previous = baseline.get(adapter.runtime, [])
        if not isinstance(previous, list) or any(
            not isinstance(value, str) for value in previous
        ):
            raise ValueError("invalid runtime events ownership record")
        desired = events if adapter.runtime in runtimes else {}
        if not previous and not any(desired.values()):
            continue
        path = _path(repo, Path(adapter.config))
        default = {"version": 1} if adapter.flat_hooks else {}
        before = _read(path, default)
        document, owned = _render(adapter, before, desired, set(previous))
        if before != document and (path.exists() or owned):
            changes.append((path, document, {**default, "hooks": {}}))
        if owned:
            next_ownership[adapter.runtime] = sorted(owned)
            journal[adapter.runtime] = sorted(set(previous) | owned)
    # Keep old and new fingerprints until all files are written, so a retry can finish a
    # partially applied installation or removal without claiming an existing user entry.
    if journal != baseline:
        _write(ownership_path, journal)
    for path, document, empty in changes:
        # A config left with only an empty hooks object holds no setting, so it is removed.
        if document == empty:
            path.unlink(missing_ok=True)
        else:
            _write(path, document)
    if next_ownership != journal:
        _write(ownership_path, next_ownership)
    return [path.relative_to(repo).as_posix() for path, _, _ in changes]


def sync(repo: Path, *, release: bool = False) -> list[str]:
    """Render the manifest into native configs; `release` removes every owned entry instead.

    Either way an entry Harness did not write, or that the user changed, stays in place.
    """
    lock_path = _path(repo, SYNC_LOCK)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("ab+") as stream:
        _lock(stream)
        try:
            return _sync(repo, release=release)
        finally:
            _unlock(stream)
