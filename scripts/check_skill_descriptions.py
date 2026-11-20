#!/usr/bin/env python3
# Copyright (c) 2026 Malov Pavel (p.malove@yandex.ru)
# SPDX-License-Identifier: BUSL-1.1
# Licensed under the Business Source License 1.1 (BSL-1.1).
# Commercial use, sale, or use in commercial application development is strictly
# prohibited without prior written permission from the copyright holder.
# Removing or altering this header is prohibited and voids all license rights.

"""Read-only format check of first-party and global skill descriptions.

Every `skills/first-party/*/*/SKILL.md` and `global-skills/*/SKILL.md` must pass rules F1-F5: a
frontmatter with a matching `name` and a single-line `description` (F1), at most
`DESCRIPTION_LIMIT` characters (F2), a sentence with an invocation condition (F3), a boundary - a
refusal or a neighbour skill named as `/<skill>` (F4), and an invocation policy that agrees with
`agents/openai.yaml` (F5). F6 compares the first-party description totals in `skills/REGISTRY.md`
with two budgets. Vendor skills are out of scope: only their names are read, so that F4 recognises
a vendor neighbour. The check never rewrites a file.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DESCRIPTION_LIMIT = 500
# Budgets of F6. Raising one is a deliberate, reviewable edit of this constant.
# Model-invoked first-party descriptions load into every session; 1445 is their total at
# 38789a0f (docs/tasks/release-skills-audit-epic-closeout/baseline.md, before the audit 1398).
MODEL_INVOKED_BUDGET = 1445
# All first-party rows of skills/REGISTRY.md: 3348 before the skills audit (9bbaa9e5^), 5452 at
# 38789a0f, 5566 after the epic #846 description rewrites; #1249 adds the 225 characters of the
# first-party setup-matt-pocock-skills override, whose vendor row was not counted.
REGISTRY_BUDGET = 5791

INVOCATION_START = re.compile(
    r"^(?:Use|Run)(?:\s+(?:it|this skill))?\s+"
    r"(?:when|whenever|explicitly|directly|before|after|between|once|only|for|on)\b"
)
REFUSAL = re.compile(
    r"\b(?:not|never|without|instead|rather than)\b|n't", re.IGNORECASE
)
SENTENCE_BREAK = re.compile(r"(?<=[.;])\s+")
REGISTRY_ROW = re.compile(
    r"^\| `(?P<name>[^`]+)` \| `(?P<path>skills/first-party/[^`]+)` \| (?P<description>.*) \|$"
)
FIELD = re.compile(r"^(?P<key>[A-Za-z][A-Za-z0-9_-]*):[ \t]*(?P<value>.*?)[ \t]*$")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _skill_files(root: Path) -> list[Path]:
    return sorted(
        [
            *(root / "skills" / "first-party").glob("*/*/SKILL.md"),
            *(root / "global-skills").glob("*/SKILL.md"),
        ]
    )


def _skill_names(root: Path) -> set[str]:
    """Names a description may cite as a neighbour, vendor skills included."""
    names = {path.parent.name for path in _skill_files(root)}
    names.update(
        path.parent.name for path in (root / "skills" / "vendor").rglob("SKILL.md")
    )
    return names


def _frontmatter(text: str) -> list[str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    return text[4:end].split("\n")


def _fields(lines: list[str]) -> dict[str, tuple[str, bool]]:
    """Map each top-level key to its raw value and whether indented continuation lines follow."""
    fields: dict[str, tuple[str, bool]] = {}
    for index, line in enumerate(lines):
        match = FIELD.match(line)
        if match is None:
            continue
        following = lines[index + 1] if index + 1 < len(lines) else ""
        continued = following[:1] in (" ", "\t") and bool(following.strip())
        fields[match["key"]] = (match["value"], continued)
    return fields


def _unquote(value: str) -> str | None:
    """Strip matching quotes; None for an unterminated quoted scalar."""
    if value[:1] in ("'", '"'):
        if len(value) < 2 or value[-1] != value[0]:
            return None
        return value[1:-1]
    return value


def _description(raw: str, continued: bool) -> str | None:
    """Return the single-line description value, or None when F1 rejects its form."""
    if continued or not raw or raw[0] in (">", "|"):
        return None
    value = _unquote(raw)
    return value if value and value.strip() else None


def _has_condition(description: str) -> bool:
    return any(
        INVOCATION_START.match(sentence.strip())
        for sentence in SENTENCE_BREAK.split(description)
    )


def _cites_neighbour(description: str, own: str, names: set[str]) -> bool:
    for name in names - {own}:
        escaped = re.escape(name)
        if re.search(rf"(?<![A-Za-z0-9./-])/{escaped}(?![A-Za-z0-9-])", description):
            return True
        if f"`{name}`" in description:
            return True
    return False


def _codex_policy(skill_dir: Path) -> tuple[bool, bool]:
    """Return (block policy sets allow_implicit_invocation: false, any false setting is present)."""
    path = skill_dir / "agents" / "openai.yaml"
    if not path.is_file():
        return False, False
    text = _text(path)
    anywhere = re.search(r"allow_implicit_invocation:\s*false\b", text) is not None
    policy = re.search(r"(?m)^policy[ \t]*:[ \t]*(?:#.*)?$", text)
    if policy is None:
        return False, anywhere
    body = text[policy.end() :]
    boundary = re.search(r"(?m)^\S", body)
    block = body[: boundary.start()] if boundary else body
    in_block = re.search(r"(?m)^[ \t]+allow_implicit_invocation:[ \t]*false\b", block)
    return in_block is not None, anywhere


def _model_invoked(skill_md: Path) -> bool:
    lines = _frontmatter(_text(skill_md)) if skill_md.is_file() else None
    if lines is None:
        return True
    raw = _fields(lines).get("disable-model-invocation", ("", False))[0]
    return _unquote(raw) != "true"


def skill_problems(root: Path, path: Path, names: set[str]) -> list[str]:
    """Rules F1-F5 for one SKILL.md."""
    relative = path.relative_to(root).as_posix()
    lines = _frontmatter(_text(path))
    if lines is None:
        return [f"{relative}: F1 missing frontmatter"]
    fields = _fields(lines)
    problems: list[str] = []
    directory = path.parent.name
    name = _unquote(fields.get("name", ("", False))[0]) or ""
    if name != directory:
        problems.append(
            f"{relative}: F1 name '{name}' does not match directory '{directory}'"
        )
    description = _description(*fields.get("description", ("", False)))
    if description is None:
        problems.append(
            f"{relative}: F1 description must be a non-empty single-line value; "
            "scripts/build_registry.py reads one line only"
        )
    else:
        if len(description) > DESCRIPTION_LIMIT:
            problems.append(
                f"{relative}: F2 description has {len(description)} characters; "
                f"the limit is {DESCRIPTION_LIMIT}"
            )
        if not _has_condition(description):
            problems.append(
                f"{relative}: F3 description has no invocation condition; add a sentence such as "
                '"Use when …", "Use explicitly after /<skill> …" or "Run once …"'
            )
        if not REFUSAL.search(description) and not _cites_neighbour(
            description, directory, names
        ):
            problems.append(
                f'{relative}: F4 description has no boundary; add "not for …", "never …", '
                "or name the neighbour skill as /<skill>"
            )
    problems.extend(_policy_problems(relative, path.parent, fields))
    return problems


def _policy_problems(
    relative: str, skill_dir: Path, fields: dict[str, tuple[str, bool]]
) -> list[str]:
    """Rule F5: disable-model-invocation agrees with agents/openai.yaml."""
    in_block, anywhere = _codex_policy(skill_dir)
    if "disable-model-invocation" not in fields:
        if anywhere:
            return [
                f"{relative}: F5 agents/openai.yaml sets allow_implicit_invocation: false "
                "but SKILL.md lacks disable-model-invocation: true"
            ]
        return []
    value = _unquote(fields["disable-model-invocation"][0])
    if value != "true":
        return [
            f"{relative}: F5 disable-model-invocation must be true or absent, got '{value}'"
        ]
    if not in_block:
        return [
            f"{relative}: F5 disable-model-invocation: true requires agents/openai.yaml "
            "with policy.allow_implicit_invocation: false"
        ]
    return []


def registry_totals(root: Path) -> tuple[int, int] | None:
    """Return (all first-party, model-invoked first-party) description totals of the registry."""
    registry = root / "skills" / "REGISTRY.md"
    if not registry.is_file():
        return None
    total = model_invoked = 0
    for line in _text(registry).split("\n"):
        match = REGISTRY_ROW.match(line)
        if match is None:
            continue
        length = len(match["description"].replace("\\|", "|"))
        total += length
        if _model_invoked(root / match["path"] / "SKILL.md"):
            model_invoked += length
    return total, model_invoked


def budget_problems(totals: tuple[int, int] | None) -> list[str]:
    """Rule F6: both first-party totals stay within their budgets."""
    if totals is None:
        return [
            "skills/REGISTRY.md: F6 registry is missing; run scripts/build_registry.py"
        ]
    total, model_invoked = totals
    problems = []
    if total > REGISTRY_BUDGET:
        problems.append(
            f"skills/REGISTRY.md: F6 first-party descriptions total {total} characters; "
            f"the budget is {REGISTRY_BUDGET}"
        )
    if model_invoked > MODEL_INVOKED_BUDGET:
        problems.append(
            f"skills/REGISTRY.md: F6 model-invoked first-party descriptions total "
            f"{model_invoked} characters; the budget is {MODEL_INVOKED_BUDGET}"
        )
    return problems


def check(root: Path) -> tuple[list[str], int, tuple[int, int] | None]:
    """Return every problem under `root`, the number of checked skills, and the registry totals."""
    names = _skill_names(root)
    skills = _skill_files(root)
    problems = [
        problem for path in skills for problem in skill_problems(root, path, names)
    ]
    totals = registry_totals(root)
    problems.extend(budget_problems(totals))
    return problems, len(skills), totals


def main() -> int:
    """Check the repository at ROOT and return a process exit code."""
    problems, count, totals = check(ROOT)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print(f"skill-descriptions: {len(problems)} problem(s)", file=sys.stderr)
        return 1
    assert totals is not None
    total, model_invoked = totals
    print(
        f"skill-descriptions: ok ({count} skills; first-party {total}/{REGISTRY_BUDGET}, "
        f"model-invoked {model_invoked}/{MODEL_INVOKED_BUDGET} characters)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
