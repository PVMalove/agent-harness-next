"""Read-only proposals to connect project-owned entry points to the installed agent contract."""

from __future__ import annotations

import difflib
import re
from pathlib import Path


RULES_POINTER = (
    "Runtime rules are in `.claude/rules/*.md`. Claude Code loads them automatically. Codex does not\n"
    "load that directory: at the start of every session, read each file in\n"
    "[.claude/rules/](.claude/rules/) and follow it as a mandatory rule.\n"
)

# Paths that moved in #1249, in application order: the Technical English contract became a runtime
# rule, and the seed guides moved from `docs/agents/` to `.harness/instructions/`. The guide pattern
# matches only a path start (optionally after `../`), so `site/docs/agents/` stays as it is.
MOVED_LINKS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\.harness/instructions/technical-english\.md"),
        ".claude/rules/technical-english.md",
    ),
    (re.compile(r"(?<![\w./-])((?:\.\./)*)docs/agents/"), r"\1.harness/instructions/"),
)


def _active(text: str) -> str:
    """Drop fenced code: examples there are not active entry-point instructions."""
    return re.sub(r"```.*?```|~~~.*?~~~", "", text, flags=re.DOTALL)


def agents_rules_pointer(text: str) -> bool:
    """Whether AGENTS.md text points Codex at `.claude/rules/` outside fenced code."""
    return ".claude/rules" in _active(text)


def rewrite_moved_links(text: str) -> str:
    """Replace the paths that moved in #1249 with their installed targets."""
    for pattern, replacement in MOVED_LINKS:
        text = pattern.sub(replacement, text)
    return text


def propose_contract_links(repo: Path, templates: Path) -> list[dict[str, str]]:
    """Return one reviewable diff per project-owned entry point; never write a file.

    A diff rewrites links to moved paths and adds the Codex pointer to `.claude/rules/` when
    AGENTS.md lacks it. Entry points: AGENTS.md, CLAUDE.md and the installed seed agents."""
    entries = [repo / "AGENTS.md", repo / "CLAUDE.md"]
    entries.extend(
        repo / ".claude/agents" / template.name
        for template in sorted((templates / "agents").glob("*.md"))
        if (repo / ".claude/agents" / template.name).is_file()
    )
    proposals = []
    for path in entries:
        original = path.read_text(encoding="utf-8") if path.is_file() else ""
        adapted = rewrite_moved_links(original)
        reasons: list[str] = []
        if adapted != original:
            reasons.append(
                "Links point to moved paths: docs/agents/ is now .harness/instructions/, "
                "Technical English is now .claude/rules/technical-english.md."
            )
        # AGENTS.md is the Codex entry point; Codex does not load .claude/rules/ itself.
        if path.name == "AGENTS.md" and path.parent == repo and not agents_rules_pointer(original):
            adapted += (
                ""
                if not adapted or adapted.endswith("\n\n")
                else "\n"
                if adapted.endswith("\n")
                else "\n\n"
            ) + RULES_POINTER
            reasons.append("No Codex read pointer to the runtime rules in .claude/rules/ was found.")
        if not reasons:
            continue
        relative = path.relative_to(repo).as_posix()
        # One diff per file: two diffs of one file do not apply one after the other.
        diff = f"diff --git a/{relative} b/{relative}\n" + "".join(
            line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
            for line in difflib.unified_diff(
                original.splitlines(keepends=True),
                adapted.splitlines(keepends=True),
                fromfile=f"a/{relative}" if path.exists() else "/dev/null",
                tofile=f"b/{relative}",
            )
        )
        proposals.append({"path": relative, "reason": " ".join(reasons), "diff": diff})
    return proposals


def print_contract_proposals(proposals: list[dict[str, str]]) -> None:
    """Keep explanations before the patch so the complete trailing diff is reviewable."""
    if not proposals:
        return
    print(
        "\nSeed entry points: review and explicitly approve these changes before applying them by edit/patch."
    )
    print(
        "The CLI has not changed these project-owned files; --force-seed-files is not needed."
    )
    for proposal in proposals:
        print(f"  {proposal['path']}: {proposal['reason']}")
    for proposal in proposals:
        print(proposal["diff"], end="")
