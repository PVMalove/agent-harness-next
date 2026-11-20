"""The contract reads every worker prompt names, whatever the transport (#1249).

Claude Code loads the language rules from `.claude/rules/` by itself; a Codex or container worker
does not, and no runtime loads the role contract. The line names both, resolved from the project
checkout the coordinator was given (``--repo``). The stdlib-only adapters repeat this literal; a
parity test keeps the copies equal.
"""

from __future__ import annotations

ROLES_RELATIVE = ".harness/orchestration/roles"
RULES_RELATIVE = ".claude/rules"

INSTRUCTION = (
    "Contracts: before task work, read the common role contract {roles}/common.md and your role "
    "contract {roles}/{role}.md. Write English coordination text by {rules}/technical-english.md "
    "and Russian report text by {rules}/technical-russian.md."
)
