"""Runtime rules: delivery and worktree rules are seeded into `.claude/rules/`, the old guide
sections point there, and a fresh AGENTS.md gives Codex an explicit read pointer (ADR 0039)."""

from __future__ import annotations

from pathlib import Path

from tests.core.test_uninstall import git, harness

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "harness/project/rules"
INSTRUCTIONS = ROOT / "harness/project/instructions"
DELIVERY_RULES = (
    "Zero Direct Commits",
    "CLI Only",
    "Body via File, Not Inline",
    "Project-Only Metadata",
    "Issue First",
    "Zero Auto-Merge",
    "PR Confirmation Required",
)
CODEX_POINTER = "Codex does not\nload that directory: at the start of every session, read each file in\n[.claude/rules/](.claude/rules/)"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section_one(text: str) -> str:
    start = text.index("### 1. Fundamental Constraints & Tooling")
    return text[start : text.index("### 2. Workflow Sequence")]


def test_delivery_rules_live_in_the_runtime_rule_and_the_old_section_names_them() -> None:
    rule = _text(RULES / "git-delivery.md")
    pointer = _section_one(_text(INSTRUCTIONS / "git-workflow.md"))
    for name in DELIVERY_RULES:
        assert f"* **{name}:**" in rule, name
        assert f"* **{name}**" in pointer, name
    assert ".claude/rules/git-delivery.md" in pointer
    assert "Codex" in pointer and "AGENTS.md" in pointer
    assert "](./" not in rule
    assert "below" not in rule


def test_worktree_rules_live_in_the_runtime_rule_and_conventions_point_there() -> None:
    rule = _text(RULES / "worktree-conventions.md")
    guide = _text(INSTRUCTIONS / "worktrees.md")
    for marker in (
        "**A session that only provisions a worktree for someone else does not enter it.**",
        "**Never change tool configuration to make a worktree behave.**",
        "still applies inside a worktree**",
    ):
        assert marker in rule, marker
        assert marker not in guide, marker
    assert ".claude/rules/worktree-conventions.md" in guide
    for kept in ("**Branch naming still applies.**", "**Base ref**", "**Cleanup**"):
        assert kept in guide, kept


ISSUE_WORKTREE = ".harness/skills/implement/references/issue-worktree.md"


def _h2(text: str, heading: str) -> str:
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    return text[start:] if end < 0 else text[start:end]


def test_coordinator_issue_worktree_is_owned_by_the_implement_skill() -> None:
    guide = _text(INSTRUCTIONS / "worktrees.md")
    pointer = _h2(guide, "## Coordinator issue worktree")
    assert ISSUE_WORKTREE in pointer
    assert "worktree create --repo" not in guide
    assert "Session write access" not in guide.split("## Coordinator issue worktree")[0]
    assert "issue worktree that a coordinator" not in guide
    worker = _h2(guide, "## Worker checkout environment")
    assert "harness worktree-venv" in worker and "PLAYWRIGHT_BROWSERS_PATH" in worker
    rule = _text(RULES / "worktree-conventions.md")
    assert ISSUE_WORKTREE in rule
    assert "#coordinator-issue-worktree" not in rule


def test_runtime_rules_have_no_path_scope() -> None:
    for name in ("git-delivery.md", "worktree-conventions.md"):
        assert not _text(RULES / name).startswith("---"), name


def test_fresh_install_seeds_the_rules_and_points_codex_at_them(tmp_path: Path) -> None:
    repo = tmp_path / "project"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    result = harness("init", str(repo), "--capability", "engineering-suite")
    assert result.returncode == 0, result.stderr

    installed = {path.name for path in (repo / ".claude/rules").iterdir()}
    assert installed == {path.name for path in RULES.glob("*.md")}
    assert CODEX_POINTER in _text(repo / "AGENTS.md")
