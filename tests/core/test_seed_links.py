"""`propose_contract_links`: the Codex read pointer to `.claude/rules/` reaches an existing
AGENTS.md as a reviewable proposal, merged with the Technical English one into a single diff."""

from __future__ import annotations

from pathlib import Path

from harness.seed_links import RULES_POINTER, agents_rules_pointer, propose_contract_links

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "harness/project"
CONTRACT = "Before the first English handoff, agents must read\n[Technical English](.harness/instructions/technical-english.md).\n"


def _repo(tmp_path: Path, agents: str) -> Path:
    (tmp_path / ".harness/instructions").mkdir(parents=True)
    (tmp_path / ".harness/instructions/technical-english.md").write_text("# TE\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text(agents, encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("# Claude Code\n\n@AGENTS.md\n", encoding="utf-8")
    return tmp_path


def test_the_template_carries_the_proposed_pointer() -> None:
    template = (TEMPLATES / "AGENTS.md.tmpl").read_text(encoding="utf-8")
    assert RULES_POINTER in template
    assert agents_rules_pointer(template)


def test_a_pointer_inside_fenced_code_does_not_count() -> None:
    assert not agents_rules_pointer("# A\n\n```\nread .claude/rules/\n```\n")
    assert agents_rules_pointer("Read [rules](.claude/rules/).\n")


def test_agents_without_the_pointer_gets_one_proposal(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "# Local\n\n" + CONTRACT)

    proposals = propose_contract_links(repo, TEMPLATES)

    assert [p["path"] for p in proposals] == ["AGENTS.md"]
    assert "runtime rules in .claude/rules/" in proposals[0]["reason"]
    added = "".join(
        line[1:] + "\n"
        for line in proposals[0]["diff"].splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )
    assert added.lstrip("\n") == RULES_POINTER


def test_both_additions_for_agents_form_a_single_diff(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "# Local\n")

    proposals = propose_contract_links(repo, TEMPLATES)

    assert [p["path"] for p in proposals] == ["AGENTS.md"]
    diff = proposals[0]["diff"]
    assert diff.count("diff --git") == 1
    assert "technical-english.md" in diff and ".claude/rules/" in diff
    assert "shared contract" in proposals[0]["reason"]
    assert "runtime rules" in proposals[0]["reason"]


def test_connected_agents_gets_no_proposal(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "# Local\n\n" + CONTRACT + "\n" + RULES_POINTER)

    assert propose_contract_links(repo, TEMPLATES) == []
