"""Контракт навыков фазы публикации: релиз, вход из фаз 1–2, повторный вход и очистка (#1214)."""

from pathlib import Path

from harness.bin.harness import package_files
from tests.core.test_developer_skill import _frontmatter

ROOT = Path(__file__).resolve().parents[2]
ENGINEERING = ROOT / "skills/first-party/engineering"
PR_SKILL = ENGINEERING / "to-pull-requests/SKILL.md"
REFERENCES = ENGINEERING / "to-pull-requests/references"
INSTRUCTIONS = ROOT / "harness/project/instructions"
INSTALLED = ROOT / "docs/agents"


def _text(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def test_pr_core_names_each_reference_and_stays_compact() -> None:
    core = _text(PR_SKILL)
    assert "`references/integration-route.md`" in core
    assert "`references/release.md`" in core
    assert len(core.split()) <= 2300


def test_engineering_suite_ships_the_pr_references() -> None:
    files = package_files(["engineering-suite"])
    for name in ("integration-route", "release"):
        relative = f"to-pull-requests/references/{name}.md"
        assert files[f".harness/skills/{relative}"] == (ENGINEERING / relative).read_bytes()


def test_release_mode_closes_the_epic_and_leaves_the_changelog_alone() -> None:
    assert "`--release <epic>`" in _frontmatter(PR_SKILL)["description"]
    release = _text(REFERENCES / "release.md")
    for rule in (
        "sub_issues",
        "every child ticket is closed",
        "`Closes #<epic>`",
        "separate confirmation",
        "Never merge it",
        "`/delivery-stats <epic>`",
        "never edits `CHANGELOG.md` or the project version",
    ):
        assert rule in release


def test_git_workflow_names_the_release_step_and_runs_qa_before_confirmation() -> None:
    text = _text(INSTRUCTIONS / "git-workflow.md")
    assert "**Release (integration → base_branch):**" in text
    assert "`/to-pull-requests --release <epic>`" in text
    assert text.index("run the `qa-gate` skill") < text.index("**Confirm before opening:**")
    assert (INSTALLED / "git-workflow.md").read_bytes() == (
        INSTRUCTIONS / "git-workflow.md"
    ).read_bytes()


def test_pr_metadata_follows_the_git_workflow_rule() -> None:
    core = _text(PR_SKILL)
    assert '§1 "Project-Only Metadata"' in core
    assert "model names or `Co-Authored-By`" not in core


def test_step_zero_resumes_from_the_pr_state() -> None:
    core = _text(PR_SKILL)
    assert "gh pr list --head <branch> --state all" in core
    assert "--source-branch <branch>" in core
    assert "Merged: run the merge checks of step 7" in core


def test_pr_body_reads_the_ticket_and_the_verification_evidence() -> None:
    core = _text(PR_SKILL)
    composer = _text(ROOT / "harness/project/agents/pr-composer.md")
    for text in (core, composer):
        assert "`Action -> Verify`" in text
        assert "`Out of scope`" in text
        assert "`handoff`" in text
    assert "if no qa-gate was run this session, say so plainly" not in composer


def test_completion_report_has_one_source_in_the_memory_format() -> None:
    assert "`## Completion report` format of `docs/agents/project-memory.md`" in _text(PR_SKILL)
    guide = _text(ENGINEERING / "to-guide/references/guide-template.md")
    assert "`/to-pull-requests` step 6" in guide
    assert "gh issue comment" not in guide


def test_unblocking_and_cleanup_follow_the_tracker_and_worktree_contracts() -> None:
    core = _text(PR_SKILL)
    assert "`docs/tasks/*.md`" not in core
    assert "worktree remove --repo . --path <path>" in core
    assert "remove it using `git worktree remove <path>`" not in core
    worktrees = _text(INSTRUCTIONS / "worktrees.md")
    assert "its PR is merged (or the ticket is abandoned)" in worktrees


def test_delivery_stats_states_when_to_call_it() -> None:
    skill = ENGINEERING / "delivery-stats"
    description = _frontmatter(skill / "SKILL.md")["description"]
    assert "Use explicitly after the epic's release PR is merged" in description
    metadata = (skill / "agents/openai.yaml").read_text(encoding="utf-8")
    assert 'default_prompt: "Use $delivery-stats ' in metadata
