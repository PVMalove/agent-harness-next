"""The installed developer skill every developer dispatch is told to read (#1161).

The path is resolved from the project checkout the coordinator was given (``--repo``), never from
this module or a pinned runtime snapshot: the skill is project installation state, outside the
hashed runtime package. The skill grants no authority: the brief and the developer role contract
stay authoritative, which the instruction itself says.
"""

from __future__ import annotations

import os
from pathlib import Path

from harness.json_types import JsonObject
from harness.orchestration.core.utils import CoordinatorError

DEVELOPER_SKILL_RELATIVE = ".harness/skills/developer/SKILL.md"

INSTRUCTION = (
    "Developer skill: read the installed developer skill {path} before implementation and apply "
    "its scope, test-first and evidence discipline. The immutable brief and the developer role "
    "contract stay authoritative for assignment, scope, commits and the completion report; the "
    "skill grants no path, tool or approval. If the file is missing or unreadable, stop before "
    "any edit with outcome blocked and name the path in blockers."
)


def developer_skill(repo: Path) -> JsonObject:
    """The installed skill's absolute path and the prompt line naming it; refuse when it is absent."""
    path = (repo / DEVELOPER_SKILL_RELATIVE).resolve()
    if not path.is_file() or not os.access(path, os.R_OK):
        raise CoordinatorError(
            f"the installed developer skill is missing: {path}",
            remedy="install or update the engineering-suite capability (harness install/update) "
            "in the main checkout, then repeat the same command; the dispatch is unchanged",
        )
    return {"path": str(path), "instruction": INSTRUCTION.format(path=path)}
