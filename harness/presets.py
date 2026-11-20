# Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
# SPDX-License-Identifier: BUSL-1.1
# Licensed under the Business Source License 1.1 (BSL-1.1).
# Commercial use, sale, or use in commercial application development is strictly
# prohibited without prior written permission from the copyright holder.
# Removing or altering this header is prohibited and voids all license rights.

"""Apply a team preset as an explicit, backed-up change to project configuration."""

from __future__ import annotations

import re
from pathlib import Path

from harness.configuration import (
    Bundle,
    parse_object,
    read_config_bundle,
    reject_secrets,
)
from harness.configuration_schema import schema_problems
from harness.configuration_store import ConfigurationStore, json_bytes
from harness.health.project_files import validate_project_data
from harness.json_types import JsonObject
from harness.orchestration.config_boundary import inspect_configuration
from harness.orchestration.workflow_overlays import resolve_slots

PRESET_ID = re.compile(r"[a-z][a-z0-9-]{0,63}")
PROJECT_FIELDS = ("language", "qa_gate_commands", "pr_checklist")
LIST_FIELDS = ("qa_gate_commands", "pr_checklist")


def _with_overlays(current: object, proposed: object) -> list[JsonObject]:
    resolve_slots(current)
    resolve_slots(proposed)
    assert isinstance(current, list) and isinstance(proposed, list)
    effective = {item["id"]: item for item in current}
    for item in proposed:
        prior = effective.setdefault(item["id"], item)
        if prior != item:
            raise ValueError(
                f"preset overlay already exists with different content: {item['id']}"
            )
    combined = list(effective.values())
    resolve_slots(combined)
    return combined


def apply_preset(
    repo: Path, preset: JsonObject, available: set[str], *, apply: bool
) -> JsonObject:
    reject_secrets(preset)
    identifier = preset.get("id")
    if set(preset) - {"id", "requires", "project", "workflow_overlays"} or not (
        isinstance(identifier, str) and PRESET_ID.fullmatch(identifier)
    ):
        raise ValueError("preset requires an id and supported fields")
    requires = preset.get("requires", [])
    if not isinstance(requires, list) or any(
        not isinstance(item, str) for item in requires
    ):
        raise ValueError("preset requires must be a list of capability names")
    if missing := set(requires) - available:
        raise ValueError(
            f"preset needs installed capabilities: {', '.join(sorted(missing))}"
        )
    supplied = preset.get("project", {})
    if not isinstance(supplied, dict) or set(supplied) - set(PROJECT_FIELDS):
        raise ValueError(
            "preset project fields must be language, qa_gate_commands or pr_checklist"
        )
    bundle = read_config_bundle(repo)
    project = parse_object(bundle["project.json"] or b"{}", "project.json")
    if not project:
        raise ValueError("install Harness in the project before applying a preset")
    reject_secrets(project)
    effective = {**project, **supplied}
    for field in LIST_FIELDS:
        if field not in supplied:
            continue
        before, after = project.get(field, []), supplied[field]
        if any(
            not isinstance(values, list)
            or any(not isinstance(item, str) or not item.strip() for item in values)
            for values in (before, after)
        ):
            raise ValueError(f"{field} must be a list of non-empty strings")
        effective[field] = list(dict.fromkeys([*before, *after]))
    problems = schema_problems(repo, "project.json", effective)
    validate_project_data(effective, problems)
    if problems:
        raise ValueError("invalid project configuration: " + "; ".join(problems))

    changes: Bundle = {}
    if effective != project:
        changes["project.json"] = json_bytes(effective)
    if "workflow_overlays" in preset:
        raw = bundle["orchestration.json"]
        if raw is None:
            raise ValueError(
                "install backend-orchestration before adding workflow overlays"
            )
        config = parse_object(raw, "orchestration.json")
        overlays = _with_overlays(
            config.get("workflow_overlays", []), preset["workflow_overlays"]
        )
        if overlays != config.get("workflow_overlays", []):
            merged = json_bytes({**config, "workflow_overlays": overlays})
            inspection = inspect_configuration(repo, merged)
            if not inspection.valid:
                raise ValueError(
                    "preset would create an invalid orchestration configuration"
                )
            changes["orchestration.json"] = merged
    backup = None
    if apply and changes:
        backup = ConfigurationStore(repo).apply(changes, expected=bundle).id
    return {
        "schema_version": 1,
        "id": identifier,
        "files": sorted(changes),
        "backup": backup,
        "project": {field: effective[field] for field in supplied},
    }
