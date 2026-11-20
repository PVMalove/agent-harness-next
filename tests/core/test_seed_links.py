"""`propose_contract_links`: a project-owned entry point gets one reviewable diff that adds the
Codex read pointer to `.claude/rules/` and rewrites links to the paths moved in #1249."""

from __future__ import annotations

from pathlib import Path

from harness.seed_links import (
    RULES_POINTER,
    agents_rules_pointer,
    propose_contract_links,
    rewrite_moved_links,
)

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "harness/project"


def _repo(tmp_path: Path, agents: str) -> Path:
    (tmp_path / "AGENTS.md").write_text(agents, encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("# Claude Code\n\n@AGENTS.md\n", encoding="utf-8")
    return tmp_path


def _added(diff: str) -> str:
    return "".join(
        line[1:] + "\n"
        for line in diff.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )


def test_the_template_carries_the_proposed_pointer() -> None:
    template = (TEMPLATES / "AGENTS.md.tmpl").read_text(encoding="utf-8")
    assert RULES_POINTER in template
    assert agents_rules_pointer(template)


def test_a_pointer_inside_fenced_code_does_not_count() -> None:
    assert not agents_rules_pointer("# A\n\n```\nread .claude/rules/\n```\n")
    assert agents_rules_pointer("Read [rules](.claude/rules/).\n")


def test_agents_without_the_pointer_gets_one_proposal(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "# Local\n")

    proposals = propose_contract_links(repo, TEMPLATES)

    assert [p["path"] for p in proposals] == ["AGENTS.md"]
    assert "runtime rules in .claude/rules/" in proposals[0]["reason"]
    assert _added(proposals[0]["diff"]).lstrip("\n") == RULES_POINTER


def test_moved_links_are_rewritten() -> None:
    text = (
        "See [Git](docs/agents/git-workflow.md), [wt](../../docs/agents/worktrees.md),\n"
        "[TE](.harness/instructions/technical-english.md) and site/docs/agents/index.md.\n"
    )

    assert rewrite_moved_links(text) == (
        "See [Git](.harness/instructions/git-workflow.md), "
        "[wt](../../.harness/instructions/worktrees.md),\n"
        "[TE](.claude/rules/technical-english.md) and site/docs/agents/index.md.\n"
    )


def test_link_rewrite_and_pointer_form_a_single_diff(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "# Local\n\nFollow [Git](docs/agents/git-workflow.md).\n")

    proposals = propose_contract_links(repo, TEMPLATES)

    assert [p["path"] for p in proposals] == ["AGENTS.md"]
    diff = proposals[0]["diff"]
    assert diff.count("diff --git") == 1
    assert "+Follow [Git](.harness/instructions/git-workflow.md)." in diff
    assert ".claude/rules/" in _added(diff)
    assert "moved paths" in proposals[0]["reason"]
    assert "runtime rules" in proposals[0]["reason"]


def test_a_moved_link_in_a_seed_agent_gets_a_proposal(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "# Local\n\n" + RULES_POINTER)
    agent = repo / ".claude/agents/pr-composer.md"
    agent.parent.mkdir(parents=True)
    agent.write_text("Read ../../docs/agents/git-workflow.md.\n", encoding="utf-8")

    proposals = propose_contract_links(repo, TEMPLATES)

    assert [p["path"] for p in proposals] == [".claude/agents/pr-composer.md"]
    assert "+Read ../../.harness/instructions/git-workflow.md." in proposals[0]["diff"]


def test_connected_agents_gets_no_proposal(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "# Local\n\n" + RULES_POINTER)

    assert propose_contract_links(repo, TEMPLATES) == []
