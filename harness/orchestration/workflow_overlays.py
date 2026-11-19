# Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
# SPDX-License-Identifier: BUSL-1.1
# Licensed under the Business Source License 1.1 (BSL-1.1).
# Commercial use, sale, or use in commercial application development is strictly
# prohibited without prior written permission from the copyright holder.
# Removing or altering this header is prohibited and voids all license rights.

"""Deterministic composition of project contributions to named verification slots."""

from __future__ import annotations

import re
from collections.abc import Mapping

SLOTS = ("post-developer", "pre-review", "qa-preparation", "pre-qa")
# A QA slot edits the configuration list of its stage, so each stage keeps one list of commands.
CONFIG_KEYS = {"qa-preparation": "qa_preparation", "pre-qa": "pre_qa_commands"}
OPERATIONS = ("append", "prepend", "replace", "remove")
_ID = re.compile(r"[a-z][a-z0-9-]{0,63}")


def resolve_config(config: Mapping[str, object]) -> dict[str, list[str]]:
    """Resolve the overlays of a configuration; each QA slot starts from its configuration key."""
    base: dict[str, list[str]] = {}
    for slot, key in CONFIG_KEYS.items():
        commands = config.get(key, [])
        if not isinstance(commands, list) or any(
            not isinstance(command, str) for command in commands
        ):
            raise ValueError(f"{key} must be a list of strings")
        base[slot] = commands
    return resolve_slots(config.get("workflow_overlays", []), base)


def resolve_slots(
    value: object, base: Mapping[str, list[str]] | None = None
) -> dict[str, list[str]]:
    slots = {slot: list((base or {}).get(slot, [])) for slot in SLOTS}
    if not isinstance(value, list) or len(value) > 64:
        raise ValueError("workflow_overlays must be a list of at most 64 overlays")
    seen: set[str] = set()
    ordered: list[tuple[int, str, list[tuple[str, str, list[str]]]]] = []
    for index, overlay in enumerate(value):
        label = f"workflow_overlays[{index}]"
        if not isinstance(overlay, dict) or set(overlay) - {
            "id",
            "priority",
            "enabled",
            "edits",
        }:
            raise ValueError(f"{label} has invalid fields")
        identifier = overlay.get("id")
        if (
            not isinstance(identifier, str)
            or not _ID.fullmatch(identifier)
            or identifier in seen
        ):
            raise ValueError(f"{label}.id must be a unique lowercase identifier")
        seen.add(identifier)
        priority, enabled = overlay.get("priority", 10), overlay.get("enabled", True)
        if type(priority) is not int or not isinstance(enabled, bool):
            raise ValueError(f"{label} needs integer priority and boolean enabled")
        edits = overlay.get("edits")
        if not isinstance(edits, list) or not 1 <= len(edits) <= 64:
            raise ValueError(f"{label}.edits needs 1 to 64 entries")
        validated = []
        for edit in edits:
            if not isinstance(edit, dict) or set(edit) - {
                "slot",
                "operation",
                "commands",
            }:
                raise ValueError(f"{label} has an invalid edit")
            slot, operation = edit.get("slot"), edit.get("operation")
            if slot not in SLOTS or operation not in OPERATIONS:
                raise ValueError(f"{label} edit needs a known slot and operation")
            commands = edit.get("commands", [])
            if (
                not isinstance(commands, list)
                or len(commands) > 32
                or any(
                    not isinstance(command, str) or not command.strip()
                    for command in commands
                )
                or (operation == "remove") != (not commands)
            ):
                raise ValueError(f"{label} edit requires commands except for remove")
            validated.append((slot, operation, commands))
        if enabled:
            ordered.append((-priority, identifier, validated))

    for _, _, edits in sorted(ordered):
        for slot, operation, commands in edits:
            if operation == "append":
                slots[slot].extend(commands)
            elif operation == "prepend":
                slots[slot][:0] = commands
            else:
                slots[slot] = list(commands)
    return slots
