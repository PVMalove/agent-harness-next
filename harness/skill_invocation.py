# Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
# SPDX-License-Identifier: BUSL-1.1
# Licensed under the Business Source License 1.1 (BSL-1.1).
# Commercial use, sale, or use in commercial application development is strictly
# prohibited without prior written permission from the copyright holder.
# Removing or altering this header is prohibited and voids all license rights.


"""Render a managed skill's explicit-invocation policy for native skill loaders."""

import re
from collections.abc import Collection
from pathlib import Path

from harness.health.runtime_contract import CODEX_INVOCATION, FRONTMATTER_INVOCATION
from harness.json_types import JsonObject

CODEX_KEY = CODEX_INVOCATION.split(".")[-1]


def requested_skills(lock: JsonObject) -> set[str]:
    value = lock.get("explicit_invocation", [])
    if not isinstance(value, list) or any(
        not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name)
        for name in value
    ):
        raise ValueError(
            "harness.lock explicit_invocation must be a list of skill names"
        )
    return set(value)


def check_targets(repo: Path, selected: set[str], previous: Collection[str]) -> None:
    for name in sorted(selected):
        skill = Path(".harness/skills") / name
        codex = skill / "agents/openai.yaml"
        for relative in (codex, *codex.parents[:-1], skill / "SKILL.md"):
            target = repo / relative
            if target.is_symlink() or target.is_junction():
                raise ValueError(
                    f"explicit invocation refuses linked path: {relative.as_posix()}"
                )
        if (repo / codex).exists() and codex.as_posix() not in previous:
            raise ValueError(f"unmanaged Codex skill metadata: {codex.as_posix()}")


def restrict_frontmatter(original: bytes) -> bytes:
    text = original.decode("utf-8")
    match = re.match(r"\A---[ \t]*\r?\n(.*?)^---[ \t]*(?=\r?$)", text, re.M | re.S)
    if not match:
        raise ValueError("skill must begin with frontmatter")
    fields, count = re.subn(
        rf"(?m)^{FRONTMATTER_INVOCATION}:[^\r\n]*",
        f"{FRONTMATTER_INVOCATION}: true",
        match[1],
    )
    if not count:
        fields += f"{FRONTMATTER_INVOCATION}: true\n"
    return (text[: match.start(1)] + fields + text[match.end(1) :]).encode("utf-8")


def restrict_codex(original: bytes) -> bytes:
    text = original.decode("utf-8").replace("\r\n", "\n")
    policy = re.search(r"(?m)^policy\s*:[^\n]*$", text)
    if policy is None:
        prefix = text.rstrip()
        return (
            prefix + ("\n" if prefix else "") + f"policy:\n  {CODEX_KEY}: false\n"
        ).encode("utf-8")
    if policy.group().split(":", 1)[1].split("#", 1)[0].strip():
        raise ValueError("policy in agents/openai.yaml must use block mapping syntax")
    start = policy.end()
    boundary = re.search(r"(?m)^\S", text[start:])
    end = start + boundary.start() if boundary else len(text)
    body = text[start:end]
    body, count = re.subn(
        rf"(?m)^  {CODEX_KEY}:[^\n]*",
        f"  {CODEX_KEY}: false",
        body,
    )
    if not count:
        indentation = re.search(r"(?m)^( +)\w", body)
        indent = indentation.group(1) if indentation else "  "
        field = f"{indent}{CODEX_KEY}: false"
        body, count = re.subn(rf"(?m)^{indent}{CODEX_KEY}:[^\n]*", field, body)
        if not count:
            body = f"\n{field}\n" + body.lstrip("\n")
    return (text[:start] + body + text[end:]).encode("utf-8")
