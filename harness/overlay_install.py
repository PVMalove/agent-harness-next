# Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
# SPDX-License-Identifier: BUSL-1.1
# Licensed under the Business Source License 1.1 (BSL-1.1).
# Commercial use, sale, or use in commercial application development is strictly
# prohibited without prior written permission from the copyright holder.
# Removing or altering this header is prohibited and voids all license rights.

"""Preview or apply an authored JSON or YAML workflow overlay manifest."""

from __future__ import annotations

import importlib
from pathlib import Path

from harness.configuration import (
    parse_object,
    read_config_bundle,
    read_limited,
    reject_secrets,
)
from harness.configuration_store import ConfigurationStore, json_bytes
from harness.json_types import JsonObject
from harness.orchestration.config_boundary import inspect_configuration
from harness.orchestration.workflow_overlays import resolve_config


def read_manifest(path: Path) -> JsonObject:
    content = read_limited(path)
    if content is None:
        raise ValueError(f"missing manifest: {path}")
    if path.suffix.lower() not in {".yaml", ".yml"}:
        return parse_object(content, path.name)
    try:
        yaml = importlib.import_module("yaml")
    except ModuleNotFoundError as exc:
        raise ValueError(
            "YAML import needs PyYAML; JSON manifests work without it"
        ) from exc

    def unique_mapping(loader: object, node: object) -> JsonObject:
        pairs = getattr(loader, "construct_pairs")(node, deep=True)
        mapping: JsonObject = {}
        for key, value in pairs:
            if not isinstance(key, str) or key in mapping:
                raise ValueError("YAML mappings need unique string keys")
            mapping[key] = value
        return mapping

    loader = type("OverlayLoader", (yaml.SafeLoader,), {})
    getattr(loader, "add_constructor")(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
    )
    try:
        if any(isinstance(event, yaml.AliasEvent) for event in yaml.parse(content)):
            raise ValueError("YAML aliases are unsupported")
        document = yaml.load(content, Loader=loader)
        if not isinstance(document, dict):
            raise ValueError("YAML manifest must contain a mapping")
        return document
    except (yaml.YAMLError, RecursionError) as exc:
        raise ValueError("invalid YAML manifest") from exc


def workflow_overlays(repo: Path, manifest: Path | None, *, apply: bool) -> JsonObject:
    bundle = read_config_bundle(repo)
    raw = bundle["orchestration.json"]
    document = parse_object(raw, "orchestration.json") if raw is not None else {}
    if manifest is not None:
        supplied = read_manifest(manifest)
        if set(supplied) != {"overlays"}:
            raise ValueError("workflow overlay manifest requires an overlays field")
        reject_secrets(supplied)
        document["workflow_overlays"] = supplied["overlays"]
    slots = resolve_config(document)
    if manifest is not None:
        desired = json_bytes(document)
        result = inspect_configuration(repo, desired)
        if not result.valid:
            raise ValueError(
                "invalid orchestration configuration: "
                + "; ".join(
                    diagnostic.message
                    for diagnostic in result.diagnostics
                    if diagnostic.severity == "error"
                )
            )
        if apply and raw != desired:
            ConfigurationStore(repo).apply(
                {"orchestration.json": desired}, expected=bundle
            )
    return {"schema_version": 1, "slots": slots}
